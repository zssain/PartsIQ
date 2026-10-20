"""Live adapters and the worker loop (database mode): PostgreSQL jobs + Redis wake-ups + Storage.

* :class:`PostgresJobStore` implements the existing ``JobStore`` / ``DispatchStore`` /
  ``SweepStore`` ports over the ``jobs`` table: ``FOR UPDATE SKIP LOCKED`` claims with a fresh
  fencing token, lease renewal, token-fenced completion and revision fencing via ``enquiries``.
* :class:`RedisQueue` is only a wake-up channel (``LPUSH``/``BRPOP``). PostgreSQL stays the
  source of truth: a lost push is recovered by the sweeper, so a Redis outage delays jobs but
  never loses them.
* :class:`SupabaseStorage` uploads/downloads private objects and mints 60-second signed URLs with
  the server-only service key.
* Handlers: ``nameplate`` (live vision only when the owner-confirmed allowance permits it —
  otherwise the fixture reader, which recognises only the committed synthetic sample) and
  ``export_pdf`` (approved snapshot → trusted template → Chromium PDF → exports bucket).

The worker never writes workspace aggregates: it records each job's result on its row and the
API (the single writer of the account workspace) applies it.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx

from partsiq.core.contracts import JobLease, JobResult
from partsiq.core.errors import PartsIQError

logger = logging.getLogger("partsiq.worker")
QUEUE_KEY = "partsiq:jobs"


class PostgresJobStore:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def insert_job(self, *, kind: str, payload: dict, dedupe_key: str, enquiry_id: UUID | None, revision: int | None, session_generation: int | None) -> UUID:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO jobs(kind,payload,dedupe_key,enquiry_id,revision,session_generation) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (dedupe_key) DO NOTHING RETURNING id",
                kind, payload, dedupe_key, enquiry_id, revision, session_generation,
            )
            if row is None:
                return await conn.fetchval("SELECT id FROM jobs WHERE dedupe_key=$1", dedupe_key)
            return row["id"]

    async def claim(self, *, job_id: UUID, worker_id: str, token: UUID, lease_seconds: int, now: datetime) -> JobLease | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE jobs SET status='running', lease_token=$2, lease_expires_at=$3, attempts=attempts+1, updated_at=now()
                   WHERE id=(SELECT id FROM jobs WHERE id=$1 AND available_at<=now() AND attempts<max_attempts
                               AND (status='pending' OR (status='running' AND lease_expires_at<now())) FOR UPDATE SKIP LOCKED)
                   RETURNING *""",
                job_id, token, now + timedelta(seconds=lease_seconds),
            )
        if row is None:
            return None
        return JobLease(
            id=row["id"], kind=row["kind"], enquiry_id=row["enquiry_id"], revision=row["revision"],
            session_generation=row["session_generation"], lease_token=row["lease_token"], expires_at=row["lease_expires_at"],
            attempt=row["attempts"], payload={k: v for k, v in row["payload"].items() if isinstance(v, (str, int, bool)) or v is None},
        )

    async def renew(self, *, job_id: UUID, token: UUID, lease_seconds: int, now: datetime) -> bool:
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval("UPDATE jobs SET lease_expires_at=$3, updated_at=now() WHERE id=$1 AND lease_token=$2 AND status='running' RETURNING 1", job_id, token, now + timedelta(seconds=lease_seconds)))

    async def complete(self, *, job_id: UUID, token: UUID, result: JobResult) -> bool:
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval(
                "UPDATE jobs SET status=$3, result=coalesce(result,'{}'::jsonb) || $4, last_error_code=$5, lease_token=NULL, lease_expires_at=NULL, updated_at=now() WHERE id=$1 AND lease_token=$2 AND status='running' RETURNING 1",
                job_id, token, result.status, {"result_id": str(result.result_id) if result.result_id else None}, result.error_code,
            ))

    async def stash_result(self, job_id: UUID, token: UUID, data: dict) -> None:
        """Attach handler output to the still-leased row (applied by the API after completion)."""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET result=coalesce(result,'{}'::jsonb) || $3 WHERE id=$1 AND lease_token=$2", job_id, token, data)

    async def fail(self, job_id: UUID, token: UUID, code: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'pending' END, available_at=now()+interval '5 seconds', last_error_code=$3, lease_token=NULL, lease_expires_at=NULL, updated_at=now() WHERE id=$1 AND lease_token=$2",
                job_id, token, code[:60],
            )

    async def current_fence(self, enquiry_id: UUID) -> tuple[int | None, int | None] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT revision, session_generation FROM enquiries WHERE id=$1", enquiry_id)
        return None if row is None else (row["revision"], row["session_generation"])

    async def find_dispatchable(self, now: datetime) -> list[UUID]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM jobs WHERE (status='pending' AND available_at<=now()) OR (status='running' AND lease_expires_at<now()) ORDER BY created_at LIMIT 50")
        return [r["id"] for r in rows]

    async def reset_to_pending(self, job_id: UUID, now: datetime) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE jobs SET status=CASE WHEN attempts>=max_attempts THEN 'failed' ELSE 'pending' END, last_error_code=CASE WHEN attempts>=max_attempts THEN coalesce(last_error_code,'MAX_ATTEMPTS') ELSE last_error_code END, lease_token=NULL, lease_expires_at=NULL, updated_at=now() WHERE id=$1 AND (status='pending' OR (status='running' AND lease_expires_at<now())) RETURNING status",
                job_id,
            )
        return row is not None and row["status"] == "pending"


