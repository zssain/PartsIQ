"""Database access for the search service. All SQL lives here."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg

from app.fulfilment import WarehouseStock
from app.identification import ConfigurationRecord, ModelRecord

MAX_SUPERSESSION_DEPTH = 20


@dataclass(frozen=True, slots=True)
class PartRecord:
    id: int
    part_number: str
    name_en: str
    name_ar: str
    description_en: str
    category: str
    unit_of_measure: str
    is_active: bool
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompatibilityRow:
    part_id: int
    quantity_per_unit: float
    source_reference: str


@dataclass(frozen=True, slots=True)
class CompatibleMachine:
    configuration_id: int
    brand: str
    model_code: str
    display_name: str
    config_code: str
    quantity_per_unit: float


class SearchRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch_models(self) -> list[ModelRecord]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT m.id, m.brand, m.model_code, m.display_name, m.rated_output,
                          f.code AS family_code, f.name_en AS family_name_en, f.name_ar AS family_name_ar,
                          c.id AS configuration_id, c.config_code, c.description, c.serial_start, c.serial_end
                   FROM equipment_models AS m
                   JOIN equipment_families AS f ON f.id = m.family_id
                   JOIN model_configurations AS c ON c.model_id = m.id
                   ORDER BY m.id, c.serial_start"""
            )
        grouped: dict[int, list[asyncpg.Record]] = defaultdict(list)
        for row in rows:
            grouped[row["id"]].append(row)
        return [
            ModelRecord(
                id=model_rows[0]["id"],
                brand=model_rows[0]["brand"],
                model_code=model_rows[0]["model_code"],
                display_name=model_rows[0]["display_name"],
                rated_output=model_rows[0]["rated_output"],
                family_code=model_rows[0]["family_code"],
                family_name_en=model_rows[0]["family_name_en"],
                family_name_ar=model_rows[0]["family_name_ar"],
                configurations=tuple(
                    ConfigurationRecord(r["configuration_id"], r["config_code"], r["description"],
                                        r["serial_start"], r["serial_end"])
                    for r in model_rows
                ),
            )
            for model_rows in grouped.values()
        ]

    async def fetch_model_for_configuration(self, configuration_id: int) -> ModelRecord | None:
        models = await self.fetch_models()
        for model in models:
            if any(configuration.id == configuration_id for configuration in model.configurations):
                return model
        return None

    async def fetch_compatibility(self, configuration_id: int) -> list[CompatibilityRow]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT part_id, quantity_per_unit, source_reference
                   FROM part_compatibility WHERE configuration_id = $1""",
                configuration_id,
            )
        return [CompatibilityRow(r["part_id"], float(r["quantity_per_unit"]), r["source_reference"]) for r in rows]

    async def fetch_supersession_chains(self, part_ids: Sequence[int]) -> dict[int, list[int]]:
        """Map each part to its forward chain [part, successor, successor's successor, ...]."""
        if not part_ids:
            return {}
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """WITH RECURSIVE chain (origin_id, part_id, depth) AS (
                       SELECT id, id, 0 FROM unnest($1::int[]) AS id
                       UNION ALL
                       SELECT chain.origin_id, s.new_part_id, chain.depth + 1
                       FROM chain JOIN part_supersessions AS s ON s.old_part_id = chain.part_id
                       WHERE chain.depth < $2
                   )
                   SELECT origin_id, part_id FROM chain ORDER BY origin_id, depth""",
                list(part_ids),
                MAX_SUPERSESSION_DEPTH,
            )
        chains: dict[int, list[int]] = defaultdict(list)
        for row in rows:
            chains[row["origin_id"]].append(row["part_id"])
        return dict(chains)

    async def fetch_parts(self, part_ids: Sequence[int]) -> dict[int, PartRecord]:
        if not part_ids:
            return {}
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT p.id, p.part_number, p.name_en, p.name_ar, p.description_en, p.category,
                          p.unit_of_measure, p.is_active,
                          COALESCE(array_agg(a.alias ORDER BY a.alias) FILTER (WHERE a.alias IS NOT NULL), '{}')
                              AS aliases
                   FROM parts AS p
                   LEFT JOIN part_aliases AS a ON a.part_id = p.id
                   WHERE p.id = ANY($1::int[])
                   GROUP BY p.id""",
                list(set(part_ids)),
            )
        return {
            r["id"]: PartRecord(r["id"], r["part_number"], r["name_en"], r["name_ar"], r["description_en"],
                                r["category"], r["unit_of_measure"], r["is_active"], tuple(r["aliases"]))
            for r in rows
        }

    async def find_part_ids_by_number_keys(self, keys: Sequence[str]) -> dict[str, int]:
        if not keys:
            return {}
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT id, part_number_key FROM parts WHERE part_number_key = ANY($1::text[])",
                list(keys),
            )
        return {r["part_number_key"]: r["id"] for r in rows}

    async def fetch_stock(self, part_ids: Sequence[int]) -> dict[int, list[WarehouseStock]]:
        """Available stock (on hand minus reserved) per warehouse; warehouses without a row report zero."""
        async with self._pool.acquire() as connection:
            warehouses = await connection.fetch("SELECT id, code, name, region FROM warehouses ORDER BY code")
            rows = await connection.fetch(
                """SELECT part_id, warehouse_id, quantity_on_hand - quantity_reserved AS available
                   FROM stock_levels WHERE part_id = ANY($1::int[])""",
                list(set(part_ids)),
            )
        available = {(r["part_id"], r["warehouse_id"]): r["available"] for r in rows}
        return {
            part_id: [
                WarehouseStock(w["code"], w["name"], w["region"], available.get((part_id, w["id"]), 0))
                for w in warehouses
            ]
            for part_id in set(part_ids)
        }

    async def fetch_transfer_days(self) -> dict[tuple[str, str], int]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT origin.code AS from_code, destination.code AS to_code, r.transfer_days
                   FROM warehouse_transfer_routes AS r
                   JOIN warehouses AS origin ON origin.id = r.from_warehouse_id
                   JOIN warehouses AS destination ON destination.id = r.to_warehouse_id"""
            )
        return {(r["from_code"], r["to_code"]): r["transfer_days"] for r in rows}

    async def fetch_warehouses(self) -> list[asyncpg.Record]:
        async with self._pool.acquire() as connection:
            return await connection.fetch("SELECT code, name, region FROM warehouses ORDER BY code")

    async def fetch_compatible_machines(self, part_id: int, limit: int = 50) -> list[CompatibleMachine]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT c.id, m.brand, m.model_code, m.display_name, c.config_code, pc.quantity_per_unit
                   FROM part_compatibility AS pc
                   JOIN model_configurations AS c ON c.id = pc.configuration_id
                   JOIN equipment_models AS m ON m.id = c.model_id
                   WHERE pc.part_id = $1
                   ORDER BY m.model_code, c.config_code
                   LIMIT $2""",
                part_id,
                limit,
            )
        return [CompatibleMachine(r["id"], r["brand"], r["model_code"], r["display_name"], r["config_code"],
                                  float(r["quantity_per_unit"])) for r in rows]

    async def fetch_embedding_sources(self, version_id: object) -> list[tuple[int, str]]:
        """Return (part_id, source_text) for active parts of a published version.

        Source text mirrors the catalogue embedder (tools/catalog embedder) so vectors
        stay consistent whichever path produced them.
        """
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT p.id,
                          p.name_en || ' | ' || p.name_ar || ' | ' || p.category || ' | ' ||
                          COALESCE(string_agg(a.alias, '; ' ORDER BY a.alias), '') || ' | ' || p.description_en
                              AS source_text
                   FROM parts AS p
                   LEFT JOIN part_aliases AS a ON a.part_id = p.id
                   WHERE p.is_active
                   GROUP BY p.id
                   ORDER BY p.id"""
            )
        return [(r["id"], r["source_text"]) for r in rows]

    async def upsert_embedding(
        self,
        part_id: int,
        model_name: str,
        source_text: str,
        vector_literal: str,
        model_revision: str,
        source_hash: str,
    ) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO part_embeddings
                       (part_id, model_name, source_text, embedding, model_revision, source_sha256)
                   VALUES ($1, $2, $3, $4::vector, $5, $6)
                   ON CONFLICT (part_id, model_name) DO UPDATE SET
                       source_text = EXCLUDED.source_text, embedding = EXCLUDED.embedding,
                       model_revision = EXCLUDED.model_revision, source_sha256 = EXCLUDED.source_sha256,
                       created_at = now()""",
                part_id, model_name, source_text, vector_literal, model_revision, source_hash,
            )

    async def fetch_semantic_similarities(
        self, query_vector: str, model_name: str, part_ids: Sequence[int]
    ) -> dict[int, float]:
        if not part_ids:
            return {}
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """SELECT part_id, 1 - (embedding <=> $1::vector) AS similarity
                   FROM part_embeddings
                   WHERE model_name = $2 AND part_id = ANY($3::int[])""",
                query_vector,
                model_name,
                list(set(part_ids)),
            )
        return {r["part_id"]: max(0.0, min(1.0, float(r["similarity"]))) for r in rows}
