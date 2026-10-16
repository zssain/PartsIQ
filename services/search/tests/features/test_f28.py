"""F28 Compatibility references — every candidate carries a version-specific citation.

The search service is the owner of catalogue retrieval (ARCHITECTURE section 2), so this
exercises the production entry point ``SearchService.search_parts`` with a deterministic
fake repository: every surfaced candidate retains its ``source_reference``, that reference
resolves to a version-specific document and page/section, and a part with no fitment
evidence is simply not offered (absent evidence shown as unavailable). The downstream
"mismatched version fails verification" gate lives in the orchestrator (F46) and is
covered there; auth is a route-level concern (prompt 06) outside this ranking function.
"""
from __future__ import annotations

import re
import unittest

from app import schemas
from app.repository import CompatibilityRow
from app.service import ResourceNotFoundError, SearchService
from tests._fakes import CONFIG_ID, FakeRepository

# A version-specific reference: the "rev N" pins the document to a catalogue version and
# the section is the page/anchor the evidence viewer opens (tools/catalog generator format).
SOURCE_RE = re.compile(r"^(?P<doc>.+?)\s+rev\s+(?P<rev>\w+)\s*,\s*section\s+(?P<section>.+)$")


def _versioned(rev: int = 1, section: str = "FILTERS") -> str:
    return f"SYNTH-CA-PB-CA-110 rev {rev}, section {section}"


def _service() -> SearchService:
    # Parts 1,2,3 have explicit, version-specific fitment; part 4 (hydraulic) has none.
    compatibility = [
        CompatibilityRow(1, 1.0, _versioned()),
        CompatibilityRow(2, 1.0, _versioned()),
        CompatibilityRow(3, 2.0, _versioned()),
    ]
    return SearchService(FakeRepository(compatibility=compatibility), None, 0.4, 5)


class CompatibilityReferences(unittest.IsolatedAsyncioTestCase):
    async def test_every_candidate_retains_a_version_specific_citation(self):  # success
        response = await _service().search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="oil filter fuel separator")
        )
        self.assertTrue(response.candidates)
        for candidate in response.candidates:
            self.assertTrue(candidate.source_reference.strip(), "citation must be retained with every candidate")
            match = SOURCE_RE.match(candidate.source_reference)
            self.assertIsNotNone(match, f"{candidate.source_reference!r} is not version-specific")
            # Resolve to a version-specific document and a page/section.
            self.assertEqual(match.group("rev"), "1")
            self.assertTrue(match.group("doc"))
            self.assertEqual(match.group("section"), "FILTERS")

    async def test_part_without_fitment_evidence_is_not_offered(self):  # absent evidence -> unavailable
        response = await _service().search_parts(
            schemas.PartSearchRequest(configuration_id=CONFIG_ID, query="hydraulic filter oil")
        )
        numbers = {candidate.part.part_number for candidate in response.candidates}
        self.assertNotIn("VP-HF-4", numbers)  # active part, but no compatibility source

    async def test_unknown_configuration_is_not_found(self):  # invalid-input
        with self.assertRaises(ResourceNotFoundError):
            await _service().search_parts(
                schemas.PartSearchRequest(configuration_id=CONFIG_ID + 999, query="oil filter")
            )

    async def test_distinct_revisions_are_distinguishable(self):  # supports stale-version detection
        # A citation naming a different revision resolves to a different document version,
        # which is what lets the verification gate reject a mismatched version downstream.
        self.assertNotEqual(
            SOURCE_RE.match(_versioned(rev=1)).group("rev"),
            SOURCE_RE.match(_versioned(rev=2)).group("rev"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
