"""Embedding provider abstraction. Semantic search is optional and disabled by default.

The default deployment performs bilingual lexical search only. Enabling the sentence-transformers
provider requires installing ``requirements-embeddings.txt`` (several gigabytes including PyTorch).
"""

from collections.abc import Sequence
from typing import Literal, Protocol

EMBEDDING_DIMENSION = 1024

EmbeddingProviderName = Literal["none", "sentence_transformers"]


class EmbeddingProvider(Protocol):
    """Converts text into unit-length vectors of ``EMBEDDING_DIMENSION`` dimensions."""

    model_name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerProvider:
    """Local multilingual embeddings, suitable for mixed Arabic and English text."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=sentence_transformers requires the packages in requirements-embeddings.txt"
            ) from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        dimension = self._model.get_sentence_embedding_dimension()
        if dimension != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Embedding model {model_name} produces {dimension} dimensions; the schema expects {EMBEDDING_DIMENSION}"
            )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]


def build_embedding_provider(provider: EmbeddingProviderName, model_name: str) -> EmbeddingProvider | None:
    """Return the configured provider, or None when semantic search is disabled."""
    if provider == "none":
        return None
    if provider == "sentence_transformers":
        return SentenceTransformerProvider(model_name)
    raise ValueError(f"Unsupported embedding provider: {provider}")


def to_vector_literal(vector: Sequence[float]) -> str:
    """Serialise a vector in the textual format accepted by pgvector."""
    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(f"Expected {EMBEDDING_DIMENSION} dimensions, received {len(vector)}")
    return "[" + ",".join(f"{component:.7f}" for component in vector) + "]"


def validate_embedding(vector: Sequence[float], *, tolerance: float = 1e-3) -> None:
    """Reject a vector of the wrong dimension, with NaN/inf, or not unit length.

    BGE-M3 vectors are L2-normalised; the schema is VECTOR(1024). Enforcing both here
    (prompt 06, F24) means a miscomputed embedding is refused rather than silently
    stored and later ranked as if valid.
    """
    import math

    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(f"Expected {EMBEDDING_DIMENSION} dimensions, received {len(vector)}")
    if any(math.isnan(component) or math.isinf(component) for component in vector):
        raise ValueError("embedding contains NaN or infinite components")
    norm = math.sqrt(sum(component * component for component in vector))
    if abs(norm - 1.0) > tolerance:
        raise ValueError(f"embedding is not unit length (norm={norm:.6f})")


def source_sha256(text: str) -> str:
    """Stable hash of the embedded source text, stored alongside each vector so a
    re-embed can detect unchanged inputs (prompt 06: upsert with source hash)."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
