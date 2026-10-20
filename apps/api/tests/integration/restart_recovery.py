"""Database-mode restart recovery against a REAL PostgreSQL + Supabase Auth (disposable/dev only).

Starts the actual API process (uvicorn) twice, kills it mid-run with SIGKILL, and checks that the
same enquiry/run is recovered from PostgreSQL, resumes without repeating committed work, and is
approved exactly once — then survives a second restart.

Env (never printed): RR_DATABASE_URL (local/disposable), RR_SUPABASE_URL, RR_SERVICE_KEY, RR_ANON_KEY,
RR_JWT_SECRET (only for legacy HS256 auth). Run: uv run --all-packages python apps/api/tests/integration/restart_recovery.py
"""
from __future__ import annotations

import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import asyncio
import json
import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[4]
PORT = int(os.environ.get("RR_PORT", "8100"))
API = f"http://127.0.0.1:{PORT}"
DSN = os.environ["RR_DATABASE_URL"]
SB = os.environ["RR_SUPABASE_URL"].rstrip("/")
SERVICE = os.environ["RR_SERVICE_KEY"]
ANON = os.environ["RR_ANON_KEY"]
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def start_api(delay_ms: int) -> subprocess.Popen:
    env = {**os.environ, "APP_ENV": "local", "DATA_SOURCE": "fixture", "AI_MODE": "fixture", "ALLOWED_ORIGINS": "http://localhost:3000",
           "DATABASE_URL_API": DSN, "DATABASE_URL_WORKFLOW": DSN, "SUPABASE_URL": SB, "SUPABASE_SERVICE_ROLE_KEY": SERVICE,
           "SUPABASE_JWT_SECRET": os.environ.get("RR_JWT_SECRET", ""), "FIXTURE_STEP_DELAY_MS": str(delay_ms)}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "partsiq.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(PORT)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=open("/tmp/partsiq-rr-api.log", "ab"))
    started = time.monotonic()
    for _ in range(480):
        try:
            if httpx.get(f"{API}/health", timeout=1).status_code == 200:
                print(f"  (API ready in {time.monotonic() - started:.1f}s)")
                return proc
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise SystemExit("API exited during startup; see /tmp/partsiq-rr-api.log")
        time.sleep(0.25)
    raise SystemExit("API did not start")


def user(email: str, roles: list[str]) -> str:
    """Create (or reuse) a confirmed local test user and return an access token for it."""
    admin = {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}
    password = secrets.token_urlsafe(18)
    found = [u for u in httpx.get(f"{SB}/auth/v1/admin/users", headers=admin, params={"per_page": 200}).json().get("users", []) if u.get("email") == email]
    if found:
        httpx.put(f"{SB}/auth/v1/admin/users/{found[0]['id']}", headers=admin, json={"password": password, "app_metadata": {"partsiq_roles": roles, "partsiq_invited": True}}).raise_for_status()
    else:
        httpx.post(f"{SB}/auth/v1/admin/users", headers=admin, json={"email": email, "password": password, "email_confirm": True, "app_metadata": {"partsiq_roles": roles, "partsiq_invited": True}}).raise_for_status()
    token = httpx.post(f"{SB}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": ANON}, json={"email": email, "password": password})
    token.raise_for_status()
    return token.json()["access_token"]


def H(token: str, key: bool = False) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if key:
        h["Idempotency-Key"] = str(uuid4())
    return h


