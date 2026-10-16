"""F23 Aliases and typo matching — normalization parity with SQL; exact outranks fuzzy."""
from __future__ import annotations

import re
import unittest

from partsiq_common.text import part_number_key

from app.lexical import LexicalScorer, PartDocument


def _sql_part_number_key(value: str) -> str:
    # Mirrors the generated column: upper(regexp_replace(part_number, '[^A-Za-z0-9]', '', 'g'))
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


class NormalizationParity(unittest.TestCase):
    def test_part_number_key_matches_sql(self) -> None:
        for value in ("VP-OF-1042", "vp of 1042", "VPOF1042", "ca/af_8973", "  CX-99  "):
            self.assertEqual(part_number_key(value), _sql_part_number_key(value))


class LexicalMatching(unittest.TestCase):
    def test_exact_token_outranks_fuzzy_variant(self) -> None:
        docs = [
            PartDocument(1, ("filters",), (), "spare"),   # prefix/fuzzy match only
            PartDocument(2, ("filter",), (), "spare"),     # exact token match
        ]
        ranked = {m.part_id: m.score for m in LexicalScorer().score("filter", docs)}
        self.assertGreater(ranked[2], ranked[1])

    def test_arabic_part_word_is_scored_not_stripped(self) -> None:
        docs = [PartDocument(1, ("فلتر زيت",), (), "")]
        ranked = LexicalScorer().score("فلتر", docs)
        self.assertGreater(ranked[0].score, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
