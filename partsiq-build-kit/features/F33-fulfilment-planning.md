# F33 Fulfilment planning

Status: specified, not implemented.

Owning prompt: `prompts/F33-fulfilment-planning.md`.

Behavior: Allocate local stock first then reachable warehouses deterministically; compute shortage; use quantity units; do not reserve stock or create orders.

Failure criteria: Total allocations never exceed request or stock; fractional quantities respect unit policy; unavailable transfer route cannot be invented.

API operations: f33_plan_enquiry

Files:
- `apps/api/partsiq/features/f33_fulfilment_planning.py`
- `apps/web/src/features/f33_fulfilment_planning/Panel.tsx`
- `tests/features/test_f33.py`
- `apps/web/tests/features/f33.test.tsx`
- `apps/api/partsiq/api/f33_fulfilment_planning.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
