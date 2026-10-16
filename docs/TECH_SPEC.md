# Technical specification

## 1. Stack and conventions
Python3.12.12,Node22.22.0,Next.js,React,TypeScript,Tailwind,shadcn-derived components,next-intl,FastAPI,LangGraph,Supabase and OpenAI. Preserve asyncpg for legacy search/catalogue; psycopg supports new transactional repositories/checkpointer. All decimals are strings over JSON. UTC timestamps; bilingual UI with RTL. Root uv workspace uses one uv.lock. Run service tests separately because legacy import packages are named app.

## 2. Exhaustive application file ownership
The table lists planned application files,not files claimed to be implemented in this ZIP. Original code comes from references/legacy-backend.zip. Generated assets are enumerated in brand/assets-manifest.json; prompt18 copies them byte-for-byte into apps/web/public/brand. Python package __init__.py markers required for new package directories are created by their first owning prompt and listed by the final manifest expansion. The machine-readable authority is spec/file-ownership.json.

| Path | Creating prompt | Later modifying prompts |
|---|---|---|
| `.env.example` | 00 | none |
| `.github/workflows/ci.yml` | 25 | none |
| `.github/workflows/deploy-backend.yml` | 25 | 26 |
| `.gitignore` | 00 | none |
| `.nvmrc` | 00 | none |
| `.python-version` | 00 | none |
| `Caddyfile` | 24 | none |
| `README.md` | 00 | F68 |
| `apps/web/app/chat/[id]/page.tsx` | 19 | none |
| `apps/web/app/demo/page.tsx` | 19 | none |
| `apps/web/app/history/page.tsx` | F19 | none |
| `apps/web/app/layout.tsx` | 18 | F06, F07, F08 |
| `apps/web/app/login/page.tsx` | 18 | none |
| `apps/web/app/page.tsx` | 18 | F06, F07, F08, F16, F17, F19, F36, F55, F56, F57, F58, F59, F60, F63, F65 |
| `apps/web/app/staff/analytics/page.tsx` | F63 | none |
| `apps/web/app/staff/catalogue/page.tsx` | F57 | none |
| `apps/web/app/staff/enquiries/[id]/page.tsx` | 20 | F29, F31, F35, F38, F41, F42, F43, F44 |
| `apps/web/app/staff/inbox/page.tsx` | 20 | F36 |
| `apps/web/components/BrandLogo.tsx` | 18 | none |
| `apps/web/components/chat/Chat.tsx` | 19 | F16, F17 |
| `apps/web/components/chat/OcrConfirmation.tsx` | 19 | none |
| `apps/web/components/chat/Progress.tsx` | 19 | none |
| `apps/web/components/chat/UploadCard.tsx` | 19 | none |
| `apps/web/components/features/AssignmentControl.tsx` | F42 | none |
| `apps/web/components/features/CandidateComparison.tsx` | F31 | none |
| `apps/web/components/features/CatalogueBrowser.tsx` | F57 | none |
| `apps/web/components/features/CatalogueVersions.tsx` | F59 | none |
| `apps/web/components/features/ConversationSummary.tsx` | F44 | none |
| `apps/web/components/features/CorrectionEditor.tsx` | F38 | none |
| `apps/web/components/features/CorrectionFeedback.tsx` | F65 | none |
| `apps/web/components/features/EvidenceViewer.tsx` | F29 | none |
| `apps/web/components/features/HistoryList.tsx` | F19 | none |
| `apps/web/components/features/ImportWizard.tsx` | F58 | none |
| `apps/web/components/features/InboxFilters.tsx` | F36 | none |
| `apps/web/components/features/InternalNotes.tsx` | F41 | none |
| `apps/web/components/features/ItemList.tsx` | F17 | none |
| `apps/web/components/features/LocaleSwitcher.tsx` | F07 | none |
| `apps/web/components/features/MetricsDashboard.tsx` | F63 | none |
| `apps/web/components/features/MissingPartsQueue.tsx` | F60 | none |
| `apps/web/components/features/OverdueBadge.tsx` | F43 | none |
| `apps/web/components/features/PhotoQualityNotice.tsx` | F16 | none |
| `apps/web/components/features/RepeatEnquiry.tsx` | F56 | none |
| `apps/web/components/features/ResponsiveShell.tsx` | F06 | none |
| `apps/web/components/features/SavedMachines.tsx` | F55 | none |
| `apps/web/components/features/StockFreshness.tsx` | F35 | none |
| `apps/web/components/features/ThemeToggle.tsx` | F08 | none |
| `apps/web/components/review/ApprovalControls.tsx` | 20 | none |
| `apps/web/components/review/Timeline.tsx` | 20 | none |
| `apps/web/components/review/Workspace.tsx` | 20 | none |
| `apps/web/eslint.config.mjs` | 18 | none |
| `apps/web/i18n/request.ts` | F07 | none |
| `apps/web/lib/api.ts` | 18 | none |
| `apps/web/lib/auth.ts` | 18 | none |
| `apps/web/lib/contracts.ts` | 18 | none |
| `apps/web/lib/features/f06_responsive_layouts.ts` | F06 | none |
| `apps/web/lib/features/f07_arabic_and_english_interface.ts` | F07 | none |
| `apps/web/lib/features/f08_light_and_dark_themes.ts` | F08 | none |
| `apps/web/lib/features/f16_photo_quality_feedback.ts` | F16 | none |
| `apps/web/lib/features/f17_multi_part_enquiries.ts` | F17 | none |
| `apps/web/lib/features/f19_enquiry_history.ts` | F19 | none |
| `apps/web/lib/features/f29_evidence_page_viewer.ts` | F29 | none |
| `apps/web/lib/features/f31_candidate_comparison.ts` | F31 | none |
| `apps/web/lib/features/f35_stock_freshness.ts` | F35 | none |
| `apps/web/lib/features/f36_staff_inbox.ts` | F36 | none |
| `apps/web/lib/features/f38_correct_extracted_details.ts` | F38 | none |
| `apps/web/lib/features/f41_internal_notes.ts` | F41 | none |
| `apps/web/lib/features/f42_assignments.ts` | F42 | none |
| `apps/web/lib/features/f43_overdue_indicators.ts` | F43 | none |
| `apps/web/lib/features/f44_conversation_summary.ts` | F44 | none |
| `apps/web/lib/features/f55_saved_machines.ts` | F55 | none |
| `apps/web/lib/features/f56_repeat_enquiry.ts` | F56 | none |
| `apps/web/lib/features/f57_catalogue_browser.ts` | F57 | none |
| `apps/web/lib/features/f58_catalogue_imports.ts` | F58 | none |
| `apps/web/lib/features/f59_catalogue_versioning.ts` | F59 | none |
| `apps/web/lib/features/f60_missing_parts_queue.ts` | F60 | none |
| `apps/web/lib/features/f63_metrics_dashboard.ts` | F63 | none |
| `apps/web/lib/features/f65_correction_feedback.ts` | F65 | none |
| `apps/web/messages/ar.json` | F07 | none |
| `apps/web/messages/en.json` | F07 | none |
| `apps/web/next.config.ts` | 18 | F07 |
| `apps/web/package.json` | 18 | none |
| `apps/web/playwright.config.ts` | 18 | none |
| `apps/web/pnpm-lock.yaml` | 18 | none |
| `apps/web/postcss.config.mjs` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/Preview.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-1024.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-128.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-144.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-152.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-16.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-180.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-192.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-24.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-256.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-32.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-384.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-48.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-512.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-64.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-transparent-96.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-1024.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-128.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-144.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-152.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-16.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-180.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-192.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-24.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-256.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-32.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-384.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-48.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-512.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-64.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/icons/partsiq-icon-white-96.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-1280.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-1740.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-320.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-transparent-640.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-1280.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-1740.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-320.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/logos/partsiq-logo-white-640.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-hdpi-72.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-mdpi-48.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xhdpi-96.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xxhdpi-144.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/android-launcher-xxxhdpi-192.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/google-play-512.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/mobile/ios-app-store-1024.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/social/partsiq-og-1200x630.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/social/partsiq-profile-1080.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/source/original-logo.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/source/transparent-logo.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/android-chrome-192x192.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/android-chrome-512x512.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/apple-touch-icon.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-16x16.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-32x32.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-48x48.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon-96x96.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/favicon.ico` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/maskable-icon-192x192.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/maskable-icon-512x512.png` | 18 | none |
| `apps/web/public/brand/assets/PartsIQ-Asset-Pack/web/site.webmanifest` | 18 | none |
| `apps/web/public/brand/fonts/NotoNaskhArabic-OFL.txt` | 18 | none |
| `apps/web/public/brand/fonts/NotoNaskhArabic.ttf` | 18 | none |
| `apps/web/public/brand/fonts/NotoSans-OFL.txt` | 18 | none |
| `apps/web/public/brand/fonts/NotoSans.ttf` | 18 | none |
| `apps/web/public/brand/fonts/NotoSansArabic-OFL.txt` | 18 | none |
| `apps/web/public/brand/fonts/NotoSansArabic.ttf` | 18 | none |
| `apps/web/public/brand/logo-original.png` | 18 | none |
| `apps/web/styles/tokens.css` | 18 | F06, F08 |
| `apps/web/tests/features/f01.test.tsx` | 18 | none |
| `apps/web/tests/features/f06.test.tsx` | F06 | none |
| `apps/web/tests/features/f07.test.tsx` | F07 | none |
| `apps/web/tests/features/f08.test.tsx` | F08 | none |
| `apps/web/tests/features/f15.test.tsx` | 19 | none |
| `apps/web/tests/features/f18.test.tsx` | 20 | none |
| `apps/web/tests/features/f27.test.tsx` | 20 | none |
| `apps/web/tests/features/f31.test.tsx` | F31 | none |
| `apps/web/tests/features/f37.test.tsx` | 20 | none |
| `apps/web/tests/features/f53.test.tsx` | 22 | none |
| `apps/web/tests/setup.ts` | 18 | none |
| `apps/web/tsconfig.json` | 18 | none |
| `apps/web/vitest.config.ts` | 18 | none |
| `data/.gitkeep` | 00 | none |
| `db/migrations/001_initial_schema.sql` | 00 | none |
| `db/migrations/002_search_and_fulfilment.sql` | 00 | none |
| `docker-compose.prod.yml` | 24 | none |
| `docker-compose.yml` | 00 | none |
| `docs/DEMO_SCRIPT.md` | F69 | none |
| `docs/RECORDING_CHECKLIST.md` | F69 | none |
| `docs/RECRUITER_GUIDE.md` | F68 | none |
| `infra/ec2/bootstrap.sh` | 26 | none |
| `infra/ec2/deploy.sh` | 26 | none |
| `infra/ec2/preflight.py` | 26 | none |
| `infra/ec2/rollback.sh` | 26 | none |
| `infra/images.lock.json` | 24 | none |
| `infra/vercel/README.md` | 27 | none |
| `infra/verify_images.py` | 24 | none |
| `libs/partsiq_common/partsiq_common/__init__.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/ai/__init__.py` | 01 | none |
| `libs/partsiq_common/partsiq_common/ai/budget.py` | 01 | 23 |
| `libs/partsiq_common/partsiq_common/ai/client.py` | 01 | 23 |
| `libs/partsiq_common/partsiq_common/ai/prices.json` | 01 | none |
| `libs/partsiq_common/partsiq_common/app_factory.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/audit.py` | 01 | none |
| `libs/partsiq_common/partsiq_common/config.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/contracts.py` | 01 | none |
| `libs/partsiq_common/partsiq_common/db.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/embeddings.py` | 00 | 06 |
| `libs/partsiq_common/partsiq_common/errors.py` | 01 | none |
| `libs/partsiq_common/partsiq_common/health.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/logging.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/middleware.py` | 00 | none |
| `libs/partsiq_common/partsiq_common/security_context.py` | 01 | none |
| `libs/partsiq_common/partsiq_common/telemetry.py` | 01 | 23 |
| `libs/partsiq_common/partsiq_common/text.py` | 00 | none |
| `libs/partsiq_common/pyproject.toml` | 00 | none |
| `pyproject.toml` | 00 | none |
| `services/gateway/Dockerfile` | 00 | 24 |
| `services/gateway/app/__init__.py` | 00 | none |
| `services/gateway/app/api_v1.py` | 08 | F19, F29, F36, F41, F42, F43, F55, F56, F57, F60, F63, F65, F58, F59, F38, F44, 16 |
| `services/gateway/app/auth.py` | 07 | none |
| `services/gateway/app/config.py` | 00 | none |
| `services/gateway/app/demo.py` | 07 | none |
| `services/gateway/app/enquiries.py` | 08 | none |
| `services/gateway/app/features/__init__.py` | F19 | none |
| `services/gateway/app/features/f19_enquiry_history.py` | F19 | none |
| `services/gateway/app/features/f29_evidence_page_viewer.py` | F29 | none |
| `services/gateway/app/features/f36_staff_inbox.py` | F36 | none |
| `services/gateway/app/features/f38_correction_routes.py` | F38 | none |
| `services/gateway/app/features/f41_internal_notes.py` | F41 | none |
| `services/gateway/app/features/f42_assignments.py` | F42 | none |
| `services/gateway/app/features/f43_overdue_indicators.py` | F43 | none |
| `services/gateway/app/features/f44_summary_routes.py` | F44 | none |
| `services/gateway/app/features/f55_saved_machines.py` | F55 | none |
| `services/gateway/app/features/f56_repeat_enquiry.py` | F56 | none |
| `services/gateway/app/features/f57_catalogue_browser.py` | F57 | none |
| `services/gateway/app/features/f58_import_routes.py` | F58 | none |
| `services/gateway/app/features/f59_publish_routes.py` | F59 | none |
| `services/gateway/app/features/f60_missing_parts_queue.py` | F60 | none |
| `services/gateway/app/features/f63_metrics_dashboard.py` | F63 | none |
| `services/gateway/app/features/f65_correction_feedback.py` | F65 | none |
| `services/gateway/app/main.py` | 00 | 07, 08 |
| `services/gateway/app/metrics.py` | 23 | none |
| `services/gateway/app/ocr_confirmation.py` | 16 | none |
| `services/gateway/app/permissions.py` | 07 | none |
| `services/gateway/app/proxy.py` | 00 | 08 |
| `services/gateway/app/rate_limit.py` | 00 | 08 |
| `services/gateway/app/routes.py` | 00 | 07 |
| `services/gateway/app/routing.py` | 00 | none |
| `services/gateway/app/security.py` | 00 | 07 |
| `services/gateway/app/storage.py` | 04 | none |
| `services/gateway/app/uploads.py` | 08 | none |
| `services/gateway/pytest.ini` | 00 | none |
| `services/gateway/requirements-dev.txt` | 00 | none |
| `services/gateway/requirements.txt` | 00 | none |
| `services/gateway/tests/__init__.py` | 00 | none |
| `services/gateway/tests/features/test_f03.py` | 20 | none |
| `services/gateway/tests/features/test_f04.py` | 22 | none |
| `services/gateway/tests/features/test_f05.py` | 19 | none |
| `services/gateway/tests/features/test_f13.py` | 19 | none |
| `services/gateway/tests/features/test_f19.py` | F19 | none |
| `services/gateway/tests/features/test_f29.py` | F29 | none |
| `services/gateway/tests/features/test_f36.py` | F36 | none |
| `services/gateway/tests/features/test_f41.py` | F41 | none |
| `services/gateway/tests/features/test_f42.py` | F42 | none |
| `services/gateway/tests/features/test_f43.py` | F43 | none |
| `services/gateway/tests/features/test_f54.py` | 22 | none |
| `services/gateway/tests/features/test_f55.py` | F55 | none |
| `services/gateway/tests/features/test_f56.py` | F56 | none |
| `services/gateway/tests/features/test_f57.py` | F57 | none |
| `services/gateway/tests/features/test_f60.py` | F60 | none |
| `services/gateway/tests/features/test_f63.py` | F63 | none |
| `services/gateway/tests/features/test_f65.py` | F65 | none |
| `services/gateway/tests/test_routing.py` | 00 | none |
| `services/gateway/tests/test_security.py` | 00 | none |
| `services/orchestrator/Dockerfile` | 24 | none |
| `services/orchestrator/app/__init__.py` | 09 | none |
| `services/orchestrator/app/approval.py` | 14 | F35 |
| `services/orchestrator/app/controller.py` | 09 | none |
| `services/orchestrator/app/events.py` | 09 | none |
| `services/orchestrator/app/features/__init__.py` | F17 | none |
| `services/orchestrator/app/features/f17_multi_part_enquiries.py` | F17 | none |
| `services/orchestrator/app/features/f38_correct_extracted_details.py` | F38 | none |
| `services/orchestrator/app/features/f44_conversation_summary.py` | F44 | none |
| `services/orchestrator/app/features/f48_input_isolation.py` | F48 | none |
| `services/orchestrator/app/graph.py` | 09 | 10, 11, 12, 13, 14 |
| `services/orchestrator/app/handlers.py` | 09 | 10, 11, 12, 13, 14, F17, F38, F44, F48 |
| `services/orchestrator/app/main.py` | 09 | none |
| `services/orchestrator/app/prompts/intake.txt` | 10 | none |
| `services/orchestrator/app/prompts/reply.txt` | 13 | none |
| `services/orchestrator/app/rendering.py` | 13 | none |
| `services/orchestrator/app/revisions.py` | 14 | none |
| `services/orchestrator/app/routes.py` | 09 | F17, F38, F44, F48 |
| `services/orchestrator/app/runner.py` | 09 | none |
| `services/orchestrator/app/search_client.py` | 11 | none |
| `services/orchestrator/app/specialists/__init__.py` | 10 | none |
| `services/orchestrator/app/specialists/intake.py` | 10 | none |
| `services/orchestrator/app/specialists/parts.py` | 11 | none |
| `services/orchestrator/app/specialists/reply.py` | 13 | none |
| `services/orchestrator/app/state.py` | 09 | none |
| `services/orchestrator/app/tools.py` | 11 | none |
| `services/orchestrator/app/verification.py` | 12 | none |
| `services/orchestrator/pyproject.toml` | 00 | none |
| `services/orchestrator/tests/features/test_f09.py` | 19 | none |
| `services/orchestrator/tests/features/test_f10.py` | 10 | none |
| `services/orchestrator/tests/features/test_f11.py` | 19 | none |
| `services/orchestrator/tests/features/test_f12.py` | 09 | none |
| `services/orchestrator/tests/features/test_f17.py` | F17 | none |
| `services/orchestrator/tests/features/test_f26.py` | 11 | none |
| `services/orchestrator/tests/features/test_f38.py` | F38 | none |
| `services/orchestrator/tests/features/test_f39.py` | 20 | none |
| `services/orchestrator/tests/features/test_f40.py` | 14 | none |
| `services/orchestrator/tests/features/test_f44.py` | F44 | none |
| `services/orchestrator/tests/features/test_f45.py` | 13 | none |
| `services/orchestrator/tests/features/test_f46.py` | 12 | none |
| `services/orchestrator/tests/features/test_f47.py` | 14 | none |
| `services/orchestrator/tests/features/test_f48.py` | F48 | none |
| `services/orchestrator/tests/features/test_f50.py` | 09 | none |
| `services/search/Dockerfile` | 00 | 06, 24 |
| `services/search/app/__init__.py` | 00 | none |
| `services/search/app/config.py` | 00 | 06 |
| `services/search/app/embedding_ingestion.py` | 06 | none |
| `services/search/app/features/__init__.py` | F35 | none |
| `services/search/app/features/f35_stock_freshness.py` | F35 | none |
| `services/search/app/fulfilment.py` | 00 | none |
| `services/search/app/identification.py` | 00 | none |
| `services/search/app/lexical.py` | 00 | none |
| `services/search/app/main.py` | 00 | 06 |
| `services/search/app/repository.py` | 00 | 06 |
| `services/search/app/routes.py` | 00 | 06, F35 |
| `services/search/app/schemas.py` | 00 | 06 |
| `services/search/app/service.py` | 00 | 06 |
| `services/search/pytest.ini` | 00 | none |
| `services/search/requirements-dev.txt` | 00 | none |
| `services/search/requirements-embeddings.txt` | 00 | none |
| `services/search/requirements.txt` | 00 | none |
| `services/search/tests/__init__.py` | 00 | none |
| `services/search/tests/features/test_f20.py` | 06 | none |
| `services/search/tests/features/test_f21.py` | 06 | none |
| `services/search/tests/features/test_f22.py` | 06 | none |
| `services/search/tests/features/test_f23.py` | 06 | none |
| `services/search/tests/features/test_f24.py` | 06 | none |
| `services/search/tests/features/test_f25.py` | 06 | none |
| `services/search/tests/features/test_f28.py` | 12 | none |
| `services/search/tests/features/test_f30.py` | 06 | none |
| `services/search/tests/features/test_f32.py` | 20 | none |
| `services/search/tests/features/test_f33.py` | 06 | none |
| `services/search/tests/features/test_f34.py` | 06 | none |
| `services/search/tests/features/test_f35.py` | F35 | none |
| `services/search/tests/test_characterization.py` | 06 | none |
| `services/search/tests/test_fulfilment.py` | 00 | none |
| `services/search/tests/test_identification.py` | 00 | none |
| `services/search/tests/test_lexical.py` | 00 | none |
| `services/search/tests/test_text.py` | 00 | none |
| `services/worker/Dockerfile` | 24 | none |
| `services/worker/app/__init__.py` | 04 | none |
| `services/worker/app/dispatcher.py` | 15 | 16, 17, F16, F58, F59 |
| `services/worker/app/features/__init__.py` | F16 | none |
| `services/worker/app/features/f16_photo_quality_feedback.py` | F16 | none |
| `services/worker/app/features/f58_catalogue_imports.py` | F58 | none |
| `services/worker/app/internal.py` | 15 | none |
| `services/worker/app/jobs/__init__.py` | 16 | none |
| `services/worker/app/jobs/catalog_publish.py` | F59 | none |
| `services/worker/app/jobs/export_pdf.py` | 17 | none |
| `services/worker/app/jobs/nameplate.py` | 16 | none |
| `services/worker/app/leases.py` | 15 | none |
| `services/worker/app/main.py` | 15 | none |
| `services/worker/app/static/brand/fonts/NotoNaskhArabic-OFL.txt` | 17 | none |
| `services/worker/app/static/brand/fonts/NotoNaskhArabic.ttf` | 17 | none |
| `services/worker/app/static/brand/fonts/NotoSans-OFL.txt` | 17 | none |
| `services/worker/app/static/brand/fonts/NotoSans.ttf` | 17 | none |
| `services/worker/app/static/brand/fonts/NotoSansArabic-OFL.txt` | 17 | none |
| `services/worker/app/static/brand/fonts/NotoSansArabic.ttf` | 17 | none |
| `services/worker/app/static/brand/logo-original.png` | 17 | none |
| `services/worker/app/storage.py` | 04 | none |
| `services/worker/app/sweeper.py` | 15 | none |
| `services/worker/app/templates/enquiry_summary.html` | 17 | none |
| `services/worker/pyproject.toml` | 00 | none |
| `services/worker/tests/features/test_f14.py` | 16 | none |
| `services/worker/tests/features/test_f16.py` | F16 | none |
| `services/worker/tests/features/test_f51.py` | 15 | none |
| `services/worker/tests/features/test_f52.py` | 15 | none |
| `services/worker/tests/features/test_f58.py` | F58 | none |
| `services/worker/tests/features/test_f61.py` | 20 | none |
| `supabase/config.toml` | 02 | none |
| `supabase/migrations/20261011000100_legacy_catalogue.sql` | 02 | none |
| `supabase/migrations/20261011000200_legacy_search.sql` | 02 | none |
| `supabase/migrations/20261011000300_application.sql` | 03 | none |
| `supabase/migrations/20261011000400_rls.sql` | 03 | none |
| `supabase/migrations/20261011000500_storage.sql` | 04 | none |
| `tests/acceptance/test_f02.py` | 19 | none |
| `tests/acceptance/test_f49.py` | 14 | none |
| `tests/acceptance/test_f59.py` | F59 | none |
| `tests/acceptance/test_f62.py` | 21 | none |
| `tests/acceptance/test_f64.py` | 23 | none |
| `tests/acceptance/test_f66.py` | 25 | none |
| `tests/acceptance/test_f67.py` | 23 | none |
| `tests/acceptance/test_f68.py` | F68 | none |
| `tests/acceptance/test_f69.py` | F69 | none |
| `tests/e2e/hosted.spec.ts` | 27 | none |
| `tests/e2e/security.spec.ts` | 22 | none |
| `tests/evals/cases.json` | 21 | none |
| `tests/evals/test_scenarios.py` | 21 | none |
| `tests/foundations/test_00.py` | 00 | none |
| `tests/foundations/test_01.py` | 01 | none |
| `tests/foundations/test_02.py` | 02 | none |
| `tests/foundations/test_03.py` | 03 | none |
| `tests/foundations/test_04.py` | 04 | none |
| `tests/foundations/test_05.py` | 05 | none |
| `tests/foundations/test_06.py` | 06 | none |
| `tests/foundations/test_07.py` | 07 | none |
| `tests/foundations/test_08.py` | 08 | none |
| `tests/foundations/test_09.py` | 09 | none |
| `tests/foundations/test_10.py` | 10 | none |
| `tests/foundations/test_11.py` | 11 | none |
| `tests/foundations/test_12.py` | 12 | none |
| `tests/foundations/test_13.py` | 13 | none |
| `tests/foundations/test_14.py` | 14 | none |
| `tests/foundations/test_15.py` | 15 | none |
| `tests/foundations/test_16.py` | 16 | none |
| `tests/foundations/test_17.py` | 17 | none |
| `tests/foundations/test_18.py` | 18 | none |
| `tests/foundations/test_19.py` | 19 | none |
| `tests/foundations/test_20.py` | 20 | none |
| `tests/foundations/test_21.py` | 21 | none |
| `tests/foundations/test_22.py` | 22 | none |
| `tests/foundations/test_23.py` | 23 | none |
| `tests/foundations/test_24.py` | 24 | none |
| `tests/foundations/test_25.py` | 25 | none |
| `tests/foundations/test_26.py` | 26 | none |
| `tests/foundations/test_27.py` | 27 | none |
| `tests/integration/conftest.py` | 03 | none |
| `tests/integration/test_budget_races.py` | 22 | none |
| `tests/integration/test_rls.py` | 22 | none |
| `tests/integration/test_security_recovery.py` | 22 | none |
| `tools/apply_catalogue_schema.py` | 02 | none |
| `tools/catalog/Dockerfile` | 00 | none |
| `tools/catalog/__init__.py` | 00 | none |
| `tools/catalog/catalog/__init__.py` | 00 | none |
| `tools/catalog/catalog/__main__.py` | 00 | F59 |
| `tools/catalog/catalog/blueprint.py` | 00 | none |
| `tools/catalog/catalog/dataset.py` | 00 | none |
| `tools/catalog/catalog/embedder.py` | 00 | 06 |
| `tools/catalog/catalog/generator.py` | 00 | none |
| `tools/catalog/catalog/loader.py` | 00 | none |
| `tools/catalog/catalog/validator.py` | 00 | none |
| `tools/catalog/catalog/versioning.py` | F59 | none |
| `tools/catalog/pytest.ini` | 00 | none |
| `tools/catalog/requirements-embeddings.txt` | 00 | none |
| `tools/catalog/tests/__init__.py` | 00 | none |
| `tools/catalog/tests/test_catalog.py` | 00 | none |
| `tools/check_readiness.py` | 23 | none |
| `tools/check_release_eligibility.py` | 00 | none |
| `tools/checkpoints_setup.py` | 03 | none |
| `tools/ci_checks.py` | 25 | none |
| `tools/credit_allowance.py` | 23 | none |
| `tools/demo/build_scenarios.py` | 05 | none |
| `tools/demo/catalogue_evidence/manifest.json` | 05 | none |
| `tools/demo/nameplates/manifest.json` | 05 | none |
| `tools/demo/render_assets.py` | 05 | none |
| `tools/demo/scenarios.json` | 05 | none |
| `tools/demo/scenarios/incompatible_number.json` | 05 | none |
| `tools/demo/scenarios/local_shortage.json` | 05 | none |
| `tools/demo/scenarios/missing_serial.json` | 05 | none |
| `tools/demo/scenarios/mixed_photo.json` | 05 | none |
| `tools/evals/__init__.py` | 21 | none |
| `tools/evals/run.py` | 21 | none |
| `tools/hosted_acceptance.py` | 27 | none |
| `tools/run_checks.py` | 00 | none |
| `tools/schema_receipt.py` | 03 | none |
| `tools/verify_env.py` | 00 | none |
| `uv.lock` | 00 | none |

