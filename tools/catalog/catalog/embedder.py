"""Computes and stores part embeddings for semantic search."""

import asyncio
import logging

import asyncpg

from partsiq_common.embeddings import EmbeddingProvider, source_sha256, to_vector_literal

logger = logging.getLogger("partsiq.catalog.embedder")

BATCH_SIZE = 32


def build_embedding_text(name_en: str, name_ar: str, category: str, description: str, aliases: list[str]) -> str:
    """Compose the text embedded for a part. Includes both languages and informal names."""
    alias_text = "; ".join(aliases)
    return f"{name_en} | {name_ar} | {category} | {alias_text} | {description}"


async def embed_parts(
    connection: asyncpg.Connection, provider: EmbeddingProvider, model_revision: str = ""
) -> int:
    """Embed every active part and upsert the vectors. Returns the number of parts embedded."""
    rows = await connection.fetch(
        """SELECT p.id, p.name_en, p.name_ar, p.category, p.description_en,
                  COALESCE(array_agg(a.alias ORDER BY a.alias) FILTER (WHERE a.alias IS NOT NULL), '{}') AS aliases
           FROM parts AS p
           LEFT JOIN part_aliases AS a ON a.part_id = p.id
           WHERE p.is_active
           GROUP BY p.id
           ORDER BY p.id"""
    )
    embedded = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        texts = [
            build_embedding_text(r["name_en"], r["name_ar"], r["category"], r["description_en"], list(r["aliases"]))
            for r in batch
        ]
        vectors = await asyncio.to_thread(provider.embed, texts)
        await connection.executemany(
            """INSERT INTO part_embeddings
                   (part_id, model_name, source_text, embedding, model_revision, source_sha256)
               VALUES ($1, $2, $3, $4::vector, $5, $6)
               ON CONFLICT (part_id, model_name)
               DO UPDATE SET source_text = EXCLUDED.source_text, embedding = EXCLUDED.embedding,
                   model_revision = EXCLUDED.model_revision, source_sha256 = EXCLUDED.source_sha256,
                   created_at = now()""",
            [(r["id"], provider.model_name, text, to_vector_literal(vector), model_revision, source_sha256(text))
             for r, text, vector in zip(batch, texts, vectors)],
        )
        embedded += len(batch)
        logger.info("embedded batch", extra={"embedded": embedded, "total": len(rows)})
    return embedded
