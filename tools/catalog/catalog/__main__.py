"""Command-line interface.

    python -m catalog generate --seed 42 --output data/catalog.json
    python -m catalog validate data/catalog.json
    python -m catalog load data/catalog.json [--force]
    python -m catalog seed [--seed 42] [--force]
    python -m catalog embed
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

from partsiq_common.embeddings import build_embedding_provider
from partsiq_common.logging import configure_logging

from catalog.dataset import CatalogDataset
from catalog.embedder import embed_parts
from catalog.generator import generate_catalog
from catalog.loader import CatalogLoadError, load_catalog
from catalog.validator import validate_catalog

logger = logging.getLogger("partsiq.catalog")


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL must be set")
    return url


async def _with_connection(operation):  # type: ignore[no-untyped-def]
    connection = await asyncpg.connect(_database_url())
    try:
        return await operation(connection)
    finally:
        await connection.close()


def _report(dataset: CatalogDataset) -> int:
    errors = validate_catalog(dataset)
    for error in errors:
        logger.error("validation error", extra={"detail": error})
    if errors:
        logger.error("dataset invalid", extra={"error_count": len(errors)})
        return 1
    logger.info("dataset valid", extra={"parts": len(dataset.parts), "models": len(dataset.models)})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalog", description="PartsIQ synthetic catalogue tooling")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Generate a synthetic dataset file")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--output", type=Path, required=True)

    validate = commands.add_parser("validate", help="Validate a dataset file")
    validate.add_argument("path", type=Path)

    load = commands.add_parser("load", help="Load a dataset file into the database")
    load.add_argument("path", type=Path)
    load.add_argument("--force", action="store_true", help="Allow deleting existing enquiries")

    seed = commands.add_parser("seed", help="Generate, validate and load in one step")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--force", action="store_true", help="Allow deleting existing enquiries")

    commands.add_parser("embed", help="Compute embeddings for all active parts")

    snapshot = commands.add_parser(
        "snapshot", help="Print the canonical publication hash + record count for a dataset file (F59)"
    )
    snapshot.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    configure_logging("catalog-tools", os.environ.get("LOG_LEVEL", "INFO"))

    try:
        if args.command == "generate":
            dataset = generate_catalog(args.seed)
            status = _report(dataset)
            if status == 0:
                dataset.write(args.output)
                logger.info("dataset written", extra={"path": str(args.output)})
            return status
        if args.command == "validate":
            return _report(CatalogDataset.read(args.path))
        if args.command == "snapshot":
            # F59: the same canonical snapshot/hash a publication would compute, offline over a
            # dataset file. The authoritative DB publication runs via the worker command.
            import json as _json

            from catalog.versioning import canonical_snapshot

            records = _json.loads(args.path.read_text(encoding="utf-8")).get("parts", [])
            snap = canonical_snapshot(records)
            logger.info("snapshot", extra={"sha256": snap.sha256, "record_count": snap.record_count})
            print(f"{snap.sha256}  records={snap.record_count}")
            return 0
        if args.command in {"load", "seed"}:
            dataset = CatalogDataset.read(args.path) if args.command == "load" else generate_catalog(args.seed)
            summary = asyncio.run(_with_connection(lambda c: load_catalog(c, dataset, force=args.force)))
            logger.info("load complete", extra=summary)
            return 0
        if args.command == "embed":
            provider = build_embedding_provider(
                os.environ.get("EMBEDDING_PROVIDER", "none"),  # type: ignore[arg-type]
                os.environ.get("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            )
            if provider is None:
                logger.error("EMBEDDING_PROVIDER is 'none'; set it to 'sentence_transformers' to embed parts")
                return 1
            count = asyncio.run(_with_connection(lambda c: embed_parts(c, provider)))
            logger.info("embedding complete", extra={"parts": count})
            return 0
    except CatalogLoadError as exc:
        logger.error("load refused", extra={"detail": str(exc)})
        return 2
    except (OSError, ValueError) as exc:
        logger.error("command failed", extra={"detail": str(exc)})
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
