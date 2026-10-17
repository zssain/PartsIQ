"""Search use cases. Coordinates repository access, identification, scoring and fulfilment.

Ported from the legacy ``services/search/app/service.py`` (foundation 06). Imports adapted to
the single package: the retrieval port and typed records come from ``partsiq.search.*``; the
embedding provider / vector helpers from ``partsiq_common.embeddings``; the bilingual text
helpers from ``partsiq_common.text``. The legacy local exceptions are preserved as thin
subclasses of the shared :class:`~partsiq.core.errors.PartsIQError` so they carry a stable
contract code (NOT_FOUND / VALIDATION_FAILED) at the route boundary while ported tests that
catch them by name keep working.

Preserved invariants (do not weaken):
  * A confirmed machine configuration is resolved BEFORE its compatible part set is ranked, and
    the compatibility gate is never removed — an LLM never decides compatibility (F22).
  * The runner-up margin is computed over the FULL ranked set BEFORE the response limit (F25);
    a NaN score is rejected rather than ranked unpredictably (F25).
  * A superseded part's current successor is offered ONLY with its OWN explicit fitment (F30).
  * Lexical and semantic capabilities are reported SEPARATELY (readiness).
"""

import asyncio
import logging
import math
from dataclasses import asdict

from partsiq.core.errors import PartsIQError
from partsiq_common.embeddings import EmbeddingProvider, to_vector_literal
from partsiq_common.text import detect_language, extract_part_number_keys, part_number_key

from . import schemas
from .fulfilment import plan_fulfilment
from .identification import ConfigurationRecord, ModelRecord, identify_machine, machine_terms
from .lexical import LexicalScorer, PartDocument
from .repository import PartRecord, SearchRepository

logger = logging.getLogger("partsiq.search")

SEMANTIC_REASON_THRESHOLD = 0.5


class ResourceNotFoundError(PartsIQError):
    """A referenced configuration or part does not exist (maps to HTTP 404)."""

    def __init__(self, detail: str) -> None:
        super().__init__("NOT_FOUND", detail=detail, internal_detail=detail)


class InvalidRequestError(PartsIQError):
    """A well-formed request that cannot be satisfied, e.g. an unknown warehouse (HTTP 422)."""

    def __init__(self, detail: str) -> None:
        super().__init__("VALIDATION_FAILED", detail=detail, internal_detail=detail)


def _model_out(model: ModelRecord) -> schemas.ModelOut:
    return schemas.ModelOut(
        id=model.id, brand=model.brand, model_code=model.model_code, display_name=model.display_name,
        rated_output=model.rated_output, family_code=model.family_code, family_name_en=model.family_name_en,
        family_name_ar=model.family_name_ar,
        configurations=[schemas.ConfigurationOut(**asdict(c)) for c in model.configurations],
    )


def _part_out(part: PartRecord) -> schemas.PartOut:
    return schemas.PartOut(
        id=part.id, part_number=part.part_number, name_en=part.name_en, name_ar=part.name_ar,
        description_en=part.description_en, category=part.category, unit_of_measure=part.unit_of_measure,
        is_active=part.is_active,
    )


