"""Composition of the workspace runtime and the port adapters the feature facades resolve.

``WorkspaceService`` is the one object behind ``container.journey`` / ``container.staff_review``
/ ``container.jobs`` / … (see ``core.dependencies.build_container``). Two existing contracts
share a method name with different signatures (F19 history ``list_owned`` vs F55 machines
``list_owned``; F64 ``read``), so they get thin adapters instead of a second implementation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from partsiq.auth.actors import require_capability
from partsiq.core.api_models import ArchiveResult, MachinePage, MachineSave, PageQuery, SavedMachineView
from partsiq.core.contracts import ActorContext, CreditAllowance
from partsiq.core.errors import PartsIQError

from .ops import OpsMixin
from .review import ReviewMixin
from .runtime import WorkspaceRuntime


class WorkspaceService(ReviewMixin, OpsMixin, WorkspaceRuntime):
    """The application-state service (runtime + review + ops/admin ports)."""


class SavedMachinesPort:
    def __init__(self, service: WorkspaceService) -> None:
        self._s = service

    async def save(self, actor: ActorContext, request: MachineSave, key: UUID) -> SavedMachineView:
        return await self._s.save(actor, request, key)

    async def list_owned(self, actor: ActorContext, query: PageQuery) -> MachinePage:
        return await self._s.list_machines(actor, query)

    async def archive(self, actor: ActorContext, machine_id: UUID) -> ArchiveResult:
        return await self._s.archive(actor, machine_id)


class AllowancePort:
    """F64: the owner's confirmed allowance. Real administrators only (never a demo sandbox)."""

    def __init__(self, service: WorkspaceService) -> None:
        self._s = service

    async def read(self, actor: ActorContext) -> tuple[CreditAllowance | None, Decimal, Decimal, str | None]:
        require_capability(actor, "ai.allowance")
        ledger = self._s._ledger
        if ledger is None:
            return None, Decimal("0"), Decimal("0"), self._s.settings.openai_text_model or None
        snap = ledger.snapshot()
        return ledger.allowance, Decimal(snap["consumed_usd"]), Decimal(snap["reserved_usd"]), self._s.settings.openai_text_model or None

    async def persist(self, actor: ActorContext, allowance: CreditAllowance, model: str) -> tuple[Decimal, Decimal]:
        require_capability(actor, "ai.allowance")
        raise PartsIQError(
            "FORBIDDEN",
            detail="The AI allowance is owner configuration (AI_CONFIRMED_ALLOWANCE_USD / AI_ALLOWANCE_EXPIRES_AT) and is not changed through the API in this deployment.",
        )


def wire(container: Any, service: WorkspaceService) -> None:
    """Attach the service and its adapters to every port attribute the facades resolve."""
    container.runtime = service
    container.journey = service
    for attr in (
        "staff_review", "repeat_enquiries", "jobs", "workflow_runs", "catalogue_imports",
        "catalogue_versions", "evaluations", "metrics_repo", "analytics_sync", "missing_parts",
        "publication",
    ):
        setattr(container, attr, service)
    container.saved_machines = SavedMachinesPort(service)
    container.ai_allowance = AllowancePort(service)
