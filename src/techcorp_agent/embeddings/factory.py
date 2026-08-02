"""Choose the right embedding client for the current configuration.

Note the asymmetry with the LLM factory: embeddings run locally and cost
nothing, so a missing API key does NOT force hash embeddings — only an
explicit TECHCORP_OFFLINE=true does (used by tests and no-download setups).
"""

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.embeddings.base import EmbeddingClient


def get_embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    settings = settings or get_settings()
    if settings.techcorp_offline:
        from techcorp_agent.embeddings.hash_client import HashEmbeddingClient

        return HashEmbeddingClient()
    from techcorp_agent.embeddings.st_client import SentenceTransformerClient

    return SentenceTransformerClient(settings)
