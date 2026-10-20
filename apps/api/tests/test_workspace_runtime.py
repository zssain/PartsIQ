"""Workspace runtime (ADR 0002): guided + collaboration runs, server-enforced controls, policy,
limits, isolation, account RBAC, imports and approval re-checks.

All execution is FIXTURE (deterministic, no provider calls) or uses INJECTED specialists; nothing
here is evidence of live OpenAI behaviour.
"""
from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from partsiq.auth.actors import AccountActorContext, capabilities_for
from partsiq.core.errors import PartsIQError
from partsiq.core.settings import Settings
from partsiq.main import create_app
from partsiq.workspace import collaboration as collab

RESOLVES = "Need 2 oil filters for a Veltrano Power VP-20, serial 120000"
MISSING_SERIAL = "I need a hydraulic filter for a Corvane Air CA-110."
AMBIGUOUS = "Need a filter for VP-60 serial 210000"
INCOMPATIBLE = "Need 1 CA-AF-1828 for my Corvane Air CA-110 (A)"


def _client(**overrides) -> TestClient:
    settings = Settings(**{"app_env": "test", "data_source": "fixture", "fixture_step_delay_ms": 0, **overrides})
    return TestClient(create_app(settings))


@pytest.fixture()
def client():
    with _client() as c:
        yield c


def H(token: str = "t1", key: bool = False) -> dict[str, str]:
    headers = {"X-Demo-Token": token}
    if key:
        headers["Idempotency-Key"] = str(uuid4())
    return headers


def create(client: TestClient, text: str, *, mode: str = "guided", token: str = "t1") -> str:
    r = client.post(f"/v1/enquiries?mode={mode}", headers=H(token, True), json={"text": text, "locale": "en", "destination_warehouse_id": 1})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def detail(client: TestClient, eid: str, token: str = "t1") -> dict:
    r = client.get(f"/v1/enquiries/{eid}/detail", headers=H(token))
    assert r.status_code == 200, r.text
    return r.json()


def events(client: TestClient, run_id: str, token: str = "t1") -> list[dict]:
    return client.get(f"/v1/runs/{run_id}/events?after=0&limit=200", headers=H(token)).json()["items"]


def command(client: TestClient, run_id: str, body: dict, *, token: str = "t1", key: str | None = None):
    headers = H(token)
    headers["Idempotency-Key"] = key or str(uuid4())
    return client.post(f"/v1/runs/{run_id}/commands", headers=headers, json=body)


