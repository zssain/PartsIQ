"""F24 Semantic retrieval capabilities facade (helper ``search.capabilities``).

Reports the search engine's lexical and semantic readiness SEPARATELY (the foundation-06
invariant: lexical search is always in-process and ready; semantic search is available only when
an embedding provider has loaded). In this environment no embedding provider (BGE-M3) and no live
pgvector surface are wired, so ``semantic`` is reported False with an explicit ``fallback_reason``
rather than pretending a provider exists — a confident-but-false "semantic ready" would be a lie.

The active catalogue source/version is read from the container: in fixture mode the seed-42
``FixtureCatalogueRepository`` reports ``catalogue_source="fixture"`` and its single published
``catalogue_version_id``. Access is ``customer`` — any verified caller may read capabilities; the
report reveals no inventory, only which retrieval modes are live.
"""
from __future__ import annotations

from partsiq.core.api_models import SearchCapabilities
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer
from partsiq.core.errors import PartsIQError


async def capabilities(actor: ActorContext, *, container: AppContainer) -> SearchCapabilities:
    """Report lexical/semantic readiness and the active catalogue source + version.

    Lexical retrieval is always ready (it runs in process). Semantic retrieval needs an
    embedding provider, which is not loaded in this environment, so it is reported False with a
    ``fallback_reason``; this never silently masquerades as semantic capability (readiness rule).
    """
    _ = actor  # a verified actor is always present; customer access needs no role
    if container.catalogue is None:
        # DB-mode catalogue read-store is not configured in this environment.
        raise PartsIQError(
            "DEPENDENCY_UNAVAILABLE",
            internal_detail="catalogue source not configured in this environment",
        )
    version_ids = container.catalogue.available_version_ids()
    return SearchCapabilities(
        lexical=True,
        semantic=False,
        embedding_model=None,
        fallback_reason="embedding provider not loaded in this environment",
        catalogue_source="fixture" if container.is_fixture else "snowflake",
        catalogue_version_id=version_ids[0] if version_ids else None,
    )
