from partsiq_common.text import detect_language, extract_part_number_keys, normalize_text, part_number_key, tokenize


def test_arabic_normalisation_unifies_letter_forms_and_strips_article() -> None:
    assert tokenize("الفلتر") == tokenize("فلتر")
    assert normalize_text("طرمبة") == normalize_text("طرمبه")
    assert normalize_text("إطار") == normalize_text("اطار")
    assert normalize_text("فِلْتَر") == normalize_text("فلتر")


def test_arabic_indic_digits_are_converted() -> None:
    assert normalize_text("٢٥٠") == "250"


def test_part_number_key_ignores_formatting() -> None:
    assert part_number_key("vp-of 1042") == part_number_key("VP.OF.1042") == "VPOF1042"


def test_extract_part_number_keys_handles_spacing() -> None:
    assert "VPOF1042" in extract_part_number_keys("do you have VP OF 1042 in stock")
    assert "VPOF1042" in extract_part_number_keys("need vp-of-1042 x2")
    assert extract_part_number_keys("need an oil filter") == []


def test_detect_language() -> None:
    assert detect_language("need oil filter") == "en"
    assert detect_language("ابغى فلتر زيت") == "ar"
    assert detect_language("ابغى فلتر زيت for the generator") == "mixed"
    assert detect_language("1234") is None