class RedisQueue:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(url, socket_timeout=10, socket_connect_timeout=3)

    async def push(self, job_id: UUID) -> None:
        await self._redis.lpush(QUEUE_KEY, str(job_id))

    async def pop(self, timeout: int = 5) -> UUID | None:
        item = await self._redis.brpop([QUEUE_KEY], timeout=timeout)
        return UUID(item[1].decode()) if item else None

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:  # noqa: BLE001
            return False

    async def close(self) -> None:
        await self._redis.aclose()


class SupabaseStorage:
    """Server-side private object storage over the Supabase Storage REST API (service key)."""

    def __init__(self, url: str, service_key: str) -> None:
        self._base = url.rstrip("/") + "/storage/v1"
        headers = {"apikey": service_key}
        if not service_key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {service_key}"
        self._headers = headers

    async def upload(self, bucket: str, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            response = await client.post(f"{self._base}/object/{bucket}/{object_key}", content=data, headers={"content-type": content_type, "x-upsert": "true"})
            if response.status_code >= 300:
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"storage upload {response.status_code}")

    async def download(self, object_key: str, media_type: str = "", bucket: str = "nameplates") -> bytes:
        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            response = await client.get(f"{self._base}/object/{bucket}/{object_key}")
            if response.status_code >= 300:
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"storage download {response.status_code}")
            return response.content

    async def sign(self, bucket: str, object_key: str, seconds: int = 60) -> str:
        async with httpx.AsyncClient(timeout=15, headers=self._headers) as client:
            response = await client.post(f"{self._base}/object/sign/{bucket}/{object_key}", json={"expiresIn": seconds})
            if response.status_code >= 300:
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", internal_detail=f"storage sign {response.status_code}")
            signed = response.json().get("signedURL") or response.json().get("signedUrl")
            return self._base + signed if signed.startswith("/object") else self._base.rsplit("/storage/v1", 1)[0] + "/storage/v1" + signed


# ----------------------------------------------------------------------------- handlers


def _fixture_plates() -> dict[str, tuple[str, str]]:
    """sha256 -> identifiers for the committed synthetic nameplate fixtures (fixture vision)."""
    from pathlib import Path

    from partsiq.workspace.steps import _FIXTURE_PLATES

    root = Path(__file__).resolve().parents[1] / "workspace" / "assets"
    return {hashlib.sha256((root / name).read_bytes()).hexdigest(): ids for name, ids in _FIXTURE_PLATES.items() if (root / name).exists()}


