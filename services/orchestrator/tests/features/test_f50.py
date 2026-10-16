"""F50 Durable workflows — thread key per enquiry+revision; dedup; stale obsolete."""
from __future__ import annotations

import unittest
from uuid import uuid4

from app.events import ClaimedEvent, consume_event
from app.state import thread_id


class FakeStore:
    def __init__(self, claim, current):
        self._claim = claim
        self._current = current
        self.processed = 0
        self.obsolete = 0

    async def claim(self, event_id):
        return self._claim

    async def current(self, enquiry_id):
        return self._current

    async def mark_obsolete(self, event_id):
        self.obsolete += 1

    async def mark_processed(self, event_id):
        self.processed += 1

    async def mark_retry(self, event_id):  # pragma: no cover
        raise AssertionError

    async def run(self, claim):
        return None


class DurableWorkflow(unittest.IsolatedAsyncioTestCase):
    def test_thread_key_includes_enquiry_and_revision(self):
        enquiry = uuid4()
        self.assertNotEqual(thread_id(enquiry, 1), thread_id(enquiry, 2))
        self.assertIn(str(enquiry), thread_id(enquiry, 1))
        self.assertTrue(thread_id(enquiry, 3).endswith(":rev:3"))

    async def test_duplicate_event_does_not_repeat_processing(self):
        # claim() returning None models an already-claimed/processed event.
        store = FakeStore(claim=None, current=(1, None))
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "obsolete")
        self.assertEqual(store.processed, 0)  # publication/processing never repeats

    async def test_stale_generation_obsolete(self):
        claim = ClaimedEvent(uuid4(), uuid4(), revision=1, session_generation=1)
        store = FakeStore(claim=claim, current=(1, 2))  # session reset to generation 2
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "obsolete")

    async def test_current_event_processed_once(self):
        claim = ClaimedEvent(uuid4(), uuid4(), revision=1, session_generation=1)
        store = FakeStore(claim=claim, current=(1, 1))
        outcome = await consume_event(uuid4(), store=store)
        self.assertEqual(outcome.state, "processed")
        self.assertEqual(store.processed, 1)

    @unittest.skip("checkpoint DDL runs only under the migration role in prompt 03; needs a live DB")
    def test_checkpoint_ddl_not_under_runtime_role(self):  # pragma: no cover
        raise AssertionError("integration-only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
