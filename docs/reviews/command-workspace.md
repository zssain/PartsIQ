# Command workspace implementation review

Baseline: 92a5c43. Focused source review, not an exhaustive line-by-line audit.

## Implemented

The `/demo/live` flow has a responsive product shell with overview, enquiries, specialist activity and access-model screens. Query navigation supports browser history. The active enquiry survives same-tab refresh. Customer/reviewer views retain one identity and existing canonical review endpoints. Slate/violet replaces the forest palette, using existing Lucide pins. No packages or migrations added. Activity renders persisted server events. Guided scenarios remain available.

The API client normalizes `/v1` paths against origin and `/v1` base URLs. Previously default configuration concatenated `/v1` with `/v1/enquiries`. Four regression cases cover default, origin, legacy relative and explicit base configurations.

## Findings and remaining work

| Finding | Evidence | Status |
| --- | --- | --- |
| Consolidated engine already uses LangGraph | workflow/graph.py and runner.py | Confirmed |
| Routing and compatible retrieval remain deterministic | route_step and resolution.resolve_items | Preserved |
| Demo header is an opaque bearer-like credential, not staff authentication | core/dependencies.py DemoActorVerifier | Synthetic scope only |
| Staff inbox is still an offline scenario list | app/staff/inbox/page.tsx | Remains; workspace uses API-connected ReviewerInbox |
| Later CSS overrode navy with forest tokens | styles/pq.css | Corrected |
| API default could duplicate /v1 | lib/api.ts and lib/live.ts | Fixed and tested |
| Agent-to-agent exchanges and user pause/cancel are absent | Current graph and live client | Not implemented; labelled unconnected |

For collaboration mode, keep guided mode and share its compatibility/verification/approval services. Persist addressed specialist messages with run ID, enquiry revision, sender, recipient, message kind, correlation ID and validated payload. Specialists may request evidence or challenge a proposal; they cannot authorize compatibility or publication. User commands need server authentication, expected revision and idempotency keys. Pause prevents next-step dispatch; cancel fences in-flight results. Resume revalidates revision and allowance. Bound turns, tools, tokens and elapsed time. Render validated summaries and tool outcomes. Before activation, test unauthorized/stale controls, restart recovery, exhausted credit, loops and changed evidence at approval.

Real staff screens still need session restoration, role-aware navigation from server capabilities and assignment-scoped requests. A role selector is not RBAC. Validate live Supabase login before claiming completion.

## Checks and limits

86 Vitest tests passed; TypeScript noEmit passed; Next.js production build passed. Node 24.19.0 differs from pinned Node 22.22.0. Pins and lockfile unchanged. Installer linked packages but reported ignored lifecycle scripts; installed binaries ran tests/build. Browser download failed with a truncated archive, so visual browser checks are blocked. DuckDNS fetch timed out. No live model, Snowflake, Redis or Supabase validation; no production deployment.

Rollback: revert implementation commit. No backend state or migration changes.