class SearchService:
    def __init__(
        self,
        repository: SearchRepository,
        embedding_provider: EmbeddingProvider | None,
        semantic_weight: float,
        default_limit: int,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._semantic_weight = semantic_weight
        self._default_limit = default_limit
        self._scorer = LexicalScorer()

    async def identify(self, request: schemas.IdentifyRequest) -> schemas.IdentifyResponse:
        models = await self._repository.fetch_models()
        result = identify_machine(request.query, request.serial, models)
        return schemas.IdentifyResponse(
            status=result.status.value,
            message=result.message,
            model=_model_out(result.model) if result.model else None,
            configuration=schemas.ConfigurationOut(**asdict(result.configuration)) if result.configuration else None,
            candidates=[schemas.ModelCandidateOut(model=_model_out(c.model), score=c.score) for c in result.candidates],
        )

    async def search_parts(self, request: schemas.PartSearchRequest) -> schemas.PartSearchResponse:
        model = await self._repository.fetch_model_for_configuration(request.configuration_id)
        if model is None:
            raise ResourceNotFoundError(f"Configuration {request.configuration_id} does not exist")
        configuration: ConfigurationRecord = next(c for c in model.configurations if c.id == request.configuration_id)
        limit = request.limit or self._default_limit

        # Compatibility comes only from the catalogue; superseded entries resolve to their current part.
        compatibility = await self._repository.fetch_compatibility(configuration.id)
        chains = await self._repository.fetch_supersession_chains([row.part_id for row in compatibility])
        current_by_origin = {origin: chain[-1] for origin, chain in chains.items()}

        number_keys = extract_part_number_keys(request.query)
        quoted_ids = await self._repository.find_part_ids_by_number_keys(number_keys)
        quoted_chains = await self._repository.fetch_supersession_chains(list(quoted_ids.values()))

        all_ids = {pid for chain in chains.values() for pid in chain}
        all_ids |= {pid for chain in quoted_chains.values() for pid in chain}
        parts = await self._repository.fetch_parts(list(all_ids))

        # ADR-018: a candidate must have EXPLICIT fitment. A superseded part's current
        # successor is offered only when the successor itself is listed as compatible
        # for this configuration; compatibility is never silently inherited across a
        # supersession without the successor's own source (F30).
        directly_compatible = {row.part_id for row in compatibility}
        candidates: dict[int, tuple[float, str, list[str]]] = {}
        for row in compatibility:
            current_id = current_by_origin.get(row.part_id, row.part_id)
            if current_id in candidates or not parts[current_id].is_active:
                continue
            if current_id != row.part_id and current_id not in directly_compatible:
                continue
            superseded = [parts[pid].part_number for pid in chains.get(row.part_id, [row.part_id])[:-1]]
            candidates[current_id] = (row.quantity_per_unit, row.source_reference, superseded)

        documents = [
            PartDocument(
                part_id=part_id,
                names=(parts[part_id].name_en, parts[part_id].name_ar),
                aliases=parts[part_id].aliases,
                secondary_text=f"{parts[part_id].category} {parts[part_id].description_en}",
            )
            for part_id in candidates
        ]
        lexical = {
            match.part_id: match
            for match in self._scorer.score(request.query, documents, machine_terms(model))
        }
        semantic = await self._semantic_scores(request.query, list(candidates))

        quoted_current = {quoted_chains[pid][-1] for pid in quoted_ids.values() if pid in quoted_chains}
        stock = await self._repository.fetch_stock(list(candidates) + list(quoted_current))

        scored: list[tuple[float, int]] = []
        for part_id in candidates:
            lexical_score = lexical[part_id].score
            semantic_score = semantic.get(part_id)
            score = (
                (1 - self._semantic_weight) * lexical_score + self._semantic_weight * semantic_score
                if semantic_score is not None
                else lexical_score
            )
            if part_id in quoted_current:
                score = 1.0
            # F25: a NaN score is rejected rather than ranked unpredictably.
            if math.isnan(score):
                raise InvalidRequestError(f"non-numeric score computed for part {part_id}")
            scored.append((round(score, 5), part_id))
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)

        # F25: compute the runner-up margin over the FULL ranked set BEFORE truncating to
        # the response limit, so limit=1 still reports a close runner-up as ambiguous.
        positive = [item for item in scored if item[0] > 0]
        top = positive[0][0] if positive else 0.0
        second = positive[1][0] if len(positive) > 1 else 0.0

        results: list[schemas.CandidateOut] = []
        for rank, (score, part_id) in enumerate(scored[:limit], start=1):
            if score <= 0:
                break
            quantity, source, superseded = candidates[part_id]
            semantic_score = semantic.get(part_id)
            reasons: list[str] = []
            if part_id in quoted_current:
                reasons.append("quoted_part_number")
            if lexical[part_id].score > 0:
                reasons.append("lexical_match")
            if semantic_score is not None and semantic_score >= SEMANTIC_REASON_THRESHOLD:
                reasons.append("semantic_match")
            if superseded:
                reasons.append("superseded_number_resolved")
            results.append(schemas.CandidateOut(
                rank=rank, part=_part_out(parts[part_id]), score=score,
                lexical_score=lexical[part_id].score, semantic_score=semantic_score,
                matched_terms=list(lexical[part_id].matched_terms), match_reasons=reasons,
                quantity_per_unit=quantity, source_reference=source, superseded_from=superseded,
                stock=[schemas.WarehouseStockOut(**asdict(s)) for s in stock[part_id]],
            ))

        number_matches = []
        for part_id in quoted_ids.values():
            chain = quoted_chains.get(part_id, [part_id])
            current = parts[chain[-1]]
            number_matches.append(schemas.PartNumberMatchOut(
                queried_part_number=parts[part_id].part_number,
                current_part=_part_out(current),
                superseded_chain=[parts[pid].part_number for pid in chain],
                compatible_with_configuration=current.id in candidates,
                stock=[schemas.WarehouseStockOut(**asdict(s)) for s in stock.get(current.id, [])],
            ))

        logger.info("part search completed", extra={
            "configuration_id": configuration.id, "candidate_pool": len(candidates),
            "returned": len(results), "top_score": top,
        })
        return schemas.PartSearchResponse(
            model=_model_out(model),
            configuration=schemas.ConfigurationOut(**asdict(configuration)),
            detected_language=detect_language(request.query),
            semantic_search_enabled=self._embedding_provider is not None,
            part_number_matches=number_matches,
            candidates=results,
            confidence=schemas.ConfidenceOut(top_score=top, margin=round(top - second, 5)),
        )

    async def part_detail(self, part_number: str) -> schemas.PartDetailResponse:
        current, chain = await self._resolve_part_number(part_number)
        stock = await self._repository.fetch_stock([current.id])
        machines = await self._repository.fetch_compatible_machines(current.id)
        return schemas.PartDetailResponse(
            queried_part_number=chain[0].part_number,
            current_part=_part_out(current),
            superseded_chain=[p.part_number for p in chain],
            stock=[schemas.WarehouseStockOut(**asdict(s)) for s in stock[current.id]],
            compatible_machines=[schemas.CompatibleMachineOut(**asdict(m)) for m in machines],
        )

    async def plan_fulfilment(self, request: schemas.FulfilmentRequest) -> schemas.FulfilmentResponse:
        current, chain = await self._resolve_part_number(request.part_number)
        stock = (await self._repository.fetch_stock([current.id]))[current.id]
        routes = await self._repository.fetch_transfer_days()
        try:
            plan = plan_fulfilment(stock, routes, request.destination_warehouse, request.quantity)
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc
        return schemas.FulfilmentResponse(
            part=_part_out(current),
            superseded_chain=[p.part_number for p in chain],
            strategy=plan.strategy,
            lines=[schemas.FulfilmentLineOut(**asdict(line)) for line in plan.lines],
            estimated_transfer_days=plan.estimated_transfer_days,
            shortfall=plan.shortfall,
            message=plan.message,
        )

    async def list_warehouses(self) -> list[schemas.WarehouseOut]:
        rows = await self._repository.fetch_warehouses()
        return [schemas.WarehouseOut(code=r["code"], name=r["name"], region=r["region"]) for r in rows]

    def readiness(self) -> dict[str, bool]:
        """Report lexical readiness and semantic capability SEPARATELY (prompt 06).

        Lexical search runs in-process and is always ready; semantic search is available
        only when an embedding provider (BGE-M3) has loaded in this search process.
        """
        return {"lexical": True, "semantic_capable": self._embedding_provider is not None}

    async def _resolve_part_number(self, part_number: str) -> tuple[PartRecord, list[PartRecord]]:
        key = part_number_key(part_number)
        found = await self._repository.find_part_ids_by_number_keys([key])
        if key not in found:
            raise ResourceNotFoundError(f"Part number {part_number} does not exist")
        chain_ids = (await self._repository.fetch_supersession_chains([found[key]]))[found[key]]
        parts = await self._repository.fetch_parts(chain_ids)
        chain = [parts[pid] for pid in chain_ids]
        return chain[-1], chain

    async def _semantic_scores(self, query: str, part_ids: list[int]) -> dict[int, float]:
        if self._embedding_provider is None or not part_ids:
            return {}
        vector = (await asyncio.to_thread(self._embedding_provider.embed, [query]))[0]
        return await self._repository.fetch_semantic_similarities(
            to_vector_literal(vector), self._embedding_provider.model_name, part_ids
        )
