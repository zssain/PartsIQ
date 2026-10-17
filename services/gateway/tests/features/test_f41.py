"""F41 Internal notes — append-only staff notes, assigned-only, never customer/PDF exposed.

Empty or over-4000-char notes rejected; unassigned staff denied (404); writes idempotent;
list in order. The customer EnquiryView has no notes field (structural: note text can never
leak to a customer response).
"""
from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.features.f41_internal_notes import F41Request, Note, append_note, list_notes
from partsiq_common.contracts import ActorContext, EnquiryView
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _actor(user_id=None):
    return ActorContext(user_id=user_id or uuid4(), request_id=uuid4(), roles=["reviewer"])


class FakeNotesRepo:
    def __init__(self, *, assigned=True, raises=None):
        self._assigned = assigned
        self._raises = raises
        self._notes: list[Note] = []
        self._by_key: dict = {}

    async def is_assigned(self, actor, enquiry_id):
        if self._raises is not None:
            raise self._raises
        return self._assigned

    async def append(self, actor, enquiry_id, body, idempotency_key):
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        note = Note(id=uuid4(), author_id=actor.user_id, body=body, created_at=WHEN + timedelta(seconds=len(self._notes)))
        self._notes.append(note)
        self._by_key[idempotency_key] = note
        return note

    async def list_notes(self, actor, enquiry_id):
        return sorted(self._notes, key=lambda n: (n.created_at, str(n.id)))


def _req(body="looks good", key=None):
    return F41Request(enquiry_id=uuid4(), body=body, idempotency_key=key or uuid4())


class AppendNote(unittest.IsolatedAsyncioTestCase):
    async def test_append_records_author_and_body(self):
        actor = _actor()
        result = await append_note(actor, _req("double-check serial"), repo=FakeNotesRepo())
        self.assertEqual(result.author_id, actor.user_id)
        self.assertEqual(result.body, "double-check serial")

    async def test_empty_note_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await append_note(_actor(), _req("   "), repo=FakeNotesRepo())
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_over_limit_note_rejected(self):
        with self.assertRaises(PartsIQError) as ctx:
            await append_note(_actor(), _req("x" * 4001), repo=FakeNotesRepo())
        self.assertEqual(ctx.exception.http_status, 422)

    async def test_unassigned_denied(self):
        with self.assertRaises(PartsIQError) as ctx:
            await append_note(_actor(), _req(), repo=FakeNotesRepo(assigned=False))
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_idempotent_append(self):
        repo = FakeNotesRepo()
        key = uuid4()
        a = await append_note(_actor(), _req(key=key), repo=repo)
        b = await append_note(_actor(), _req(key=key), repo=repo)
        self.assertEqual(a.id, b.id)
        self.assertEqual(len(repo._notes), 1)

    async def test_customer_view_has_no_notes_field(self):
        self.assertNotIn("notes", EnquiryView.model_fields)  # note text can never leak to a customer

    async def test_dependency_failure_propagates(self):
        repo = FakeNotesRepo(raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await append_note(_actor(), _req(), repo=repo)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


class ListNotes(unittest.IsolatedAsyncioTestCase):
    async def test_list_in_order_and_assigned_only(self):
        repo = FakeNotesRepo()
        actor = _actor()
        await append_note(actor, _req("first"), repo=repo)
        await append_note(actor, _req("second"), repo=repo)
        listed = await list_notes(actor, uuid4(), repo=repo)
        self.assertEqual([n.body for n in listed], ["first", "second"])

    async def test_list_unassigned_denied(self):
        with self.assertRaises(PartsIQError) as ctx:
            await list_notes(_actor(), uuid4(), repo=FakeNotesRepo(assigned=False))
        self.assertEqual(ctx.exception.http_status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