async def handle_nameplate(lease: JobLease, *, storage: SupabaseStorage, store: PostgresJobStore, settings: Any) -> JobResult:
    """Read one private nameplate image. Live vision only when the settings gate allows it.

    ``Settings`` refuses ``AI_MODE=live`` without a confirmed, unexpired allowance, so the live
    branch is unreachable on a zero allowance. The fixture reader recognises only the committed
    synthetic sample by content hash; any other image is ``unreadable`` (never invented).
    """
    from partsiq.jobs.repository import finish_job

    image = await storage.download(str(lease.payload["object_key"]))
    if settings.ai_mode == "live":
        from partsiq.ai.client import build_openai_client
        from partsiq.ai.vision import read_nameplate

        client = build_openai_client(api_key=settings.openai_api_key, allow_live=True)
        result = await read_nameplate(lease, image, client=client, model=settings.openai_vision_model or "gpt-4o", allow_live=True)
        reading = {"model_text": result.model_text, "serial_text": result.serial_text, "issues": list(result.issues), "source": "live"}
    else:
        ids = _fixture_plates().get(hashlib.sha256(image).hexdigest())
        reading = {"model_text": ids[0], "serial_text": ids[1], "issues": [], "source": "fixture"} if ids else {"model_text": None, "serial_text": None, "issues": ["unreadable"], "source": "fixture"}
    await store.stash_result(lease.id, lease.lease_token, {"reading": reading})
    committed = await finish_job(lease, JobResult(status="succeeded", result_id=None, error_code=None), store=store)
    if not committed:
        # Superseded revision or lost lease: the reading must not land over newer data.
        async with store.pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET status='cancelled', last_error_code='STALE_REVISION', lease_token=NULL, lease_expires_at=NULL, updated_at=now() WHERE id=$1 AND lease_token=$2", lease.id, lease.lease_token)
    return JobResult(status="succeeded" if committed else "cancelled", result_id=None, error_code=None if committed else "STALE_REVISION")


class NameplateDispatcher:
    """API side of the nameplate job: stage the image privately, enqueue, await the reading.

    The API stays the single writer of the enquiry: it applies the worker's reading itself.
    The job is deduplicated per attachment, so a restarted run re-attaches to the same job
    instead of reading the photo twice.
    """

    def __init__(self, pool: Any, queue: RedisQueue | None, storage: SupabaseStorage, *, wait_seconds: float = 90.0) -> None:
        self.pool = pool
        self.store = PostgresJobStore(pool)
        self.queue = queue
        self.storage = storage
        self.wait_seconds = wait_seconds

    async def stage(self, enquiry_id: UUID, attachment_id: UUID, data: bytes, media_type: str) -> str:
        key = f"account/{enquiry_id}/{attachment_id}"
        await self.storage.upload("nameplates", key, data, media_type)
        return key

    async def read(self, *, enquiry_id: UUID, revision: int, attachment_id: UUID, object_key: str) -> dict[str, Any]:
        from partsiq.jobs.repository import enqueue_job

        dedupe = f"nameplate:{attachment_id}:{revision}"
        job_id = await enqueue_job(
            kind="nameplate", payload={"attachment_id": str(attachment_id), "object_key": object_key}, dedupe_key=dedupe,
            enquiry_id=enquiry_id, revision=revision, session_generation=None, store=self.store, queue=self.queue or _NoQueue(),
        )
        deadline = asyncio.get_running_loop().time() + self.wait_seconds
        while True:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT status, result, last_error_code FROM jobs WHERE id=$1", job_id)
            if row["status"] == "succeeded" and row["result"] and row["result"].get("reading"):
                return dict(row["result"]["reading"])
            if row["status"] in ("failed", "cancelled"):
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", detail="The nameplate photo could not be read. Staff can retry.", internal_detail=f"nameplate job {row['status']}: {row['last_error_code']}")
            if asyncio.get_running_loop().time() > deadline:
                raise PartsIQError("DEPENDENCY_UNAVAILABLE", detail="The nameplate reader is not responding. Staff can retry.", internal_detail="nameplate job wait timed out")
            await asyncio.sleep(0.5)