async def db_counts(enquiry_id: str) -> dict[str, int]:
    conn = await asyncpg.connect(DSN, statement_cache_size=0)
    try:
        return {
            "recommendations": await conn.fetchval("SELECT count(*) FROM messages WHERE enquiry_id=$1 AND kind='recommendation'", enquiry_id),
            "decisions": await conn.fetchval("SELECT count(*) FROM review_decisions WHERE enquiry_id=$1", enquiry_id),
            "runs": await conn.fetchval("SELECT count(*) FROM workflow_runs WHERE enquiry_id=$1", enquiry_id),
            "steps": await conn.fetchval("SELECT count(*) FROM agent_exchanges x JOIN workflow_runs r ON r.id=x.run_id WHERE r.enquiry_id=$1 AND x.kind='step_completed'", enquiry_id),
            "distinct_steps": await conn.fetchval("SELECT count(DISTINCT x.payload->>'step') FROM agent_exchanges x JOIN workflow_runs r ON r.id=x.run_id WHERE r.enquiry_id=$1 AND x.kind='step_completed'", enquiry_id),
            "checkpoints": await conn.fetchval("SELECT count(*) FROM checkpoints WHERE thread_id LIKE $1", f"enquiry:{enquiry_id}%"),
        }
    finally:
        await conn.close()