## 3. Exact dependency pins
Direct release dates were retrieved from official PyPI/npm registries on2026-10-11. Cutoff2026-09-26. Registry receipts include source URL,integrity and dependency requirements. Resolved references are not a claim of full application tests or a vulnerability-free system. Recheck security advisories before internet exposure; a required emergency patch newer than the cutoff needs an explicitly recorded exception.

| Package | Exact version | Release date | Installation owner | Registry evidence |
|---|---|---|---|---|
| fastapi | 0.135.1 | 2026-03-01 | 01 | https://pypi.org/pypi/fastapi/0.135.1/json |
| uvicorn | 0.41.0 | 2026-02-16 | 01 | https://pypi.org/pypi/uvicorn/0.41.0/json |
| pydantic | 2.12.5 | 2025-11-26 | 01 | https://pypi.org/pypi/pydantic/2.12.5/json |
| pydantic-settings | 2.13.1 | 2026-02-19 | 01 | https://pypi.org/pypi/pydantic-settings/2.13.1/json |
| httpx | 0.28.1 | 2024-12-06 | 01 | https://pypi.org/pypi/httpx/0.28.1/json |
| asyncpg | 0.31.0 | 2025-11-24 | 01 | https://pypi.org/pypi/asyncpg/0.31.0/json |
| psycopg | 3.3.3 | 2026-02-18 | 01 | https://pypi.org/pypi/psycopg/3.3.3/json |
| psycopg-pool | 3.3.0 | 2025-12-01 | 01 | https://pypi.org/pypi/psycopg-pool/3.3.0/json |
| langgraph | 1.1.3 | 2026-03-18 | 09 | https://pypi.org/pypi/langgraph/1.1.3/json |
| langgraph-checkpoint-postgres | 3.0.4 | 2026-01-31 | 09 | https://pypi.org/pypi/langgraph-checkpoint-postgres/3.0.4/json |
| redis | 7.3.0 | 2026-03-06 | 01 | https://pypi.org/pypi/redis/7.3.0/json |
| openai | 3.19.2 | 2026-09-24 | 01 | https://pypi.org/pypi/openai/3.19.2/json |
| structlog | 25.5.0 | 2025-10-27 | 01 | https://pypi.org/pypi/structlog/25.5.0/json |
| tenacity | 9.1.2 | 2025-04-02 | 01 | https://pypi.org/pypi/tenacity/9.1.2/json |
| PyJWT | 2.12.1 | 2026-03-13 | 01 | https://pypi.org/pypi/PyJWT/2.12.1/json |
| cryptography | 46.0.5 | 2026-02-10 | 01 | https://pypi.org/pypi/cryptography/46.0.5/json |
| sentence-transformers | 5.2.3 | 2026-02-17 | 06 | https://pypi.org/pypi/sentence-transformers/5.2.3/json |
| transformers | 4.57.6 | 2026-01-16 | 06 | https://pypi.org/pypi/transformers/4.57.6/json |
| torch | 2.10.0+cpu (base release2.10.0) | 2026-01-21 | 06 | https://pypi.org/pypi/torch/2.10.0/json |
| numpy | 2.4.2 | 2026-01-31 | 06 | https://pypi.org/pypi/numpy/2.4.2/json |
| Jinja2 | 3.1.6 | 2025-03-05 | 17 | https://pypi.org/pypi/Jinja2/3.1.6/json |
| Pillow | 12.1.1 | 2026-02-11 | 05 | https://pypi.org/pypi/Pillow/12.1.1/json |
| playwright | 1.58.0 | 2026-01-30 | 17 | https://pypi.org/pypi/playwright/1.58.0/json |
| openpyxl | 3.1.5 | 2024-06-28 | F58 | https://pypi.org/pypi/openpyxl/3.1.5/json |
| PyYAML | 6.0.3 | 2025-09-25 | 00 | https://pypi.org/pypi/PyYAML/6.0.3/json |
| pytest | 9.0.2 | 2025-12-06 | 00 | https://pypi.org/pypi/pytest/9.0.2/json |
| pytest-asyncio | 1.3.0 | 2025-11-10 | 00 | https://pypi.org/pypi/pytest-asyncio/1.3.0/json |
| ruff | 0.15.6 | 2026-03-12 | 00 | https://pypi.org/pypi/ruff/0.15.6/json |
| mypy | 1.19.1 | 2025-12-15 | 00 | https://pypi.org/pypi/mypy/1.19.1/json |
| uv | 0.10.9 | 2026-03-06 | 00 | https://pypi.org/pypi/uv/0.10.9/json |
| langfuse | 3.14.5 | 2026-02-23 | 23 | https://pypi.org/pypi/langfuse/3.14.5/json |
| python-docx | 1.2.0 | 2025-06-16 | F68 | https://pypi.org/pypi/python-docx/1.2.0/json |
| pypdf | 6.8.0 | 2026-03-09 | 17 | https://pypi.org/pypi/pypdf/6.8.0/json |
| python-multipart | 0.0.22 | 2026-01-25 | 01 | https://pypi.org/pypi/python-multipart/0.0.22/json |
| next | 16.2.12 | 2026-07-25 | 18 | https://registry.npmjs.org/next |
| react | 19.2.6 | 2026-05-06 | 18 | https://registry.npmjs.org/react |
| react-dom | 19.2.6 | 2026-05-06 | 18 | https://registry.npmjs.org/react-dom |
| typescript | 5.9.3 | 2025-09-30 | 18 | https://registry.npmjs.org/typescript |
| tailwindcss | 4.1.18 | 2025-12-11 | 18 | https://registry.npmjs.org/tailwindcss |
| @tailwindcss/postcss | 4.1.18 | 2025-12-11 | 18 | https://registry.npmjs.org/%40tailwindcss%2Fpostcss |
| postcss | 8.5.6 | 2025-06-16 | 18 | https://registry.npmjs.org/postcss |
| @supabase/supabase-js | 2.99.1 | 2026-03-11 | 18 | https://registry.npmjs.org/%40supabase%2Fsupabase-js |
| @supabase/ssr | 0.8.0 | 2025-11-26 | 18 | https://registry.npmjs.org/%40supabase%2Fssr |
| next-intl | 4.8.3 | 2026-02-16 | 18 | https://registry.npmjs.org/next-intl |
| zod | 4.6.5 | 2026-09-13 | 18 | https://registry.npmjs.org/zod |
| vitest | 4.1.11 | 2026-08-18 | 18 | https://registry.npmjs.org/vitest |
| @playwright/test | 1.58.2 | 2026-02-06 | 18 | https://registry.npmjs.org/%40playwright%2Ftest |
| eslint | 9.39.1 | 2025-11-03 | 18 | https://registry.npmjs.org/eslint |
| eslint-config-next | 16.2.12 | 2026-07-25 | 18 | https://registry.npmjs.org/eslint-config-next |
| @testing-library/react | 16.3.0 | 2025-04-02 | 18 | https://registry.npmjs.org/%40testing-library%2Freact |
| @testing-library/dom | 10.4.1 | 2025-07-27 | 18 | https://registry.npmjs.org/%40testing-library%2Fdom |
| @testing-library/jest-dom | 6.9.1 | 2025-10-01 | 18 | https://registry.npmjs.org/%40testing-library%2Fjest-dom |
| @testing-library/user-event | 14.6.1 | 2025-01-21 | 18 | https://registry.npmjs.org/%40testing-library%2Fuser-event |
| jsdom | 27.4.0 | 2025-12-26 | 18 | https://registry.npmjs.org/jsdom |
| @vitejs/plugin-react | 5.1.4 | 2026-02-10 | 18 | https://registry.npmjs.org/%40vitejs%2Fplugin-react |
| @types/react | 19.2.14 | 2026-02-11 | 18 | https://registry.npmjs.org/%40types%2Freact |
| @types/react-dom | 19.2.3 | 2025-11-12 | 18 | https://registry.npmjs.org/%40types%2Freact-dom |
| @types/node | 22.19.15 | 2026-03-06 | 18 | https://registry.npmjs.org/%40types%2Fnode |
| clsx | 2.1.1 | 2024-04-23 | 18 | https://registry.npmjs.org/clsx |
| tailwind-merge | 3.5.0 | 2026-02-18 | 18 | https://registry.npmjs.org/tailwind-merge |
| class-variance-authority | 0.7.1 | 2024-11-26 | 18 | https://registry.npmjs.org/class-variance-authority |
| lucide-react | 0.577.0 | 2026-03-04 | 18 | https://registry.npmjs.org/lucide-react |
| radix-ui | 1.4.3 | 2025-08-13 | 18 | https://registry.npmjs.org/radix-ui |
| shadcn | 4.20.1 | 2026-09-02 | 18 | https://registry.npmjs.org/shadcn |
| pnpm | 10.30.3 | 2026-02-26 | 18 | https://registry.npmjs.org/pnpm |
| supabase | 2.75.0 | 2026-02-02 | 02 | https://registry.npmjs.org/supabase |