class PostgresExportSource:
    """F61 port (database mode): queue an approved-snapshot PDF export; sign its download.

    Access: the enquiry's owner, its assignee, or an administrator; anything else is NOT_FOUND
    (no existence leak). Only a recorded approval of that exact revision can be exported.
    """

    def __init__(self, pool: Any, queue: RedisQueue | None, storage: SupabaseStorage) -> None:
        self.pool = pool
        self.store = PostgresJobStore(pool)
        self.queue = queue
        self.storage = storage

    async def _visible(self, conn: Any, actor: Any, enquiry_id: UUID) -> bool:
        from partsiq.auth.actors import actor_kind

        if actor_kind(actor) != "account":
            return False  # demo sandboxes are in memory; their PDFs are not exported
        row = await conn.fetchrow("SELECT owner_id, assigned_to FROM enquiries WHERE id=$1", enquiry_id)
        return row is not None and ("admin" in actor.roles or actor.user_id in (row["owner_id"], row["assigned_to"]))

    async def request_pdf(self, actor: Any, request: Any, key: UUID) -> Any:
        from partsiq.jobs.repository import enqueue_job

        async with self.pool.acquire() as conn:
            if not await self._visible(conn, actor, request.enquiry_id):
                raise PartsIQError("NOT_FOUND")
            approved = await conn.fetchval(
                "SELECT 1 FROM review_decisions WHERE id=$1 AND enquiry_id=$2 AND revision=$3 AND decision IN ('approved','edited')",
                request.decision_id, request.enquiry_id, request.revision,
            )
        if not approved:
            raise PartsIQError("CONFLICT", detail="Only an approved revision can be exported")
        # One export per approved revision: the dedupe key makes retries and double clicks safe.
        job_id = await enqueue_job(
            kind="export_pdf", payload={"enquiry_id": str(request.enquiry_id), "revision": request.revision, "decision_id": str(request.decision_id)},
            dedupe_key=f"export:{request.enquiry_id}:{request.revision}", enquiry_id=request.enquiry_id, revision=request.revision,
            session_generation=None, store=self.store, queue=self.queue or _NoQueue(),
        )
        return await self.job_view(job_id)

    async def job_view(self, job_id: UUID) -> Any:
        from partsiq.core.api_models import JobView

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, status, kind, attempts, last_error_code, result FROM jobs WHERE id=$1", job_id)
        result = row["result"] or {}
        return JobView(id=row["id"], status=row["status"], kind=row["kind"], attempts=row["attempts"], error_code=row["last_error_code"], resource_id=UUID(result["export_id"]) if result.get("export_id") else None)

    async def sign_download(self, actor: Any, export_id: UUID) -> Any:
        from partsiq.core.contracts import DownloadTicket

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT enquiry_id, storage_key, status FROM exports WHERE id=$1", export_id)
            if row is None or not await self._visible(conn, actor, row["enquiry_id"]):
                raise PartsIQError("NOT_FOUND")
        if row["status"] != "ready" or not row["storage_key"]:
            raise PartsIQError("CONFLICT", detail="The export is not ready yet")
        url = await self.storage.sign("exports", row["storage_key"], 60)
        return DownloadTicket(url=url, expires_at=datetime.now(UTC) + timedelta(seconds=60))


class _NoQueue:
    async def push(self, job_id: UUID) -> None:  # Redis absent: the worker's sweeper dispatches it
        return None


