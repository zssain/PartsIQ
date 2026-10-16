"""F20 Machine identification — boundary serials, single match, conflicting hints."""
from __future__ import annotations

import unittest

from app.identification import ConfigurationRecord, ModelRecord, IdentificationStatus, identify_machine


def _model(code, configs):
    return ModelRecord(
        id=hash(code) % 1000, brand="Veltrano", model_code=code, display_name=f"Veltrano {code}",
        rated_output=None, family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=tuple(configs),
    )


A = _model("VP-20", [
    ConfigurationRecord(100, "A", "A", 100000, 149999),
    ConfigurationRecord(101, "B", "B", 150000, 199999),
])
OTHER = _model("CX-99", [ConfigurationRecord(200, "A", "A", 500000, 599999)])


class MachineIdentification(unittest.TestCase):
    def test_boundary_serials_match_exactly_one_configuration(self) -> None:
        self.assertEqual(identify_machine("VP-20", "149999", [A]).configuration.config_code, "A")
        self.assertEqual(identify_machine("VP-20", "150000", [A]).configuration.config_code, "B")

    def test_serial_only_resolves_when_unique(self) -> None:
        result = identify_machine("", "520000", [A, OTHER])
        self.assertEqual(result.status, IdentificationStatus.RESOLVED)
        self.assertEqual(result.model.model_code, "CX-99")

    def test_conflicting_hint_does_not_silently_override(self) -> None:
        # Model VP-20 but a serial from CX-99's range -> mismatch, never a silent switch.
        result = identify_machine("VP-20", "520000", [A, OTHER])
        self.assertEqual(result.status, IdentificationStatus.SERIAL_MISMATCH)

    def test_unknown_machine_not_found(self) -> None:
        self.assertEqual(identify_machine("ZZ-00", None, [A]).status, IdentificationStatus.NOT_FOUND)


if __name__ == "__main__":
    unittest.main(verbosity=2)
