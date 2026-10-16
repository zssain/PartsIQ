"""F21 Machine mismatch detection — model+serial compared together, safe handling."""
from __future__ import annotations

import unittest

from app.identification import ConfigurationRecord, ModelRecord, IdentificationStatus, identify_machine


def _model(code, start, end):
    return ModelRecord(
        id=start, brand="Veltrano", model_code=code, display_name=f"Veltrano {code}",
        rated_output=None, family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=(ConfigurationRecord(start, "A", "A", start, end),),
    )


A = _model("VP-20", 100000, 199999)
B = _model("CX-99", 500000, 599999)


class MismatchDetection(unittest.TestCase):
    def test_valid_serial_of_different_model_is_mismatch(self) -> None:
        result = identify_machine("VP-20", "550000", [A, B])
        self.assertEqual(result.status, IdentificationStatus.SERIAL_MISMATCH)
        self.assertIn("re-check", result.message.lower())

    def test_nonnumeric_serial_does_not_crash(self) -> None:
        result = identify_machine("VP-20", "no-serial-here", [A])
        # Falls back to model-only resolution (single config) without raising.
        self.assertEqual(result.status, IdentificationStatus.RESOLVED)

    def test_retrieval_blocked_until_identity_resolved(self) -> None:
        # Mismatch yields no configuration, so downstream search has nothing to run on.
        self.assertIsNone(identify_machine("VP-20", "550000", [A, B]).configuration)


if __name__ == "__main__":
    unittest.main(verbosity=2)