Infrastructure and GitHub action SHAs are in spec/infrastructure-receipts.json. Python base3.12.12 and Node22.22.0 must use immutable image manifests recorded by prompt24. BGE-M3 revision is immutable; model weights are downloaded only in the search image. Managed Supabase PostgreSQL/extension versions are collected from the actual project by schema receipt rather than falsely fixed by this kit.

## 4. Exact data model and policies
The following SQL is authoritative for all48 application-owned tables,columns,constraints,indexes,triggers,grants and RLS policies. It preserves legacy names and extends them. auth.users,storage.buckets and storage.objects are Supabase-managed. The four LangGraph checkpoint tables have exact extracted DDL below; prompt03 runs pinned library setup in autocommit mode and then applies explicit checkpoint RLS/grants. Application routes never create those library tables ad hoc.

Gateway identity is transaction-local app.actor_id,set only after JWT verification. Private policy helper functions run as their migration owner with fixed search_path and PUBLIC execution revoked; untrusted browser roles have no application-table grants. Internal worker/orchestrator roles have system access to the tables they own; application handlers still fence revision/session/lease. Runtime credentials are not database owners and have no BYPASSRLS.

JSON fields use schemas in spec/contracts.py: extraction=IntakeResult,revision snapshot=ApprovedSnapshot or preapproval EnquiryState,candidate reasons=array of strings,plan allocations=array of Allocation,stock snapshot=array of StockEvidence,draft prose=ReplySlots,verified_facts=VerifiedFacts,verification failures=array of VerificationFailure. Import payload uses legacy CatalogDataset entity records. Job payload fields are checked against kind before dispatch. Audit payload is bounded/redacted. No JSON blob is permission to invent critical fields.

