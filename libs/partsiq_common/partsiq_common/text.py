"""Bilingual (Arabic and English) text normalisation shared by ingestion and search.

The same functions must be applied to catalogue text and to user queries; otherwise matching
silently degrades. Arabic handling covers diacritics, tatweel, letter-form variants, Arabic-Indic
digits and common attached prefixes such as the definite article.
"""

import re
import unicodedata
from typing import Literal

_ARABIC_DIACRITICS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_ARABIC_LETTER_MAP = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "\u0640": None}
)
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NON_WORD = re.compile("[^0-9a-z\u0621-\u064a]+")
_ARABIC_LETTER = re.compile("[\u0621-\u064a]")
_LATIN_LETTER = re.compile("[a-zA-Z]")
_NON_ALNUM_ASCII = re.compile(r"[^A-Z0-9]")

# Longest prefixes first so that "وال" is removed before "ال".
_ARABIC_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_MIN_STEM_LENGTH = 2

Language = Literal["en", "ar", "mixed"]


def normalize_text(text: str) -> str:
    """Lower-case, unify Arabic letter forms and digits, and collapse punctuation to spaces."""
    value = unicodedata.normalize("NFKC", text).translate(_DIGIT_MAP).lower()
    value = _ARABIC_DIACRITICS.sub("", value).translate(_ARABIC_LETTER_MAP)
    return " ".join(_NON_WORD.sub(" ", value).split())


def normalize_token(token: str) -> str:
    """Strip a leading Arabic article or conjunction-plus-article from an already normalised token."""
    if _ARABIC_LETTER.match(token):
        for prefix in _ARABIC_PREFIXES:
            if token.startswith(prefix) and len(token) - len(prefix) >= _MIN_STEM_LENGTH:
                return token[len(prefix):]
    return token


def tokenize(text: str) -> list[str]:
    """Normalise text and split it into comparable tokens."""
    return [normalize_token(token) for token in normalize_text(text).split()]


def detect_language(text: str) -> Language | None:
    """Classify text by script. Returns None when the text contains no letters."""
    arabic = len(_ARABIC_LETTER.findall(unicodedata.normalize("NFKC", text)))
    latin = len(_LATIN_LETTER.findall(text))
    if arabic == 0 and latin == 0:
        return None
    if arabic and latin:
        minority = min(arabic, latin) / (arabic + latin)
        if minority >= 0.15:
            return "mixed"
    return "ar" if arabic > latin else "en"


def part_number_key(value: str) -> str:
    """Canonical form for part-number comparison: upper-case ASCII letters and digits only.

    Must stay consistent with the generated column ``parts.part_number_key``.
    """
    return _NON_ALNUM_ASCII.sub("", unicodedata.normalize("NFKC", value).translate(_DIGIT_MAP).upper())


def extract_part_number_keys(text: str, max_window: int = 3) -> list[str]:
    """Find token sequences that look like part numbers: letters plus at least three digits.

    Adjacent tokens are also joined (up to ``max_window``) so that "VP OF 1042" is recognised.
    Candidates are only lookup keys; a key that matches no catalogue record is harmless.
    """
    tokens = unicodedata.normalize("NFKC", text).translate(_DIGIT_MAP).split()
    keys: list[str] = []
    for start in range(len(tokens)):
        for width in range(1, max_window + 1):
            if start + width > len(tokens):
                break
            key = part_number_key("".join(tokens[start:start + width]))
            digit_count = sum(character.isdigit() for character in key)
            has_letter = any(character.isalpha() for character in key)
            if 5 <= len(key) <= 30 and digit_count >= 3 and has_letter and key not in keys:
                keys.append(key)
    return keys
