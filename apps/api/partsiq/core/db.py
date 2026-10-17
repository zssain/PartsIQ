"""PostgreSQL pools and the per-request transactional actor scope (foundation 01).

Pools are created per runtime role during the FastAPI lifespan and closed on shutdown.
``request_scope`` opens a transaction and binds the verified subject to the
transaction-local GUC ``app.actor_id`` with ``set_config(..., is_local => true)`` so the
identity is scoped to the transaction and disappears on commit or rollback — RLS policies
read it, and no request body can spoof it (ARCHITECTURE section 4, CONSTRAINTS).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from .contracts import ActorContext
from .settings import RuntimeRole, Settings


async def _init_connection(connection: asyncpg.Connection) -> None:
    """Decode json/jsonb columns into Python objects transparently."""
    for type_name in ("json", "jsonb"):
        await connection.set_type_codec(
            type_name,
            encoder=lambda value: json.dumps(value, ensure_ascii=False),
            decoder=json.loads,
            schema="pg_catalog",
        )


class Database:
    """Owns the role-scoped asyncpg pools for one process."""

    def __init__(self, pools: dict[RuntimeRole, asyncpg.Pool]) -> None:
        self._pools = pools

    @classmethod
    async def connect(
        cls,
        settings: Settings,
        roles: tuple[RuntimeRole, ...] = ("api",),
        *,
        min_size: int = 1,
        max_size: int = 10,
        command_timeout: float = 15.0,
    ) -> "Database":
        pools: dict[RuntimeRole, asyncpg.Pool] = {}
        for role in roles:
            pools[role] = await asyncpg.create_pool(
                dsn=settings.runtime_dsn(role),
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
                init=_init_connection,
            )
        return cls(pools)

    def pool(self, role: RuntimeRole = "api") -> asyncpg.Pool:
        if role not in self._pools:
            raise RuntimeError(f"no pool configured for role '{role}'")
        return self._pools[role]

    async def close(self) -> None:
        for pool in self._pools.values():
            await pool.close()

    @asynccontextmanager
    async def request_scope(
        self, actor: ActorContext, role: RuntimeRole = "api"
    ) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a connection, begin a transaction, bind the actor, and yield it.

        The actor is a verified :class:`ActorContext`; a request body is never passed
        here. On exit the transaction commits (or rolls back on exception), which drops
        the transaction-local actor GUC.
        """
        async with self.pool(role).acquire() as connection:
            transaction = connection.transaction()
            await transaction.start()
            try:
                await connection.execute(
                    "SELECT set_config('app.actor_id', $1, true)", str(actor.user_id)
                )
                yield connection
            except BaseException:
                await transaction.rollback()
                raise
            else:
                await transaction.commit()