### 001_initial_schema.sql

```sql
-- PartsIQ initial schema.
-- Executed automatically by the postgres container on first initialisation (empty data volume).
-- Design principle: the database is the single source of truth for part compatibility.
-- AI components may rank and describe candidates, but never decide whether a part fits a machine.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------------------
-- Shared trigger functions
-- ---------------------------------------------------------------------------

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Equipment catalogue
-- ---------------------------------------------------------------------------

CREATE TABLE equipment_families (
    id          SMALLSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{2,32}$'),
    name_en     TEXT NOT NULL,
    name_ar     TEXT NOT NULL
);

CREATE TABLE equipment_models (
    id            SERIAL PRIMARY KEY,
    family_id     SMALLINT NOT NULL REFERENCES equipment_families (id),
    brand         TEXT NOT NULL,
    model_code    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    rated_output  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand, model_code)
);

CREATE INDEX equipment_models_model_code_trgm_idx
    ON equipment_models USING gin (model_code gin_trgm_ops);

-- A configuration is a serial-number range of a model that shares one bill of materials.
-- Overlapping ranges for the same model are rejected so serial lookup is always unambiguous.
CREATE TABLE model_configurations (
    id            SERIAL PRIMARY KEY,
    model_id      INTEGER NOT NULL REFERENCES equipment_models (id) ON DELETE CASCADE,
    config_code   TEXT NOT NULL,
    description   TEXT NOT NULL,
    serial_start  BIGINT NOT NULL CHECK (serial_start >= 0),
    serial_end    BIGINT NOT NULL,
    CHECK (serial_start <= serial_end),
    UNIQUE (model_id, config_code),
    EXCLUDE USING gist (
        model_id WITH =,
        int8range(serial_start, serial_end, '[]') WITH &&
    )
);

-- ---------------------------------------------------------------------------
-- Parts
-- ---------------------------------------------------------------------------

CREATE TABLE parts (
    id               SERIAL PRIMARY KEY,
    part_number      TEXT NOT NULL UNIQUE,
    name_en          TEXT NOT NULL,
    name_ar          TEXT NOT NULL,
    description_en   TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL,
    unit_of_measure  TEXT NOT NULL DEFAULT 'EA',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_document  TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'simple'::regconfig,
            part_number || ' ' || name_en || ' ' || name_ar || ' ' || description_en
        )
    ) STORED
);

CREATE INDEX parts_search_document_idx ON parts USING gin (search_document);
CREATE INDEX parts_part_number_trgm_idx ON parts USING gin (part_number gin_trgm_ops);
CREATE INDEX parts_category_idx ON parts (category);

CREATE TRIGGER parts_set_updated_at
    BEFORE UPDATE ON parts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Informal names used by customers and staff, e.g. "black filter" or Arabic colloquial terms.
CREATE TABLE part_aliases (
    id        SERIAL PRIMARY KEY,
    part_id   INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    language  TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    UNIQUE (part_id, alias)
);

CREATE INDEX part_aliases_alias_trgm_idx ON part_aliases USING gin (alias gin_trgm_ops);

-- Embeddings are stored separately so the embedding model can be replaced without altering parts.
-- Dimension 1024 matches multilingual models such as BGE-M3, which support Arabic and English.
CREATE TABLE part_embeddings (
    part_id      INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    model_name   TEXT NOT NULL,
    source_text  TEXT NOT NULL,
    embedding    VECTOR(1024) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, model_name)
);

CREATE INDEX part_embeddings_hnsw_idx
    ON part_embeddings USING hnsw (embedding vector_cosine_ops);

-- The authoritative compatibility matrix. Every row must cite the document it was derived from.
CREATE TABLE part_compatibility (
    part_id            INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    configuration_id   INTEGER NOT NULL REFERENCES model_configurations (id) ON DELETE CASCADE,
    quantity_per_unit  NUMERIC(10, 3) NOT NULL DEFAULT 1 CHECK (quantity_per_unit > 0),
    source_reference   TEXT NOT NULL,
    notes              TEXT,
    PRIMARY KEY (part_id, configuration_id)
);

CREATE INDEX part_compatibility_configuration_idx ON part_compatibility (configuration_id);

-- Each superseded part has exactly one direct successor; chains are resolved by recursive query.
CREATE TABLE part_supersessions (
    old_part_id     INTEGER PRIMARY KEY REFERENCES parts (id) ON DELETE CASCADE,
    new_part_id     INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    effective_date  DATE NOT NULL,
    reason          TEXT,
    CHECK (old_part_id <> new_part_id)
);

CREATE INDEX part_supersessions_new_part_idx ON part_supersessions (new_part_id);

CREATE FUNCTION prevent_supersession_cycle() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        WITH RECURSIVE chain (part_id) AS (
            SELECT NEW.new_part_id
            UNION
            SELECT s.new_part_id
            FROM part_supersessions AS s
            JOIN chain AS c ON s.old_part_id = c.part_id
            WHERE s.old_part_id <> NEW.old_part_id
        )
        SELECT 1 FROM chain WHERE part_id = NEW.old_part_id
    ) THEN
        RAISE EXCEPTION 'Supersession % -> % would create a cycle', NEW.old_part_id, NEW.new_part_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER part_supersessions_no_cycles
    BEFORE INSERT OR UPDATE ON part_supersessions
    FOR EACH ROW EXECUTE FUNCTION prevent_supersession_cycle();

-- ---------------------------------------------------------------------------
-- Inventory
-- ---------------------------------------------------------------------------

CREATE TABLE warehouses (
    id      SMALLSERIAL PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_]{2,16}$'),
    name    TEXT NOT NULL,
    region  TEXT NOT NULL
);

CREATE TABLE stock_levels (
    part_id            INTEGER NOT NULL REFERENCES parts (id) ON DELETE CASCADE,
    warehouse_id       SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    quantity_on_hand   INTEGER NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    quantity_reserved  INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, warehouse_id),
    CHECK (quantity_reserved <= quantity_on_hand)
);

CREATE TRIGGER stock_levels_set_updated_at
    BEFORE UPDATE ON stock_levels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Enquiry workflow
-- ---------------------------------------------------------------------------

CREATE TYPE enquiry_status AS ENUM (
    'received',
    'processing',
    'needs_information',
    'awaiting_review',
    'approved',
    'rejected',
    'failed'
);

CREATE TABLE enquiries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel             TEXT NOT NULL CHECK (channel IN ('chat', 'email', 'staff')),
    customer_reference  TEXT,
    raw_text            TEXT NOT NULL,
    detected_language   TEXT CHECK (detected_language IN ('en', 'ar', 'mixed')),
    extracted           JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration_id    INTEGER REFERENCES model_configurations (id),
    status              enquiry_status NOT NULL DEFAULT 'received',
    failure_reason      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX enquiries_status_created_idx ON enquiries (status, created_at DESC);

CREATE TRIGGER enquiries_set_updated_at
    BEFORE UPDATE ON enquiries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE enquiry_attachments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enquiry_id   UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    storage_key  TEXT NOT NULL UNIQUE,
    media_type   TEXT NOT NULL CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes   INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX enquiry_attachments_enquiry_idx ON enquiry_attachments (enquiry_id);

CREATE TABLE enquiry_candidates (
    enquiry_id     UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    rank           SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 10),
    part_id        INTEGER NOT NULL REFERENCES parts (id),
    score          NUMERIC(6, 5) NOT NULL CHECK (score >= 0 AND score <= 1),
    match_reasons  JSONB NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (enquiry_id, rank),
    UNIQUE (enquiry_id, part_id)
);

CREATE TABLE review_decisions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enquiry_id   UUID NOT NULL REFERENCES enquiries (id) ON DELETE CASCADE,
    reviewer     TEXT NOT NULL,
    decision     TEXT NOT NULL CHECK (decision IN ('approved', 'edited', 'rejected')),
    final_reply  TEXT,
    comment      TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (decision = 'rejected' OR final_reply IS NOT NULL)
);

CREATE INDEX review_decisions_enquiry_idx ON review_decisions (enquiry_id, decided_at DESC);

CREATE TABLE review_approved_parts (
    decision_id  UUID NOT NULL REFERENCES review_decisions (id) ON DELETE CASCADE,
    part_id      INTEGER NOT NULL REFERENCES parts (id),
    quantity     NUMERIC(10, 3) NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (decision_id, part_id)
);

-- ---------------------------------------------------------------------------
-- Append-only audit trail
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type   TEXT NOT NULL CHECK (actor_type IN ('system', 'ai', 'user')),
    actor_id     TEXT NOT NULL,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    request_id   TEXT,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id, occurred_at DESC);

CREATE FUNCTION prevent_audit_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_mutation();

COMMIT;
```

### 002_search_and_fulfilment.sql

```sql
-- Search and fulfilment support.

BEGIN;

-- Canonical part-number key so that "vp of 1042", "VP-OF-1042" and "VPOF1042" all match.
-- Must remain consistent with partsiq_common.text.part_number_key.
ALTER TABLE parts
    ADD COLUMN part_number_key TEXT GENERATED ALWAYS AS (
        upper(regexp_replace(part_number, '[^A-Za-z0-9]', '', 'g'))
    ) STORED;

CREATE INDEX parts_part_number_key_idx ON parts (part_number_key);

-- Planned transfer lead times between warehouses, used to recommend where to fulfil from.
CREATE TABLE warehouse_transfer_routes (
    from_warehouse_id  SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    to_warehouse_id    SMALLINT NOT NULL REFERENCES warehouses (id) ON DELETE CASCADE,
    transfer_days      SMALLINT NOT NULL CHECK (transfer_days BETWEEN 1 AND 60),
    PRIMARY KEY (from_warehouse_id, to_warehouse_id),
    CHECK (from_warehouse_id <> to_warehouse_id)
);

COMMIT;
```

