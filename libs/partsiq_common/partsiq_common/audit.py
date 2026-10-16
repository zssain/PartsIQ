"""Append-only audit writing.

``append_audit`` INSERTs one row into ``audit_log`` using the CALLER's connection, so
it shares the caller's transaction: if the audit write fails, the business change
(e.g. an approval) rolls back with it (F49). The payload is redacted before it is
stored — no secret, no full photo, bounded size (CONSTRAINTS.md rules 10, 17).

The table is append-only for application roles (enforced by migration grants/RLS);
this function never updates or deletes.
"""
from __future__ import annotations

import json
from typing import Any

from partsiq_common.contracts import AuditEvent
from partsiq_common.telemetry import redact_payload

_INSERT_AUDIT = """
INSERT INTO audit_log
    (actor_type, actor_id, action, entity_type, entity_id, request_id, enquiry_id, revision, payload)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
RETURNING id
""".strip()


async def append_audit(conn: Any, event: AuditEvent) -> int:
    """Insert a redacted audit row in the caller's transaction and return its id.

    Any database error propagates intentionally so the surrounding business
    transaction is rolled back.
    """
    safe_payload = redact_payload(event.payload)
    params = (
        event.actor_type,
        event.actor_id,
        event.action,
        event.entity_type,
        event.entity_id,
        str(event.request_id),
        str(event.enquiry_id) if event.enquiry_id is not None else None,
        event.revision,
        json.dumps(safe_payload, ensure_ascii=False),
    )
    async with conn.cursor() as cur:
        await cur.execute(_INSERT_AUDIT, params)
        row = await cur.fetchone()
    return int(row[0])
