"""F62 Labelled evaluations facade (helpers ``evaluation.enqueue_run`` / ``evaluation.read_run``).

An admin runs the labelled evaluation suite against the deterministic pipeline and reads the
result. Two surfaces:

  * ``enqueue_run`` queues a durable evaluation job for the chosen suite and returns the job handle
    (202). The DETERMINISTIC suite runs with no AI calls and scores exact-match ground truth, so
    its abstentions (a case the pipeline declines) are counted SEPARATELY from wrong answers and
    never fabricated into passes; the LIVE suite is gated on a confirmed credit allowance (F64) and
    stays disabled otherwise. Demo traffic is excluded unless ``include_demo`` is set (F04).
  * ``read_run`` returns the run's state and per-case results (200), read-only.

Both require the ``admin`` role; any other (or anonymous) caller is refused with FORBIDDEN (403).
Thin adapter over an injected port; the live eval runner/store is BLOCKED offline, so an admin gets
a clean 503 rather than a fabricated run.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from partsiq.core.api_models import EvalRequest, EvaluationView, JobView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.features._ops_ports import require_store


def require_admin(actor: ActorContext) -> None:
    """Refuse a non-admin caller with FORBIDDEN before any run is enqueued or read (403)."""
    if "admin" not in actor.roles:
        raise PartsIQError("FORBIDDEN", internal_detail="evaluation runs are admin-only")


@runtime_checkable
class EvaluationSource(Protocol):
    """Admin evaluation enqueue/read port."""

    async def enqueue_run(
        self, actor: ActorContext, request: EvalRequest, key: UUID
    ) -> JobView: ...

    async def read_run(self, actor: ActorContext, run_id: UUID) -> EvaluationView: ...


async def enqueue_run(
    actor: ActorContext,
    request: EvalRequest,
    key: UUID,
    *,
    container: AppContainer,
    source: EvaluationSource | None = None,
) -> JobView:
    """Queue a labelled evaluation run for the chosen suite (admin-only); idempotent on the key."""
    require_admin(actor)
    source = source or require_store(container, "evaluations")
    return await source.enqueue_run(actor, request, key)


async def read_run(
    actor: ActorContext,
    run_id: UUID,
    *,
    container: AppContainer,
    source: EvaluationSource | None = None,
) -> EvaluationView:
    """Return a run's state and per-case results (admin-only; read-only)."""
    require_admin(actor)
    source = source or require_store(container, "evaluations")
    return await source.read_run(actor, run_id)