### 003_application.sql

```sql
-- Additive application schema. Apply after immutable legacy migrations 001 and 002.
BEGIN;
CREATE SCHEMA IF NOT EXISTS app_private;
REVOKE ALL ON SCHEMA app_private FROM PUBLIC;
CREATE TABLE profiles (
 id uuid PRIMARY KEY REFERENCES auth.users(id),
 display_name text NOT NULL CHECK(length(display_name) BETWEEN 1 AND 120),
 preferred_locale text NOT NULL DEFAULT 'en' CHECK(preferred_locale IN ('en','ar')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE staff_roles (
 user_id uuid NOT NULL REFERENCES profiles(id),
 role text NOT NULL CHECK(role IN ('reviewer','catalogue_admin','admin')),
 granted_by uuid REFERENCES profiles(id),
 granted_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,role)
);
CREATE TABLE demo_sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL REFERENCES profiles(id),
 generation integer NOT NULL DEFAULT 1 CHECK(generation>0),
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(expires_at>created_at)
);
CREATE INDEX demo_sessions_owner_idx ON demo_sessions(owner_id,expires_at DESC);
CREATE TABLE catalogue_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 label text NOT NULL UNIQUE,
 state text NOT NULL CHECK(state IN ('staging','published','retired')),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 created_by uuid REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 CHECK((state='staging' AND published_at IS NULL) OR (state IN ('published','retired') AND published_at IS NOT NULL))
);
CREATE UNIQUE INDEX catalogue_one_published_idx ON catalogue_versions((state)) WHERE state='published';
CREATE TABLE catalogue_records (
 version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 entity_type text NOT NULL CHECK(entity_type IN ('equipment_families','equipment_models','model_configurations','parts','part_aliases','part_compatibility','part_supersessions','warehouses','warehouse_transfer_routes')),
 entity_key text NOT NULL,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 PRIMARY KEY(version_id,entity_type,entity_key)
);
CREATE TABLE catalogue_evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 source_reference text NOT NULL CHECK(length(trim(source_reference))>0),
 storage_key text NOT NULL,
 page_number integer NOT NULL CHECK(page_number>0),
 sha256 text NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'),
 synthetic boolean NOT NULL DEFAULT true,
 UNIQUE(version_id,source_reference)
);
ALTER TABLE part_compatibility ADD CONSTRAINT compatibility_nonempty_source CHECK(length(trim(source_reference))>0);
ALTER TABLE part_embeddings ADD COLUMN model_revision text;
ALTER TABLE part_embeddings ADD COLUMN source_sha256 text;
ALTER TABLE enquiries ADD COLUMN owner_id uuid REFERENCES profiles(id);
ALTER TABLE enquiries ADD COLUMN session_id uuid REFERENCES demo_sessions(id);
ALTER TABLE enquiries ADD COLUMN session_generation integer;
ALTER TABLE enquiries ADD COLUMN revision integer NOT NULL DEFAULT 1 CHECK(revision>0);
ALTER TABLE enquiries ADD COLUMN catalogue_version_id uuid REFERENCES catalogue_versions(id);
ALTER TABLE enquiries ADD COLUMN destination_warehouse_id smallint REFERENCES warehouses(id);
ALTER TABLE enquiries ADD COLUMN assigned_to uuid REFERENCES profiles(id);
ALTER TABLE enquiries ADD COLUMN priority text NOT NULL DEFAULT 'normal' CHECK(priority IN ('normal','urgent'));
ALTER TABLE enquiries ADD COLUMN due_at timestamptz;
ALTER TABLE enquiries ADD COLUMN idempotency_key uuid;
ALTER TABLE enquiries ADD CONSTRAINT enquiry_demo_pair CHECK((session_id IS NULL AND session_generation IS NULL) OR (session_id IS NOT NULL AND session_generation>0));
CREATE UNIQUE INDEX enquiries_owner_idempotency_idx ON enquiries(owner_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX enquiries_owner_created_idx ON enquiries(owner_id,created_at DESC,id);
CREATE INDEX enquiries_assigned_status_idx ON enquiries(assigned_to,status,created_at DESC,id);
CREATE INDEX enquiries_demo_idx ON enquiries(session_id,session_generation);
CREATE TABLE enquiry_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 20),
 requested_text text NOT NULL CHECK(length(trim(requested_text))>0),
 quantity numeric(10,3) NOT NULL CHECK(quantity>0 AND quantity<=100000),
 model_text text,
 serial_text text,
 configuration_id integer REFERENCES model_configurations(id),
 selected_part_id integer REFERENCES parts(id),
 status text NOT NULL DEFAULT 'unresolved' CHECK(status IN ('unresolved','needs_information','ready','unavailable')),
 revision integer NOT NULL CHECK(revision>0),
 UNIQUE(enquiry_id,ordinal),
 UNIQUE(enquiry_id,id)
);
ALTER TABLE enquiry_candidates ADD COLUMN item_id uuid;
ALTER TABLE enquiry_candidates ADD COLUMN revision integer NOT NULL DEFAULT 1;
ALTER TABLE enquiry_candidates ADD COLUMN catalogue_version_id uuid REFERENCES catalogue_versions(id);
ALTER TABLE enquiry_candidates ADD COLUMN evidence_id uuid REFERENCES catalogue_evidence(id);
ALTER TABLE enquiry_candidates DROP CONSTRAINT enquiry_candidates_pkey;
ALTER TABLE enquiry_candidates DROP CONSTRAINT enquiry_candidates_enquiry_id_part_id_key;
-- Historical rows receive a legacy item before the new per-item keys are enforced.
INSERT INTO enquiry_items(enquiry_id,ordinal,requested_text,quantity,revision)
 SELECT id,1,CASE WHEN length(trim(raw_text))>0 THEN raw_text ELSE 'Historical enquiry' END,1,revision FROM enquiries;
UPDATE enquiry_candidates c SET item_id=i.id FROM enquiry_items i WHERE i.enquiry_id=c.enquiry_id AND i.ordinal=1;
ALTER TABLE enquiry_candidates ALTER COLUMN item_id SET NOT NULL;
ALTER TABLE enquiry_candidates ADD CONSTRAINT candidate_item_fk FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id);
ALTER TABLE enquiry_candidates ADD PRIMARY KEY(item_id,revision,rank);
ALTER TABLE enquiry_candidates ADD UNIQUE(item_id,revision,part_id);
ALTER TABLE enquiry_attachments ADD COLUMN status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','validated','rejected','deleted'));
ALTER TABLE enquiry_attachments ADD COLUMN sha256 text;
ALTER TABLE enquiry_attachments ADD COLUMN revision integer NOT NULL DEFAULT 1;
CREATE TABLE messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK(revision>0),
 kind text NOT NULL CHECK(kind IN ('customer','clarification','status','recommendation')),
 body text NOT NULL CHECK(length(body) BETWEEN 1 AND 12000),
 author_id uuid REFERENCES profiles(id),
 decision_id uuid REFERENCES review_decisions(id),
 idempotency_key uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,idempotency_key),
 CHECK((kind='recommendation' AND decision_id IS NOT NULL) OR (kind<>'recommendation' AND decision_id IS NULL))
);
CREATE UNIQUE INDEX messages_one_publication_idx ON messages(enquiry_id,revision) WHERE kind='recommendation';
CREATE INDEX messages_enquiry_created_idx ON messages(enquiry_id,created_at,id);
CREATE TABLE enquiry_revisions (
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL CHECK(revision>0),
 snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'),
 changed_by uuid REFERENCES profiles(id),
 reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(enquiry_id,revision)
);
CREATE TABLE extractions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 attachment_id uuid REFERENCES enquiry_attachments(id),
 revision integer NOT NULL,
 model_text text,
 serial_text text,
 issues jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(issues)='array'),
 confirmed_by uuid REFERENCES profiles(id),
 confirmed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((confirmed_by IS NULL)=(confirmed_at IS NULL))
);
CREATE INDEX extractions_enquiry_idx ON extractions(enquiry_id,revision);
CREATE TABLE fulfilment_plans (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 item_id uuid NOT NULL,
 requested_quantity numeric(10,3) NOT NULL CHECK(requested_quantity>0),
 allocations jsonb NOT NULL CHECK(jsonb_typeof(allocations)='array'),
 shortage numeric(10,3) NOT NULL CHECK(shortage>=0),
 stock_snapshot jsonb NOT NULL CHECK(jsonb_typeof(stock_snapshot)='array'),
 calculated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id),
 UNIQUE(item_id,revision)
);
CREATE TABLE drafts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 locale text NOT NULL CHECK(locale IN ('en','ar')),
 prose jsonb NOT NULL CHECK(jsonb_typeof(prose)='object'),
 verified_facts jsonb NOT NULL CHECK(jsonb_typeof(verified_facts)='object'),
 rendered_text text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,revision)
);
CREATE TABLE verification_results (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL,
 draft_id uuid NOT NULL REFERENCES drafts(id),
 passed boolean NOT NULL,
 failures jsonb NOT NULL CHECK(jsonb_typeof(failures)='array'),
 facts_sha256 text NOT NULL CHECK(facts_sha256 ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(enquiry_id,revision)
);
ALTER TABLE review_decisions ADD COLUMN revision integer NOT NULL DEFAULT 1;
ALTER TABLE review_decisions ADD COLUMN reviewer_id uuid REFERENCES profiles(id);
ALTER TABLE review_decisions ADD COLUMN verification_id uuid REFERENCES verification_results(id);
ALTER TABLE review_decisions ADD COLUMN idempotency_key uuid;
CREATE UNIQUE INDEX review_decisions_idempotency_idx ON review_decisions(enquiry_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE review_approved_parts ADD COLUMN item_id uuid REFERENCES enquiry_items(id);
CREATE TABLE internal_notes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 author_id uuid NOT NULL REFERENCES profiles(id), body text NOT NULL CHECK(length(trim(body)) BETWEEN 1 AND 4000),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX internal_notes_enquiry_idx ON internal_notes(enquiry_id,created_at,id);
CREATE TABLE assignment_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 assigned_to uuid REFERENCES profiles(id), assigned_by uuid NOT NULL REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE saved_machines (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), owner_id uuid NOT NULL REFERENCES profiles(id),
 session_id uuid REFERENCES demo_sessions(id), session_generation integer,
 label text NOT NULL CHECK(length(trim(label)) BETWEEN 1 AND 120),
 model_id integer NOT NULL REFERENCES equipment_models(id), serial_text text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), archived_at timestamptz,
 CHECK((session_id IS NULL AND session_generation IS NULL) OR (session_id IS NOT NULL AND session_generation>0))
);
CREATE INDEX saved_machines_owner_idx ON saved_machines(owner_id,created_at DESC);
CREATE TABLE missing_part_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 item_id uuid NOT NULL, status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','resolved','unavailable')),
 staff_note text NOT NULL DEFAULT '', resolved_by uuid REFERENCES profiles(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(enquiry_id,item_id) REFERENCES enquiry_items(enquiry_id,id), UNIQUE(item_id)
);
CREATE TABLE jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid REFERENCES enquiries(id),
 revision integer, session_generation integer,
 kind text NOT NULL CHECK(kind IN ('nameplate','export_pdf','catalog_import','catalog_publish','storage_cleanup')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed','cancelled')),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 result jsonb, dedupe_key text NOT NULL UNIQUE,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), max_attempts integer NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 5),
 available_at timestamptz NOT NULL DEFAULT now(), lease_token uuid, lease_expires_at timestamptz,
 last_error_code text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK((status='running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR status<>'running')
);
CREATE INDEX jobs_claim_idx ON jobs(status,available_at,lease_expires_at);
CREATE TABLE workflow_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id), revision integer NOT NULL,
 kind text NOT NULL CHECK(kind IN ('start','message','ocr_completed','approved','retry')),
 payload jsonb NOT NULL DEFAULT '{}', dedupe_key text NOT NULL UNIQUE,
 processed_at timestamptz, lease_token uuid, lease_expires_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX workflow_events_pending_idx ON workflow_events(created_at) WHERE processed_at IS NULL;
CREATE TABLE exports (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL, decision_id uuid NOT NULL REFERENCES review_decisions(id),
 job_id uuid NOT NULL REFERENCES jobs(id), storage_key text UNIQUE, sha256 text,
 status text NOT NULL CHECK(status IN ('pending','ready','failed','deleted')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(enquiry_id,revision)
);
CREATE TABLE import_batches (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), created_by uuid NOT NULL REFERENCES profiles(id),
 version_id uuid REFERENCES catalogue_versions(id), job_id uuid REFERENCES jobs(id),
 storage_key text NOT NULL, sha256 text NOT NULL, status text NOT NULL CHECK(status IN ('uploaded','validating','invalid','valid','published')),
 row_count integer NOT NULL DEFAULT 0 CHECK(row_count BETWEEN 0 AND 50000),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE import_rows (
 batch_id uuid NOT NULL REFERENCES import_batches(id), row_number integer NOT NULL CHECK(row_number>0),
 entity_type text NOT NULL, payload jsonb NOT NULL, errors jsonb NOT NULL DEFAULT '[]',
 PRIMARY KEY(batch_id,row_number)
);
CREATE TABLE ai_budget_accounts (
 id text PRIMARY KEY, cap_usd numeric(14,8) NOT NULL CHECK(cap_usd>=0),
 reserved_usd numeric(14,8) NOT NULL DEFAULT 0 CHECK(reserved_usd>=0),
 consumed_usd numeric(14,8) NOT NULL DEFAULT 0 CHECK(consumed_usd>=0),
 expires_at timestamptz NOT NULL, enabled boolean NOT NULL DEFAULT false,
 CHECK(reserved_usd+consumed_usd<=cap_usd)
);
CREATE TABLE ai_usage (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid REFERENCES enquiries(id),
 request_key uuid NOT NULL UNIQUE, budget_account_id text NOT NULL REFERENCES ai_budget_accounts(id),
 model text NOT NULL, stage text NOT NULL, status text NOT NULL CHECK(status IN ('reserved','completed','uncertain','released')),
 reserved_usd numeric(14,8) NOT NULL CHECK(reserved_usd>=0), actual_usd numeric(14,8) CHECK(actual_usd>=0),
 input_tokens integer CHECK(input_tokens>=0), output_tokens integer CHECK(output_tokens>=0),
 duration_ms integer CHECK(duration_ms>=0), provider_request_id text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_usage_created_idx ON ai_usage(created_at,stage);
CREATE TABLE eval_cases (
 id text PRIMARY KEY, scenario text NOT NULL, input jsonb NOT NULL, expected jsonb NOT NULL,
 catalogue_version_id uuid NOT NULL REFERENCES catalogue_versions(id),
 language text NOT NULL CHECK(language IN ('en','ar','mixed')), approved_by uuid REFERENCES profiles(id)
);
CREATE TABLE eval_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), git_sha text NOT NULL, model text NOT NULL,
 dataset_sha256 text NOT NULL, started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 status text NOT NULL CHECK(status IN ('running','passed','failed'))
);
CREATE TABLE eval_results (
 run_id uuid NOT NULL REFERENCES eval_runs(id), case_id text NOT NULL REFERENCES eval_cases(id),
 actual jsonb NOT NULL, passed boolean NOT NULL, duration_ms integer NOT NULL CHECK(duration_ms>=0),
 PRIMARY KEY(run_id,case_id)
);
CREATE TABLE correction_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), enquiry_id uuid NOT NULL REFERENCES enquiries(id),
 revision integer NOT NULL, corrected_by uuid NOT NULL REFERENCES profiles(id),
 before_value jsonb NOT NULL, after_value jsonb NOT NULL, reason text NOT NULL,
 eval_case_id text REFERENCES eval_cases(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE enquiry_summaries (
 enquiry_id uuid NOT NULL REFERENCES enquiries(id), revision integer NOT NULL,
 summary text NOT NULL, source_message_ids uuid[] NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(enquiry_id,revision)
);
CREATE TABLE retention_policies (
 scope text PRIMARY KEY CHECK(scope IN ('demo','client')),
 enquiry_days integer CHECK(enquiry_days BETWEEN 1 AND 3650),
 upload_days integer CHECK(upload_days BETWEEN 1 AND 3650),
 audit_days integer CHECK(audit_days BETWEEN 1 AND 3650),
 configured_by uuid REFERENCES profiles(id), configured_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO retention_policies(scope,enquiry_days,upload_days,audit_days) VALUES ('demo',1,1,NULL),('client',NULL,NULL,NULL);
-- NULL client values disable live-client onboarding, not indefinite silent consent.
ALTER TABLE audit_log ADD COLUMN enquiry_id uuid REFERENCES enquiries(id);
ALTER TABLE audit_log ADD COLUMN revision integer;
CREATE INDEX audit_log_enquiry_idx ON audit_log(enquiry_id,occurred_at DESC);
CREATE FUNCTION app_private.lock_supersessions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN PERFORM pg_advisory_xact_lock(710069); RETURN NEW; END; $$;
CREATE TRIGGER aa_supersessions_lock BEFORE INSERT OR UPDATE ON part_supersessions FOR EACH ROW EXECUTE FUNCTION app_private.lock_supersessions();
CREATE FUNCTION app_private.immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable historical record' USING ERRCODE='42501'; END; $$;
CREATE TRIGGER catalogue_records_immutable BEFORE UPDATE OR DELETE ON catalogue_records FOR EACH ROW EXECUTE FUNCTION app_private.immutable_record();
CREATE TRIGGER revisions_immutable BEFORE UPDATE OR DELETE ON enquiry_revisions FOR EACH ROW EXECUTE FUNCTION app_private.immutable_record();
CREATE TABLE idempotency_records (
 actor_id uuid NOT NULL REFERENCES profiles(id),
 operation text NOT NULL,
 key uuid NOT NULL,
 request_sha256 text NOT NULL CHECK(request_sha256 ~ '^[a-f0-9]{64}$'),
 response jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(actor_id,operation,key)
);
COMMIT;
```

