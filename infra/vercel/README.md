# Vercel frontend deployment (prompt 27)

The Next.js app (`apps/web`) is hosted on Vercel. Two **separate** environment bindings — never
shared — mirror the two Supabase projects:

| Vercel environment | Supabase project | Gateway (`NEXT_PUBLIC_API_BASE_URL`) |
|---|---|---|
| Preview / Development | dev | the dev gateway origin |
| Production | prod | the prod gateway origin (HTTPS, operator domain) |

## Public (NEXT_PUBLIC) variables — the ONLY values sent to the browser
- `NEXT_PUBLIC_API_BASE_URL` — the gateway origin (HTTPS in production).
- `NEXT_PUBLIC_SUPABASE_URL` — the Supabase project URL.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` — the publishable key (browser-safe; **not** a secret).
- `NEXT_PUBLIC_REPO_URL` — optional; when unset the landing page hides the source link.

No service-role key, JWT secret, Storage key, internal service token or OpenAI key is ever a
`NEXT_PUBLIC` variable or shipped in the bundle (verified by `tests/foundations/test_18.py`).

## CORS
The gateway's `ALLOWED_ORIGINS` must list the **exact** Vercel origins (preview + production) —
no wildcard, and never `Access-Control-Allow-Origin: *` together with credentials. Each
environment's origin is set explicitly; a preview origin cannot call the production gateway.

## Hosted acceptance
`tools/hosted_acceptance.py::run_hosted_acceptance(base_url, api_url)` runs the four demo
scenarios against the live deployment (each including approval + the approved PDF), measures
actual timings, and returns a `HostedReceipt`. Non-HTTPS URLs outside localhost are rejected.
The deployment is **not** claimed available unless `is_available(receipt)` is true (all four
scenarios passed). Mobile (360px) and Arabic/RTL are inspected via `tests/e2e/hosted.spec.ts`.

## Documented operating limits (measured facts, not guarantees)
- **Supabase inactivity pausing** — a free Supabase project pauses after inactivity; the first
  request after a pause is slow or fails until the project resumes. This is a known free-tier
  limit, not an outage of the application.
- **AWS credit expiry** — the single EC2 host runs on free-plan credit; when the credit expires
  the backend stops. There is no automatic paid upgrade (prompt 26 preflight).
- **Single-host availability** — one EC2 host (ADR-002); no high-availability claim is made.