def reply_html(text: str) -> str:
    """Approved plain-text reply -> escaped HTML with line breaks kept.

    The export template marks ``reply`` ``|safe``; escaping here guarantees no stored string can
    become markup in the PDF.
    """
    return "<br>".join(html.escape(line) for line in text.splitlines())


async def chromium_pdf(document: str) -> bytes:
    """Render trusted HTML to A4 PDF in headless Chromium with ALL network access refused.

    The page is loaded from a private temp file so its bundled ``file://`` fonts and logo
    resolve; any http(s)/other request is aborted.
    """
    import tempfile
    from pathlib import Path

    from playwright.async_api import async_playwright

    with tempfile.TemporaryDirectory(prefix="partsiq-export-") as tmp:
        page_path = Path(tmp) / "export.html"
        page_path.write_text(document, encoding="utf-8")
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                page = await browser.new_page()
                await page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file://") else route.abort())
                await page.goto(page_path.as_uri(), wait_until="load")
                return await page.pdf(format="A4", print_background=True, margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
            finally:
                await browser.close()


async def handle_export(lease: JobLease, *, storage: SupabaseStorage, store: PostgresJobStore, pool: Any) -> JobResult:
    from partsiq.core.contracts import ApprovedSnapshot, ExportRequest, VerifiedFacts
    from partsiq.exports.service import export_enquiry

    request = ExportRequest(enquiry_id=UUID(str(lease.payload["enquiry_id"])), revision=int(lease.payload["revision"]), decision_id=UUID(str(lease.payload["decision_id"])))

    async def load_snapshot(enquiry_id: UUID, revision: int, decision_id: UUID) -> ApprovedSnapshot | None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT d.decided_at, d.final_reply, e.locale, dr.verified_facts FROM review_decisions d JOIN enquiries e ON e.id=d.enquiry_id
                   LEFT JOIN drafts dr ON dr.enquiry_id=d.enquiry_id AND dr.revision=d.revision
                   WHERE d.id=$1 AND d.enquiry_id=$2 AND d.revision=$3 AND d.decision IN ('approved','edited')""",
                decision_id, enquiry_id, revision,
            )
        if row is None or row["verified_facts"] is None:
            return None
        return ApprovedSnapshot(decision_id=decision_id, approved_at=row["decided_at"], locale=row["locale"] or "en", facts=VerifiedFacts.model_validate_json(json.dumps(row["verified_facts"])), reply=reply_html(row["final_reply"] or ""), synthetic=True)

    class _Uploader:
        async def upload(self, bucket: str, object_key: str, data: bytes) -> None:
            await storage.upload(bucket, object_key, data, "application/pdf")

    async def record_writer(lease: JobLease, req: ExportRequest, storage_key: str, sha256: str) -> UUID:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO exports(enquiry_id,revision,decision_id,job_id,storage_key,sha256,status) VALUES ($1,$2,$3,$4,$5,$6,'ready')
                   ON CONFLICT (enquiry_id,revision) DO UPDATE SET storage_key=EXCLUDED.storage_key, sha256=EXCLUDED.sha256, status='ready', job_id=EXCLUDED.job_id RETURNING id""",
                req.enquiry_id, req.revision, req.decision_id, lease.id, storage_key, sha256,
            )

    result = await export_enquiry(request, lease=lease, load_snapshot=load_snapshot, render_pdf=chromium_pdf, uploader=_Uploader(), record_writer=record_writer, job_store=store)
    await store_result_after(store, lease.id, {"export_id": str(result.export_id), "storage_key": result.storage_key, "sha256": result.sha256})
    return JobResult(status="succeeded", result_id=result.export_id, error_code=None)


async def store_result_after(store: PostgresJobStore, job_id: UUID, data: dict) -> None:
    async with store.pool.acquire() as conn:
        await conn.execute("UPDATE jobs SET result=coalesce(result,'{}'::jsonb) || $2 WHERE id=$1", job_id, data)


