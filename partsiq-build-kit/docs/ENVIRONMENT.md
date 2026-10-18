# Environment contract

Empty secret/account values are intentionally required operator inputs, not fabricated credentials. Local fixture mode needs local Supabase values but no Snowflake/OpenAI key. Copy environment.example to ignored .env during implementation.

| Variable | Default | Consumer | Meaning |
|---|---|---|---|
| APP_ENV | local | API and worker | local, dev or prod; tests reject prod |
| DATA_SOURCE | fixture | Worker | fixture or snowflake; never automatic fallback |
| AI_MODE | fixture | Worker | fixture or live; fixture banner mandatory |
| REAL_ONBOARDING_ENABLED | false | API | Remain false until client retention is agreed |
| DATABASE_URL_API | Required when applicable | API | Least-privilege LOGIN with partsiq_api |
| DATABASE_URL_WORKFLOW | Required when applicable | Worker | LOGIN with partsiq_workflow |
| DATABASE_URL_SEARCH | Required when applicable | Worker | LOGIN with partsiq_search |
| DATABASE_URL_WORKER | Required when applicable | Worker | LOGIN with partsiq_worker |
| DATABASE_URL_CATALOGUE | Required when applicable | Worker | LOGIN with partsiq_catalogue |
| DATABASE_URL_MIGRATION | Required when applicable | Migration command only | Schema owner; never runtime |
| SUPABASE_URL | Required when applicable | API and web | Development or production project URL |
| SUPABASE_ANON_KEY | Required when applicable | Web | Public browser key; authorization still required |
| SUPABASE_SERVICE_ROLE_KEY | Required when applicable | Storage adapter only | Secret; never used for ordinary database queries |
| SUPABASE_JWT_ISSUER | Required when applicable | API | Exact configured auth issuer |
| SUPABASE_JWT_AUDIENCE | authenticated | API | Exact JWT audience |
| REDIS_URL | redis://redis:6379/0 | API and worker | Private Compose network |
| ALLOWED_ORIGINS | http://localhost:3000 | API | Comma-separated exact origins |
| OPENAI_API_KEY | Required when applicable | Worker | Secret live key |
| OPENAI_TEXT_MODEL | Required when applicable | Worker | Owner-approved available structured-output model |
| OPENAI_VISION_MODEL | Required when applicable | Worker | Owner-approved available image model |
| AI_ALLOWANCE_EXPIRES_AT | Required when applicable | Preflight | Owner-confirmed expiry in UTC; no invented value |
| AI_CONFIRMED_ALLOWANCE_USD | 0 | Preflight | Dedicated free allowance; zero blocks live calls |
| SNOWFLAKE_ACCOUNT | Required when applicable | Worker | Account identifier without domain suffix |
| SNOWFLAKE_USER_READER | Required when applicable | Worker | Read-only service user |
| SNOWFLAKE_USER_LOADER | Required when applicable | Publisher | Publisher service user |
| SNOWFLAKE_USER_REPORTER | Required when applicable | Analytics worker | Reporting service user |
| SNOWFLAKE_PRIVATE_KEY_FILE | Required when applicable | Worker | Mounted secret file; restricted permissions |
| SNOWFLAKE_PRIVATE_KEY_PASSWORD | Required when applicable | Worker | Secret optional key passphrase |
| SNOWFLAKE_DATABASE | PARTSIQ_DEV | Worker | Allowlist PARTSIQ_DEV or PARTSIQ_PROD |
| SNOWFLAKE_WAREHOUSE | PARTSIQ_WH | Worker | Confirmed allowance required |
| SNOWFLAKE_CREDIT_ALLOWANCE | 0 | Preflight | Zero blocks warehouse creation/resume |
| SNOWFLAKE_ALLOWANCE_EXPIRES_AT | Required when applicable | Preflight | Confirmed UTC expiry |
| SEMANTIC_SEARCH_ENABLED | false | Worker | Enable only after memory/capability check |
| BGE_MODEL_REVISION | Required when applicable | Worker | Copy verified immutable revision from infrastructure receipts |
| STOCK_MAX_AGE_SECONDS | 3600 | Domain | Provisional policy; real client chooses |
| DEMO_SESSION_TTL_SECONDS | 86400 | API | 24-hour access lifetime |
| DEMO_CLEANUP_GRACE_SECONDS | 3600 | Worker | Cleanup after access expiry plus one hour |
| JOB_LEASE_SECONDS | 120 | Worker | Heartbeat every30seconds |
| MAX_UPLOAD_BYTES | 10485760 | API and worker | 10MiB |
| MAX_IMAGE_PIXELS | 20000000 | Worker | Decoded pixel budget |
| LANGFUSE_PUBLIC_KEY | Required when applicable | Telemetry | Optional |
| LANGFUSE_SECRET_KEY | Required when applicable | Telemetry | Optional secret |
| LANGFUSE_BASE_URL | Required when applicable | Telemetry | Optional approved endpoint |
| NEXT_PUBLIC_API_ORIGIN | http://localhost:8000 | Web | Public backend origin |
| NEXT_PUBLIC_SUPABASE_URL | Required when applicable | Web | Matching project URL |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Required when applicable | Web | Matching public auth key |
| API_DOMAIN | Required when applicable | Caddy | Existing owner-controlled domain for hosted HTTPS |

Never place private keys in NEXT_PUBLIC variables. Preflight verifies separate dev/prod hosts and reports missing names without values. Environment seeding initializes allowance only when no existing account row exists; restarts must not reset consumed/reserved amounts. Allowance changes require admin audit.
