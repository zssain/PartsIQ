"""Search-owned embeddings: the optional encoder abstraction + version ingestion.

Ported from the legacy ``services/search/app/embedding_ingestion.py`` and the
``partsiq_common/embeddings.py`` helpers (foundation 06). Semantic search is OPTIONAL and
disabled by default; the default deployment performs bilingual lexical search only. Only the
search worker ever loads BGE-M3 (one CPU encoder per process); API handlers never load it.

The provider/encoder and the datastore are INJECTED so the pure ingestion flow is testable
without a GPU/CPU model download or a database. The real BGE-M3 (torch /
sentence-transformers) is BLOCKED in this environment — a fake encoder returning fixed,
unit-norm 1024-d vectors is used in tests. Every vector is validated (1024-d, unit-norm, no
NaN/inf — F24) before it is stored; a miscomputed embedding is refused, never ranked as valid.

The vector helpers are re-exported from ``partsiq_common.embeddings`` so this module is the
single search-side surface for them (contracts/receipt come from ``partsiq.core.contracts``).
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol
from uuid import UUID

from partsiq.core.contracts import EmbeddingReceipt
from partsiq_common.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingProvider,
    EmbeddingProviderName,
    SentenceTransformerProvider,
    build_embedding_provider,
    source_sha256,
    to_vector_literal,
    validate_embedding,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "EmbeddingProvider",
    "EmbeddingProviderName",
    "SentenceTransformerProvider",
    "build_embedding_provider",
    "source_sha256",
    "to_vector_literal",
    "validate_embedding",
    "EmbeddingStore",
    "Encoder",
    "embed_version",
]


class EmbeddingStore(Protocol):
    """Datastore surface for ingestion. ``(part_id, source_text)`` in; upserts out."""

    async def fetch_embedding_sources(self, version_id: UUID) -> list[tuple[int, str]]: ...

    async def upsert_embedding(
        self,
        part_id: int,
        model_name: str,
        source_text: str,
        vector_literal: str,
        model_revision: str,
        source_hash: str,
    ) -> None: ...


Encoder = Callable[[Sequence[str]], Awaitable[list[list[float]]]]


def _batches(items: list[tuple[int, str]], size: int) -> list[list[tuple[int, str]]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


async def embed_version(
    version_id: UUID,
    batch_size: int = 16,
    *,
    provider: EmbeddingProvider | None = None,
    store: EmbeddingStore | None = None,
    model_revision: str = "",
) -> EmbeddingReceipt:
    """Embed every part of a published version and upsert its vector. Returns a receipt.

    Reads the parts of a VALIDATED published catalogue version, encodes them with the one
    process-wide provider, validates every vector (1024-d, unit-norm, no NaN — F24), and upserts
    each with its model revision and a source hash so an unchanged input is detectable on
    re-embed. Both the provider and the store are injected; the live DB pool + loaded BGE-M3
    provider are used only in the running search worker (BLOCKED here).
    """
    if provider is None or store is None:  # pragma: no cover - needs a live DB + BGE-M3
        raise RuntimeError("embed_version requires an embedding provider and a store (search runtime only)")

    sources = await store.fetch_embedding_sources(version_id)
    embedded = 0
    for batch in _batches(sources, batch_size):
        texts = [text for _, text in batch]
        vectors = await asyncio.to_thread(provider.embed, texts)
        if len(vectors) != len(batch):
            raise ValueError("encoder returned a different number of vectors than inputs")
        for (part_id, text), vector in zip(batch, vectors):
            validate_embedding(vector)  # dims + unit-norm + NaN (F24)
            await store.upsert_embedding(
                part_id,
                provider.model_name,
                text,
                to_vector_literal(vector),
                model_revision,
                source_sha256(text),
            )
        embedded += len(batch)

    return EmbeddingReceipt(version_id=version_id, embedded_count=embedded, model_revision=model_revision)
