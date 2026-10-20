# Access model (RBAC + resource scope)

Roles come only from the server: the Supabase Auth admin API (`app_metadata.partsiq_roles`,
writable only with the service role) or `staff_roles` when the database is wired. Token claims
are never trusted for roles. Capabilities are derived in `apps/api/partsiq/auth/actors.py`, and
the frontend builds navigation from `GET /v1/me`. Every endpoint re-checks capability **and**
resource scope.

| Capability | Customer (no role) | reviewer | catalogue_admin | admin | Demo visitor (own sandbox only) |
| --- | --- | --- | --- | --- | --- |
| enquiry.create / read_own, machines, run.control_own | ✓ own | ✓ own | ✓ own | ✓ own | ✓ |
| review.queue / review.decide / run.control_assigned | — | ✓ **assigned only** | — | ✓ all | ✓ sandbox |
| catalogue.browse | — | ✓ | ✓ | ✓ | ✓ |
| catalogue.import / publish | — | — | ✓ | ✓ | ✓ sandbox copy |
| admin.users / admin.assign | — | — | — | ✓ | ✓ synthetic personas |
| analytics / audit / jobs / evaluation | — | — | — | ✓ | ✓ sandbox data |
| ai.allowance (owner configuration) | — | — | — | ✓ | **never** |

Scope rules:

* A customer sees only enquiries they own. A reviewer sees only enquiries assigned to them;
  an unassigned real enquiry is 404, not 403. An admin sees the whole account workspace.
* A demo visitor's workspace is its own session generation. Nothing in another session or
  in the account workspace is reachable. Reset or expiry abandons the sandbox.
* The demo "Preview as" selector only changes which screens are shown. It sends nothing that
  could widen access.
* Admin role changes are version-checked and audited, and you cannot remove your own admin
  role. Approval, publication, stock, catalogue activation and role changes are never available
  to specialists or tools.
