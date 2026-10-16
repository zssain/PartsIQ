"""Resolves free-text machine descriptions and serial numbers to an exact model configuration."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from partsiq_common.text import normalize_text, part_number_key, tokenize

RESOLVE_THRESHOLD = 0.5
AMBIGUITY_MARGIN = 0.05
MAX_CANDIDATES = 5

_SERIAL_DIGITS = re.compile(r"\d+")
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Words customers use for each equipment family, including Gulf colloquial Arabic.
FAMILY_KEYWORDS: dict[str, frozenset[str]] = {
    code: frozenset(token for word in words.split() for token in tokenize(word))
    for code, words in {
        "GENSET": "generator generators genset gensets مولد مولدات ماطور ماطورات",
        "COMPRESSOR": "compressor compressors كمبروسر كمبريسور ضاغط ضواغط",
        "FORKLIFT": "forklift forklifts كلارك رافعة رافعه شوكية شوكيه",
        "EXCAVATOR": "excavator excavators digger بوكلين حفار حفارة",
    }.items()
}


class IdentificationStatus(StrEnum):
    RESOLVED = "resolved"
    NEEDS_SERIAL = "needs_serial"
    AMBIGUOUS_MODEL = "ambiguous_model"
    SERIAL_MISMATCH = "serial_mismatch"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class ConfigurationRecord:
    id: int
    config_code: str
    description: str
    serial_start: int
    serial_end: int

    def contains(self, serial: int) -> bool:
        return self.serial_start <= serial <= self.serial_end


@dataclass(frozen=True, slots=True)
class ModelRecord:
    id: int
    brand: str
    model_code: str
    display_name: str
    rated_output: str | None
    family_code: str
    family_name_en: str
    family_name_ar: str
    configurations: tuple[ConfigurationRecord, ...]


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    model: ModelRecord
    score: float


@dataclass(frozen=True, slots=True)
class IdentificationResult:
    status: IdentificationStatus
    message: str
    model: ModelRecord | None = None
    configuration: ConfigurationRecord | None = None
    candidates: tuple[ModelCandidate, ...] = ()


def machine_terms(model: ModelRecord) -> frozenset[str]:
    """Tokens that describe the machine rather than the part (model code, brand, family words)."""
    texts = (model.model_code, model.brand, model.display_name, model.rated_output or "")
    terms = {token for text in texts for token in tokenize(text)}
    terms |= {part_number_key(model.model_code).lower()}
    return frozenset(terms) | FAMILY_KEYWORDS.get(model.family_code, frozenset())


def parse_serial(raw: str | None) -> int | None:
    """Extract the numeric serial from inputs such as "SN 124510" or Arabic-Indic digits."""
    if raw is None:
        return None
    groups = _SERIAL_DIGITS.findall(raw.translate(_ARABIC_INDIC_DIGITS))
    if not groups:
        return None
    longest = max(groups, key=len)
    return int(longest) if len(longest) <= 18 else None


def _query_keys(query: str) -> list[str]:
    raw_tokens = normalize_text(query).split()
    keys = [part_number_key(token) for token in raw_tokens]
    keys += [part_number_key(first + second) for first, second in zip(raw_tokens, raw_tokens[1:])]
    return [key for key in keys if len(key) >= 3]


def score_model(query: str, model: ModelRecord) -> float:
    """Score in [0, 1] for how strongly the query refers to the model."""
    model_key = part_number_key(model.model_code)
    keys = _query_keys(query)
    tokens = set(tokenize(query))

    score = 0.0
    if model_key in keys:
        score = 1.0
    else:
        best_ratio = max((SequenceMatcher(None, model_key, key).ratio() for key in keys), default=0.0)
        if best_ratio >= 0.8:
            score = best_ratio * 0.85

    if model.rated_output:
        output_tokens = tokenize(model.rated_output)
        joined = part_number_key(model.rated_output)
        if (output_tokens and all(token in tokens for token in output_tokens)) or joined in keys:
            score = max(score, 0.6)

    if tokens & FAMILY_KEYWORDS.get(model.family_code, frozenset()):
        score = min(1.0, score + 0.1) if score > 0 else 0.0
    brand_tokens = set(tokenize(model.brand))
    if brand_tokens & tokens:
        score = min(1.0, score + 0.1) if score > 0 else 0.0
    return round(score, 4)


def identify_machine(query: str, serial_text: str | None, models: Sequence[ModelRecord]) -> IdentificationResult:
    """Identify the configuration, or explain precisely what information is missing."""
    serial = parse_serial(serial_text) if serial_text else None
    if serial is None and query:
        # Customers often put the serial in the message itself, e.g. "VP-100 serial 312455".
        match = re.search(r"(?:serial|s/?n|سيريال|رقم تسلسلي)\s*[:#]?\s*([0-9٠-٩]{4,18})", query, re.IGNORECASE)
        if match:
            serial = parse_serial(match.group(1))

    scored = sorted(
        (ModelCandidate(model, score_model(query, model)) for model in models) if query.strip() else (),
        key=lambda candidate: candidate.score,
        reverse=True,
    )
    viable = [candidate for candidate in scored if candidate.score >= RESOLVE_THRESHOLD]

    if not viable:
        if serial is not None:
            return _identify_by_serial_only(serial, models)
        return IdentificationResult(
            IdentificationStatus.NOT_FOUND,
            "The machine could not be identified. Ask for the model shown on the nameplate.",
        )

    top_score = viable[0].score
    contenders = [c for c in viable if c.score >= top_score - AMBIGUITY_MARGIN]
    if len(contenders) > 1 and serial is not None:
        by_serial = [c for c in contenders if any(cfg.contains(serial) for cfg in c.model.configurations)]
        if len(by_serial) == 1:
            contenders = by_serial
    if len(contenders) > 1:
        return IdentificationResult(
            IdentificationStatus.AMBIGUOUS_MODEL,
            "Several models match. Ask the customer to confirm the exact model.",
            candidates=tuple(contenders[:MAX_CANDIDATES]),
        )

    chosen = contenders[0]
    return _resolve_configuration(chosen.model, serial, tuple(viable[:MAX_CANDIDATES]))


def _resolve_configuration(
    model: ModelRecord, serial: int | None, candidates: tuple[ModelCandidate, ...]
) -> IdentificationResult:
    if serial is not None:
        for configuration in model.configurations:
            if configuration.contains(serial):
                return IdentificationResult(
                    IdentificationStatus.RESOLVED,
                    "Machine configuration identified from model and serial number.",
                    model, configuration, candidates,
                )
        return IdentificationResult(
            IdentificationStatus.SERIAL_MISMATCH,
            f"Serial {serial} does not belong to model {model.model_code}. Ask the customer to re-check the nameplate.",
            model, None, candidates,
        )
    if len(model.configurations) == 1:
        return IdentificationResult(
            IdentificationStatus.RESOLVED,
            "Machine identified; this model has a single configuration.",
            model, model.configurations[0], candidates,
        )
    return IdentificationResult(
        IdentificationStatus.NEEDS_SERIAL,
        f"Model {model.model_code} has {len(model.configurations)} configurations with different parts. "
        "Ask for the serial number from the nameplate.",
        model, None, candidates,
    )


def _identify_by_serial_only(serial: int, models: Sequence[ModelRecord]) -> IdentificationResult:
    matches = [
        (model, configuration)
        for model in models
        for configuration in model.configurations
        if configuration.contains(serial)
    ]
    if len(matches) == 1:
        model, configuration = matches[0]
        return IdentificationResult(
            IdentificationStatus.RESOLVED,
            "Machine configuration identified from the serial number alone.",
            model, configuration, (ModelCandidate(model, 1.0),),
        )
    return IdentificationResult(
        IdentificationStatus.NOT_FOUND,
        "The serial number does not match any known machine. Ask for the model and serial from the nameplate.",
    )
