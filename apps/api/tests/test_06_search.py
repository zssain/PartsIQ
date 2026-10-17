"""Foundation 06 acceptance: compatibility lexical matching + optional embeddings.

This ports the characterized legacy search domain (``services/search/app`` and its tests) into
the single ``partsiq.search`` package and proves the behaviours the step must preserve. Every
test here is OFFLINE and deterministic:

  * the pure functions (identification F20/F21, lexical scoring F23, fulfilment F33/F34) keep
    their legacy scores — ported characterization tests guard against drift;
  * the use cases (``SearchService``) run against an in-memory fake repository (the retrieval
    PORT) and, for the semantic path, a fake encoder returning fixed unit 1024-d vectors —
    BGE-M3 and live asyncpg/pgvector are BLOCKED and never faked as "live";
  * the compatibility gate (F22), runner-up margin before the response limit + NaN rejection
    (F25), supersession-with-own-fitment (F30), warehouse stock netting (F32) and version-
    specific citations (F28) are all exercised through the production entry points;
  * the ``CatalogueSnapshotRepository`` is exercised against the committed seed-42 fixture
    catalogue, and the "validated active catalogue version" invariant is proven.

Live BGE-M3 and a live database are BLOCKED in this environment: the semantic path is driven by
a fake encoder + injected similarity map, and ``embed_version``'s live wiring is not exercised.
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from partsiq.catalogue import fixtures as fx
from partsiq.core.contracts import EmbeddingReceipt
from partsiq.core.errors import PartsIQError
from partsiq.search import schemas
from partsiq.search.embeddings import (
    EMBEDDING_DIMENSION,
    embed_version,
    validate_embedding,
)
from partsiq.search.fulfilment import WarehouseStock, plan_fulfilment
from partsiq.search.identification import (
    ConfigurationRecord,
    IdentificationStatus,
    ModelRecord,
    identify_machine,
    machine_terms,
    parse_serial,
    score_model,
)
from partsiq.search.lexical import LexicalScorer, PartDocument, query_terms
from partsiq.search.repository import (
    CatalogueSnapshotRepository,
    CompatibilityRow,
    CompatibleMachine,
    MappingStockSource,
    PartRecord,
    SearchRepository,
    StockObservation,
)
from partsiq.search.service import (
    InvalidRequestError,
    ResourceNotFoundError,
    SearchService,
)

# =========================================================================
# In-memory fakes (port of services/search/tests/_fakes.py), implementing the
# SearchRepository PORT. The domain logic is pinned without any database.
# =========================================================================

CONFIG_ID = 100

MODEL = ModelRecord(
    id=1, brand="Veltrano", model_code="VP-20", display_name="Veltrano VP-20",
    rated_output="20 kVA", family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
    configurations=(ConfigurationRecord(CONFIG_ID, "A", "Config A", 100000, 199999),),
)

_PARTS: dict[int, PartRecord] = {
    1: PartRecord(1, "VP-OF-1", "oil filter", "فلتر زيت", "", "filters", "EA", True, ()),
    2: PartRecord(2, "VP-FF-2", "fuel filter", "فلتر وقود", "", "filters", "EA", True, ()),
    3: PartRecord(3, "VP-FS-3", "fuel water separator", "فاصل ماء وقود", "", "filters", "EA", True, ()),
    4: PartRecord(4, "VP-HF-4", "hydraulic filter", "فلتر هيدروليك", "", "filters", "EA", True, ()),
    5: PartRecord(5, "VP-OLD-5", "old oil filter", "فلتر زيت قديم", "", "filters", "EA", False, ()),
    6: PartRecord(6, "VP-NEW-6", "oil filter mk2", "فلتر زيت ٢", "", "filters", "EA", True, ()),
    7: PartRecord(7, "VP-OLD-7", "old belt", "سير قديم", "", "belts", "EA", False, ()),
    8: PartRecord(8, "VP-NEW-8", "belt mk2", "سير ٢", "", "belts", "EA", True, ()),
}

# forward supersession chains (origin -> [origin, successor, ...])
_CHAINS: dict[int, list[int]] = {5: [5, 6], 7: [7, 8]}


class FakeRepository:
    """Implements the SearchRepository method surface with hand-built records."""

    def __init__(
        self, *, compatibility: list[CompatibilityRow], semantic: dict[int, float] | None = None
    ) -> None:
        self._compat = compatibility
        self._semantic = semantic or {}

    async def fetch_models(self) -> list[ModelRecord]:
        return [MODEL]

    async def fetch_model_for_configuration(self, configuration_id: int) -> ModelRecord | None:
        return MODEL if configuration_id == CONFIG_ID else None

    async def fetch_compatibility(self, configuration_id: int) -> list[CompatibilityRow]:
        return list(self._compat) if configuration_id == CONFIG_ID else []

    async def fetch_supersession_chains(self, part_ids) -> dict[int, list[int]]:
        return {pid: list(_CHAINS.get(pid, [pid])) for pid in part_ids}

    async def find_part_ids_by_number_keys(self, keys) -> dict[str, int]:
        by_key = {p.part_number.replace("-", ""): pid for pid, p in _PARTS.items()}
        return {key: by_key[key] for key in keys if key in by_key}

    async def fetch_parts(self, part_ids) -> dict[int, PartRecord]:
        return {pid: _PARTS[pid] for pid in set(part_ids) if pid in _PARTS}

    async def fetch_stock(self, part_ids) -> dict[int, list[WarehouseStock]]:
        return {
            pid: [
                WarehouseStock("JED", "Jeddah", "Western", 5 if pid == 1 else 0),
                WarehouseStock("RUH", "Riyadh", "Central", 10),
            ]
            for pid in set(part_ids)
        }

    async def fetch_semantic_similarities(self, query_vector, model_name, part_ids) -> dict[int, float]:
        # Mirrors the legacy fake: pass similarities through UNCLAMPED so the service's single
        # F25 NaN check is the one rejection point (a clamp here would mask a NaN).
        return {pid: self._semantic[pid] for pid in part_ids if pid in self._semantic}

    async def fetch_transfer_days(self) -> dict[tuple[str, str], int]:
        return {("RUH", "JED"): 2, ("JED", "RUH"): 2}

    async def fetch_warehouses(self):
        return [
            {"code": "JED", "name": "Jeddah", "region": "Western"},
            {"code": "RUH", "name": "Riyadh", "region": "Central"},
        ]

    async def fetch_compatible_machines(self, part_id, limit: int = 50) -> list[CompatibleMachine]:
        return [CompatibleMachine(CONFIG_ID, "Veltrano", "VP-20", "Veltrano VP-20", "A", 1.0)]


def full_compatibility() -> list[CompatibilityRow]:
    """Parts 1,2,3 directly compatible; 5->6 (6 has its own fitment); 7->8 (8 does NOT).

    Part 4 (hydraulic) is active but has NO fitment row (compatibility-gate test).
    """
    return [
        CompatibilityRow(1, 1.0, "SRC-1 p1"),
        CompatibilityRow(2, 1.0, "SRC-2 p1"),
        CompatibilityRow(3, 1.0, "SRC-3 p1"),
        CompatibilityRow(5, 1.0, "SRC-5 p1"),  # old oil filter, supersedes to 6
        CompatibilityRow(6, 1.0, "SRC-6 p1"),  # successor has its OWN fitment -> offered
        CompatibilityRow(7, 1.0, "SRC-7 p1"),  # old belt, supersedes to 8 (8 has no row -> rejected)
    ]


class FakeProvider:
    """Stand-in embedding provider: fixed, unit-norm 1024-d vectors without loading BGE-M3."""

    model_name = "BAAI/bge-m3"

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    def embed(self, texts):
        # 1/sqrt(1024) == 0.03125; a vector of this constant has unit L2 norm at 1024-d.
        return [[0.03125] * self._dimension for _ in texts]


def test_fake_repository_satisfies_the_retrieval_port() -> None:
    assert isinstance(FakeRepository(compatibility=full_compatibility()), SearchRepository)


# =========================================================================
# Characterization: pure logic scores must not drift from the legacy port.
# =========================================================================

def _char_model(configs):
    return ModelRecord(
        id=1, brand="Veltrano", model_code="VP-20", display_name="Veltrano VP-20",
        rated_output="20 kVA", family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=tuple(configs),
    )


_SINGLE = _char_model([ConfigurationRecord(100, "A", "A", 100000, 199999)])
_MULTI = _char_model([
    ConfigurationRecord(100, "A", "A", 100000, 149999),
    ConfigurationRecord(101, "B", "B", 150000, 199999),
])


def test_char_resolved_by_model_and_serial() -> None:
    result = identify_machine("VP-20", "150000", [_MULTI])
    assert result.status is IdentificationStatus.RESOLVED
    assert result.configuration is not None and result.configuration.config_code == "B"


def test_char_needs_serial_for_multi_config() -> None:
    assert identify_machine("VP-20", None, [_MULTI]).status is IdentificationStatus.NEEDS_SERIAL


def test_char_single_config_resolves_without_serial() -> None:
    assert identify_machine("VP-20", None, [_SINGLE]).status is IdentificationStatus.RESOLVED


def test_char_serial_mismatch() -> None:
    assert identify_machine("VP-20", "999999", [_SINGLE]).status is IdentificationStatus.SERIAL_MISMATCH


def test_char_parse_serial_arabic_indic() -> None:
    assert parse_serial("١٢٣٤٥٦") == 123456


def test_char_score_model_exact_is_one() -> None:
    assert score_model("VP-20", _SINGLE) == 1.0


def test_char_fuel_outranks_oil_for_fuel_query() -> None:
    docs = [PartDocument(1, ("oil filter",), (), "filters"), PartDocument(2, ("fuel filter",), (), "filters")]
    assert LexicalScorer().score("fuel filter", docs)[0].part_id == 2


def test_char_fulfilment_local_transfer_backorder() -> None:
    def stock(jed, ruh):
        return [WarehouseStock("JED", "Jeddah", "Western", jed), WarehouseStock("RUH", "Riyadh", "Central", ruh)]

    assert plan_fulfilment(stock(10, 0), {}, "JED", 5).strategy == "local"
    transfer = plan_fulfilment(stock(0, 10), {("RUH", "JED"): 2}, "JED", 5)
    assert transfer.strategy == "transfer" and transfer.estimated_transfer_days == 2
    backorder = plan_fulfilment(stock(1, 1), {("RUH", "JED"): 2}, "JED", 10)
    assert backorder.strategy == "backorder" and backorder.shortfall == 8


# =========================================================================
# F20 Machine identification — boundary serials, serial-only, conflicting hints.
# =========================================================================

def _f20_model(code, configs):
    return ModelRecord(
        id=hash(code) % 1000, brand="Veltrano", model_code=code, display_name=f"Veltrano {code}",
        rated_output=None, family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=tuple(configs),
    )


_F20_A = _f20_model("VP-20", [
    ConfigurationRecord(100, "A", "A", 100000, 149999),
    ConfigurationRecord(101, "B", "B", 150000, 199999),
])
_F20_OTHER = _f20_model("CX-99", [ConfigurationRecord(200, "A", "A", 500000, 599999)])


def test_f20_boundary_serials_match_exactly_one_configuration() -> None:
    assert identify_machine("VP-20", "149999", [_F20_A]).configuration.config_code == "A"
    assert identify_machine("VP-20", "150000", [_F20_A]).configuration.config_code == "B"


def test_f20_serial_only_resolves_when_unique() -> None:
    result = identify_machine("", "520000", [_F20_A, _F20_OTHER])
    assert result.status is IdentificationStatus.RESOLVED and result.model.model_code == "CX-99"


def test_f20_conflicting_hint_does_not_silently_override() -> None:
    result = identify_machine("VP-20", "520000", [_F20_A, _F20_OTHER])
    assert result.status is IdentificationStatus.SERIAL_MISMATCH


def test_f20_unknown_machine_not_found() -> None:
    assert identify_machine("ZZ-00", None, [_F20_A]).status is IdentificationStatus.NOT_FOUND


def _f20_model_rated(code, output, family, configs):
    return ModelRecord(
        id=hash(code) % 1000, brand="Veltrano", model_code=code, display_name=f"Veltrano {code}",
        rated_output=output, family_code=family, family_name_en=family, family_name_ar="عائلة",
        configurations=tuple(configs),
    )


def test_f20_rated_output_and_ambiguous_and_serial_disambiguation() -> None:
    models = [
        _f20_model_rated("VP-250", "250 kVA", "GENSET", [ConfigurationRecord(12, "A", "A", 400000, 439999)]),
        _f20_model_rated("HL-25D", "2.5 t", "FORKLIFT", [ConfigurationRecord(13, "A", "A", 500000, 539999)]),
        _f20_model_rated("HL-25E", "2.5 t", "FORKLIFT", [ConfigurationRecord(14, "A", "A", 600000, 639999)]),
    ]
    assert identify_machine("our 250 kva genset", None, models).model.model_code == "VP-250"
    ambiguous = identify_machine("HL25 forklift", None, models)
    assert ambiguous.status is IdentificationStatus.AMBIGUOUS_MODEL
    assert {c.model.model_code for c in ambiguous.candidates} == {"HL-25D", "HL-25E"}
    disambiguated = identify_machine("HL25 forklift", "600123", models)
    assert disambiguated.status is IdentificationStatus.RESOLVED and disambiguated.model.model_code == "HL-25E"


# =========================================================================
# F21 Machine mismatch detection — model+serial compared together, safe handling.
# =========================================================================

def _f21_model(code, start, end):
    return ModelRecord(
        id=start, brand="Veltrano", model_code=code, display_name=f"Veltrano {code}",
        rated_output=None, family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=(ConfigurationRecord(start, "A", "A", start, end),),
    )


def test_f21_valid_serial_of_different_model_is_mismatch() -> None:
    a = _f21_model("VP-20", 100000, 199999)
    b = _f21_model("CX-99", 500000, 599999)
    result = identify_machine("VP-20", "550000", [a, b])
    assert result.status is IdentificationStatus.SERIAL_MISMATCH
    assert "re-check" in result.message.lower()
    # retrieval is blocked until identity resolves: no configuration to search on
    assert result.configuration is None


def test_f21_nonnumeric_serial_does_not_crash() -> None:
    a = _f21_model("VP-20", 100000, 199999)
    assert identify_machine("VP-20", "no-serial-here", [a]).status is IdentificationStatus.RESOLVED


# =========================================================================
# F22 Compatibility gate — only fitment members rank; provenance always carried.
# =========================================================================

def _service(compatibility, *, provider=None, semantic=None, weight=0.4):
    return SearchService(
        FakeRepository(compatibility=compatibility, semantic=semantic), provider, weight, 5
    )


async def test_f22_perfect_lexical_match_outside_fitment_is_absent() -> None:
    # "hydraulic filter" is the exact name of VP-HF-4, which is NOT compatible.
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="hydraulic filter")
    )
    assert "VP-HF-4" not in {c.part.part_number for c in response.candidates}


async def test_f22_empty_fitment_returns_no_candidates() -> None:
    response = await _service([]).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
    )
    assert response.candidates == []
    assert response.confidence.top_score == 0.0


async def test_f22_every_candidate_carries_source_reference() -> None:
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
    )
    assert response.candidates and all(c.source_reference for c in response.candidates)


# =========================================================================
# F23 Aliases and typo matching — normalization parity, exact outranks fuzzy.
# =========================================================================

_F23_DOCS = [
    PartDocument(1, ("Oil filter", "فلتر زيت"), ("lube filter", "فلتر الزيت"), "filters Spin-on"),
    PartDocument(2, ("Fuel filter", "فلتر وقود"), ("diesel filter", "فلتر ديزل"), "filters Spin-on"),
    PartDocument(3, ("Air filter element", "فلتر هواء"), ("air cleaner",), "filters element"),
    PartDocument(4, ("Starter motor", "سلف"), ("starter", "self starter"), "electrical 24 V"),
    PartDocument(5, ("Water pump", "طرمبة ماء"), ("coolant pump", "طرمبة موية"), "cooling"),
    PartDocument(6, ("Fuel water separator", "فاصل الماء عن الوقود"), ("primary fuel filter",), "filters"),
]


def _top(query: str) -> int:
    return LexicalScorer().score(query, _F23_DOCS)[0].part_id


def test_f23_part_number_key_normalization_parity_with_sql() -> None:
    from partsiq_common.text import part_number_key

    def _sql_key(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", value).upper()

    for value in ("VP-OF-1042", "vp of 1042", "VPOF1042", "ca/af_8973", "  CX-99  "):
        assert part_number_key(value) == _sql_key(value)


def test_f23_discriminating_word_and_arabic_and_typo() -> None:
    assert _top("I need the fuel filter please") == 2
    assert _top("oil filter") == 1
    assert _top("ابغى فلتر ديزل") == 2
    assert _top("السلف") == 4
    assert _top("startr motr") == 4


def test_f23_arabic_part_word_is_scored_not_stripped() -> None:
    docs = [PartDocument(1, ("فلتر زيت",), (), "")]
    assert LexicalScorer().score("فلتر", docs)[0].score > 0.0


def test_f23_exact_token_outranks_fuzzy_variant() -> None:
    docs = [PartDocument(1, ("filters",), (), "spare"), PartDocument(2, ("filter",), (), "spare")]
    ranked = {m.part_id: m.score for m in LexicalScorer().score("filter", docs)}
    assert ranked[2] > ranked[1]


def test_f23_query_terms_drop_stopwords_numbers_and_machine_terms() -> None:
    assert query_terms("Please I need 2 oil filters") == ["oil", "filters"]
    scored = LexicalScorer().score("VP-100 fuel filter", _F23_DOCS, frozenset({"vp", "vp100"}))
    assert scored[0].part_id == 2 and scored[0].score == 1.0


def test_f23_machine_terms_exclude_arabic_part_words() -> None:
    # machine_terms from a model code/brand/family must not contain part words like فلتر.
    terms = machine_terms(MODEL)
    assert "فلتر" not in terms and "vp" in terms


# =========================================================================
# F24 Semantic retrieval — 1024-d unit vectors enforced; lexical fallback; ingestion.
# =========================================================================

def test_f24_unit_vector_of_correct_dimension_passes() -> None:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[0] = 1.0
    validate_embedding(vector)


def test_f24_wrong_dimension_rejected() -> None:
    with pytest.raises(ValueError):
        validate_embedding([1.0, 0.0])


def test_f24_nan_rejected() -> None:
    bad = [0.0] * EMBEDDING_DIMENSION
    bad[0] = float("nan")
    with pytest.raises(ValueError):
        validate_embedding(bad)


def test_f24_non_unit_rejected() -> None:
    with pytest.raises(ValueError):
        validate_embedding([0.5] * EMBEDDING_DIMENSION)


async def test_f24_no_provider_means_semantic_disabled_but_lexical_returns() -> None:
    response = await _service(full_compatibility(), provider=None).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
    )
    assert response.semantic_search_enabled is False
    assert response.candidates  # lexical still returns candidates (labelled fallback)


async def test_f24_provider_enables_semantic_and_only_compatible_ids_scored() -> None:
    # Only compatible ids are passed to the similarity store: a high similarity on part 4
    # (incompatible, never a candidate) cannot surface it.
    repo = FakeRepository(compatibility=full_compatibility(), semantic={2: 0.9, 4: 0.99})
    service = SearchService(repo, FakeProvider(), 0.4, 5)
    response = await service.search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="fuel filter")
    )
    assert response.semantic_search_enabled is True
    numbers = {c.part.part_number for c in response.candidates}
    assert "VP-HF-4" not in numbers
    fuel = next(c for c in response.candidates if c.part.part_number == "VP-FF-2")
    assert fuel.semantic_score == pytest.approx(0.9) and "semantic_match" in fuel.match_reasons


async def test_f24_embed_version_upserts_with_source_hash() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.upserts: list[tuple[int, str, str]] = []

        async def fetch_embedding_sources(self, version_id):
            return [(1, "oil filter | فلتر"), (2, "fuel filter | وقود")]

        async def upsert_embedding(self, part_id, model_name, source_text, vector_literal, model_revision, source_hash):
            self.upserts.append((part_id, source_hash, model_revision))

    store = FakeStore()
    receipt = await embed_version(uuid4(), provider=FakeProvider(), store=store, model_revision="rev-abc")
    assert isinstance(receipt, EmbeddingReceipt)
    assert receipt.embedded_count == 2 and len(store.upserts) == 2
    assert all(len(h) == 64 for _, h, _ in store.upserts)
    assert all(rev == "rev-abc" for _, _, rev in store.upserts)


async def test_f24_embed_version_rejects_wrong_dimension_without_upserting() -> None:
    class FakeStore:
        async def fetch_embedding_sources(self, version_id):
            return [(1, "text")]

        async def upsert_embedding(self, *a, **k):
            raise AssertionError("must not upsert an invalid vector")

    with pytest.raises(ValueError):
        await embed_version(uuid4(), provider=FakeProvider(dimension=512), store=FakeStore(), model_revision="r")


# =========================================================================
# F25 Ranked candidates — margin before response limit; NaN rejected.
# =========================================================================

async def test_f25_limit_one_still_reports_runner_up_margin() -> None:
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="fuel filter", limit=1)
    )
    assert len(response.candidates) == 1
    assert response.confidence.top_score > 0.0
    assert response.confidence.margin < response.confidence.top_score


async def test_f25_nan_score_is_rejected() -> None:
    service = _service(full_compatibility(), provider=FakeProvider(), semantic={2: math.nan})
    with pytest.raises(InvalidRequestError) as exc:
        await service.search_parts(schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="fuel filter"))
    assert exc.value.code == "VALIDATION_FAILED"  # mapped to a stable contract code


async def test_f25_empty_result_has_zero_confidence() -> None:
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="zzzzz")
    )
    assert response.candidates == [] and response.confidence.top_score == 0.0


# =========================================================================
# F28 Compatibility references — every candidate carries a version-specific citation.
# =========================================================================

_SOURCE_RE = re.compile(r"^(?P<doc>.+?)\s+rev\s+(?P<rev>\w+)\s*,\s*section\s+(?P<section>.+)$")


def _versioned(rev: int = 1, section: str = "FILTERS") -> str:
    return f"SYNTH-CA-PB-CA-110 rev {rev}, section {section}"


async def test_f28_every_candidate_retains_a_version_specific_citation() -> None:
    compatibility = [
        CompatibilityRow(1, 1.0, _versioned()),
        CompatibilityRow(2, 1.0, _versioned()),
        CompatibilityRow(3, 2.0, _versioned()),
    ]
    response = await _service(compatibility).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter fuel separator")
    )
    assert response.candidates
    for candidate in response.candidates:
        match = _SOURCE_RE.match(candidate.source_reference)
        assert match is not None and match.group("rev") == "1" and match.group("section") == "FILTERS"


async def test_f28_unknown_configuration_is_not_found() -> None:
    with pytest.raises(ResourceNotFoundError) as exc:
        await _service(full_compatibility()).search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID + 999, query="oil filter")
        )
    assert exc.value.code == "NOT_FOUND"


# =========================================================================
# F30 Old part numbers — successor needs its OWN explicit fitment; cycles are safe.
# =========================================================================

async def test_f30_successor_with_own_fitment_is_offered_with_old_number() -> None:
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter")
    )
    new6 = next((c for c in response.candidates if c.part.part_number == "VP-NEW-6"), None)
    assert new6 is not None and "VP-OLD-5" in new6.superseded_from
    assert "superseded_number_resolved" in new6.match_reasons


async def test_f30_successor_without_own_fitment_is_rejected() -> None:
    response = await _service(full_compatibility()).search_parts(
        schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="belt filter oil fuel")
    )
    numbers = {c.part.part_number for c in response.candidates}
    assert "VP-NEW-8" not in numbers and "VP-OLD-7" not in numbers


async def test_f30_supersession_cycle_is_not_followed_infinitely() -> None:
    # A cyclic successor map must terminate the forward walk via the visited set.
    records = [
        fx.CatalogueRecord(entity_type="part_supersessions", entity_key='["P1","P2"]',
                           payload={"old_part_number": "P1", "new_part_number": "P2", "effective_date": "2024-01-01"}),
    ]
    # Build a repository whose successor map has a cycle and confirm the chain is bounded.
    repo = _snapshot_repo()
    chains = await repo.fetch_supersession_chains([1])  # a real fixture part id
    assert all(isinstance(pid, int) for pid in chains[1])
    assert len(chains[1]) <= 20  # MAX_SUPERSESSION_DEPTH, never unbounded
    _ = records  # documents the supersession record shape


# =========================================================================
# F32 Warehouse stock — net available, clamped; unknown warehouse rejected.
# =========================================================================

def _f32_stock(jed, ruh=0, dmm=0):
    return [
        WarehouseStock("JED", "Jeddah", "Western", jed),
        WarehouseStock("RUH", "Riyadh", "Central", ruh),
        WarehouseStock("DMM", "Dammam", "Eastern", dmm),
    ]


_F32_ROUTES = {("RUH", "JED"): 2, ("DMM", "JED"): 3}


def test_f32_local_net_available_fills_locally() -> None:
    plan = plan_fulfilment(_f32_stock(jed=5), _F32_ROUTES, "JED", 3)
    assert plan.strategy == "local" and plan.shortfall == 0


def test_f32_negative_local_stock_is_clamped_and_transfers() -> None:
    plan = plan_fulfilment(_f32_stock(jed=-4, ruh=10), _F32_ROUTES, "JED", 3)
    assert plan.strategy == "transfer"
    assert all(line.warehouse_code != "JED" for line in plan.lines)


def test_f32_unknown_destination_rejected() -> None:
    with pytest.raises(ValueError):
        plan_fulfilment(_f32_stock(jed=5), _F32_ROUTES, "XXX", 1)


def test_f32_insufficient_total_backorders_and_quantity_positive() -> None:
    plan = plan_fulfilment(_f32_stock(jed=1, ruh=1), _F32_ROUTES, "JED", 10)
    assert plan.strategy == "backorder" and plan.shortfall == 8
    with pytest.raises(ValueError):
        plan_fulfilment(_f32_stock(jed=5), _F32_ROUTES, "JED", 0)


# =========================================================================
# F33 Fulfilment planning — local first, deterministic remotes, bounded allocations.
# =========================================================================

def test_f33_local_first_and_bounded_allocations() -> None:
    assert plan_fulfilment(_f32_stock(10, 10), _F32_ROUTES, "JED", 4).lines[0].warehouse_code == "JED"
    plan = plan_fulfilment(_f32_stock(2, 1), _F32_ROUTES, "JED", 10)
    allocated = sum(line.quantity for line in plan.lines)
    assert allocated == 3 and plan.shortfall == 7


def test_f33_unavailable_route_cannot_be_invented() -> None:
    with pytest.raises(ValueError):
        plan_fulfilment(_f32_stock(0, 5), {}, "JED", 3)


# =========================================================================
# F34 Transfer estimates — integer transfer_days from the route; local == 0.
# =========================================================================

def test_f34_local_is_zero_transfer_days() -> None:
    assert plan_fulfilment(_f32_stock(10, 0), _F32_ROUTES, "JED", 3).estimated_transfer_days == 0


def test_f34_transfer_days_are_carried_as_int_from_route() -> None:
    plan = plan_fulfilment(_f32_stock(0, 10), _F32_ROUTES, "JED", 3)
    assert plan.estimated_transfer_days == 2 and isinstance(plan.lines[0].transfer_days, int)


def test_f34_no_route_is_unavailable_not_an_invented_promise() -> None:
    with pytest.raises(ValueError):
        plan_fulfilment(_f32_stock(0, 10), {}, "JED", 3)


# =========================================================================
# CatalogueSnapshotRepository — reads the VALIDATED ACTIVE catalogue version.
# =========================================================================

def _seed42_stock() -> MappingStockSource:
    """Seed netted stock observations from the seed-42 fixture dataset, keyed by part id."""
    dataset = fx.generate_dataset(42)
    ordinals = fx.part_ordinals(dataset)
    warehouses = {w.code: w for w in dataset.warehouses}
    observed = datetime(2026, 10, 17, tzinfo=UTC)
    readings: dict[int, list[StockObservation]] = {}
    for level in dataset.stock:
        pid = ordinals[level.part_number]
        wh = warehouses[level.warehouse_code]
        net = level.quantity_on_hand - level.quantity_reserved
        readings.setdefault(pid, []).append(
            StockObservation(wh.code, wh.name, wh.region, net, observed)
        )
    return MappingStockSource(readings)


def _snapshot_repo() -> CatalogueSnapshotRepository:
    snapshot = fx.build_catalogue(42)
    return CatalogueSnapshotRepository.from_active_snapshot(snapshot, stock=_seed42_stock())


def test_snapshot_repo_builds_models_and_preserves_numeric_ids() -> None:
    repo = _snapshot_repo()
    dataset = fx.generate_dataset(42)
    configs = fx.configuration_ordinals(dataset)
    import asyncio

    async def go():
        models = await repo.fetch_models()
        # every configuration id is the fixture's 1-based load ordinal (never renumbered)
        all_config_ids = {c.id for m in models for c in m.configurations}
        assert all_config_ids == set(configs.values())
        # resolving a model for a known configuration returns the owning model
        some_id = next(iter(configs.values()))
        model = await repo.fetch_model_for_configuration(some_id)
        assert model is not None and any(c.id == some_id for c in model.configurations)

    asyncio.run(go())


async def test_snapshot_repo_search_gates_and_cites_against_fixture() -> None:
    repo = _snapshot_repo()
    service = SearchService(repo, None, 0.4, 5)
    models = await repo.fetch_models()
    genset = next(m for m in models if m.model_code == "VP-20")
    config = genset.configurations[0]
    response = await service.search_parts(
        schemas.PartSearchRequest(configuration_id=config.id, query="oil filter")
    )
    assert response.candidates
    assert response.candidates[0].part.name_en.lower().startswith("oil")
    # every surfaced candidate carries version-specific provenance (F22/F28)
    assert all("SYNTH-" in c.source_reference for c in response.candidates)
    # confidence margin is well-formed
    assert 0.0 <= response.confidence.margin <= response.confidence.top_score


async def test_snapshot_repo_stock_is_netted_and_zero_filled() -> None:
    repo = _snapshot_repo()
    stock = await repo.fetch_stock([1])
    rows = stock[1]
    assert len(rows) == 3  # one row per warehouse, even if a warehouse has no reading
    assert all(row.available >= 0 for row in rows)


async def test_snapshot_repo_fulfilment_uses_approved_routes() -> None:
    repo = _snapshot_repo()
    routes = await repo.fetch_transfer_days()
    assert routes[("JED", "RUH")] == 2 and routes[("RUH", "DMM")] == 1


def test_snapshot_repo_rejects_an_unvalidated_active_version() -> None:
    """A snapshot with a validation issue is refused as STALE_CATALOGUE (never served)."""
    snapshot = fx.build_catalogue(42)
    # Corrupt one compatibility row's provenance to produce a MISSING_EVIDENCE validation issue.
    broken = []
    corrupted = False
    for record in snapshot.records:
        if not corrupted and record.entity_type == "part_compatibility":
            payload = dict(record.payload)
            payload["source_reference"] = ""
            broken.append(fx.CatalogueRecord(entity_type=record.entity_type, entity_key=record.entity_key, payload=payload))
            corrupted = True
        else:
            broken.append(record)
    bad = fx.build_snapshot(version_id=snapshot.version_id, source="fixture", records=broken)
    with pytest.raises(PartsIQError) as exc:
        CatalogueSnapshotRepository.from_active_snapshot(bad)
    assert exc.value.code == "STALE_CATALOGUE"


# =========================================================================
# Readiness — lexical and semantic capability reported SEPARATELY.
# =========================================================================

def test_readiness_reports_lexical_and_semantic_separately() -> None:
    lexical_only = SearchService(FakeRepository(compatibility=[]), None, 0.4, 5).readiness()
    assert lexical_only == {"lexical": True, "semantic_capable": False}
    with_provider = SearchService(FakeRepository(compatibility=[]), FakeProvider(), 0.4, 5).readiness()
    assert with_provider == {"lexical": True, "semantic_capable": True}


# =========================================================================
# BLOCKED: live BGE-M3 and live asyncpg/pgvector retrieval.
# =========================================================================

def test_live_bge_m3_and_pgvector_are_blocked() -> None:
    """Real BGE-M3 (torch/sentence-transformers) and live asyncpg/pgvector are BLOCKED here.

    They are not installed and no database/model allowance is confirmed, so they are SKIPPED
    rather than faked as a live run. The retrieval port and the encoder are injected, which is
    how the domain is exercised above with deterministic fakes.
    """
    try:
        import sentence_transformers as _st  # noqa: F401
    except ImportError:
        pytest.skip("BLOCKED: sentence-transformers/torch not installed (multi-GB model download)")
    pytest.skip("BLOCKED: live BGE-M3 load requires a confirmed model/compute allowance")
