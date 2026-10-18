# F23 Aliases and typo matching

Status: specified, not implemented.

Owning prompt: `prompts/F23-aliases-and-typo-matching.md`.

Behavior: Preserve Arabic normalization, part-number keys, phrase scoring and fuzzy token matching; remove machine terms using resolved model context.

Failure criteria: Arabic part words are not removed as machine words; exact part number outranks unrelated fuzzy alias; normalization parity test matches SQL.

API operations: f23_lexical_evidence

Files:
- `apps/api/partsiq/features/f23_aliases_and_typo_matching.py`
- `apps/web/src/features/f23_aliases_and_typo_matching/Panel.tsx`
- `tests/features/test_f23.py`
- `apps/web/tests/features/f23.test.tsx`
- `apps/api/partsiq/api/f23_aliases_and_typo_matching.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
