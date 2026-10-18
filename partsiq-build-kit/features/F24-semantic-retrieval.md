# F24 Semantic retrieval

Status: specified, not implemented.

Owning prompt: `prompts/F24-semantic-retrieval.md`.

Behavior: Load one BGE-M3 encoder in the worker search module; use normalized 1024-d vectors; retain legacy weighted fusion; fall back to lexical on unavailable embedding path.

Failure criteria: Wrong dimension rejected; no model loaded in API process; no semantic candidate outside compatible IDs.

API operations: f24_capabilities

Files:
- `apps/api/partsiq/features/f24_semantic_retrieval.py`
- `apps/web/src/features/f24_semantic_retrieval/Panel.tsx`
- `tests/features/test_f24.py`
- `apps/web/tests/features/f24.test.tsx`
- `apps/api/partsiq/api/f24_semantic_retrieval.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
