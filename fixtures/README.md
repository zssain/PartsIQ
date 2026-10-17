# PartsIQ demo fixtures

**All data here is synthetic. It is never real client or TAMGO inventory.** Every brand, model,
platform, part number, warehouse and stock level is fabricated by a seeded generator. The files
must not be presented as real inventory in any demo, screenshot or recording.

## Files

| File | Contents |
| --- | --- |
| `catalogue.json` | One immutable catalogue version (the nine catalogue entity types) in the `CatalogueSnapshot` record shape foundation 02 defined. Loads directly through `FixtureCatalogueRepository.from_file(...)`. |
| `scenarios.json` | The four derived `DemoScenario` cases (`mixed_photo`, `missing_serial`, `incompatible_number`, `local_shortage`). |

Both documents carry `"synthetic": true` and a `provenance` string so the marker travels with
the data.

## Provenance and determinism

- **Generator:** `apps/api/partsiq/catalogue/fixtures.py` (self-contained; no dependency on
  `tools/`).
- **Seed:** `42` (`fixtures.DEFAULT_SEED`). The same seed always produces the **byte-identical**
  `catalogue.json` and `scenarios.json`. The `test_05_fixtures.py` acceptance test regenerates
  from the seed and asserts the committed files match exactly.
- **`version_id`:** derived deterministically from the canonical content digest (UUIDv5), so it
  never drifts between runs.

Regenerate with:

```bash
uv run --all-packages python -m partsiq.catalogue.fixtures
```

## Database ids == 1-based load ordinals

The catalogue loader inserts records in dataset order under `RESTART IDENTITY`, so a record's
database SERIAL id equals its 1-based insertion ordinal. `parts` and `model_configurations`
records therefore use that ordinal as their `entity_key`, and the scenarios reference the SAME
ordinals in `expected_part_ids` / `expected_configuration_id`. Loading the fixture under the
same controlled seed transaction assigns the identical ids, so a scenario resolved against the
serving database matches the fixture.

## The four scenarios are derived from real records (F02)

Scenarios are **selected from the generated records**, never hand-written. Generation **refuses**
(raises `ScenarioError`) rather than emit a case the catalogue cannot demonstrate — for example
an `incompatible_number` whose expected part is actually compatible with the resolved machine, or
a `local_shortage` whose stock claim is unsupported by the generated warehouse quantities.

`scenarios.json` carries the request input, the expected clarification/status and the
approved-compatible part set only. **No fixture inserts an approved recommendation**; approval
always requires the human publication gate at runtime.

Note: `mixed_photo` references `attachment_path` (`fixtures/nameplates/...png`). The binary PNG
is **not** committed by this step — the path is a reference the demo asset renderer fills in
later; the scenario is valid without the binary present.
