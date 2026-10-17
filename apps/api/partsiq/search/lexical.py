"""Bilingual lexical scoring over a small, compatibility-filtered candidate set.

Ported verbatim (scores unchanged) from the legacy ``services/search/app/lexical.py``
(foundation 06); only the package path for the shared tokenizer changed.

Because candidates are already restricted to parts that fit one machine configuration (typically
10 to 20 parts), scoring is done in process, which keeps it deterministic and unit-testable.
Token weights use inverse document frequency within the candidate set, so a discriminating word
such as "fuel" outweighs a common word such as "filter". A phrase component rewards query word
pairs that appear together in a part's name (or, more weakly, an alias), which separates
"oil filter" from "oil separator".
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from partsiq_common.text import tokenize

_STOPWORDS_RAW = (
    "a an and are as at be by can do for from have hi hello i in is it me my need needs of on or our please "
    "pls send the this to we with want looking require required urgent kindly thanks thank you sir "
    "part parts spare spares price quote quotation available availability machine unit one new "
    "ابغي ابغا ابي ابى احتاج نحتاج اريد نبي نبغي لو سمحت من في على عن الى مع هل عندكم عندك "
    "قطعة قطع غيار سعر كم يا شكرا ممكن جديد"
)
STOPWORDS = frozenset(token for word in _STOPWORDS_RAW.split() for token in tokenize(word))

SECONDARY_FIELD_WEIGHT = 0.4
FUZZY_MIN_LENGTH = 4
FUZZY_THRESHOLD = 0.84
FUZZY_DISCOUNT = 0.85
PREFIX_MATCH_STRENGTH = 0.75
PHRASE_WEIGHT = 0.15
NAME_PHRASE_STRENGTH = 1.0
ALIAS_PHRASE_STRENGTH = 0.8


@dataclass(frozen=True, slots=True)
class PartDocument:
    """Searchable text for one part. Names and aliases are primary; description and category secondary."""

    part_id: int
    names: tuple[str, ...]
    aliases: tuple[str, ...]
    secondary_text: str


@dataclass(frozen=True, slots=True)
class LexicalMatch:
    part_id: int
    score: float
    matched_terms: tuple[str, ...]


def query_terms(query: str, ignore: frozenset[str] = frozenset()) -> list[str]:
    """Informative query tokens: normalised, de-duplicated, without stopwords, numbers or ignored terms."""
    seen: list[str] = []
    for token in tokenize(query):
        if token in STOPWORDS or token in ignore or token.isdigit() or len(token) < 2 or token in seen:
            continue
        seen.append(token)
    return seen


def _bigrams(phrases: Sequence[str]) -> frozenset[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for phrase in phrases:
        tokens = tokenize(phrase)
        pairs.update(zip(tokens, tokens[1:]))
    return frozenset(pairs)


def _token_strength(term: str, vocabulary: frozenset[str]) -> float:
    if term in vocabulary:
        return 1.0
    if len(term) < FUZZY_MIN_LENGTH:
        return 0.0
    best = 0.0
    for candidate in vocabulary:
        if len(candidate) < FUZZY_MIN_LENGTH:
            continue
        if candidate.startswith(term) or term.startswith(candidate):
            best = max(best, PREFIX_MATCH_STRENGTH)
            continue
        if abs(len(candidate) - len(term)) > 3:
            continue
        ratio = SequenceMatcher(None, term, candidate).ratio()
        if ratio >= FUZZY_THRESHOLD:
            best = max(best, ratio * FUZZY_DISCOUNT)
    return best


class LexicalScorer:
    """Scores documents against a query. Scores are in [0, 1]; 1 means every informative term matched
    and every query word pair appeared together in the part name."""

    def score(
        self,
        query: str,
        documents: Sequence[PartDocument],
        ignore_terms: frozenset[str] = frozenset(),
    ) -> list[LexicalMatch]:
        """Rank documents. ``ignore_terms`` are words already used elsewhere, such as the machine model,
        which carry no evidence about which part is wanted."""
        terms = query_terms(query, ignore_terms)
        if not terms or not documents:
            return [LexicalMatch(document.part_id, 0.0, ()) for document in documents]

        vocabularies = [
            (
                frozenset(token for text in (*document.names, *document.aliases) for token in tokenize(text)),
                frozenset(tokenize(document.secondary_text)),
            )
            for document in documents
        ]
        strengths = [
            [
                max(_token_strength(term, primary), SECONDARY_FIELD_WEIGHT * _token_strength(term, secondary))
                for term in terms
            ]
            for primary, secondary in vocabularies
        ]

        document_count = len(documents)
        weights: list[float] = []
        for index in range(len(terms)):
            frequency = sum(1 for row in strengths if row[index] > 0)
            # Terms matching no candidate carry no information about which candidate is right.
            weights.append(math.log(1 + document_count / frequency) if frequency else 0.0)
        total_weight = sum(weights)

        informative = [term for term, weight in zip(terms, weights) if weight > 0]
        query_pairs = list(zip(informative, informative[1:]))

        results: list[LexicalMatch] = []
        for document, row in zip(documents, strengths):
            if total_weight == 0:
                results.append(LexicalMatch(document.part_id, 0.0, ()))
                continue
            base = sum(weight * strength for weight, strength in zip(weights, row)) / total_weight
            score = base
            if query_pairs and base > 0:
                name_pairs = _bigrams(document.names)
                alias_pairs = _bigrams(document.aliases)
                phrase = sum(
                    NAME_PHRASE_STRENGTH if pair in name_pairs else ALIAS_PHRASE_STRENGTH if pair in alias_pairs else 0.0
                    for pair in query_pairs
                ) / len(query_pairs)
                score = (1 - PHRASE_WEIGHT) * base + PHRASE_WEIGHT * phrase
            matched = tuple(term for term, strength in zip(terms, row) if strength > 0)
            results.append(LexicalMatch(document.part_id, round(min(score, 1.0), 5), matched))
        results.sort(key=lambda match: match.score, reverse=True)
        return results
