"""F55 Saved machines — save/list/rename/archive, owner-scoped, identifiers only.

A duplicate label is allowed (identity is the UUID); the idempotency key dedupes a double
submit; a foreign id is denied as NOT_FOUND; archiving is a soft delete; and a saved machine
stores only identifiers so a stale configuration is never reused as authoritative.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.features.f55_saved_machines import (
    F55Request,
    SavedMachine,
    archive_machine,
    list_machines,
    prefill_from_machine,
    rename_machine,
    save_machine,
)
from partsiq_common.contracts import ActorContext
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


def _req(label="My loader", model_id=1, serial="000150", key=None):
    return F55Request(label=label, model_id=model_id, serial_text=serial, idempotency_key=key or uuid4())


class FakeMachineRepo:
    def __init__(self):
        self._by_id: dict = {}
        self._by_key: dict = {}

    async def save(self, actor, request):
        key = (actor.user_id, request.idempotency_key)
        if key in self._by_key:
            return self._by_id[self._by_key[key]]
        machine = SavedMachine(
            id=uuid4(), owner_user_id=actor.user_id, session_id=actor.session_id,
            session_generation=actor.session_generation, label=request.label,
            model_id=request.model_id, serial_text=request.serial_text, archived_at=None,
        )
        self._by_id[machine.id] = machine
        self._by_key[key] = machine.id
        return machine

    async def list_active(self, actor):
        return [m for m in self._by_id.values() if m.owner_user_id == actor.user_id and m.archived_at is None]

    async def get(self, actor, machine_id):
        machine = self._by_id.get(machine_id)
        if machine is None or machine.owner_user_id != actor.user_id:
            return None
        return machine

    async def set_label(self, actor, machine_id, label):
        self._by_id[machine_id] = replace(self._by_id[machine_id], label=label)
        return self._by_id[machine_id]

    async def archive(self, actor, machine_id):
        self._by_id[machine_id] = replace(self._by_id[machine_id], archived_at=WHEN)


class Failing:
    async def save(self, *a, **k):
        raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="db down")


class SaveMachine(unittest.IsolatedAsyncioTestCase):
    async def test_save_preserves_serial_verbatim(self):
        result = await save_machine(_actor(), _req(serial="000150"), repo=FakeMachineRepo())
        self.assertEqual(result.serial_text, "000150")  # leading zeros preserved
        self.assertEqual(result.label, "My loader")

    async def test_idempotent_save_returns_same_id(self):
        repo, actor, key = FakeMachineRepo(), _actor(), uuid4()
        a = await save_machine(actor, _req(key=key), repo=repo)
        b = await save_machine(actor, _req(key=key), repo=repo)
        self.assertEqual(a.id, b.id)

    async def test_duplicate_label_distinct_id(self):
        repo, actor = FakeMachineRepo(), _actor()
        a = await save_machine(actor, _req(label="Shared", key=uuid4()), repo=repo)
        b = await save_machine(actor, _req(label="Shared", key=uuid4()), repo=repo)
        self.assertNotEqual(a.id, b.id)

    async def test_blank_label_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await save_machine(_actor(), _req(label="   "), repo=FakeMachineRepo())
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_nonpositive_model_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await save_machine(_actor(), _req(model_id=0), repo=FakeMachineRepo())
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_blank_serial_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await save_machine(_actor(), _req(serial="   "), repo=FakeMachineRepo())
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_dependency_failure_propagates(self):
        with self.assertRaises(PartsIQError) as ctx:
            await save_machine(_actor(), _req(), repo=Failing())
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class ListRenameArchive(unittest.IsolatedAsyncioTestCase):
    async def test_list_excludes_foreign_and_archived(self):
        repo = FakeMachineRepo()
        owner, stranger = _actor(), _actor()
        mine = await save_machine(owner, _req(label="mine"), repo=repo)
        await save_machine(stranger, _req(label="theirs"), repo=repo)
        archived = await save_machine(owner, _req(label="old"), repo=repo)
        await archive_machine(owner, archived.id, repo=repo)
        listed = await list_machines(owner, repo=repo)
        self.assertEqual([m.id for m in listed], [mine.id])

    async def test_rename_updates_label_only(self):
        repo, actor = FakeMachineRepo(), _actor()
        saved = await save_machine(actor, _req(label="old"), repo=repo)
        renamed = await rename_machine(actor, saved.id, "new", repo=repo)
        self.assertEqual(renamed.label, "new")
        self.assertEqual(renamed.model_id, saved.model_id)

    async def test_rename_foreign_id_denied(self):
        repo = FakeMachineRepo()
        owner, stranger = _actor(), _actor()
        saved = await save_machine(owner, _req(), repo=repo)
        with self.assertRaises(PartsIQError) as ctx:
            await rename_machine(stranger, saved.id, "hijack", repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_archive_foreign_id_denied(self):
        repo = FakeMachineRepo()
        owner, stranger = _actor(), _actor()
        saved = await save_machine(owner, _req(), repo=repo)
        with self.assertRaises(PartsIQError) as ctx:
            await archive_machine(stranger, saved.id, repo=repo)
        self.assertEqual(ctx.exception.http_status, 404)


class Prefill(unittest.IsolatedAsyncioTestCase):
    async def test_prefill_carries_identifiers_only_not_configuration(self):
        saved = await save_machine(_actor(), _req(serial="000150"), repo=FakeMachineRepo())
        prefill = prefill_from_machine(saved)
        self.assertEqual(prefill["serial_text"], "000150")
        self.assertNotIn("configuration_id", prefill)  # stale configuration never reused as authoritative
        self.assertNotIn("candidate_part_ids", prefill)


if __name__ == "__main__":
    unittest.main(verbosity=2)