### 004_rls.sql

```sql
-- Runtime roles are NOLOGIN groups. The operator creates distinct LOGIN roles and grants one group per service.
BEGIN;
CREATE ROLE partsiq_gateway NOLOGIN;
CREATE ROLE partsiq_search NOLOGIN;
CREATE ROLE partsiq_orchestrator NOLOGIN;
CREATE ROLE partsiq_worker NOLOGIN;
CREATE ROLE partsiq_catalogue NOLOGIN;
GRANT USAGE ON SCHEMA public,app_private TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker,partsiq_catalogue;
CREATE FUNCTION app_private.actor() RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT nullif(current_setting('app.actor_id',true),'')::uuid;
$$;
CREATE FUNCTION app_private.has_role(wanted text) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM staff_roles WHERE user_id=app_private.actor() AND role=wanted);
$$;
CREATE FUNCTION app_private.demo_active(sid uuid, gen integer, uid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM demo_sessions WHERE id=sid AND owner_id=uid AND generation=gen AND revoked_at IS NULL AND expires_at>now());
$$;
CREATE FUNCTION app_private.can_read_enquiry(eid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM enquiries e WHERE e.id=eid AND (
 (e.owner_id=app_private.actor() AND (e.session_id IS NULL OR app_private.demo_active(e.session_id,e.session_generation,e.owner_id)))
 OR (e.session_id IS NULL AND (app_private.has_role('admin') OR (e.assigned_to=app_private.actor() AND app_private.has_role('reviewer'))))));
$$;
CREATE FUNCTION app_private.can_review(eid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM enquiries e WHERE e.id=eid AND (
 (e.session_id IS NOT NULL AND e.owner_id=app_private.actor() AND app_private.demo_active(e.session_id,e.session_generation,e.owner_id))
 OR (e.session_id IS NULL AND (app_private.has_role('admin') OR (e.assigned_to=app_private.actor() AND app_private.has_role('reviewer'))))));
$$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app_private FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app_private TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker,partsiq_catalogue;
ALTER TABLE equipment_families ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON equipment_families FROM anon,authenticated;
GRANT SELECT ON equipment_families TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY equipment_families_read ON equipment_families FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON equipment_families TO partsiq_catalogue;
CREATE POLICY equipment_families_publisher ON equipment_families TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE equipment_models ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON equipment_models FROM anon,authenticated;
GRANT SELECT ON equipment_models TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY equipment_models_read ON equipment_models FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON equipment_models TO partsiq_catalogue;
CREATE POLICY equipment_models_publisher ON equipment_models TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE model_configurations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON model_configurations FROM anon,authenticated;
GRANT SELECT ON model_configurations TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY model_configurations_read ON model_configurations FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON model_configurations TO partsiq_catalogue;
CREATE POLICY model_configurations_publisher ON model_configurations TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE parts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON parts FROM anon,authenticated;
GRANT SELECT ON parts TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY parts_read ON parts FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON parts TO partsiq_catalogue;
CREATE POLICY parts_publisher ON parts TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE part_aliases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON part_aliases FROM anon,authenticated;
GRANT SELECT ON part_aliases TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY part_aliases_read ON part_aliases FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON part_aliases TO partsiq_catalogue;
CREATE POLICY part_aliases_publisher ON part_aliases TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE part_embeddings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON part_embeddings FROM anon,authenticated;
GRANT SELECT ON part_embeddings TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY part_embeddings_read ON part_embeddings FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON part_embeddings TO partsiq_catalogue;
CREATE POLICY part_embeddings_publisher ON part_embeddings TO partsiq_catalogue USING (true) WITH CHECK (true);
GRANT INSERT,UPDATE ON part_embeddings TO partsiq_search;
CREATE POLICY part_embeddings_encoder ON part_embeddings FOR INSERT TO partsiq_search WITH CHECK(true);
CREATE POLICY part_embeddings_encoder_update ON part_embeddings FOR UPDATE TO partsiq_search USING(true) WITH CHECK(true);
ALTER TABLE part_compatibility ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON part_compatibility FROM anon,authenticated;
GRANT SELECT ON part_compatibility TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY part_compatibility_read ON part_compatibility FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON part_compatibility TO partsiq_catalogue;
CREATE POLICY part_compatibility_publisher ON part_compatibility TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE part_supersessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON part_supersessions FROM anon,authenticated;
GRANT SELECT ON part_supersessions TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY part_supersessions_read ON part_supersessions FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON part_supersessions TO partsiq_catalogue;
CREATE POLICY part_supersessions_publisher ON part_supersessions TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE warehouses ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON warehouses FROM anon,authenticated;
GRANT SELECT ON warehouses TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY warehouses_read ON warehouses FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON warehouses TO partsiq_catalogue;
CREATE POLICY warehouses_publisher ON warehouses TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE stock_levels ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON stock_levels FROM anon,authenticated;
GRANT SELECT ON stock_levels TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY stock_levels_read ON stock_levels FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON stock_levels TO partsiq_catalogue;
CREATE POLICY stock_levels_publisher ON stock_levels TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE enquiries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiries FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON enquiries TO partsiq_gateway,partsiq_orchestrator,partsiq_worker;
CREATE POLICY enquiries_gateway ON enquiries TO partsiq_gateway USING(app_private.can_read_enquiry(id)) WITH CHECK(owner_id=app_private.actor() OR app_private.can_review(id));
CREATE POLICY enquiries_internal ON enquiries TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE enquiry_attachments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiry_attachments FROM anon,authenticated;
GRANT SELECT ON enquiry_attachments TO partsiq_gateway;
CREATE POLICY enquiry_attachments_gateway_read ON enquiry_attachments FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT INSERT ON enquiry_attachments TO partsiq_gateway;
CREATE POLICY enquiry_attachments_gateway_insert ON enquiry_attachments FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT UPDATE ON enquiry_attachments TO partsiq_gateway;
CREATE POLICY enquiry_attachments_gateway_update ON enquiry_attachments FOR UPDATE TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id)) WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON enquiry_attachments TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY enquiry_attachments_internal ON enquiry_attachments TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE enquiry_candidates ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiry_candidates FROM anon,authenticated;
GRANT SELECT ON enquiry_candidates TO partsiq_gateway;
CREATE POLICY enquiry_candidates_gateway_read ON enquiry_candidates FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON enquiry_candidates TO partsiq_orchestrator;
GRANT SELECT ON enquiry_candidates TO partsiq_worker;
CREATE POLICY enquiry_candidates_internal ON enquiry_candidates TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON review_decisions FROM anon,authenticated;
GRANT SELECT ON review_decisions TO partsiq_gateway;
CREATE POLICY review_decisions_gateway_read ON review_decisions FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON review_decisions TO partsiq_orchestrator;
GRANT SELECT ON review_decisions TO partsiq_worker;
CREATE POLICY review_decisions_internal ON review_decisions TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE review_approved_parts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON review_approved_parts FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON review_approved_parts TO partsiq_orchestrator;
GRANT SELECT ON review_approved_parts TO partsiq_worker;
CREATE POLICY review_approved_parts_internal ON review_approved_parts TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON audit_log FROM anon,authenticated;
GRANT INSERT ON audit_log TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker,partsiq_catalogue;
CREATE POLICY audit_log_append ON audit_log FOR INSERT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker,partsiq_catalogue WITH CHECK(true);
GRANT SELECT ON audit_log TO partsiq_gateway;
CREATE POLICY audit_log_read ON audit_log FOR SELECT TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.can_review(enquiry_id));
ALTER TABLE warehouse_transfer_routes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON warehouse_transfer_routes FROM anon,authenticated;
GRANT SELECT ON warehouse_transfer_routes TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY warehouse_transfer_routes_read ON warehouse_transfer_routes FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON warehouse_transfer_routes TO partsiq_catalogue;
CREATE POLICY warehouse_transfer_routes_publisher ON warehouse_transfer_routes TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON profiles FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON profiles TO partsiq_gateway;
CREATE POLICY profiles_owner ON profiles TO partsiq_gateway USING(id=app_private.actor()) WITH CHECK(id=app_private.actor());
GRANT SELECT,UPDATE ON profiles TO partsiq_worker;
CREATE POLICY profiles_cleanup ON profiles TO partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE staff_roles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON staff_roles FROM anon,authenticated;
GRANT SELECT,INSERT,DELETE ON staff_roles TO partsiq_gateway;
CREATE POLICY staff_roles_read ON staff_roles FOR SELECT TO partsiq_gateway USING(user_id=app_private.actor() OR app_private.has_role('admin'));
CREATE POLICY staff_roles_insert ON staff_roles FOR INSERT TO partsiq_gateway WITH CHECK(app_private.has_role('admin'));
CREATE POLICY staff_roles_delete ON staff_roles FOR DELETE TO partsiq_gateway USING(app_private.has_role('admin'));
ALTER TABLE demo_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON demo_sessions FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON demo_sessions TO partsiq_gateway;
CREATE POLICY demo_sessions_owner ON demo_sessions TO partsiq_gateway USING(owner_id=app_private.actor()) WITH CHECK(owner_id=app_private.actor());
GRANT SELECT,UPDATE ON demo_sessions TO partsiq_worker;
CREATE POLICY demo_sessions_cleanup ON demo_sessions TO partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE catalogue_versions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON catalogue_versions FROM anon,authenticated;
GRANT SELECT ON catalogue_versions TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY catalogue_versions_read ON catalogue_versions FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON catalogue_versions TO partsiq_catalogue;
CREATE POLICY catalogue_versions_publisher ON catalogue_versions TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE catalogue_records ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON catalogue_records FROM anon,authenticated;
GRANT SELECT ON catalogue_records TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY catalogue_records_read ON catalogue_records FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON catalogue_records TO partsiq_catalogue;
CREATE POLICY catalogue_records_publisher ON catalogue_records TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE catalogue_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON catalogue_evidence FROM anon,authenticated;
GRANT SELECT ON catalogue_evidence TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker;
CREATE POLICY catalogue_evidence_read ON catalogue_evidence FOR SELECT TO partsiq_gateway,partsiq_search,partsiq_orchestrator,partsiq_worker USING (true);
GRANT SELECT,INSERT,UPDATE ON catalogue_evidence TO partsiq_catalogue;
CREATE POLICY catalogue_evidence_publisher ON catalogue_evidence TO partsiq_catalogue USING (true) WITH CHECK (true);
ALTER TABLE enquiry_items ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiry_items FROM anon,authenticated;
GRANT SELECT ON enquiry_items TO partsiq_gateway;
CREATE POLICY enquiry_items_gateway_read ON enquiry_items FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT INSERT ON enquiry_items TO partsiq_gateway;
CREATE POLICY enquiry_items_gateway_insert ON enquiry_items FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT UPDATE ON enquiry_items TO partsiq_gateway;
CREATE POLICY enquiry_items_gateway_update ON enquiry_items FOR UPDATE TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id)) WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON enquiry_items TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY enquiry_items_internal ON enquiry_items TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON messages FROM anon,authenticated;
GRANT SELECT ON messages TO partsiq_gateway;
CREATE POLICY messages_gateway_read ON messages FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT INSERT ON messages TO partsiq_gateway;
CREATE POLICY messages_gateway_insert ON messages FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_read_enquiry(enquiry_id) AND kind='customer');
GRANT SELECT,INSERT,UPDATE ON messages TO partsiq_orchestrator;
GRANT SELECT ON messages TO partsiq_worker;
CREATE POLICY messages_internal ON messages TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE enquiry_revisions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiry_revisions FROM anon,authenticated;
GRANT SELECT ON enquiry_revisions TO partsiq_gateway;
CREATE POLICY enquiry_revisions_gateway_read ON enquiry_revisions FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON enquiry_revisions TO partsiq_orchestrator;
GRANT SELECT ON enquiry_revisions TO partsiq_worker;
CREATE POLICY enquiry_revisions_internal ON enquiry_revisions TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON extractions FROM anon,authenticated;
GRANT SELECT ON extractions TO partsiq_gateway;
CREATE POLICY extractions_gateway_read ON extractions FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON extractions TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY extractions_internal ON extractions TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE fulfilment_plans ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON fulfilment_plans FROM anon,authenticated;
GRANT SELECT ON fulfilment_plans TO partsiq_gateway;
CREATE POLICY fulfilment_plans_gateway_read ON fulfilment_plans FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON fulfilment_plans TO partsiq_orchestrator;
GRANT SELECT ON fulfilment_plans TO partsiq_worker;
CREATE POLICY fulfilment_plans_internal ON fulfilment_plans TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON drafts FROM anon,authenticated;
GRANT SELECT ON drafts TO partsiq_gateway;
CREATE POLICY drafts_gateway_read ON drafts FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON drafts TO partsiq_orchestrator;
GRANT SELECT ON drafts TO partsiq_worker;
CREATE POLICY drafts_internal ON drafts TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE verification_results ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON verification_results FROM anon,authenticated;
GRANT SELECT ON verification_results TO partsiq_gateway;
CREATE POLICY verification_results_gateway_read ON verification_results FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON verification_results TO partsiq_orchestrator;
GRANT SELECT ON verification_results TO partsiq_worker;
CREATE POLICY verification_results_internal ON verification_results TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE internal_notes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON internal_notes FROM anon,authenticated;
GRANT SELECT ON internal_notes TO partsiq_gateway;
CREATE POLICY internal_notes_gateway_read ON internal_notes FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT INSERT ON internal_notes TO partsiq_gateway;
CREATE POLICY internal_notes_gateway_insert ON internal_notes FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_review(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON internal_notes TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY internal_notes_internal ON internal_notes TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE assignment_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON assignment_events FROM anon,authenticated;
GRANT SELECT ON assignment_events TO partsiq_gateway;
CREATE POLICY assignment_events_gateway_read ON assignment_events FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT INSERT ON assignment_events TO partsiq_gateway;
CREATE POLICY assignment_events_gateway_insert ON assignment_events FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_review(enquiry_id) AND app_private.has_role('admin'));
GRANT SELECT,INSERT,UPDATE ON assignment_events TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY assignment_events_internal ON assignment_events TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE saved_machines ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON saved_machines FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON saved_machines TO partsiq_gateway;
CREATE POLICY saved_machines_owner ON saved_machines TO partsiq_gateway USING(owner_id=app_private.actor() AND (session_id IS NULL OR app_private.demo_active(session_id,session_generation,owner_id))) WITH CHECK(owner_id=app_private.actor() AND (session_id IS NULL OR app_private.demo_active(session_id,session_generation,owner_id)));
GRANT SELECT,UPDATE ON saved_machines TO partsiq_worker;
CREATE POLICY saved_machines_cleanup ON saved_machines TO partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE missing_part_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON missing_part_requests FROM anon,authenticated;
GRANT SELECT ON missing_part_requests TO partsiq_gateway;
CREATE POLICY missing_part_requests_gateway_read ON missing_part_requests FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT INSERT ON missing_part_requests TO partsiq_gateway;
CREATE POLICY missing_part_requests_gateway_insert ON missing_part_requests FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT UPDATE ON missing_part_requests TO partsiq_gateway;
CREATE POLICY missing_part_requests_gateway_update ON missing_part_requests FOR UPDATE TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id)) WITH CHECK(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON missing_part_requests TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY missing_part_requests_internal ON missing_part_requests TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON jobs FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON jobs TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY jobs_internal ON jobs TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT INSERT,SELECT ON jobs TO partsiq_gateway;
CREATE POLICY jobs_gateway ON jobs TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id)) WITH CHECK(app_private.can_read_enquiry(enquiry_id));
ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON workflow_events FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON workflow_events TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY workflow_events_internal ON workflow_events TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT INSERT,SELECT ON workflow_events TO partsiq_gateway;
CREATE POLICY workflow_events_gateway ON workflow_events TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id)) WITH CHECK(app_private.can_read_enquiry(enquiry_id));
ALTER TABLE exports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON exports FROM anon,authenticated;
GRANT SELECT ON exports TO partsiq_gateway;
CREATE POLICY exports_gateway_read ON exports FOR SELECT TO partsiq_gateway USING(app_private.can_read_enquiry(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON exports TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY exports_internal ON exports TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON import_batches FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON import_batches TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY import_batches_internal ON import_batches TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON import_batches TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY import_batches_admin ON import_batches TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY import_batches_catalogue ON import_batches TO partsiq_catalogue USING(true) WITH CHECK(true);
ALTER TABLE import_rows ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON import_rows FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON import_rows TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY import_rows_internal ON import_rows TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON import_rows TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY import_rows_admin ON import_rows TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY import_rows_catalogue ON import_rows TO partsiq_catalogue USING(true) WITH CHECK(true);
ALTER TABLE ai_budget_accounts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ai_budget_accounts FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON ai_budget_accounts TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY ai_budget_accounts_internal ON ai_budget_accounts TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ai_usage FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON ai_usage TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY ai_usage_internal ON ai_usage TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE eval_cases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON eval_cases FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON eval_cases TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY eval_cases_internal ON eval_cases TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON eval_cases TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY eval_cases_admin ON eval_cases TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY eval_cases_catalogue ON eval_cases TO partsiq_catalogue USING(true) WITH CHECK(true);
ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON eval_runs FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON eval_runs TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY eval_runs_internal ON eval_runs TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON eval_runs TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY eval_runs_admin ON eval_runs TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY eval_runs_catalogue ON eval_runs TO partsiq_catalogue USING(true) WITH CHECK(true);
ALTER TABLE eval_results ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON eval_results FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON eval_results TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY eval_results_internal ON eval_results TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON eval_results TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY eval_results_admin ON eval_results TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY eval_results_catalogue ON eval_results TO partsiq_catalogue USING(true) WITH CHECK(true);
ALTER TABLE correction_records ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON correction_records FROM anon,authenticated;
GRANT SELECT ON correction_records TO partsiq_gateway;
CREATE POLICY correction_records_gateway_read ON correction_records FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT INSERT ON correction_records TO partsiq_gateway;
CREATE POLICY correction_records_gateway_insert ON correction_records FOR INSERT TO partsiq_gateway WITH CHECK(app_private.can_review(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON correction_records TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY correction_records_internal ON correction_records TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE enquiry_summaries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON enquiry_summaries FROM anon,authenticated;
GRANT SELECT ON enquiry_summaries TO partsiq_gateway;
CREATE POLICY enquiry_summaries_gateway_read ON enquiry_summaries FOR SELECT TO partsiq_gateway USING(app_private.can_review(enquiry_id));
GRANT SELECT,INSERT,UPDATE ON enquiry_summaries TO partsiq_orchestrator;
GRANT SELECT ON enquiry_summaries TO partsiq_worker;
CREATE POLICY enquiry_summaries_internal ON enquiry_summaries TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
ALTER TABLE retention_policies ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON retention_policies FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON retention_policies TO partsiq_orchestrator,partsiq_worker;
CREATE POLICY retention_policies_internal ON retention_policies TO partsiq_orchestrator,partsiq_worker USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON retention_policies TO partsiq_gateway,partsiq_catalogue;
CREATE POLICY retention_policies_admin ON retention_policies TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.has_role('catalogue_admin')) WITH CHECK(app_private.has_role('admin') OR app_private.has_role('catalogue_admin'));
CREATE POLICY retention_policies_catalogue ON retention_policies TO partsiq_catalogue USING(true) WITH CHECK(true);
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO partsiq_gateway,partsiq_orchestrator,partsiq_worker,partsiq_catalogue;
CREATE FUNCTION app_private.validate_publication() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
BEGIN
 IF NEW.kind='recommendation' AND NOT EXISTS(
 SELECT 1 FROM review_decisions d JOIN enquiries e ON e.id=d.enquiry_id
 JOIN verification_results v ON v.id=d.verification_id
 WHERE d.id=NEW.decision_id AND d.enquiry_id=NEW.enquiry_id AND d.revision=NEW.revision
 AND e.revision=NEW.revision AND d.decision='approved' AND v.passed AND v.revision=NEW.revision
 ) THEN RAISE EXCEPTION 'approval required for current revision' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION app_private.validate_publication() FROM PUBLIC;
CREATE TRIGGER messages_publication_guard BEFORE INSERT ON messages FOR EACH ROW EXECUTE FUNCTION app_private.validate_publication();
GRANT USAGE ON SEQUENCE audit_log_id_seq TO partsiq_search;
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON idempotency_records FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON idempotency_records TO partsiq_gateway,partsiq_orchestrator,partsiq_worker,partsiq_catalogue;
CREATE POLICY idempotency_actor ON idempotency_records TO partsiq_gateway USING(actor_id=app_private.actor()) WITH CHECK(actor_id=app_private.actor());
CREATE POLICY idempotency_internal ON idempotency_records TO partsiq_orchestrator,partsiq_worker,partsiq_catalogue USING(true) WITH CHECK(true);
GRANT SELECT ON ai_usage TO partsiq_gateway;
CREATE POLICY ai_usage_metrics ON ai_usage FOR SELECT TO partsiq_gateway USING(app_private.has_role('admin') OR app_private.can_review(enquiry_id));
COMMIT;
```

