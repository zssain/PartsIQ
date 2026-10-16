"""API key parsing, constant-time verification and non-reversible client fingerprints."""

import hashlib
import hmac

MIN_API_KEY_LENGTH = 32


def parse_api_keys(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated key list, removing blanks and duplicates while preserving order."""
    keys = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    if not keys:
        raise ValueError("At least one gateway API key must be configured")
    if any(len(key) < MIN_API_KEY_LENGTH for key in keys):
        raise ValueError(f"Every gateway API key must be at least {MIN_API_KEY_LENGTH} characters long")
    return keys


def is_valid_api_key(candidate: str, valid_keys: tuple[str, ...]) -> bool:
    """Compare against every configured key in constant time, without early exit."""
    candidate_bytes = candidate.encode("utf-8")
    matched = False
    for key in valid_keys:
        matched |= hmac.compare_digest(candidate_bytes, key.encode("utf-8"))
    return matched


def key_fingerprint(key: str) -> str:
    """Return a short, non-reversible identifier for logs and rate-limit buckets."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
