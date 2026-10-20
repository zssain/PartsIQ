# Releasing the workspace build to the current EC2 host

Current production (deployed 2026-10-20, database mode, live AI for invited accounts): EC2 t3.small `3.111.33.177`, Caddy (auto-HTTPS)
for `partsiq.duckdns.org`, systemd `partsiq` (uvicorn :8000, `~/partsiq`, env
`~/partsiq/.env.runtime`) and `partsiq-web` (Next standalone :3000, `~/partsiq-web`).
`DATA_SOURCE=fixture` (Snowflake paused), `AI_MODE=live` ($3 allowance to 2026-11-20; the public demo stays fixture), database mode with Redis and the `partsiq-worker` unit. Measured DB round trip from the host: 260 ms; API start about 55 s.

This build runs in one of two modes, chosen only by the environment:

- **Memory mode** (no `DATABASE_URL_API`): same as today; a restart clears workspaces.
- **Database mode** (`DATABASE_URL_API` set): the account workspace, runs, checkpoints, jobs
  and the AI allowance ledger persist in the Supabase project. The migrations through
  `20261020000200_workspace_persistence.sql` are **already applied** to project
  `jihekqczlaokinuylxml` (2026-10-20). Apply any later ones with
  `PARTSIQ_MIGRATE_TARGET=<name> uv run --all-packages python tools/apply_migrations.py --target <name>`,
  which refuses edited or destructive migrations.

Region note: the project is in Tokyo (`aws-0-ap-northeast-1` session pooler) and the host in
Mumbai. Every write-through is a cross-region round trip. Measured: a guided run took 17.2 s
from a client about 235 ms away. Mumbai to Tokyo is roughly 120 ms, so expect about half that.
For production latency, put the database in `ap-south-1`.

## 1. Build (on your machine, Node 22.22.0)

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=https://partsiq.duckdns.org \
# optional, only if invited accounts are enabled (public values only):
# NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<anon key> \
pnpm build
cp -R public .next/standalone/ && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/
```

## 2. Upload (keep a rollback copy)

```bash
H=ubuntu@3.111.33.177; K=~/Downloads/partsiq-key.pem
ssh -i $K $H 'rm -rf ~/partsiq.prev && cp -a ~/partsiq ~/partsiq.prev && rm -rf ~/partsiq-web.prev && cp -a ~/partsiq-web ~/partsiq-web.prev'
rsync -az --delete -e "ssh -i $K" apps/api/ $H:~/partsiq/apps/api/ --exclude __pycache__ --exclude .pytest_cache
rsync -az -e "ssh -i $K" libs pyproject.toml uv.lock $H:~/partsiq/
rsync -az -e "ssh -i $K" evals $H:~/partsiq/ --relative   # labelled set (the sample nameplate ships inside the package)
rsync -az -e "ssh -i $K" infra/ec2/partsiq-worker.service apps/web/public/brand $H:~/partsiq/ --relative
rsync -az --delete -e "ssh -i $K" apps/web/.next/standalone/ $H:~/partsiq-web/
```

## 3. Environment (append to `~/partsiq/.env.runtime` as needed)

| Variable | Value for the public demo | Notes |
| --- | --- | --- |
| DEMO_ENABLED | true | anonymous sandbox demo |
| COLLABORATION_ENABLED | true | activation flag for agent collaboration |
| FIXTURE_STEP_DELAY_MS | 600 | pacing so visitors can watch and pause |
| DEMO_MAX_WORKSPACES | 400 | memory bound on t3.small |
| SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY | (optional) | enables invited accounts and the users screen; service key stays server-side |
| SUPABASE_JWT_SECRET | (only legacy HS256 projects) | server-side |
| AI_MODE / OPENAI_* / AI_CONFIRMED_ALLOWANCE_USD / AI_ALLOWANCE_EXPIRES_AT | keep fixture | live needs a confirmed allowance and a priced model in `ai/prices.json` |
| DATABASE_URL_API / DATABASE_URL_WORKFLOW / DATABASE_URL_WORKER | session-pooler URL, `?sslmode=require` | **database mode**; the direct `db.<ref>.supabase.co` host is IPv6-only and unreachable from this host |
| REDIS_URL | `redis://127.0.0.1:6379/0` | worker wake-ups; jobs still run from PostgreSQL if Redis is down |
| SUPABASE_JWT_ISSUER | `https://<ref>.supabase.co/auth/v1` | |
| PARTSIQ_BRAND_DIR | `/home/ubuntu/partsiq/apps/web/public/brand` | fonts + logo for PDF exports |

