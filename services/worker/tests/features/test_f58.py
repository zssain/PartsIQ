"""F58 Catalogue imports — dry-run validation of CSV/XLSX without evaluating formulas.

Rejects macro-enabled workbooks and formula cells; enforces the 10 MiB / 50 000-row limits;
validates schema, model references, serial overlap, supersession cycles and source evidence;
never writes published data; only catalogue_admin/admin may validate.
"""
from __future__ import annotations

import csv
import io
import unittest
import zipfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from openpyxl import Workbook

from app.features.f58_catalogue_imports import (
    F58Request,
    ImportFile,
    MAX_BYTES,
    validate_import,
)
from partsiq_common.contracts import ActorContext, JobLease
from partsiq_common.errors import PartsIQError

WHEN = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
COLUMNS = ["part_number", "name_en", "name_ar", "category", "model_id",
           "serial_start", "serial_end", "superseded_by", "source_reference"]
GOOD_SOURCE = "SYNTH-CA rev 1, section FILTERS"


def _admin():
    return ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["catalogue_admin"])


def _lease():
    return JobLease(id=uuid4(), kind="catalog_import", enquiry_id=None, revision=None,
                    session_generation=None, lease_token=uuid4(),
                    expires_at=WHEN + timedelta(seconds=60), attempt=1, payload={})


def _csv_bytes(rows, columns=COLUMNS):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _good_row(part="VP-10", model="1", start="", end="", superseded="", source=GOOD_SOURCE):
    return [part, "fuel filter", "فلتر", "filters", model, start, end, superseded, source]


def _xlsx_bytes(rows, *, formula=False):
    wb = Workbook()
    ws = wb.active
    ws.append(COLUMNS)
    for row in rows:
        ws.append(row)
    if formula:
        ws["B2"] = "=1+1"  # a real formula cell (data_type 'f'); must be rejected, never computed
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _inject_macro(xlsx: bytes) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(xlsx)) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("xl/vbaProject.bin", b"\x00macro")
    return out.getvalue()


class FakeImportStore:
    def __init__(self, file, models=frozenset({1, 2}), *, raises=None):
        self._file = file
        self._models = set(models)
        self._raises = raises

    async def load_batch(self, batch_id):
        if self._raises is not None:
            raise self._raises
        return self._file

    async def known_model_ids(self):
        return self._models


def _file(data, name="import.csv", media="text/csv"):
    return ImportFile(filename=name, media_type=media, data=data)


async def _run(file, actor=None, store=None):
    store = store or FakeImportStore(file)
    return await validate_import(actor or _admin(), F58Request(batch_id=uuid4(), lease=_lease()), store=store)


class ValidateImport(unittest.IsolatedAsyncioTestCase):
    async def test_valid_csv(self):
        result = await _run(_file(_csv_bytes([_good_row()])))
        self.assertTrue(result.valid)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.errors, [])

    async def test_missing_column_schema_error(self):
        cols = [c for c in COLUMNS if c != "source_reference"]
        data = _csv_bytes([["VP-10", "fuel", "ف", "filters", "1", "", "", ""]], columns=cols)
        result = await _run(_file(data))
        self.assertFalse(result.valid)
        self.assertIn("SCHEMA", {e.code for e in result.errors})

    async def test_csv_formula_rejected(self):
        row = _good_row()
        row[1] = "=cmd|' /C calc'!A0"  # formula-injection in name_en
        result = await _run(_file(_csv_bytes([row])))
        self.assertIn("FORMULA_NOT_ALLOWED", {e.code for e in result.errors})

    async def test_unknown_model_reference(self):
        result = await _run(_file(_csv_bytes([_good_row(model="99")])))
        self.assertIn("BAD_REFERENCE", {e.code for e in result.errors})

    async def test_bad_source_evidence(self):
        result = await _run(_file(_csv_bytes([_good_row(source="loose text")])))
        self.assertIn("MISSING_EVIDENCE", {e.code for e in result.errors})

    async def test_serial_overlap(self):
        rows = [_good_row(part="A", start="100", end="200"), _good_row(part="B", start="150", end="250")]
        result = await _run(_file(_csv_bytes(rows)))
        self.assertIn("SERIAL_OVERLAP", {e.code for e in result.errors})

    async def test_supersession_cycle(self):
        rows = [_good_row(part="A", superseded="B"), _good_row(part="B", superseded="A")]
        result = await _run(_file(_csv_bytes(rows)))
        self.assertIn("SUPERSESSION_CYCLE", {e.code for e in result.errors})

    async def test_valid_xlsx(self):
        data = _xlsx_bytes([_good_row()])
        result = await _run(_file(data, name="import.xlsx",
                                  media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        self.assertTrue(result.valid)
        self.assertEqual(result.row_count, 1)

    async def test_xlsx_formula_rejected_not_evaluated(self):
        data = _xlsx_bytes([_good_row()], formula=True)
        result = await _run(_file(data, name="import.xlsx", media="application/octet-stream"))
        self.assertIn("FORMULA_NOT_ALLOWED", {e.code for e in result.errors})

    async def test_macro_workbook_rejected(self):
        data = _inject_macro(_xlsx_bytes([_good_row()]))
        result = await _run(_file(data, name="import.xlsx", media="application/octet-stream"))
        self.assertIn("MACROS_NOT_ALLOWED", {e.code for e in result.errors})

    async def test_file_too_large(self):
        result = await _run(_file(b"x" * (MAX_BYTES + 1)))
        self.assertFalse(result.valid)
        self.assertIn("FILE_TOO_LARGE", {e.code for e in result.errors})

    async def test_too_many_rows(self):
        rows = [_good_row(part=f"VP-{i}") for i in range(50_001)]
        result = await _run(_file(_csv_bytes(rows)))
        self.assertIn("TOO_MANY_ROWS", {e.code for e in result.errors})

    async def test_non_admin_forbidden(self):
        reviewer = ActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
        with self.assertRaises(PartsIQError) as ctx:
            await _run(_file(_csv_bytes([_good_row()])), actor=reviewer)
        self.assertEqual(ctx.exception.http_status, 403)

    async def test_missing_batch_not_found(self):
        with self.assertRaises(PartsIQError) as ctx:
            await _run(None)
        self.assertEqual(ctx.exception.http_status, 404)

    async def test_dependency_failure_propagates(self):
        store = FakeImportStore(None, raises=PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail="down"))
        with self.assertRaises(PartsIQError) as ctx:
            await _run(None, store=store)
        self.assertEqual(ctx.exception.code, "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
