"""PostgreSQL connection pool management."""

import json

import asyncpg

from partsiq_common.config import BaseServiceSettings


async def _init_connection(connection: asyncpg.Connection) -> None:
    """Decode JSON and JSONB columns into Python objects transparently."""
    for type_name in ("json", "jsonb"):
        await connection.set_type_codec(
            type_name,
            encoder=lambda value: json.dumps(value, ensure_ascii=False),
            decoder=json.loads,
            schema="pg_catalog",
        )


async def create_db_pool(settings: BaseServiceSettings) -> asyncpg.Pool:
    """Create a connection pool. Raises if the database URL is not configured."""
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL must be configured for a service that requires the database")
    return await asyncpg.create_pool(
        dsn=str(settings.database_url),
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout_seconds,
        init=_init_connection,
    )
