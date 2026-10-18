# F32 Warehouse stock

Status: specified, not implemented.

Owning prompt: `prompts/F32-warehouse-stock.md`.

Behavior: Show available quantity as on_hand minus reserved; include timestamp and warehouse name; keep display and planner using same snapshot.

Failure criteria: Negative stock blocked; stock unavailable never displayed as zero without explanation; unknown warehouse rejected.

API operations: f32_stock_for_selection

Files:
- `apps/api/partsiq/features/f32_warehouse_stock.py`
- `apps/web/src/features/f32_warehouse_stock/Panel.tsx`
- `tests/features/test_f32.py`
- `apps/web/tests/features/f32.test.tsx`
- `apps/api/partsiq/api/f32_warehouse_stock.py`

Execution receipt: no application tests have been executed during kit authoring. The implementation agent must append command, actual result, commit and remaining blocker here.