### 005_storage.sql

```sql
BEGIN;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types) VALUES
 ('nameplates','nameplates',false,10485760,ARRAY['image/jpeg','image/png','image/webp']),
 ('catalogue-evidence','catalogue-evidence',false,20971520,ARRAY['application/pdf']),
 ('imports','imports',false,10485760,ARRAY['text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']),
 ('exports','exports',false,20971520,ARRAY['application/pdf']);
CREATE FUNCTION public.partsiq_storage_allowed(object_name text, target_bucket text, write_access boolean) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE actor uuid:=auth.uid(); allowed boolean:=false;
BEGIN
 IF actor IS NULL THEN RETURN false; END IF;
 IF target_bucket='nameplates' THEN
 SELECT EXISTS(SELECT 1 FROM enquiry_attachments a JOIN enquiries e ON e.id=a.enquiry_id
 WHERE a.storage_key=object_name AND e.owner_id=actor
 AND (e.session_id IS NULL OR app_private.demo_active(e.session_id,e.session_generation,actor))
 AND ((write_access AND a.status='pending') OR (NOT write_access AND a.status='validated'))) INTO allowed;
 END IF;
 RETURN allowed;
END; $$;
REVOKE ALL ON FUNCTION public.partsiq_storage_allowed(text,text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.partsiq_storage_allowed(text,text,boolean) TO authenticated;
CREATE POLICY nameplate_insert ON storage.objects FOR INSERT TO authenticated
 WITH CHECK(bucket_id='nameplates' AND public.partsiq_storage_allowed(name,bucket_id,true));
CREATE POLICY nameplate_read ON storage.objects FOR SELECT TO authenticated
 USING(bucket_id='nameplates' AND public.partsiq_storage_allowed(name,bucket_id,false));
-- Other buckets have no end-user policy. Worker signs authorized downloads only after gateway scope validation.
COMMIT;
```

