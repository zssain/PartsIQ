# F57 Catalogue browser

Status: specified, not implemented.

Owning prompt: `prompts/F57-catalogue-browser.md`.

Behavior: Read published catalogue with model/category/text filters; page results; show part detail and supersession; staff can inspect fitment and sources.

Failure criteria: No unpublished import rows exposed; missing number returns 404; literal query cannot become SQL.

API operations: f57_browse, f57_get_part

Files:
- `apps/api/partsiq/features/f57_catalogue_browser.py`
- `apps/web/src/features/f57_catalogue_browser/Panel.tsx`
- `tests/features/test_f57.py`
- `apps/web/tests/features/f57.test.tsx`
- `apps/api/partsiq/api/f57_catalogue_browser.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