def wait_for(fn, timeout: float = 8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition not reached")


# ============================================================ guided mode


def test_guided_run_reaches_review_with_a_real_compatible_part(client: TestClient) -> None:
    eid = create(client, RESOLVES)
    d = detail(client, eid)
    assert d["status"] == "awaiting_review"
    item = d["items"][0]
    assert item["selected"]["part_number"] == "VP-OF-2824"  # seed-42 oil filter for VP-20 config A
    assert item["configuration_label"].endswith("configuration A")
    assert item["plan"]["lines"] and d["verification"]["passed"] is True
    assert d["run"]["mode"] == "guided" and d["run"]["execution_source"] == "fixture"
    steps = [e["payload"]["step"] for e in events(client, d["run"]["id"]) if e["kind"] == "step_completed"]
    assert steps == ["intake", "identify", "search", "plan", "draft", "verify"]


def test_missing_serial_clarification_answer_resumes_with_a_new_revision(client: TestClient) -> None:
    eid = create(client, MISSING_SERIAL)
    d = detail(client, eid)
    assert d["status"] == "needs_information" and d["pending_code"] == "needs_serial"
    run_id = d["run"]["id"]
    assert d["run"]["status"] == "waiting_user" and d["pending"][0]["kind"] == "clarification"
    r = command(client, run_id, {"type": "answer", "expected_revision": 1, "payload": {"text": "The serial is 812345"}})
    assert r.status_code == 202, r.text
    d2 = detail(client, eid)
    assert d2["revision"] == 2 and d2["run"]["id"] != run_id
    old = client.get(f"/v1/runs/{run_id}", headers=H()).json()
    assert old["status"] == "superseded" and old["stale"] is True
    # The hydraulic filter for CA-110 config A is a single compatible part.
    assert d2["status"] in ("awaiting_review", "needs_information")
    assert d2["items"][0]["configuration_label"].endswith("configuration A")


def test_unparseable_answer_is_422_and_keeps_the_question_open(client: TestClient) -> None:
    eid = create(client, MISSING_SERIAL)
    run_id = detail(client, eid)["run"]["id"]
    r = command(client, run_id, {"type": "answer", "expected_revision": 1, "payload": {"text": "I don't know"}})
    assert r.status_code == 422
    assert detail(client, eid)["pending"][0]["status"] == "open"


# ============================================================ collaboration mode


def test_collaboration_run_has_real_addressed_exchanges(client: TestClient) -> None:
    eid = create(client, RESOLVES, mode="collaboration")
    d = detail(client, eid)
    assert d["status"] == "awaiting_review" and d["run"]["mode"] == "collaboration"
    ex = events(client, d["run"]["id"])
    pairs = [(e["sender"], e["recipient"], e["kind"]) for e in ex]
    assert ("controller", "intake", "task") in pairs
    assert ("intake", "identification", "tool_call") in pairs
    assert ("identification", "intake", "tool_result") in pairs
    assert ("intake", "parts", "handoff") in pairs
    assert ("parts", "compatibility_search", "tool_call") in pairs
    assert ("parts", "fulfilment", "tool_call") in pairs
    assert ("parts", "reply", "proposal") in pairs
    assert ("reply", "verification", "tool_call") in pairs
    assert ("reply", "controller", "ready_for_review") in pairs
    # Ordered, gap-free sequence numbers (reconnect/dedupe rely on this).
    assert [e["seq"] for e in ex] == list(range(1, len(ex) + 1))
    # Every tool result answers a specific tool call.
    calls = {e["id"] for e in ex if e["kind"] == "tool_call"}
    assert all(e["reply_to"] in calls for e in ex if e["kind"] == "tool_result")
    # The proposal names the code-computed compatible part, not a model choice.
    proposal = next(e for e in ex if e["kind"] == "proposal")
    assert proposal["payload"]["items"][0]["part_number"] == "VP-OF-2824"


def test_collaboration_ambiguity_becomes_a_customer_clarification(client: TestClient) -> None:
    eid = create(client, AMBIGUOUS, mode="collaboration")
    d = detail(client, eid)
    assert d["run"]["status"] == "waiting_user"
    assert d["pending"][0]["code"] == "ambiguous_part" and len(d["pending"][0]["options"]) >= 2
    ex = events(client, d["run"]["id"])
    assert any(e["sender"] == "parts" and e["recipient"] == "customer" and e["kind"] == "clarification_request" for e in ex)
    # Answer by choosing one option: a new revision continues collaboration and reaches review.
    choice = d["pending"][0]["options"][0]["part_number"]
    r = command(client, d["run"]["id"], {"type": "answer", "expected_revision": d["revision"], "payload": {"text": f"I need {choice}, 1 unit"}})
    assert r.status_code == 202, r.text
    d2 = detail(client, eid)
    assert d2["run"]["mode"] == "collaboration" and d2["run"]["carried_from"] == d["run"]["id"]


def test_incompatible_number_needs_consent_before_delegated_search(client: TestClient) -> None:
    eid = create(client, INCOMPATIBLE, mode="collaboration")
    d = detail(client, eid)
    assert d["run"]["status"] == "waiting_consent"
    pending = d["pending"][0]
    assert pending["kind"] == "delegation_consent" and pending["requested_by"] == "parts"
    run_id = d["run"]["id"]
    before = len(events(client, run_id))
    time.sleep(0.2)
    assert len(events(client, run_id)) == before  # nothing dispatched while waiting for consent
    r = command(client, run_id, {"type": "resolve_delegation", "expected_revision": d["revision"], "payload": {"decision": "approve"}})
    assert r.status_code == 202, r.text
    ex = wait_for(lambda: [e for e in events(client, run_id) if e["kind"] == "tool_result" and e["payload"].get("mode") == "alternatives"])
    assert ex, "delegated alternative search ran only after consent"
    assert any(e["kind"] == "consent_result" and e["recipient"] == "parts" for e in events(client, run_id))


# ============================================================ controller policy


def test_policy_rejects_unsupported_routes_kinds_tools_and_arguments() -> None:
    items = {"i1"}
    bad = [
        ("parts", collab.Action("handoff", "reply", "x")),  # kind not allowed for parts
        ("intake", collab.Action("proposal", "reply", "x")),  # intake cannot propose
        ("reply", collab.Action("tool_call", "fulfilment", "x", tool="fulfilment", args={"item_id": "i1"})),  # tool not allow-listed
        ("parts", collab.Action("tool_call", "fulfilment", "x", tool="fulfilment", args={"item_id": "i1", "quantity": 9})),  # arg injection
        ("parts", collab.Action("tool_call", "compatibility_search", "x", tool="compatibility_search", args={"item_id": "other"})),  # foreign item
        ("parts", collab.Action("request_info", "customer", "x")),  # recipient not allowed
        ("intake", collab.Action("handoff", "parts", "x" * 700)),  # oversized summary
        ("parts", collab.Action("delegation_request", "compatibility_search", "x", {"action": "approve_reply", "item_id": "i1"})),
    ]
    for sender, action in bad:
        with pytest.raises(collab.PolicyViolation):
            collab.validate_action(sender, action, max_bytes=4096, item_ids=items)
    collab.validate_action("parts", collab.Action("tool_call", "compatibility_search", "ok", tool="compatibility_search", args={"item_id": "i1"}), max_bytes=4096, item_ids=items)


class _RogueParts:
    """Injected specialist that proposes an incompatible part and claims readiness."""

    name = "parts"
    source = "fixture"

    async def respond(self, message, board):
        item_id = board["items"][0]["item_id"]
        return collab.Turn([
            collab.Action("proposal", "reply", "Use part 999 instead.", {"items": [{"item_id": item_id, "part_id": 999, "part_number": "FAKE-1", "source_reference": "made up"}]}),
        ])


def _inject(client: TestClient, overrides: dict) -> None:
    service = client.app.state.container.runtime
    original = service._specialists_for

    def patched(ws, run):
        specs = original(ws, run)
        specs.update(overrides)
        return specs

    service._specialists_for = patched
    service.executor._specialists_for = patched


def test_model_output_cannot_override_compatibility(client: TestClient) -> None:
    _inject(client, {"parts": _RogueParts()})
    eid = create(client, RESOLVES, mode="collaboration")
    d = detail(client, eid)
    ex = events(client, d["run"]["id"])
    rejected = [e for e in ex if e["kind"] == "action_rejected"]
    assert rejected and rejected[0]["payload"]["code"] in ("ITEM_NOT_READY", "NOT_COMPATIBLE")
    assert d["status"] != "awaiting_review"  # nothing reached review on a rogue proposal
    assert d["run"]["status"] in ("blocked",) and d["run"]["blocked_reason"] in ("loop_detected", "no_progress")


class _LoopingIntake:
    name = "intake"
    source = "fixture"

    async def respond(self, message, board):
        return collab.Turn([collab.Action("request_info", "parts", "ping")])


class _LoopingParts:
    name = "parts"
    source = "fixture"

    async def respond(self, message, board):
        return collab.Turn([collab.Action("request_info", "intake", "pong")])


def test_repeated_identical_exchanges_stop_a_loop(client: TestClient) -> None:
    _inject(client, {"intake": _LoopingIntake(), "parts": _LoopingParts()})
    eid = create(client, RESOLVES, mode="collaboration")
    run = detail(client, eid)["run"]
    assert run["status"] == "blocked" and run["blocked_reason"] in ("loop_detected", "no_progress")
    ex = events(client, run["id"])
    assert any(e["kind"] == "action_rejected" and e["payload"]["code"] == "REPEATED_EXCHANGE" for e in ex)


def test_agent_turn_limit_blocks_and_preserves_work() -> None:
    with _client(run_max_agent_turns=2) as c:
        eid = create(c, RESOLVES, mode="collaboration")
        d = detail(c, eid)
        assert d["run"]["status"] == "blocked" and d["run"]["blocked_reason"] == "agent_turns"
        assert d["run"]["usage"]["agent_turns"] == 2
        assert "fixture_replay" in d["run"]["available_actions"]
        assert d["items"][0]["configuration_label"]  # completed work kept
        assert d["status"] != "awaiting_review"  # no fabricated success


def test_tool_call_limit_blocks() -> None:
    with _client(run_max_tool_calls=1) as c:
        d = detail(c, create(c, RESOLVES, mode="collaboration"))
        assert d["run"]["blocked_reason"] == "tool_calls"


def test_live_is_never_selected_without_a_confirmed_allowance(client: TestClient) -> None:
    status = client.get("/v1/workspace/status", headers=H()).json()
    assert status["live_available"] is False and status["live_unavailable_reason"]
    d = detail(client, create(client, RESOLVES, mode="collaboration"))
    assert d["run"]["execution_source"] == "fixture"
    assert d["run"]["usage"]["output_tokens"] is None  # not measured, not zero


def test_run_budget_blocks_instead_of_spending_without_allowance() -> None:
    from partsiq.workspace.limits import LimitReached, RunBudget, RunLimits
    from partsiq.workspace.records import RunUsage

    limits = RunLimits.from_settings(Settings(app_env="test"))
    budget = RunBudget(ledger=None, model="gpt-4.1-mini", limits=limits, usage=RunUsage())
    with pytest.raises(PartsIQError) as exc:
        asyncio.run(budget.reserve("intake", 100))
    assert exc.value.code == "CREDIT_UNAVAILABLE"
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from partsiq.ai.budget import InMemoryBudgetLedger
    from partsiq.core.contracts import CreditAllowance

    ledger = InMemoryBudgetLedger(allowance=CreditAllowance(amount_usd=Decimal("0.0001"), expires_at=datetime.now(timezone.utc) + timedelta(days=1), paid_budget_usd=Decimal("0")))
    tight = RunBudget(ledger=ledger, model="gpt-4.1-mini", limits=limits, usage=RunUsage())
    with pytest.raises(LimitReached) as limit:
        asyncio.run(tight.reserve("intake", 400))
    assert limit.value.reason in ("allowance_exhausted", "run_allowance")


# ============================================================ master controls


def test_pause_stops_dispatch_resume_continues_and_cancel_fences() -> None:
    with _client(fixture_step_delay_ms=150) as c:
        eid = create(c, RESOLVES)
        run_id = detail(c, eid)["run"]["id"]
        r = command(c, run_id, {"type": "pause", "expected_revision": 1})
        assert r.status_code == 202, r.text
        wait_for(lambda: c.get(f"/v1/runs/{run_id}", headers=H()).json()["status"] == "paused")
        count = len(events(c, run_id))
        time.sleep(0.6)
        assert len(events(c, run_id)) == count  # no new step dispatched while paused
        assert detail(c, eid)["status"] == "processing"
        r = command(c, run_id, {"type": "resume", "expected_revision": 1})
        assert r.status_code == 202, r.text
        wait_for(lambda: detail(c, eid)["status"] == "awaiting_review")
        steps = [e["payload"]["step"] for e in events(c, run_id) if e["kind"] == "step_completed"]
        assert steps == ["intake", "identify", "search", "plan", "draft", "verify"]  # nothing replayed

        # Cancel a separate run mid-flight: its late result is discarded and it cannot publish.
        eid2 = create(c, RESOLVES)
        run2 = detail(c, eid2)["run"]["id"]
        wait_for(lambda: c.get(f"/v1/runs/{run2}", headers=H()).json()["in_flight"])
        r = command(c, run2, {"type": "cancel", "expected_revision": 1})
        assert r.status_code == 202
        time.sleep(0.6)
        run = c.get(f"/v1/runs/{run2}", headers=H()).json()
        assert run["status"] == "cancelled"
        d2 = detail(c, eid2)
        assert d2["status"] != "awaiting_review" and d2["published_reply"] is None
        ws = c.get(f"/v1/staff/enquiries/{eid2}", headers=H()).json()
        approve = c.post(f"/v1/staff/enquiries/{eid2}/approve", headers=H(key=True), json={"enquiry_id": eid2, "expected_revision": 1, "draft_id": ws.get("draft_id") or str(uuid4())})
        assert approve.status_code == 409


def test_commands_are_idempotent_and_reject_stale_or_mismatched_requests(client: TestClient) -> None:
    eid = create(client, MISSING_SERIAL)
    run_id = detail(client, eid)["run"]["id"]
    key = str(uuid4())
    body = {"type": "instruct", "expected_revision": 1, "payload": {"text": "Please mention delivery timing."}}
    first = command(client, run_id, body, key=key)
    second = command(client, run_id, body, key=key)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"] and second.json()["replayed"] is True
    other = command(client, run_id, {**body, "payload": {"text": "different"}}, key=key)
    assert other.status_code == 409 and other.json()["code"] == "IDEMPOTENCY_MISMATCH"
    stale = command(client, run_id, {"type": "cancel", "expected_revision": 7})
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_REVISION"
    bad = command(client, run_id, {"type": "drop_tables", "expected_revision": 1})
    assert bad.status_code == 422


def test_instruction_with_facts_is_flagged_not_applied(client: TestClient) -> None:
    eid = create(client, MISSING_SERIAL, mode="collaboration")
    run_id = detail(client, eid)["run"]["id"]
    r = command(client, run_id, {"type": "instruct", "expected_revision": 1, "payload": {"text": "Actually the serial is 845000"}})
    assert r.status_code == 202 and "factual" in r.json()["result"]
    d = detail(client, eid)
    assert d["revision"] == 1 and d["items"][0]["serial_text"] is None  # facts change only via a revision


def test_mode_change_needs_a_new_run_and_keeps_history(client: TestClient) -> None:
    eid = create(client, MISSING_SERIAL)
    d = detail(client, eid)
    busy = client.post(f"/v1/enquiries/{eid}/runs", headers=H(key=True), json={"mode": "collaboration", "expected_revision": 1})
    assert busy.status_code == 409  # an in-flight/waiting run is never switched to another mode
    command(client, d["run"]["id"], {"type": "cancel", "expected_revision": 1})
    started = client.post(f"/v1/enquiries/{eid}/runs", headers=H(key=True), json={"mode": "collaboration", "expected_revision": 1})
    assert started.status_code == 202, started.text
    runs = client.get(f"/v1/enquiries/{eid}/runs", headers=H()).json()
    assert {r["mode"] for r in runs} == {"guided", "collaboration"} and len(runs) >= 2


# ============================================================ isolation


def test_demo_sessions_cannot_read_or_control_each_others_runs(client: TestClient) -> None:
    eid = create(client, RESOLVES, token="alice")
    run_id = detail(client, eid, token="alice")["run"]["id"]
    for path in (f"/v1/enquiries/{eid}/detail", f"/v1/runs/{run_id}", f"/v1/runs/{run_id}/events", f"/v1/enquiries/{eid}/runs"):
        assert client.get(path, headers=H("mallory")).status_code == 404
    assert command(client, run_id, {"type": "cancel", "expected_revision": 1}, token="mallory").status_code == 404


def test_demo_reset_abandons_the_previous_generation(client: TestClient) -> None:
    eid = create(client, RESOLVES, token="resetter")
    me = client.get("/v1/me", headers=H("resetter")).json()
    assert me["kind"] == "demo" and me["roles"] == [] and "admin.users" in me["capabilities"]
    r = client.post(f"/v1/demo/sessions/{me['demo_session_id']}/reset", headers=H("resetter", True), json={"expected_revision": 1})
    assert r.status_code == 201 and r.json()["generation"] == me["demo_session_generation"] + 1
    assert client.get(f"/v1/enquiries/{eid}/detail", headers=H("resetter")).status_code == 404
    stale = {**H("resetter"), "X-Demo-Session-Id": me["demo_session_id"], "X-Demo-Session-Generation": str(me["demo_session_generation"])}
    assert client.get("/v1/workspace/dashboard", headers=stale).status_code == 404


# ============================================================ accounts / RBAC


async def _account_flow() -> None:
    from partsiq.workspace.catalogue import fixture_catalogue_context  # noqa: F401
    from partsiq.catalogue.fixtures import build_catalogue
    from partsiq.core.contracts import EnquiryCreate
    from partsiq.core.api_models import InboxQuery
    from partsiq.workspace.service import WorkspaceService

    settings = Settings(app_env="test", fixture_step_delay_ms=0)
    snapshot = build_catalogue()
    service = WorkspaceService(settings=settings, snapshot_factory=lambda: snapshot)
    customer = AccountActorContext(user_id=uuid4(), request_id=uuid4(), roles=[])
    reviewer = AccountActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
    other = AccountActorContext(user_id=uuid4(), request_id=uuid4(), roles=["reviewer"])
    admin = AccountActorContext(user_id=uuid4(), request_id=uuid4(), roles=["admin"])
    view = await service.create_enquiry_atomic(customer, EnquiryCreate(text=RESOLVES, locale="en", destination_warehouse_id=1))
    # Customer reads own; cannot use staff surfaces.
    assert (await service.enquiry_detail(customer, view.id))["status"] == "awaiting_review"
    for call in (service.list_assigned(customer, InboxQuery()), service.list_members(customer), service.audit_search(customer, action=None, entity=None, actor_id=None, cursor=0, limit=10)):
        with pytest.raises(PartsIQError) as exc:
            await call
        assert exc.value.code == "FORBIDDEN"
    # An unassigned reviewer cannot see a real enquiry (404, not 403).
    with pytest.raises(PartsIQError) as exc:
        await service.get_workspace(reviewer, view.id)
    assert exc.value.code == "NOT_FOUND"
    assert (await service.list_assigned(reviewer, InboxQuery())).items == []
    # Admin assigns; the assigned reviewer gains access, the other reviewer still does not.
    ws = service.account_workspace
    from partsiq.workspace.records import MemberRecord, utcnow

    ws.members[reviewer.user_id] = MemberRecord(reviewer.user_id, "r@example.test", "Reviewer", ["reviewer"], "account", utcnow())
    assignment = await service.assign(admin, view.id, reviewer.user_id, view.revision, uuid4())
    assert assignment.assigned_to == reviewer.user_id
    review = await service.get_workspace(reviewer, view.id)
    assert review.draft_id is not None
    with pytest.raises(PartsIQError):
        await service.get_workspace(other, view.id)
    # Reviewer cannot assign (admin-only).
    with pytest.raises(PartsIQError) as exc:
        await service.assign(reviewer, view.id, None, view.revision, uuid4())
    assert exc.value.code == "FORBIDDEN"
    # Capabilities mirror the role model.
    assert "review.decide" in capabilities_for(reviewer) and "admin.users" not in capabilities_for(reviewer)
    assert "ai.allowance" in capabilities_for(admin) and "ai.allowance" not in capabilities_for(AccountActorContext(user_id=uuid4(), request_id=uuid4(), roles=["catalogue_admin"]))


def test_account_rbac_customer_reviewer_admin_scoping() -> None:
    asyncio.run(_account_flow())


# ============================================================ approval re-checks


def test_stock_change_before_approval_blocks_publication(client: TestClient) -> None:
    eid = create(client, RESOLVES)
    ws_view = client.get(f"/v1/staff/enquiries/{eid}", headers=H()).json()
    service = client.app.state.container.runtime
    workspace = next(w for w in service._workspaces.values())
    for part in workspace.catalogue.stock.levels.values():
        for code in part:
            part[code] = 0  # stock sold out before the reviewer approves
    r = client.post(f"/v1/staff/enquiries/{eid}/approve", headers=H(key=True), json={"enquiry_id": eid, "expected_revision": 1, "draft_id": ws_view["draft_id"]})
    assert r.status_code == 409
    assert detail(client, eid)["published_reply"] is None


def test_approval_publishes_exactly_once_with_retried_key(client: TestClient) -> None:
    eid = create(client, RESOLVES)
    ws_view = client.get(f"/v1/staff/enquiries/{eid}", headers=H()).json()
    key = str(uuid4())
    body = {"enquiry_id": eid, "expected_revision": 1, "draft_id": ws_view["draft_id"]}
    first = client.post(f"/v1/staff/enquiries/{eid}/approve", headers={**H(), "Idempotency-Key": key}, json=body)
    again = client.post(f"/v1/staff/enquiries/{eid}/approve", headers={**H(), "Idempotency-Key": key}, json=body)
    assert first.status_code == 200 and again.status_code == 200
    assert again.json()["already_applied"] is True and again.json()["decision_id"] == first.json()["decision_id"]
    d = detail(client, eid)
    assert d["status"] == "approved" and d["published_reply"]["body"]
    assert sum(1 for m in d["messages"] if m["kind"] == "recommendation") == 1


# ============================================================ imports


VALID_CSV = (
    "entity_type,part_number,name_en,name_ar,category,unit_of_measure,brand,model_code,config_code,quantity_per_unit,source_reference\n"
    "parts,VP-AF-9999,Heavy duty air filter,فلتر هواء ثقيل,filters,EA,,,,,\n"
    "part_compatibility,VP-AF-9999,,,,,Veltrano Power,VP-20,A,1,SYNTH-VP-PB-VP-20 rev 7, section FILTERS\n"
)
INVALID_CSV = (
    "entity_type,part_number,name_en,name_ar,category,unit_of_measure\n"
    "parts,=HYPERLINK(\"x\"),Bad,سيء,filters,EA\n"
    "widgets,XX-1,,,,\n"
    "parts,VP-ZZ-1,,,,\n"
)


def _import(client: TestClient, csv_text: str) -> str:
    staged = client.post("/v1/admin/imports", headers=H(key=True), json={"filename": "batch.csv", "format": "csv", "size_bytes": len(csv_text.encode())})
    assert staged.status_code == 201, staged.text
    iid = staged.json()["id"]
    up = client.put(f"/v1/admin/imports/{iid}/content", headers={**H(), "Content-Type": "text/csv"}, content=csv_text.encode())
    assert up.status_code == 200, up.text
    assert client.post(f"/v1/admin/imports/{iid}/validate", headers=H()).status_code == 202
    return iid


def test_import_dry_run_reports_row_errors_and_never_evaluates_formulas(client: TestClient) -> None:
    iid = _import(client, INVALID_CSV.replace("source_reference", ""))
    report = client.get(f"/v1/admin/imports/{iid}/preview", headers=H()).json()
    assert report["state"] == "invalid"
    codes = {(i["row_number"], i["code"]) for i in report["issues"]}
    assert (2, "FORMULA_NOT_ALLOWED") in codes and (3, "UNKNOWN_ENTITY") in codes and (4, "REQUIRED") in codes
    publish = client.post(f"/v1/admin/imports/{iid}/publish", headers=H(key=True), json={"content_sha256": "0" * 64, "expected_active_version_id": None})
    assert publish.status_code == 409


def test_valid_import_publishes_a_new_version_with_compare_and_set(client: TestClient) -> None:
    # The source reference contains a comma, so quote it for CSV.
    csv_text = VALID_CSV.replace("SYNTH-VP-PB-VP-20 rev 7, section FILTERS", '"SYNTH-VP-PB-VP-20 rev 7, section FILTERS"')
    eid = create(client, RESOLVES)  # an enquiry bound to the current version
    iid = _import(client, csv_text)
    report = client.get(f"/v1/admin/imports/{iid}/preview", headers=H()).json()
    assert report["state"] == "validated", report["issues"]
    assert report["preview"]["added"] == {"parts": 1, "part_compatibility": 1}
    stale = client.post(f"/v1/admin/imports/{iid}/publish", headers=H(key=True), json={"content_sha256": report["content_sha256"], "expected_active_version_id": str(uuid4())})
    assert stale.status_code == 409
    ok = client.post(f"/v1/admin/imports/{iid}/publish", headers=H(key=True), json={"content_sha256": report["content_sha256"], "expected_active_version_id": report["active_version_id"]})
    assert ok.status_code == 202, ok.text
    versions = client.get("/v1/admin/catalogue/versions", headers=H()).json()["items"]
    assert versions[0]["state"] == "published" and any(v["state"] == "retired" for v in versions)
    part = client.get("/v1/catalogue/parts/VP-AF-9999/detail", headers=H()).json()
    assert part["compatibility"][0]["model_code"] == "VP-20"
    # The earlier enquiry's draft is bound to the retired version: approval is refused.
    ws_view = client.get(f"/v1/staff/enquiries/{eid}", headers=H()).json()
    r = client.post(f"/v1/staff/enquiries/{eid}/approve", headers=H(key=True), json={"enquiry_id": eid, "expected_revision": 1, "draft_id": ws_view["draft_id"]})
    assert r.status_code == 409 and r.json()["code"] == "STALE_CATALOGUE"
    # Another demo session's catalogue is untouched.
    assert client.get("/v1/catalogue/parts/VP-AF-9999/detail", headers=H("bystander")).status_code == 404


def test_analytics_reports_unmeasured_values_as_null(client: TestClient) -> None:
    create(client, RESOLVES)
    a = client.get("/v1/admin/analytics", headers=H()).json()
    assert a["enquiries"]["total"] == 1 and a["scope"] == "demo"
    assert a["tokens"] is None and a["tokens_note"]
    assert a["allowance"] is None and a["accuracy"] is None and a["accuracy_note"]


def test_labelled_evaluation_runs_the_real_pipeline_with_a_denominator(client: TestClient) -> None:
    r = client.post("/v1/admin/evaluations", headers=H(key=True), json={"suite": "deterministic", "include_demo": True})
    assert r.status_code == 202, r.text
    run = client.get(f"/v1/admin/evaluations/{r.json()['id']}", headers=H()).json()
    assert run["total"] >= 8 and run["passed"] + run["failed"] == run["total"]
    a = client.get("/v1/admin/analytics", headers=H()).json()
    assert a["accuracy"]["total"] == run["total"] and a["accuracy"]["dataset"] == "evals/cases.json"


def test_public_demo_never_uses_live_ai_even_when_live_is_configured() -> None:
    # Live AI configured with a confirmed allowance: anonymous demo runs must still be fixture,
    # so a public visitor can never spend the owner's credit.
    with _client(ai_mode="live", openai_api_key="sk-test-not-used", openai_text_model="gpt-4o-mini",
                 ai_confirmed_allowance_usd="3", ai_allowance_expires_at="2099-01-01T00:00:00Z") as c:
        eid = create(c, RESOLVES)
        run = c.get(f"/v1/runs/{detail(c, eid)['run']['id']}", headers=H()).json()
        assert run["execution_source"] == "fixture"
        assert run["usage"]["estimated_usd"] is None
