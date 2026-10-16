from app.identification import (
    ConfigurationRecord,
    IdentificationStatus,
    ModelRecord,
    identify_machine,
    parse_serial,
)


def _model(model_id: int, code: str, output: str, family: str, configs: list[tuple[int, str, int, int]]) -> ModelRecord:
    return ModelRecord(
        id=model_id, brand="Veltrano Power", model_code=code, display_name=f"{code} unit", rated_output=output,
        family_code=family, family_name_en=family, family_name_ar="عائلة",
        configurations=tuple(ConfigurationRecord(cid, cc, cc, start, end) for cid, cc, start, end in configs),
    )


MODELS = [
    _model(1, "VP-100", "100 kVA", "GENSET", [(10, "A", 300000, 339999), (11, "B", 340000, 379999)]),
    _model(2, "VP-250", "250 kVA", "GENSET", [(12, "A", 400000, 439999)]),
    _model(3, "HL-25D", "2.5 t", "FORKLIFT", [(13, "A", 500000, 539999)]),
    _model(4, "HL-25E", "2.5 t", "FORKLIFT", [(14, "A", 600000, 639999)]),
]


def test_exact_model_with_serial_resolves_configuration() -> None:
    result = identify_machine("vp 100 generator", "SN 345001", MODELS)
    assert result.status is IdentificationStatus.RESOLVED
    assert result.configuration is not None and result.configuration.id == 11


def test_serial_inside_query_text_is_used() -> None:
    result = identify_machine("VP-100 serial 301234 need oil filter", None, MODELS)
    assert result.status is IdentificationStatus.RESOLVED and result.configuration.id == 10


def test_multi_configuration_model_without_serial_asks_for_serial() -> None:
    assert identify_machine("VP100", None, MODELS).status is IdentificationStatus.NEEDS_SERIAL


def test_single_configuration_model_resolves_without_serial() -> None:
    result = identify_machine("vp-250", None, MODELS)
    assert result.status is IdentificationStatus.RESOLVED and result.configuration.id == 12


def test_rated_output_identifies_generator() -> None:
    result = identify_machine("our 250 kva genset", None, MODELS)
    assert result.model is not None and result.model.model_code == "VP-250"


def test_ambiguous_partial_model_is_reported() -> None:
    result = identify_machine("HL25 forklift", None, MODELS)
    assert result.status is IdentificationStatus.AMBIGUOUS_MODEL
    assert {c.model.model_code for c in result.candidates} == {"HL-25D", "HL-25E"}


def test_serial_disambiguates_ambiguous_models() -> None:
    result = identify_machine("HL25 forklift", "600123", MODELS)
    assert result.status is IdentificationStatus.RESOLVED and result.model.model_code == "HL-25E"


def test_serial_from_wrong_model_is_flagged() -> None:
    assert identify_machine("VP-100", "400001", MODELS).status is IdentificationStatus.SERIAL_MISMATCH


def test_serial_only_and_unknown_inputs() -> None:
    assert identify_machine("", "405000", MODELS).configuration.id == 12
    assert identify_machine("tractor", None, MODELS).status is IdentificationStatus.NOT_FOUND


def test_parse_serial_handles_prefixes_and_arabic_digits() -> None:
    assert parse_serial("SN-345001") == 345001
    assert parse_serial("٣٤٥٠٠١") == 345001
    assert parse_serial("no digits") is None
