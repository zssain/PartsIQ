# F08 Light and dark themes

Status: specified, not implemented.

Owning prompt: `prompts/F08-light-and-dark-themes.md`.

Behavior: Use CSS semantic tokens; initialize from saved preference then system setting; expose accessible toggle; honor reduced motion and browser color-scheme.

Failure criteria: No hydration mismatch; chart colors and focus rings meet contrast checks; storage-disabled browsers still work.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f08_light_and_dark_themes.py`
- `apps/web/src/features/f08_light_and_dark_themes/Panel.tsx`
- `tests/features/test_f08.py`
- `apps/web/tests/features/f08.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
