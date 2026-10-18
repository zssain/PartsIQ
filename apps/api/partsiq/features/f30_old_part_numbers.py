"""F30 Old part numbers / supersession resolution facade (helper ``search.resolve_supersession``).

Resolves a quoted (possibly superseded) part number to its forward supersession chain and current
terminal part over the VALIDATED ACTIVE catalogue version. The chain is ``[requested, …, current]``
with cycle protection; ``terminal_number`` is the current successor and ``active`` reports whether
that terminal part is still active in the catalogue. An unknown part number is a 404.

Invariant (F30): a superseded number resolves ONLY along explicit catalogue supersession edges —
compatibility is never silently inherited across a supersession here (that gate lives in F22/F25).
Access is ``customer``; the lookup reveals catalogue facts only, never inventory.

Serves real seed-42 data in fixture mode by deriving a :class:`CatalogueSnapshotRepository` from
the active ``container.catalogue`` snapshot; in DB mode the live read store is not configured, so a
clean 503 is surfaced rather than an invented chain.
"""
from __future__ import annotations

from partsiq.core.api_models import SupersessionView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError
from partsiq.search.repository import CatalogueSnapshotRepository
from partsiq_common.text import part_number_key


def _active_repository(container: AppContainer) -> CatalogueSnapshotRepository:
    """Build a search repository over the active catalogue snapshot, or raise 503 when none.

    The active snapshot is re-validated by :meth:`from_active_snapshot`; an invalid version is a
    409 STALE_CATALOGUE rather than a silently-served unvalidated version.
    """
    if container.catalogue is None:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="catalogue read store not configured in this environment",
        )
    version_ids = container.catalogue.available_version_ids()
    if not version_ids:
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE", internal_detail="no active catalogue version available"
        )
    snapshot = container.catalogue.read_version(version_ids[0])
    return CatalogueSnapshotRepository.from_active_snapshot(snapshot)


async def resolve_supersession(
    actor: ActorContext, part_number: str, *, container: AppContainer
) -> SupersessionView:
    """Resolve a part number to its forward supersession chain + current terminal (F30)."""
    _ = actor  # a verified actor is always present; customer access needs no role
    repo = _active_repository(container)
    key = part_number_key(part_number)
    found = await repo.find_part_ids_by_number_keys([key])
    if key not in found:
        raise PartsIQError(
            "NOT_FOUND",
            detail="The requested part number is not in the active catalogue.",
            internal_detail=f"part number {part_number} not found",
        )
    origin_id = found[key]
    chain_ids = (await repo.fetch_supersession_chains([origin_id]))[origin_id]
    parts = await repo.fetch_parts(chain_ids)
    chain = [parts[pid].part_number for pid in chain_ids]
    terminal = parts[chain_ids[-1]]
    return SupersessionView(
        requested_number=part_number,
        chain=chain,
        terminal_number=terminal.part_number,
        active=terminal.is_active,
    )
