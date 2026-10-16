"""Search service configuration."""

from pydantic import Field

from partsiq_common.config import BaseServiceSettings
from partsiq_common.embeddings import EmbeddingProviderName


class SearchSettings(BaseServiceSettings):
    embedding_provider: EmbeddingProviderName = "none"
    embedding_model_name: str = "BAAI/bge-m3"
    semantic_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    default_result_limit: int = Field(default=5, ge=1, le=10)
