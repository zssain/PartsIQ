# Test checklist

## Build-kit checks
`python tools/kit/verify_kit.py`: 69 features,97 prompt files,template headings,dependency order,file ownership,release receipts and schema RLS coverage. `python -m compileall spec/contracts.py tools/kit`: syntax check for shipped specification/tooling. These checks do not certify runtime features.

## Per-prompt application checks
Run `python tools/run_checks.py --prompt 00` for bootstrap,then the current ID. The runner dispatches exact files from spec/features.json and spec/prompts.json. Python services execute in separate processes with their own app path; no mixed legacy app import cache. Frontend runs `pnpm --dir apps/web exec vitest run` on named tests,`pnpm --dir apps/web typecheck`,and `pnpm --dir apps/web lint`. Use `uv run --project services/search pytest` for legacy characterization in its isolated working directory. Expected exit0; log actual counts.

## Database and permission checks
Use disposable local Supabase,not bare Postgres alone. Apply all migrations; collect schema receipt; compare tables,columns,indexes,FKs,checks and RLS. Insert overlapping serial ranges and supersession cycles and expect rejection. Exercise concurrent cycle insertion under lock. Check unknown identity,customerA/customerB,assigned reviewer/unassigned reviewer/admin and own/foreign demo. Reuse one DB connection across actors to prove transaction-local context isolation. Test private Storage upload/read with real Auth tokens.

## Workflow checks
Start interrupted enquiry;restart process;resume. Inject duplicate event,expired lease,old revision and reset generation. Confirm stale results cannot commit. Kill Redis and confirm pending jobs survive; gateway rate limiter fails closed. Provider timeout leaves conservative budget reservation. Two simultaneous approvals create one recommendation; changed stock/catalogue returns409.

## Quality checks
Run deterministic labelled suite with no provider calls. Report candidate recall,top-choice correctness,clarification correctness and incompatible-offer count separately. Include denominator,dataset hash and catalogue version. Optional live model eval runs only with dedicated confirmed free credit. Never claim a measured accuracy from written expected outcomes.

## UI/PDF checks
360/768/1280 widths,200percent zoom,keyboard focus,screen-reader names,Arabic RTL,mixed serials,long content,empty/error/loading states. Export long bilingual approved enquiry; inspect every page for clipping,overlap and font loss. No internal notes in customer or PDF response.

## Hosted checks
After27,run hosted scenario suite over HTTPS against demo only. No destructive production fixtures. Record real environment,commit,latency and result. Free-plan expiry,paused project or unavailable credentials are blocked checks. A build-kit validation pass does not substitute for them.
