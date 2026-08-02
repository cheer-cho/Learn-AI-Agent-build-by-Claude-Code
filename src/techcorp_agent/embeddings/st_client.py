"""Real semantic embeddings via sentence-transformers (runs locally, free).

The model (~90 MB for the course default) downloads once on first use and is
cached. Loading is lazy so importing this module stays cheap.
"""

from techcorp_agent.config import Settings, get_settings


class SentenceTransformerClient:
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.model_name = settings.embedding_model
        self._model = None
        self._dimension: int | None = None

    def _load(self):
        if self._model is None:
            # Heavy import (torch) deferred until embeddings are actually needed.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
        return self._model

    @property
    def dimension(self) -> int:
        self._load()
        assert self._dimension is not None
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]