### 006_checkpoint_library.sql

```sql
-- Exact library migration statements from langgraph-checkpoint-postgres3.0.4.
-- Applied by pinned saver setup in dedicated checkpoints schema.
CREATE SCHEMA IF NOT EXISTS checkpoints;
SET search_path=checkpoints,public,extensions;
CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    v INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP not null;
SELECT 1;

    CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);
    

    CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
    

    CREATE INDEX CONCURRENTLY IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);
    
ALTER TABLE checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT '';
```

### 007_checkpoint_permissions.sql

```sql
-- Run after library saver setup,never within its concurrent-index transaction.
BEGIN;
REVOKE ALL ON SCHEMA checkpoints FROM PUBLIC,anon,authenticated;
GRANT USAGE ON SCHEMA checkpoints TO partsiq_orchestrator;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA checkpoints TO partsiq_orchestrator;
ALTER TABLE checkpoints.checkpoint_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoint_blobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE checkpoints.checkpoint_writes ENABLE ROW LEVEL SECURITY;
CREATE POLICY checkpoints_migration_read ON checkpoints.checkpoint_migrations FOR SELECT TO partsiq_orchestrator USING(true);
CREATE POLICY checkpoints_state_runtime ON checkpoints.checkpoints TO partsiq_orchestrator USING(true) WITH CHECK(true);
CREATE POLICY checkpoints_blobs_runtime ON checkpoints.checkpoint_blobs TO partsiq_orchestrator USING(true) WITH CHECK(true);
CREATE POLICY checkpoints_writes_runtime ON checkpoints.checkpoint_writes TO partsiq_orchestrator USING(true) WITH CHECK(true);
REVOKE INSERT,UPDATE,DELETE ON checkpoints.checkpoint_migrations FROM partsiq_orchestrator;
COMMIT;
```

## 5. Environment variables
Values marked operator input/secret are deployment inputs,not invented credentials. Disabled optional capabilities do not require their credentials. Startup validation must explain missing names without printing secret values.

| Name | Default/input | Used by | Purpose |
|---|---|---|---|
| APP_ENV | local | all | local/test/production; no prod in tests |
| NEXT_PUBLIC_SUPABASE_URL | operator input | web | dev/prod Auth endpoint |
| NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY | operator input | web | publishable key only |
| NEXT_PUBLIC_API_BASE_URL | operator input | web | HTTPS gateway |
| SUPABASE_URL | operator input | gateway,worker | project URL |
| SUPABASE_JWT_ISSUER | operator input | gateway | exact issuer |
| SUPABASE_JWKS_URL | operator input | gateway | trusted fixed JWKS URL |
| SUPABASE_STORAGE_KEY | operator secret | worker only | private object signing/cleanup; not database REST |
| DATABASE_URL | operator secret | each service | separate restricted login |
| MIGRATION_DATABASE_URL | operator secret | migration only | DDL credential |
| DATABASE_POOL_MAX | 4 | each service | bounded connections |
| ALLOWED_ORIGINS | operator input | gateway | exact Vercel origins |
| REDIS_URL | redis://redis:6379/0 | backend | private dispatch and rate limits |
| INTERNAL_SERVICE_TOKEN | operator secret | internal services | random32-byte minimum |
| SEARCH_URL | http://search:8000 | gateway,orchestrator | internal search |
| ORCHESTRATOR_URL | http://orchestrator:8000 | gateway | internal workflow |
| WORKER_URL | http://worker:8000 | gateway | authorized signing/import control |
| OPENAI_API_KEY | operator secret | orchestrator,worker | owner key; never in browser |
| OPENAI_MODEL_TEXT | gpt-4.1-mini-2025-04-14 | orchestrator | pinned structured-output model |
| OPENAI_MODEL_VISION | gpt-4.1-mini-2025-04-14 | worker | pinned vision model |
| AI_ENABLED | false | AI services | enable only after credit preflight |
| AI_FREE_CREDIT_USD | 0 | AI services | owner-confirmed dedicated allowance |
| AI_CREDIT_EXPIRES_AT | operator input | AI services | required UTC expiry when enabled |
| AI_PAID_BUDGET_USD | 0 | AI services | must stay0 |
| AI_DAILY_ALLOWANCE_USD | 0 | AI services | required allowance within confirmed total |
| AI_SESSION_ALLOWANCE_USD | 0 | AI services | required per-session limit |
| BUDGET_TIMEZONE | Asia/Kolkata | AI services | daily reset timezone |
| WORKFLOW_MAX_STEPS | 12 | orchestrator | bounded transition count |
| TOOL_MAX_CALLS | 4 | orchestrator | per-stage tool bound |
| UPLOAD_MAX_BYTES | 10485760 | gateway,worker | 10MiB |
| UPLOAD_MAX_PIXELS | 24000000 | worker | decode cap |
| RATE_LIMIT_PER_MINUTE | 20 | gateway | per actor plus IP limiter |
| DEMO_TTL_HOURS | 24 | gateway,sweeper | session expiry |
| STOCK_MAX_AGE_SECONDS | 3600 | search,approval | demo freshness default |
| NORMAL_REVIEW_HOURS | 24 | gateway | noncontractual deadline |
| URGENT_REVIEW_HOURS | 2 | gateway | noncontractual deadline |
| EMBEDDING_MODEL_REVISION | 5617a9f61b028005a4858fdac845db406aefb181 | search only | BAAI/bge-m3 revision |
| LANGFUSE_ENABLED | false | common telemetry | optional free tracing |
| LANGFUSE_PUBLIC_KEY | operator input | backend | not browser |
| LANGFUSE_SECRET_KEY | operator secret | backend | redacted traces only |
| LANGFUSE_BASE_URL | operator input | backend | selected free cloud region |
| API_DOMAIN | operator input | Caddy | owned or no-cost DNS name |
| RELEASE_SHA | operator input | deployment | immutable Git commit |
| AWS_REGION | ap-south-1 | deployment | verify free-plan service availability |
| AWS_ACCOUNT_ID | operator input | deployment | never invent account ID |
| AWS_ROLE_ARN | operator input | CI | OIDC deploy role |
| EC2_INSTANCE_ID | operator input | deployment | SSM target |
| PRODUCTION_PROJECT_REF | operator input | tests,deploy | test safety denylist |

## 6. Routes and signatures
Common typed shapes are in spec/contracts.py and docs/CONTRACTS.md. Every F implementation prompt defines its own request/result,exact route and component. Foundation08 owns POST /v1/enquiries,POST /v1/enquiries/{id}/messages,GET /v1/enquiries/{id},GET /v1/enquiries/{id}/messages,POST /v1/uploads and POST /v1/uploads/{id}/confirm. Foundation07 owns POST /v1/demo/sessions and POST /v1/demo/sessions/reset. Foundation14 owns POST /internal/approvals and gateway routes POST /v1/staff/enquiries/{id}/approve,/edit,/reject. Foundation17 owns POST /v1/enquiries/{id}/export and authorized download retrieval. Foundation20 consumes GET /v1/staff/enquiries/{id}/review. Search preserves identify,parts,part-detail,warehouses and fulfilment APIs behind /internal. Health GET /health reports process alive; /ready reports required dependency status without secrets.

## 7. Limits
Text12000chars,20items,upload10MiB,24million decoded pixels,import50000rows,tool4calls/stage,workflow12transitions,job3attempts,lease45seconds,heartbeat10seconds,signing60seconds. These are implementation defaults,not measured throughput claims. Performance tests report median/p95 with concurrency1 and3,warm/cold search separated; no latency guarantee is fabricated for free hardware.
