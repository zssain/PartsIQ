import pytest

from app.security import MIN_API_KEY_LENGTH, is_valid_api_key, key_fingerprint, parse_api_keys

VALID_KEY_A = "a" * MIN_API_KEY_LENGTH
VALID_KEY_B = "b" * (MIN_API_KEY_LENGTH + 8)


def test_parse_api_keys_strips_blanks_and_duplicates() -> None:
    assert parse_api_keys(f" {VALID_KEY_A} ,,{VALID_KEY_B},{VALID_KEY_A} ") == (VALID_KEY_A, VALID_KEY_B)


def test_parse_api_keys_rejects_empty_configuration() -> None:
    with pytest.raises(ValueError):
        parse_api_keys(" , ")


def test_parse_api_keys_rejects_short_keys() -> None:
    with pytest.raises(ValueError):
        parse_api_keys(f"{VALID_KEY_A},short-key")


def test_is_valid_api_key_accepts_any_configured_key() -> None:
    keys = (VALID_KEY_A, VALID_KEY_B)
    assert is_valid_api_key(VALID_KEY_A, keys)
    assert is_valid_api_key(VALID_KEY_B, keys)


def test_is_valid_api_key_rejects_unknown_and_prefix_keys() -> None:
    keys = (VALID_KEY_A,)
    assert not is_valid_api_key("c" * MIN_API_KEY_LENGTH, keys)
    assert not is_valid_api_key(VALID_KEY_A[:-1], keys)
    assert not is_valid_api_key("", keys)


def test_key_fingerprint_is_stable_and_does_not_expose_key() -> None:
    fingerprint = key_fingerprint(VALID_KEY_A)
    assert fingerprint == key_fingerprint(VALID_KEY_A)
    assert fingerprint != key_fingerprint(VALID_KEY_B)
    assert len(fingerprint) == 16
    assert VALID_KEY_A not in fingerprint
