# PartsIQ labelled evaluation dataset (F62)

This directory holds the **labelled, deterministic** evaluation fixture used by
`partsiq.evaluation.runner`. It is the single source of ground truth for the offline
evaluation suite and is pinned by a content hash on every run.

## Files

- `cases.json` — the labelled cases, one JSON object per `partsiq.core.contracts.EvalCase`
  (`id`, `scenario`, `input_text`, `expected_status`, `expected_part_ids`).

## What the dataset covers

The eleven cases span the four product demos plus the required boundary and robustness
categories:

| scenario | id | labelled outcome |
| --- | --- | --- |
| `mixed_photo` | `demo-mixed-photo` | resolves → `awaiting_review`, part `[92]` |
| `missing_serial` | `demo-missing-serial` | abstains → `needs_information` (needs serial) |
| `incompatible_number` | `demo-incompatible-number` | abstains → `needs_information` (mismatch) |
| `local_shortage` | `demo-local-shortage` | resolves → `awaiting_review`, part `[92]` |
| `arabic_normalization` | `arabic-normalization` | resolves (Arabic request) → part `[92]` |
| `typo_tolerance` | `typo-tolerance` | resolves (misspellings, no hyphens) → part `[92]` |
| `serial_boundary` | `serial-boundary` | resolves (serial at range start) → part `[92]` |
| `ambiguity` | `ambiguity-close-scores` | abstains → `needs_information`, candidates `[91, 92]` |
| `multi_item_stock` | `multi-item-stock` | resolves → part `[92]` |
| `injection` | `prompt-injection` | resolves to the SAME part `[92]` — the embedded `SYSTEM:` instruction is ignored |
| `unreadable` | `unreadable-photo` | **unlabelled**: excluded from accuracy |

## How it is scored (non-negotiable rules)

- **Exact match only.** A case passes only when the actual `status` and the (order-insensitive)
  `part_ids` equal the labels. A failing case keeps its **actual** output in the receipt; the
  expected answer is never edited to make a test pass.
- **No model confidence as accuracy.** `EvalOutput` carries no confidence field. A model's
  self-reported score is never used as accuracy, and a deterministic (simulated) run never claims
  measured model accuracy.
- **Accuracy over definitive cases only.** `accuracy()` scores the definitive labelled cases;
  the labelled abstentions (`needs_information`) are reported **separately**, and the
  `unlabelled` unreadable case is **excluded** entirely — never counted correct or wrong.
- **Input isolation (F48).** The deterministic resolver keys only off a case's `scenario`; the
  `injection` case proves an injected instruction in `input_text` cannot change the output.
- **Dataset pinning.** `dataset_sha256()` canonically hashes this file so every `EvalRun` and
  receipt records the exact dataset it scored.

## Deterministic vs. live

The deterministic suite runs fully offline against the seed-42 synthetic catalogue
(`partsiq.catalogue.fixtures`) and makes **no** OpenAI or Snowflake call, so it needs no account
credit. The live-extraction evaluation is a **separate, allowance-gated** path and is not run
here; it is BLOCKED until a confirmed OpenAI credit allowance and expiry exist
(`docs/CONSTRAINTS.md` rule 13).

## Synthetic, never real client data

Every brand, model, part number and request text is synthetic. New cases enter this set only
through `partsiq.evaluation.curation.curate_case`: a staff-approved, **anonymized** correction,
linked to its source correction id and recorded in the audit log. Raw customer PII is never
committed here.
