# 18 - Frontend shell and authentication
PHASE: Web   DEPENDS ON: 17   RISK: high

## GOAL
Create Next.js App Router shell from pinned package manifest. Public landing explains independent synthetic project; disable real-client signup. Supabase anonymous login supports demo; invited staff login supports operational roles. Keep all business API calls through gateway; only Auth and authorized private Storage transfer bypass it. Use bearer token in Authorization,not URL. Implement responsive skeleton,typed ApiError and request-ID display. Copy approved PNG icons and fonts from brand manifest.

## READ FIRST
- AGENTS.md
- docs/HANDOVER.md
- docs/CONSTRAINTS.md
- docs/ARCHITECTURE.md sections 2 and 4
- docs/TECH_SPEC.md
- docs/CONTRACTS.md
- docs/FLOW.md
- spec/file-ownership.json
- features/F01-branded-landing.md
- features/F54-access-and-permissions.md

## PLAN CHECK
State the exact files to create/modify, packages, validation commands and risk before implementation. The approved build sequence authorizes these listed changes. Ask only if a new decision changes locked scope, introduces a destructive action or crosses a boundary. Do not repeatedly ask for approval already granted. Verify prerequisite prompts are complete, not merely present as documents.

## PACKAGES
- `npm exec --yes --package=shadcn@4.20.1 -- shadcn --version`
- `npm exec --yes --package=pnpm@10.30.3 -- pnpm --version`
- `pnpm --dir apps/web add --save-exact next@16.2.12 react@19.2.6 react-dom@19.2.6 typescript@5.9.3 tailwindcss@4.1.18 @tailwindcss/postcss@4.1.18 postcss@8.5.6 @supabase/supabase-js@2.99.1 @supabase/ssr@0.8.0 next-intl@4.8.3 zod@4.6.5 vitest@4.1.11 @playwright/test@1.58.2 eslint@9.39.1 eslint-config-next@16.2.12 @testing-library/react@16.3.0 @testing-library/dom@10.4.1 @testing-library/jest-dom@6.9.1 @testing-library/user-event@14.6.1 jsdom@27.4.0 @vitejs/plugin-react@5.1.4 @types/react@19.2.14 @types/react-dom@19.2.3 @types/node@22.19.15 clsx@2.1.1 tailwind-merge@3.5.0 class-variance-authority@0.7.1 lucide-react@0.577.0 radix-ui@1.4.3`

Release dates and registry receipts are in spec/dependency-receipts.json. Use spec/python-requirements.lock and spec/pnpm-lock.yaml as resolution references; do not claim installing these packages proves application compatibility.

## FILES TO CREATE
- `apps/web/package.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/tsconfig.json`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/next.config.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/postcss.config.mjs`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/eslint.config.mjs`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/vitest.config.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/app/layout.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/app/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/app/login/page.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/styles/tokens.css`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/api.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/auth.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/components/BrandLogo.tsx`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/lib/contracts.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/pnpm-lock.yaml`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/tests/setup.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/playwright.config.ts`: implement the responsibility specified in the ordered logic and typed contracts below; no unregistered duplicate implementation.
- `apps/web/tests/features/f01.test.tsx`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.
- `tests/foundations/test_18.py`: acceptance source for the cases below; arrange isolated fixtures, invoke the production entry point, assert persisted and visible outcomes.

Typed entry contracts:

export function BrandLogo(props: {compact?: boolean}): React.JSX.Element; export async function api<T>(path: string, options: RequestInit): Promise<T>; export async function startAnonymousDemo(): Promise<DemoSession>.

Implementation sequence:
1. Create Next.js App Router shell from pinned package manifest.
2. Public landing explains independent synthetic project; disable real-client signup.
3. Supabase anonymous login supports demo; invited staff login supports operational roles.
4. Keep all business API calls through gateway; only Auth and authorized private Storage transfer bypass it.
5. Use bearer token in Authorization,not URL.
6. Implement responsive skeleton,typed ApiError and request-ID display.
7. Copy approved PNG icons and fonts from brand manifest.

Required feature behaviours:
- F01 Branded landing: Explain the enquiry-to-approval journey; show synthetic-demo notice; expose Start demo and architecture links; display the supplied bilingual logo without stretching. Failure cases: Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim.
- F54 Access and permissions: Verify Supabase issuer,audience,signature,expiry; derive identity server-side; enforce assigned-only review; keep credentials server-side; disable public real-client signup. Failure cases: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue.

