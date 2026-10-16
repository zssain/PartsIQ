"""F05 Demo reset — reset increments the generation and is idempotent per key.

Exercises the gateway reset_demo use case over a fake store that mirrors the row-locked
generation increment: a repeated reset with the same Idempotency-Key returns the same
generation, while a new key advances it.
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.demo import reset_demo
from partsiq_common.contracts import ActorContext, DemoSession

NOW = datetime(2026, 10, 18, tzinfo=UTC)


class FakeDemoStore:
    def __init__(self):
        self.generation = 1
        self.session_id = uuid4()
        self.applied: dict = {}  # idempotency_key -> generation

    async def create_session(self, owner_id):  # pragma: no cover
        return DemoSession(id=self.session_id, generation=self.generation, expires_at=NOW)

    async def reset_session(self, owner_id, idempotency_key):
        if idempotency_key in self.applied:
            return DemoSession(id=self.session_id, generation=self.applied[idempotency_key], expires_at=NOW)
        self.generation += 1
        self.applied[idempotency_key] = self.generation
        return DemoSession(id=self.session_id, generation=self.generation, expires_at=NOW)


def _actor():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=[], session_id=uuid4(), session_generation=1)


class DemoReset(unittest.IsolatedAsyncioTestCase):
    async def test_reset_increments_generation(self):
        store = FakeDemoStore()
        result = await reset_demo(_actor(), uuid4(), store=store)
        self.assertEqual(result.generation, 2)

    async def test_repeated_key_returns_same_generation(self):  # idempotency
        store = FakeDemoStore()
        key = uuid4()
        first = await reset_demo(_actor(), key, store=store)
        second = await reset_demo(_actor(), key, store=store)
        self.assertEqual(first.generation, second.generation)

    async def test_new_key_advances_generation(self):
        store = FakeDemoStore()
        await reset_demo(_actor(), uuid4(), store=store)
        latest = await reset_demo(_actor(), uuid4(), store=store)
        self.assertEqual(latest.generation, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
