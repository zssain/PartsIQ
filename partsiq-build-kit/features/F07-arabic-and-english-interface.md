# F07 Arabic and English interface

Status: specified, not implemented.

Owning prompt: `prompts/F07-arabic-and-english-interface.md`.

Behavior: Use a locale cookie and complete en/ar message catalogs; persist preference; set document lang and dir; isolate serials, numbers and part identifiers with bdi.

Failure criteria: Missing translation fails tests; language switch preserves enquiry ID and unsent draft; mixed Arabic identifiers remain readable.

API operations: No independent endpoint

Files:
- `apps/api/partsiq/features/f07_arabic_and_english_interface.py`
- `apps/web/src/features/f07_arabic_and_english_interface/Panel.tsx`
- `tests/features/test_f07.py`
- `apps/web/tests/features/f07.test.tsx`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