Exact package markers and bundled assets created by this step:
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/Preview.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-1024.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-128.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-144.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-152.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-16.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-180.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-192.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-24.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-256.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-32.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-384.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-48.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-512.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-64.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-96.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-1024.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-128.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-144.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-152.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-16.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-180.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-192.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-24.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-256.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-32.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-384.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-48.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-512.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-64.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-96.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-1280.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-1740.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-320.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-640.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-1280.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-1740.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-320.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-640.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-hdpi-72.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-mdpi-48.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xhdpi-96.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xxhdpi-144.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xxxhdpi-192.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/google-play-512.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/ios-app-store-1024.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/social/partsiq-og-1200x630.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/social/partsiq-profile-1080.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/source/original-logo.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/source/transparent-logo.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/android-chrome-192x192.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/android-chrome-512x512.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/apple-touch-icon.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-16x16.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-32x32.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-48x48.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-96x96.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon.ico`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/maskable-icon-192x192.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/maskable-icon-512x512.png`
- `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/site.webmanifest`
- `apps/web/public/brand/fonts/NotoNaskhArabic-OFL.txt`
- `apps/web/public/brand/fonts/NotoNaskhArabic.ttf`
- `apps/web/public/brand/fonts/NotoSans-OFL.txt`
- `apps/web/public/brand/fonts/NotoSans.ttf`
- `apps/web/public/brand/fonts/NotoSansArabic-OFL.txt`
- `apps/web/public/brand/fonts/NotoSansArabic.ttf`
- `apps/web/public/brand/logo-original.png`

## FILES TO MODIFY
No existing runtime file requires modification beyond the documentation updates and package manifests named here.

## HOW IT CONNECTS
Owner: Web; ARCHITECTURE.md section2. FLOW.md row `18` identifies the entry contract and preceding owners. Required predecessors: 17. HTTP routes call application functions,which invoke domain rules and infrastructure adapters. Specialist tools are read-only. Gateway passes verified identity and request ID; worker events carry revision and lease generation. Register new routes in the named existing entry point; never create a parallel public backend.

## CONSTRAINTS FOR THIS STEP
Preserve legacy domain names and compatible-set filtering. OpenAI only through common client. BGE-M3 only in search. Assigned-only real review; own-session demo review. No final recommendation without current-revision approval. No paid fallback,external message,quotation,voice,reservation or order creation. Document assumptions as measured facts or explicit configuration,never as guarantees.

## ACCEPTANCE TESTS
- `apps/web/tests/features/f01.test.tsx`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `tests/foundations/test_18.py`: run success,invalid-input,unauthorized,stale-revision and dependency-failure cases applicable to its feature; use the feature-specific assertions below.
- `F01`: Missing repository link hides that action; logo has meaningful alternative text; no affiliation claim. Assert explain the enquiry-to-approval journey.
- `F54`: Forged role claim ignored; missing context denies rows; preview cannot reach prod database; demo cannot publish shared catalogue. Assert verify supabase issuer,audience,signature,expiry.

`python tools/run_checks.py --prompt 18` must exit0 and report all named tests passed, with no required test skipped. It dispatches each service test in its own process and runs UI tests through pnpm. Before that runner exists, prompt00 creates and tests it using the standard library. Do not fabricate a passing count. Record actual output in the feature trace. Test databases must be disposable local Supabase; no production reset.

## MANUAL VERIFICATION
Run the relevant demo path for frontend shell and authentication using synthetic fixtures. Inspect customer view and assigned-reviewer view where applicable. Confirm the success outcome,then exercise at least one listed failure. Inspect persisted revision,audit event and request ID without exposing secrets. For UI,check Arabic,keyboard operation and 360px width. For infrastructure,save the real provider/preflight receipt; missing account access is blocked,not passed.

## DOC UPDATES
Update docs/HANDOVER.md with completed step `18`, actual commands, blockers and next ID from prompts/README.md. Append docs/SESSION_LOG.md with actual model identifier if exposed,otherwise 'not exposed'. Record decision changes in docs/DECISIONS.md; update matching FLOW row and file-ownership manifest for approved additions. Update docs/TECH_SPEC.md schema/package receipts only after comparing reality. Set each affected feature trace to done only when its tests pass; retain original failures and corrective evidence.

## ROLLBACK
Before edits create `git tag pre-18` if absent. Commit this task independently. To undo,run `git log -1 --format=%H`,verify the displayed commit is this task,then `git revert --no-edit HEAD`. Do not revert unrelated later work. Applied SQL requires a new compensating migration and backup review; never reset production. Publication history and audit are retained. Deployment rollback selects previous immutable images and a schema-compatible release as described in docs/ROLLBACK.md.

## COMMIT
`feat(web): 18 frontend shell and authentication`

## DONE WHEN
- [ ] Exact paths and contracts implemented.
- [ ] Listed tests executed with actual evidence.
- [ ] Failure and permission cases pass.
- [ ] No forward runtime dependency introduced.
- [ ] Documentation and feature traces updated.
- [ ] Diff reviewed; no unrelated change.
- [ ] Commit recorded; unexecuted deployment checks remain explicitly blocked.