Copy values from the owner's `.env.prod.local` on the deploying machine. Never paste them into
a chat, a commit or a `NEXT_PUBLIC_*` variable (only the URL and publishable key are public).

## 4. Restart and verify

```bash
ssh -i $K $H 'cd ~/partsiq && ~/.local/bin/uv sync --all-packages --frozen && sudo systemctl restart partsiq && sleep 3 && sudo systemctl restart partsiq-web && systemctl is-active partsiq partsiq-web'
curl -s https://partsiq.duckdns.org/health                       # {"status":"ok"}
curl -s https://partsiq.duckdns.org/v1/workspace/status -H "X-Demo-Token: smoke-$(date +%s)" | head -c 300
cd apps/web && E2E_BASE_URL=https://partsiq.duckdns.org node tests/e2e/workspace-app.mjs   # synthetic smoke
```

Confirm the new build is served: `/demo/live` redirects to `/workspace`, and the header
"Workspace" link points to `/workspace`.

## 4b. Background worker (database mode only)

```bash
ssh -i $K $H 'sudo apt-get install -y redis-server && sudo systemctl enable --now redis-server'
ssh -i $K $H 'cd ~/partsiq && ~/.local/bin/uv run --all-packages playwright install --with-deps --only-shell chromium'
ssh -i $K $H 'sudo cp ~/partsiq/infra/ec2/partsiq-worker.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now partsiq-worker && systemctl is-active partsiq-worker'
```

The unit caps the worker at 900 MB. One PDF render peaked at about 440 MB RSS and took 1.6 to
2.2 s. Do **not** enable semantic search (BGE-M3) on this 2 GB host: its weights alone are
about 2.3 GB.

## 5. Rollback

```bash
ssh -i $K $H 'rm -rf ~/partsiq && mv ~/partsiq.prev ~/partsiq && rm -rf ~/partsiq-web && mv ~/partsiq-web.prev ~/partsiq-web && sudo systemctl restart partsiq partsiq-web'
```

There is no data migration to undo: the persistence migration is additive and older code
ignores its columns. In memory mode a restart clears workspaces. In database mode the data
stays in Supabase across restarts and rollbacks.

## Invited accounts in production

1. In the Supabase dashboard (project `jihekqczlaokinuylxml`):
   - Authentication → URL Configuration → **Site URL** `https://partsiq.duckdns.org`.
   - **Redirect URLs**: add `https://partsiq.duckdns.org/login` and
     `http://localhost:3000/login`. Invitation and magic links land on `/login`.
   - Authentication → Sign In / Providers → turn **off** "Allow new users to sign up". It is
     currently **on**. The API already refuses any account that was not invited (403), but
     turning it off stops strangers from creating Auth users at all.
2. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY on the API, and NEXT_PUBLIC_SUPABASE_URL +
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY at web build time. Then rebuild and redeploy.
3. Create the first administrator: invite yourself in the Supabase dashboard, then set
   `app_metadata = {"partsiq_roles": ["admin"], "partsiq_invited": true}` on that user (dashboard SQL:
   `update auth.users set raw_app_meta_data = raw_app_meta_data || '{"partsiq_roles":["admin"],"partsiq_invited":true}' where email = '<you>';`).
   Invite everyone else from **Users & access**. `tools/provision_accounts.py` refuses
   production by design.
