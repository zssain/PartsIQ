# F06 Responsive layouts

Status: specified, not implemented.

Owning prompt: `prompts/F06-responsive-layouts.md`.

Behavior: Support 360, 768, 1280 CSS-pixel widths; stack review panels; horizontally scroll comparison tables within their region; preserve sticky primary review actions without covering content.

Failure criteria: No page-wide horizontal overflow; zoom 200 percent remains usable; mobile dialogs retain visible close action.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f06_responsive_layouts.py`
- `apps/web/src/features/f06_responsive_layouts/Panel.tsx`
- `tests/features/test_f06.py`
- `apps/web/tests/features/f06.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
