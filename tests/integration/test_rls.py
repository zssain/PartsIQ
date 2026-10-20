"""RLS enforcement integration tests (prompt 22 — F54) on a DISPOSABLE migrated database.

Seeds two customers, an assigned reviewer, an unassigned reviewer and an admin, then reads
``enquiries`` as the restricted ``partsiq_gateway`` role with a transaction-local
``app.actor_id``: each customer sees only their own row, reviewers only what is assigned,
admins everything, and a connection with no actor context sees nothing (default deny).
SKIPPED when no disposable DATABASE_URL is configured (the conftest enforces the prod denylist).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest


async def _seed(conn) -> dict[str, UUID]:
    # Operator step from the RLS migration: the login that serves requests is a member of the
    # NOLOGIN partsiq_gateway group (the migration runner created it, so it may grant it).
    await conn.execute("GRANT partsiq_gateway TO CURRENT_USER")
    ids = {name: uuid4() for name in ("alice", "bob", "reviewer", "other_reviewer", "admin")}
    for name, uid in ids.items():
        await conn.execute("INSERT INTO auth.users(id, email) VALUES (%s, %s)", (uid, f"{name}-{uid.hex[:6]}@example.test"))
        await conn.execute("INSERT INTO profiles(id, display_name) VALUES (%s, %s)", (uid, name))
    for name, role in (("reviewer", "reviewer"), ("other_reviewer", "reviewer"), ("admin", "admin")):
        await conn.execute("INSERT INTO staff_roles(user_id, role) VALUES (%s, %s)", (ids[name], role))
    ids["alice_enquiry"], ids["bob_enquiry"] = uuid4(), uuid4()
    for owner, eid, assignee in (("alice", ids["alice_enquiry"], ids["reviewer"]), ("bob", ids["bob_enquiry"], None)):
        await conn.execute(
            "INSERT INTO enquiries(id, channel, raw_text, owner_id, assigned_to) VALUES (%s, 'chat', 'synthetic', %s, %s)",
            (eid, ids[owner], assignee),
        )
    return ids


async def _visible(conn, actor: UUID | None, seeded: set[UUID]) -> set[UUID]:
    async with conn.transaction():
        await conn.execute("SET LOCAL ROLE partsiq_gateway")
        if actor is not None:
            await conn.execute("SELECT set_config('app.actor_id', %s, true)", (str(actor),))
        rows = await (await conn.execute("SELECT id FROM enquiries")).fetchall()
    return {r[0] for r in rows} & seeded


@pytest.mark.asyncio
async def test_foreign_actor_sees_no_rows(actor_pool):
    async with actor_pool.connection() as conn:
        async with conn.transaction():
            ids = await _seed(conn)
        mine = {ids["alice_enquiry"], ids["bob_enquiry"]}
        assert await _visible(conn, ids["alice"], mine) == {ids["alice_enquiry"]}
        assert await _visible(conn, ids["bob"], mine) == {ids["bob_enquiry"]}
        assert await _visible(conn, ids["reviewer"], mine) == {ids["alice_enquiry"]}  # assigned only
        assert await _visible(conn, ids["other_reviewer"], mine) == set()
        assert await _visible(conn, ids["admin"], mine) == mine
        # No actor context: RLS denies by default.
        assert await _visible(conn, None, mine) == set()


@pytest.mark.asyncio
async def test_actor_context_does_not_leak_across_pooled_transactions(actor_pool):
    async with actor_pool.connection() as conn:
        async with conn.transaction():
            ids = await _seed(conn)
        mine = {ids["alice_enquiry"], ids["bob_enquiry"]}
        assert await _visible(conn, ids["alice"], mine) == {ids["alice_enquiry"]}
        # Same physical connection, next transaction, no SET: Alice's context is gone.
        assert await _visible(conn, None, mine) == set()
        setting = await (await conn.execute("SELECT current_setting('app.actor_id', true)")).fetchone()
        assert not setting[0]


@pytest.mark.asyncio
async def test_customer_cannot_create_an_enquiry_for_someone_else(actor_pool):
    import psycopg

    async with actor_pool.connection() as conn:
        async with conn.transaction():
            ids = await _seed(conn)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE partsiq_gateway")
                await conn.execute("SELECT set_config('app.actor_id', %s, true)", (str(ids["alice"]),))
                await conn.execute("INSERT INTO enquiries(id, channel, raw_text, owner_id) VALUES (%s, 'chat', 'x', %s)", (uuid4(), ids["bob"]))
