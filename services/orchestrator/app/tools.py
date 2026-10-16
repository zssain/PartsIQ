"""Bounded, read-only specialist tools.

Only identify, search_parts, part_detail and plan_fulfilment are exposed, each with
typed arguments and a fixed internal URL. A session enforces the per-stage tool-call
bound (TOOL_MAX_CALLS = 4) and rejects a response whose catalogue version no longer
matches the one the stage started with (stale version). An LLM receives NO write,
approval or publication tool (CONSTRAINTS.md rule 6).
"""
from __future__ import annotations

from uuid import UUID

from app.search_client import IdentifyResult, PartSearchResult, SearchClient
from partsiq_common.contracts import ToolContext
from partsiq_common.errors import PartsIQError


class ToolBudgetError(PartsIQError):
    """Raised when a stage exceeds its tool-call bound."""


class StaleCatalogueError(PartsIQError):
    """Raised when the live catalogue version has moved on from the stage's version."""


class ToolSession:
    """A per-stage, bounded view over the read-only search tools."""

    def __init__(self, client: SearchClient, context: ToolContext, current_catalogue_version: UUID) -> None:
        self._client = client
        self._ctx = context
        self._current = current_catalogue_version
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def _charge(self) -> None:
        self._calls += 1
        if self._calls > self._ctx.max_calls:
            raise ToolBudgetError("QUOTA_EXCEEDED", internal_detail="tool-call budget exceeded")

    def _ensure_current(self) -> None:
        # Reject work bound to a superseded catalogue version (stale version).
        if self._ctx.catalogue_version_id != self._current:
            raise StaleCatalogueError("STALE_REVISION", internal_detail="catalogue version changed")

    async def identify(self, query: str, serial: str | None) -> IdentifyResult:
        self._ensure_current()
        self._charge()
        return await self._client.identify(query, serial)

    async def search_parts(self, configuration_id: int, query: str, limit: int | None = None) -> PartSearchResult:
        self._ensure_current()
        self._charge()
        return await self._client.search_parts(configuration_id, query, limit)
