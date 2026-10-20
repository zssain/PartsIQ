"""Database-mode worker end-to-end: PostgreSQL jobs + Redis wake-ups + private Supabase Storage.

Runs the real API and the real worker as processes. Checks that a nameplate photo is stored
privately, read by the worker (fixture vision unless live AI is allowed), confirmed by the
customer, approved once, and exported to a private PDF. The export also survives a
worker SIGKILL mid-job (lease expiry, sweeper re-dispatch, no duplicate export) and a Redis outage
(the PostgreSQL sweeper still dispatches).

Only synthetic data is created. Env (never printed): WE_DATABASE_URL, WE_SUPABASE_URL,
WE_SERVICE_KEY, WE_ANON_KEY, WE_REDIS_URL, WE_EMAIL (a test user; it is given the admin role).
Run: uv run --all-packages python apps/api/tests/integration/worker_e2e.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[4]
PORT = int(os.environ.get("WE_PORT", "8102"))
API = f"http://127.0.0.1:{PORT}"
DSN = os.environ["WE_DATABASE_URL"]
SB = os.environ["WE_SUPABASE_URL"].rstrip("/")
SERVICE = os.environ["WE_SERVICE_KEY"]
ANON = os.environ["WE_ANON_KEY"]
REDIS = os.environ["WE_REDIS_URL"]
EMAIL = os.environ["WE_EMAIL"]
LOGS = Path(os.environ.get("WE_LOG_DIR", "/tmp"))
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""), flush=True)


def env(**extra: str) -> dict[str, str]:
    return {**os.environ, "APP_ENV": "dev", "DATA_SOURCE": "fixture", "AI_MODE": "fixture", "ALLOWED_ORIGINS": "http://localhost:3000",
            "DATABASE_URL_API": DSN, "DATABASE_URL_WORKFLOW": DSN, "DATABASE_URL_WORKER": DSN, "SUPABASE_URL": SB,
            "SUPABASE_SERVICE_ROLE_KEY": SERVICE, "SUPABASE_JWT_ISSUER": f"{SB}/auth/v1", "REDIS_URL": REDIS,
            "FIXTURE_STEP_DELAY_MS": "100", "JOB_LEASE_SECONDS": "15", **extra}


def start_api() -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "partsiq.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(PORT)],
                            cwd=ROOT, env=env(), stdout=subprocess.DEVNULL, stderr=open(LOGS / "partsiq-we-api.log", "ab"))
    for _ in range(600):
        try:
            if httpx.get(f"{API}/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise SystemExit("API exited during startup; see partsiq-we-api.log")
        time.sleep(0.25)
    raise SystemExit("API did not start")


def start_worker(**extra: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "partsiq.jobs.main"], cwd=ROOT, env=env(**extra),
                            stdout=subprocess.DEVNULL, stderr=open(LOGS / "partsiq-we-worker.log", "ab"))


def stop(proc: subprocess.Popen, sig: int = signal.SIGTERM) -> None:
    proc.send_signal(sig)
    proc.wait(timeout=60)


def token(roles: list[str]) -> tuple[str, str]:
    admin = {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"} if not SERVICE.startswith("sb_") else {"apikey": SERVICE}
    password = secrets.token_urlsafe(24)
    users = httpx.get(f"{SB}/auth/v1/admin/users", headers=admin, params={"per_page": 200}, timeout=20).json().get("users", [])
    found = [u for u in users if u.get("email") == EMAIL]
    if found:
        uid = found[0]["id"]
        meta = {**(found[0].get("app_metadata") or {}), "partsiq_roles": roles}
        httpx.put(f"{SB}/auth/v1/admin/users/{uid}", headers=admin, json={"password": password, "app_metadata": meta, "ban_duration": "none"}, timeout=20).raise_for_status()
    else:
        created = httpx.post(f"{SB}/auth/v1/admin/users", headers=admin, json={"email": EMAIL, "password": password, "email_confirm": True, "app_metadata": {"partsiq_roles": roles}}, timeout=20)
        created.raise_for_status()
        uid = created.json()["id"]
    got = httpx.post(f"{SB}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": ANON}, json={"email": EMAIL, "password": password}, timeout=20)
    got.raise_for_status()
    return got.json()["access_token"], uid


def H(tok: str, key: bool = False) -> dict[str, str]:
    h = {"Authorization": f"Bearer {tok}"}
    if key:
        h["Idempotency-Key"] = str(uuid4())
    return h


async def q(sql: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(DSN, statement_cache_size=0)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def jobs(eid: str, kind: str) -> list[asyncpg.Record]:
    from uuid import UUID

    return asyncio.run(q("SELECT id,status,attempts,result,last_error_code FROM jobs WHERE enquiry_id=$1 AND kind=$2 ORDER BY created_at", UUID(eid), kind))


def wait(fn, timeout: float = 90, every: float = 0.5):  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    value = None
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(every)
    return value


def main() -> int:
    tok, _uid = token(["admin"])
    c = httpx.Client(timeout=30)
    api = start_api()
    worker = None
    try:
        # 1. Enquiry + nameplate photo while NO worker runs: the job is durable and waits.
        created = c.post(f"{API}/v1/enquiries?mode=guided", headers=H(tok, True), json={"text": "Need 2 air filters for the machine on the attached nameplate. Deliver to Jeddah.", "locale": "en", "destination_warehouse_id": 1})
        check("enquiry created (database mode)", created.status_code == 202, f"{created.status_code} {created.text[:160]}")
        eid = created.json()["id"]
        wait(lambda: c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(tok)).json().get("status") != "processing", 60)
        attached = c.post(f"{API}/v1/enquiries/{eid}/attachments/sample", headers=H(tok, True))
        check("nameplate photo accepted", attached.status_code == 201, f"{attached.status_code} {attached.text[:160]}")
        pending = wait(lambda: [j for j in jobs(eid, "nameplate") if j["status"] == "pending"], 30)
        check("nameplate job persisted in PostgreSQL before any worker exists", bool(pending), str(jobs(eid, "nameplate")))
        objects = httpx.post(f"{SB}/storage/v1/object/list/nameplates", headers={"apikey": SERVICE}, json={"prefix": f"account/{eid}/", "limit": 10}, timeout=20)
        check("photo stored in the PRIVATE nameplates bucket", objects.status_code == 200 and len(objects.json()) == 1, objects.text[:120])
        public = httpx.get(f"{SB}/storage/v1/object/public/nameplates/account/{eid}/{objects.json()[0]['name'] if objects.status_code == 200 and objects.json() else 'x'}", timeout=20)
        check("photo is not publicly readable", public.status_code >= 400, str(public.status_code))

        # 2. Worker starts: it drains the job (Redis wake-up or the sweeper) and the run asks to confirm.
        worker = start_worker()
        done = wait(lambda: [j for j in jobs(eid, "nameplate") if j["status"] == "succeeded"], 60)
        check("worker read the stored photo and recorded the reading", bool(done) and (done[0]["result"] or {}).get("reading", {}).get("model_text") == "CA-110", str(done and done[0]["result"]))
        pend = wait(lambda: [p for p in (lambda r: r if isinstance(r, list) else r.get("items", []))(c.get(f"{API}/v1/enquiries/{eid}/pending", headers=H(tok)).json()) if p.get("kind") == "nameplate_confirmation"], 60)
        check("customer is asked to confirm the identifiers", bool(pend), "")
        detail = c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(tok)).json()
        run = c.get(f"{API}/v1/runs/{detail['run']['id']}", headers=H(tok)).json()
        confirm = c.post(f"{API}/v1/runs/{run['id']}/commands", headers=H(tok, True), json={"type": "confirm_nameplate", "expected_revision": detail["revision"], "payload": {"model_text": "CA-110", "serial_text": "800000"}})
        check("customer confirms the identifiers", confirm.status_code == 202, f"{confirm.status_code} {confirm.text[:200]}")
        review = None
        for _ in range(4):  # answer clarifications like a customer would (first offered option)
            settled = wait(lambda: (lambda d: d if d.get("status") != "processing" else None)(c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(tok)).json()), 90)
            if settled and settled["status"] == "awaiting_review":
                review = settled
                break
            asks = [p for p in c.get(f"{API}/v1/enquiries/{eid}/pending", headers=H(tok)).json() if p["kind"] == "clarification" and p["status"] == "open"]
            if not asks:
                break
            options = asks[0]["options"] or [{"label": "the first one"}]
            answer = next((o for o in options if "air filter" in o.get("label", "").lower()), options[0])
            sent = c.post(f"{API}/v1/runs/{asks[0]['run_id']}/commands", headers=H(tok, True), json={"type": "answer", "expected_revision": settled["revision"], "payload": {"text": answer.get("part_number") or answer.get("label")}})
            check(f"customer answers clarification {asks[0]['code']}", sent.status_code == 202, f"{sent.status_code} {sent.text[:300]}")
        check("run reaches human review", bool(review), str(review and review.get("status")))
        check("only one nameplate job for the photo", len(jobs(eid, "nameplate")) == 1, str(len(jobs(eid, "nameplate"))))

        # 3. An unapproved revision cannot be exported.
        staff = c.get(f"{API}/v1/staff/enquiries/{eid}", headers=H(tok)).json()
        early = c.post(f"{API}/v1/enquiries/{eid}/exports", headers=H(tok, True), json={"enquiry_id": eid, "revision": staff["enquiry"]["revision"], "decision_id": str(uuid4())})
        check("export of an unapproved revision is refused", early.status_code == 409, f"{early.status_code} {early.text[:120]}")

        approved = c.post(f"{API}/v1/staff/enquiries/{eid}/approve", headers=H(tok, True), json={"enquiry_id": eid, "expected_revision": staff["enquiry"]["revision"], "draft_id": staff["draft_id"]})
        check("approved once", approved.status_code == 200 and not approved.json()["already_applied"], approved.text[:160])
        decision = approved.json()["decision_id"]
        body = {"enquiry_id": eid, "revision": staff["enquiry"]["revision"], "decision_id": decision}

        # 4. Export with the worker killed mid-job: the lease expires, the sweeper re-dispatches,
        #    a fresh worker finishes it, and there is still exactly one export.
        stop(worker)
        queued = c.post(f"{API}/v1/enquiries/{eid}/exports", headers=H(tok, True), json=body)
        check("export queued (202, durable job)", queued.status_code == 202 and queued.json()["status"] == "pending", f"{queued.status_code} {queued.text[:160]}")
        worker = start_worker()
        running = wait(lambda: [j for j in jobs(eid, "export_pdf") if j["status"] == "running"] or [j for j in jobs(eid, "export_pdf") if j["status"] == "succeeded"], 60, 0.05)
        if running and running[0]["status"] == "running":
            stop(worker, signal.SIGKILL)
            check("worker SIGKILLed while the export was running", True)
            worker = start_worker()
        else:
            check("worker SIGKILLed while the export was running", False, "export finished before the kill window")
        finished = wait(lambda: [j for j in jobs(eid, "export_pdf") if j["status"] == "succeeded"], 120)
        check("export completed after the crash (lease expiry + re-dispatch)", bool(finished), str(jobs(eid, "export_pdf")))
        again = c.post(f"{API}/v1/enquiries/{eid}/exports", headers=H(tok, True), json=body)
        check("re-request returns the same job with the export id", again.status_code == 202 and again.json()["id"] == queued.json()["id"] and again.json()["resource_id"], again.text[:200])
        rows = asyncio.run(q("SELECT id, sha256, storage_key FROM exports WHERE enquiry_id=$1", __import__("uuid").UUID(eid)))
        check("exactly one export row", len(rows) == 1, str(len(rows)))
        ticket = c.get(f"{API}/v1/exports/{again.json()['resource_id']}/download", headers=H(tok))
        check("signed download ticket issued", ticket.status_code == 200, f"{ticket.status_code} {ticket.text[:160]}")
        pdf = httpx.get(ticket.json()["url"], timeout=30).content if ticket.status_code == 200 else b""
        check("downloaded file is a PDF matching the recorded sha256", pdf.startswith(b"%PDF") and rows and hashlib.sha256(pdf).hexdigest() == rows[0]["sha256"], f"{len(pdf)} bytes")
        unsigned = httpx.get(f"{SB}/storage/v1/object/public/exports/{rows[0]['storage_key']}", timeout=20) if rows else None
        check("PDF is not publicly readable", unsigned is not None and unsigned.status_code >= 400, str(unsigned and unsigned.status_code))
        check("PDF is a few KB to a few MB", 2_000 < len(pdf) < 5_000_000, str(len(pdf)))

        # 5. Redis down: a new job still runs via the PostgreSQL sweeper.
        stop(worker)
        worker = start_worker(REDIS_URL="redis://127.0.0.1:1/0")
        enquiry2 = c.post(f"{API}/v1/enquiries?mode=guided", headers=H(tok, True), json={"text": "Need an oil filter for the machine on the attached nameplate.", "locale": "en", "destination_warehouse_id": 1}).json()["id"]
        wait(lambda: c.get(f"{API}/v1/enquiries/{enquiry2}/detail", headers=H(tok)).json().get("status") != "processing", 60)
        c.post(f"{API}/v1/enquiries/{enquiry2}/attachments/sample", headers=H(tok, True))
        swept = wait(lambda: [j for j in jobs(enquiry2, "nameplate") if j["status"] == "succeeded"], 60)
        check("with Redis unavailable the sweeper still dispatches the job", bool(swept), str(jobs(enquiry2, "nameplate")))
        stop(worker)
    finally:
        if worker is not None and worker.poll() is None:
            stop(worker)
        stop(api)
        token([])  # drop the temporary admin role
    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
