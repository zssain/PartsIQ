"""Search-owned embedding ingestion.

Contract (FLOW.md row 06):
    async def embed_version(version_id: UUID, batch_size: int = 16) -> EmbeddingReceipt

Only the search service loads BGE-M3 (CONSTRAINTS.md rule 4). This reads the parts of a
validated PUBLISHED catalogue version, encodes them with the one process-wide provider,
validates every vector (1024-d, unit-norm, no NaN — F24), and upserts each with its
model revision and a source hash so an unchanged input can be detected on re-embed.

The provider and the datastore are injected so the pure ingestion flow is testable
without a GPU/CPU model download or a database; the default wiring (DB pool + loaded
provider) is used only in the running service.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol
from uuid import UUID

from partsiq_common.contracts import EmbeddingReceipt
from partsiq_common.embeddings import EmbeddingProvider, source_sha256, to_vector_literal, validate_embedding


class EmbeddingStore(Protocol):
    """Datastore surface for ingestion. (part_id, source_text) in; upserts out."""

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


def _batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def embed_version(
    version_id: UUID,
    batch_size: int = 16,
    *,
    provider: EmbeddingProvider | None = None,
    store: EmbeddingStore | None = None,
    model_revision: str = "",
) -> EmbeddingReceipt:
    """Embed every part of a published version and upsert its vector. Returns a receipt."""
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