def main() -> int:
    customer = user("rr-customer@example.test", [])
    admin = user("rr-admin@example.test", ["admin"])
    reviewer = user("rr-reviewer@example.test", ["reviewer"])

    # 1. Create a guided enquiry with slow steps, then kill the API mid-run.
    api = start_api(delay_ms=900)
    c = httpx.Client(timeout=20)
    created = c.post(f"{API}/v1/enquiries?mode=guided", headers=H(customer, True), json={"text": "Need 2 oil filters for a Veltrano Power VP-20, serial 120000", "locale": "en", "destination_warehouse_id": 1})
    check("customer creates an enquiry (database mode)", created.status_code == 202, str(created.status_code))
    eid = created.json()["id"]
    time.sleep(2.2)  # a few steps commit, the rest are still pending
    before = c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(customer)).json()
    steps_before = [e["step"] for e in before["events"]]
    api.send_signal(signal.SIGKILL)
    api.wait()
    check("API killed mid-run (some steps committed, run not finished)", 0 < len(steps_before) < 6 and before["status"] == "processing", ",".join(steps_before))

    # 2. Restart: the same enquiry and run are recovered and the run resumes to review.
    api = start_api(delay_ms=150)
    detail = None
    for _ in range(60):
        detail = c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(customer)).json()
        if detail.get("status") == "awaiting_review":
            break
        time.sleep(0.5)
    check("enquiry recovered after restart", detail and detail["id"] == eid, "")
    check("interrupted run resumed to human review", detail and detail["status"] == "awaiting_review", detail and detail["status"])
    check("same run continued (no new run created)", detail and detail["run"]["id"] == before["run"]["id"], "")
    counts = asyncio.run(db_counts(eid))
    check("no step was executed twice", counts["steps"] == counts["distinct_steps"] == 6, str(counts))
    check("LangGraph checkpoints are in PostgreSQL", counts["checkpoints"] > 0, str(counts["checkpoints"]))

    # 3. Customer signs back in (fresh token) and sees it; unassigned reviewer cannot.
    customer = user("rr-customer@example.test", [])
    check("customer signs back in and sees the enquiry", c.get(f"{API}/v1/enquiries/{eid}/detail", headers=H(customer)).status_code == 200)
    check("unassigned reviewer gets 404", c.get(f"{API}/v1/staff/enquiries/{eid}", headers=H(reviewer)).status_code == 404)

    # 4. Admin assigns; reviewer approves once (retry with same key + different key both replay).
    reviewer_id = [u for u in httpx.get(f"{SB}/auth/v1/admin/users", headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}, params={"per_page": 200}).json()["users"] if u["email"] == "rr-reviewer@example.test"][0]["id"]
    assign = c.put(f"{API}/v1/staff/enquiries/{eid}/assignment", headers=H(admin, True), json={"assignee_id": reviewer_id, "expected_revision": detail["revision"]})
    check("admin assigns the reviewer", assign.status_code == 200, assign.text[:120])
    review = c.get(f"{API}/v1/staff/enquiries/{eid}", headers=H(reviewer)).json()
    key = str(uuid4())
    body = {"enquiry_id": eid, "expected_revision": review["enquiry"]["revision"], "draft_id": review["draft_id"]}
    first = c.post(f"{API}/v1/staff/enquiries/{eid}/approve", headers={**H(reviewer), "Idempotency-Key": key}, json=body)
    check("assigned reviewer approves", first.status_code == 200 and not first.json()["already_applied"], first.text[:120])

    # 5. Restart again: decision and publication persist; replays never publish twice.
    api.send_signal(signal.SIGTERM)
    api.wait()
    api = start_api(delay_ms=150)
    again = c.post(f"{API}/v1/staff/enquiries/{eid}/approve", headers={**H(reviewer), "Idempotency-Key": key}, json=body)
    other = c.post(f"{API}/v1/staff/enquiries/{eid}/approve", headers=H(reviewer, True), json=body)
    check("approval replay after restart is already_applied", again.status_code == 200 and again.json()["already_applied"], again.text[:120])
    check("a second approval key does not publish again", other.status_code == 200 and other.json()["already_applied"], other.text[:120])
    published = c.get(f"{API}/v1/enquiries/{eid}/published-reply", headers=H(customer)).json()
    check("customer sees the persisted published reply", bool(published.get("message")), "")
    counts = asyncio.run(db_counts(eid))
    check("exactly one recommendation and one decision in PostgreSQL", counts["recommendations"] == 1 and counts["decisions"] == 1, str(counts))
    audit = c.get(f"{API}/v1/admin/audit?limit=200", headers=H(admin)).json()["items"]
    actions = {a["action"] for a in audit}
    check("audit trail persisted across restarts", {"enquiry.created", "assignment.changed", "review.approved"} <= actions, ",".join(sorted(actions))[:200])
    api.send_signal(signal.SIGTERM)
    api.wait()

    # 6. Collaboration run: kill mid-exchange, restart, the conversation resumes without repeats.
    api = start_api(delay_ms=700)
    created = c.post(f"{API}/v1/enquiries?mode=collaboration", headers=H(customer, True), json={"text": "Need 2 oil filters for a Veltrano Power VP-20, serial 120000", "locale": "en", "destination_warehouse_id": 1})
    cid = created.json()["id"]
    time.sleep(3.0)
    run_id = c.get(f"{API}/v1/enquiries/{cid}/detail", headers=H(customer)).json()["run"]["id"]
    seen_before = c.get(f"{API}/v1/runs/{run_id}/events", headers=H(customer)).json()["items"]
    api.send_signal(signal.SIGKILL)
    api.wait()
    api = start_api(delay_ms=100)
    final = None
    for _ in range(80):
        final = c.get(f"{API}/v1/runs/{run_id}", headers=H(customer)).json()
        if final.get("status") in ("awaiting_review", "blocked", "failed", "needs_staff"):
            break
        time.sleep(0.5)
    events = c.get(f"{API}/v1/runs/{run_id}/events?limit=200", headers=H(customer)).json()["items"]
    seqs = [e["seq"] for e in events]
    calls = [(e["sender"], e["recipient"], json.dumps(e["payload"].get("args"), sort_keys=True)) for e in events if e["kind"] == "tool_call"]
    check("collaboration killed mid-exchange", 0 < len(seen_before) < len(events), f"{len(seen_before)} of {len(events)} events before kill")
    check("collaboration run resumed to human review", final["status"] == "awaiting_review", final["status"])
    check("exchange sequence is gap-free after restart", seqs == list(range(1, len(seqs) + 1)), "")
    check("no tool call was repeated", len(calls) == len(set(calls)), f"{len(calls)} tool calls")
    api.send_signal(signal.SIGTERM)
    api.wait()

    for name, ok, detail_text in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail_text})' if detail_text else ''}")
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"RESTART-RECOVERY: {'all ' + str(len(results)) + ' checks passed' if not failed else str(failed) + ' failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
