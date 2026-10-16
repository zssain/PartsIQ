"""Characterization tests: pin the preserved legacy behaviour before/after prompt 06.

Pure logic only (no DB): identification, lexical scoring and fulfilment planning. These
guard against accidental changes to the legacy domain the kit requires us to preserve.
"""
from __future__ import annotations

import unittest

from app.fulfilment import WarehouseStock, plan_fulfilment
from app.identification import (
    ConfigurationRecord,
    ModelRecord,
    IdentificationStatus,
    identify_machine,
    parse_serial,
    score_model,
)
from app.lexical import LexicalScorer, PartDocument


def _model(configs):
    return ModelRecord(
        id=1, brand="Veltrano", model_code="VP-20", display_name="Veltrano VP-20",
        rated_output="20 kVA", family_code="GENSET", family_name_en="Generator", family_name_ar="مولد",
        configurations=tuple(configs),
    )


SINGLE = _model([ConfigurationRecord(100, "A", "A", 100000, 199999)])
MULTI = _model([
    ConfigurationRecord(100, "A", "A", 100000, 149999),
    ConfigurationRecord(101, "B", "B", 150000, 199999),
])


class IdentificationCharacterization(unittest.TestCase):
    def test_resolved_by_model_and_serial(self) -> None:
        result = identify_machine("VP-20", "150000", [MULTI])
        self.assertEqual(result.status, IdentificationStatus.RESOLVED)
        self.assertEqual(result.configuration.config_code, "B")

    def test_needs_serial_for_multi_config(self) -> None:
        self.assertEqual(identify_machine("VP-20", None, [MULTI]).status, IdentificationStatus.NEEDS_SERIAL)

    def test_single_config_resolves_without_serial(self) -> None:
        self.assertEqual(identify_machine("VP-20", None, [SINGLE]).status, IdentificationStatus.RESOLVED)

    def test_serial_mismatch(self) -> None:
        self.assertEqual(identify_machine("VP-20", "999999", [SINGLE]).status, IdentificationStatus.SERIAL_MISMATCH)

    def test_parse_serial_arabic_indic(self) -> None:
        self.assertEqual(parse_serial("١٢٣٤٥٦"), 123456)

    def test_score_model_exact_is_one(self) -> None:
        self.assertEqual(score_model("VP-20", SINGLE), 1.0)


class LexicalCharacterization(unittest.TestCase):
    def test_fuel_outranks_oil_for_fuel_query(self) -> None:
        docs = [
            PartDocument(1, ("oil filter",), (), "filters"),
            PartDocument(2, ("fuel filter",), (), "filters"),
        ]
        ranked = LexicalScorer().score("fuel filter", docs)
        self.assertEqual(ranked[0].part_id, 2)


class FulfilmentCharacterization(unittest.TestCase):
    def _stock(self, jed, ruh):
        return [WarehouseStock("JED", "Jeddah", "Western", jed), WarehouseStock("RUH", "Riyadh", "Central", ruh)]

    def test_local_only(self) -> None:
        plan = plan_fulfilment(self._stock(10, 0), {}, "JED", 5)
        self.assertEqual(plan.strategy, "local")
        self.assertEqual(plan.estimated_transfer_days, 0)

    def test_transfer_from_remote(self) -> None:
        plan = plan_fulfilment(self._stock(0, 10), {("RUH", "JED"): 2}, "JED", 5)
        self.assertEqual(plan.strategy, "transfer")
        self.assertEqual(plan.estimated_transfer_days, 2)

    def test_backorder_when_insufficient(self) -> None:
        plan = plan_fulfilment(self._stock(1, 1), {("RUH", "JED"): 2}, "JED", 10)
        self.assertEqual(plan.strategy, "backorder")
        self.assertEqual(plan.shortfall, 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
