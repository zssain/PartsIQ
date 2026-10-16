"""Loads a validated dataset into PostgreSQL in a single transaction."""

import json
import logging
from datetime import date
from decimal import Decimal

import asyncpg

from catalog.dataset import CatalogDataset
from catalog.validator import validate_catalog

logger = logging.getLogger("partsiq.catalog.loader")

# Order matters only for readability; TRUNCATE ... CASCADE handles dependencies.
_CATALOGUE_TABLES = (
    "review_approved_parts",
    "review_decisions",
    "enquiry_candidates",
    "enquiry_attachments",
    "enquiries",
    "stock_levels",
    "warehouse_transfer_routes",
    "warehouses",
    "part_supersessions",
    "part_compatibility",
    "part_embeddings",
    "part_aliases",
    "parts",
    "model_configurations",
    "equipment_models",
    "equipment_families",
)


class CatalogLoadError(Exception):
    """Raised when the dataset cannot be loaded safely."""


async def load_catalog(connection: asyncpg.Connection, dataset: CatalogDataset, *, force: bool = False) -> dict[str, int]:
    """Replace all catalogue data with the dataset. Refuses to delete existing enquiries unless forced."""
    errors = validate_catalog(dataset)
    if errors:
        raise CatalogLoadError(f"Dataset failed validation with {len(errors)} error(s): " + "; ".join(errors[:10]))

    async with connection.transaction():
        existing_enquiries = await connection.fetchval("SELECT count(*) FROM enquiries")
        if existing_enquiries and not force:
            raise CatalogLoadError(
                f"{existing_enquiries} enquiries exist and would be deleted. Re-run with --force to proceed."
            )

        await connection.execute(f"TRUNCATE {', '.join(_CATALOGUE_TABLES)} RESTART IDENTITY CASCADE")

        await connection.executemany(
            "INSERT INTO equipment_families (code, name_en, name_ar) VALUES ($1, $2, $3)",
            [(f.code, f.name_en, f.name_ar) for f in dataset.families],
        )
        family_ids = {row["code"]: row["id"] for row in await connection.fetch("SELECT id, code FROM equipment_families")}

        await connection.executemany(
            """INSERT INTO equipment_models (family_id, brand, model_code, display_name, rated_output)
               VALUES ($1, $2, $3, $4, $5)""",
            [(family_ids[m.family_code], m.brand, m.model_code, m.display_name, m.rated_output) for m in dataset.models],
        )
        model_ids = {
            (row["brand"], row["model_code"]): row["id"]
            for row in await connection.fetch("SELECT id, brand, model_code FROM equipment_models")
        }

        await connection.executemany(
            """INSERT INTO model_configurations (model_id, config_code, description, serial_start, serial_end)
               VALUES ($1, $2, $3, $4, $5)""",
            [
                (model_ids[(m.brand, m.model_code)], c.config_code, c.description, c.serial_start, c.serial_end)
                for m in dataset.models
                for c in m.configurations
            ],
        )
        configuration_ids = {
            (row["brand"], row["model_code"], row["config_code"]): row["id"]
            for row in await connection.fetch(
                """SELECT c.id, m.brand, m.model_code, c.config_code
                   FROM model_configurations AS c JOIN equipment_models AS m ON m.id = c.model_id"""
            )
        }

        await connection.executemany(
            """INSERT INTO parts (part_number, name_en, name_ar, description_en, category, unit_of_measure, is_active)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            [(p.part_number, p.name_en, p.name_ar, p.description_en, p.category, p.unit_of_measure, p.is_active)
             for p in dataset.parts],
        )
        part_ids = {row["part_number"]: row["id"] for row in await connection.fetch("SELECT id, part_number FROM parts")}

        await connection.copy_records_to_table(
            "part_aliases",
            columns=["part_id", "alias", "language"],
            records=[(part_ids[a.part_number], a.alias, a.language) for a in dataset.aliases],
        )
        await connection.copy_records_to_table(
            "part_compatibility",
            columns=["part_id", "configuration_id", "quantity_per_unit", "source_reference"],
            records=[
                (part_ids[c.part_number], configuration_ids[(c.brand, c.model_code, c.config_code)],
                 Decimal(str(c.quantity_per_unit)), c.source_reference)
                for c in dataset.compatibility
            ],
        )
        # Inserted row by row so the cycle-prevention trigger evaluates each link.
        await connection.executemany(
            """INSERT INTO part_supersessions (old_part_id, new_part_id, effective_date, reason)
               VALUES ($1, $2, $3, $4)""",
            [(part_ids[s.old_part_number], part_ids[s.new_part_number], date.fromisoformat(s.effective_date), s.reason)
             for s in dataset.supersessions],
        )

        await connection.executemany(
            "INSERT INTO warehouses (code, name, region) VALUES ($1, $2, $3)",
            [(w.code, w.name, w.region) for w in dataset.warehouses],
        )
        warehouse_ids = {row["code"]: row["id"] for row in await connection.fetch("SELECT id, code FROM warehouses")}
        await connection.copy_records_to_table(
            "warehouse_transfer_routes",
            columns=["from_warehouse_id", "to_warehouse_id", "transfer_days"],
            records=[(warehouse_ids[r.from_code], warehouse_ids[r.to_code], r.transfer_days)
                     for r in dataset.transfer_routes],
        )
        await connection.copy_records_to_table(
            "stock_levels",
            columns=["part_id", "warehouse_id", "quantity_on_hand", "quantity_reserved"],
            records=[(part_ids[s.part_number], warehouse_ids[s.warehouse_code], s.quantity_on_hand, s.quantity_reserved)
                     for s in dataset.stock],
        )

        summary = {
            "families": len(dataset.families),
            "models": len(dataset.models),
            "configurations": len(configuration_ids),
            "parts": len(dataset.parts),
            "aliases": len(dataset.aliases),
            "compatibility_rows": len(dataset.compatibility),
            "supersessions": len(dataset.supersessions),
            "stock_rows": len(dataset.stock),
        }
        await connection.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, payload)
               VALUES ('system', 'catalog-loader', 'catalog.loaded', 'catalog', $1, $2::jsonb)""",
            f"seed-{dataset.seed}",
            json.dumps(summary),
        )

    logger.info("catalogue loaded", extra=summary)
    return summary