# ----------------------------------------------------------------------------- loop


async def run_worker(settings: Any, *, stop: asyncio.Event | None = None, once: bool = False, sweep_only: bool = False) -> None:
    """Claim and run jobs, sweeping stranded ones every 10 s.

    ``sweep_only`` (the compose ``--sweeper`` service) only re-dispatches expired/stranded jobs and
    never runs one, so a small container never launches Chromium.
    """
    import asyncpg

    from partsiq.jobs.repository import claim_job, heartbeat
    from partsiq.jobs.sweeper import sweep_once
    from partsiq.persistence.workspace_store import _init

    if not settings.database_url_worker and not settings.database_url_api:
        raise RuntimeError("worker: no database configured")
    pool = await asyncpg.create_pool(settings.database_url_worker or settings.database_url_api, min_size=1, max_size=4, statement_cache_size=0, init=_init)
    store = PostgresJobStore(pool)
    queue = RedisQueue(settings.redis_url)
    if not await queue.ping():
        logger.warning("worker: Redis unavailable; relying on the PostgreSQL sweeper only")
    storage = SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    stop = stop or asyncio.Event()
    worker_id = f"worker-{uuid4().hex[:8]}"
    last_sweep = 0.0
    logger.info("worker %s started%s", worker_id, " (sweep only)" if sweep_only else "")
    try:
        while sweep_only and not stop.is_set():
            await sweep_once(datetime.now(UTC), store=store, queue=queue)
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=10)
            except TimeoutError:
                pass
        while not stop.is_set():
            loop_time = asyncio.get_running_loop().time()
            if loop_time - last_sweep > 10:
                await sweep_once(datetime.now(UTC), store=store, queue=queue)
                last_sweep = loop_time
            job_id = None
            try:
                job_id = await queue.pop(timeout=2)
            except Exception:  # noqa: BLE001 - Redis is only the wake-up channel
                # Redis down: poll PostgreSQL directly (the row is the source of truth), so an
                # outage slows dispatch to the poll cadence but never strands a job.
                due = await store.find_dispatchable(datetime.now(UTC))
                job_id = due[0] if due else None
                if job_id is None:
                    await asyncio.sleep(2)
            if job_id is None:
                if once:
                    break
                continue
            lease = await claim_job(job_id, worker_id, store=store)
            if lease is None:
                continue
            beat = asyncio.create_task(_beat(lease, store, heartbeat))
            try:
                if lease.kind == "nameplate":
                    await handle_nameplate(lease, storage=storage, store=store, settings=settings)
                elif lease.kind == "export_pdf":
                    await handle_export(lease, storage=storage, store=store, pool=pool)
                else:
                    await store.fail(lease.id, lease.lease_token, "UNSUPPORTED_KIND")
            except PartsIQError as exc:
                logger.warning("job %s failed: %s", lease.id, exc.code)
                await store.fail(lease.id, lease.lease_token, exc.code)
            except Exception as exc:  # noqa: BLE001
                logger.exception("job %s crashed", lease.id)
                await store.fail(lease.id, lease.lease_token, type(exc).__name__)
            finally:
                beat.cancel()
            if once:
                break
    finally:
        await queue.close()
        await pool.close()


async def _beat(lease: JobLease, store: PostgresJobStore, heartbeat: Any) -> None:
    from partsiq.jobs.repository import _lease_seconds

    while True:
        await asyncio.sleep(max(1.0, _lease_seconds() / 3))
        if not await heartbeat(lease, store=store):
            return


def main() -> None:
    from partsiq.core.settings import load_settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = asyncio.Event()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)  # drain: finish the current job, claim no new one
        await run_worker(load_settings(), stop=stop, sweep_only="--sweeper" in sys.argv[1:])

    asyncio.run(_run())


if __name__ == "__main__":
    main()
