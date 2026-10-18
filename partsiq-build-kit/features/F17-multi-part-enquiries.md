# F17 Multi-part enquiries

Status: specified, not implemented.

Owning prompt: `prompts/F17-multi-part-enquiries.md`.

Behavior: Track up to 20 items with independent quantity, machine, candidate selection and status; clarify individual items; verify aggregate allocation for repeated part requests.

Failure criteria: One unresolved item blocks final all-items approval; allocations across duplicate parts cannot double count available stock; zero quantity rejected.

API operations: f17_correct_items

Files:
- `apps/api/partsiq/features/f17_multi_part_enquiries.py`
- `apps/web/src/features/f17_multi_part_enquiries/Panel.tsx`
- `tests/features/test_f17.py`
- `apps/web/tests/features/f17.test.tsx`
- `apps/api/partsiq/api/f17_multi_part_enquiries.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
