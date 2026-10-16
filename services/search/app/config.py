"""Search service configuration."""

from pydantic import Field

from partsiq_common.config import BaseServiceSettings
from partsiq_common.embeddings import EmbeddingProviderName


class SearchSettings(BaseServiceSettings):
    embedding_provider: EmbeddingProviderName = "none"
    embedding_model_name: str = "BAAI/bge-m3"
    # Immutable BGE-M3 revision recorded with every vector (spec/environment.json).
    embedding_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    semantic_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    default_result_limit: int = Field(default=5, ge=1, le=10)
    # Shared secret required on internal calls; internal services never face the public internet.
    internal_service_token: str | None = None
