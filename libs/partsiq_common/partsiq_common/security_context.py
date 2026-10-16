"""Transaction-local actor context for row-level security.

The database authorizes application reads/writes against ``app.actor_id`` (and
``app.request_id`` for audit correlation). These are set with ``set_config(..., true)``
so they are TRANSACTION-local: committed or rolled back with the surrounding
transaction and never leaking to the next checkout of a pooled connection
(CONSTRAINTS.md rule 11). No ``SET SESSION`` / session-global state is used.

Runtime services use a restricted psycopg pool here; the legacy asyncpg pool
(partsiq_common.db) is preserved untouched for the legacy search/catalogue code.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from partsiq_common.contracts import ActorContext

# A psycopg_pool.AsyncConnectionPool, configured once at service startup. Kept as
# Any so importing this module does not require a live pool (and tests can inject one).
_pool: Any | None = None


def configure_actor_pool(pool: Any) -> None:
    """Install the process-wide psycopg pool used by actor_transaction."""
    global _pool
    _pool = pool


async def apply_actor_context(conn: Any, actor: ActorContext) -> None:
    """Bind the verified actor to THIS transaction only (is_local=true)."""
    await conn.execute(
        "SELECT set_config('app.actor_id', %s, true)", (str(actor.user_id),)
    )
    await conn.execute(
        "SELECT set_config('app.request_id', %s, true)", (str(actor.request_id),)
    )
    if actor.session_id is not None:
        await conn.execute(
            "SELECT set_config('app.session_id', %s, true)", (str(actor.session_id),)
        )


@asynccontextmanager
async def actor_transaction(actor: ActorContext, *, pool: Any | None = None) -> AsyncIterator[Any]:
    """Yield a connection inside one transaction with the actor context applied.

    Commit on success, roll back on error — both discard the transaction-local actor
    settings automatically. Business writes (and their audit insert) run here so they
    share one atomic unit (F49).
    """
    chosen = pool or _pool
    if chosen is None:
        raise RuntimeError("actor pool is not configured; call configure_actor_pool() at startup")
    async with chosen.connection() as conn:
        async with conn.transaction():
            await apply_actor_context(conn, actor)
            yield conn
