"""Typed client to the internal search service.

The orchestrator never imports the search app; it speaks to it over HTTP at a FIXED
internal URL with the internal service token, and parses responses into its own small
adapter types (CONTRACTS.md: do not duplicate search domain types). All calls are
read-only. The HTTP client is injected so the adapter is testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Candidate:
    part_id: int
    score: float


@dataclass(frozen=True, slots=True)
class IdentifyResult:
    status: str
    configuration_id: int | None


@dataclass(frozen=True, slots=True)
class PartSearchResult:
    configuration_id: int
    candidates: list[Candidate]
    top_score: float
    margin: float


class SearchClient:
    def __init__(self, base_url: str, token: str | None, http: Any) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._http = http

    async def _post(self, path: str, payload: dict) -> dict:
        headers = {"X-Internal-Token": self._token} if self._token else {}
        response = await self._http.post(f"{self._base}{path}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def identify(self, query: str, serial: str | None) -> IdentifyResult:
        data = await self._post("/v1/search/identify", {"query": query, "serial": serial})
        configuration = data.get("configuration")
        return IdentifyResult(data["status"], configuration["id"] if configuration else None)

    async def search_parts(self, configuration_id: int, query: str, limit: int | None = None) -> PartSearchResult:
        payload: dict = {"configuration_id": configuration_id, "query": query}
        if limit is not None:
            payload["limit"] = limit
        data = await self._post("/v1/search/parts", payload)
        candidates = [Candidate(c["part"]["id"], c["score"]) for c in data["candidates"]]
        confidence = data["confidence"]
        return PartSearchResult(
            configuration_id=data["configuration"]["id"],
            candidates=candidates,
            top_score=confidence["top_score"],
            margin=confidence["margin"],
        )
