"""The application-facing embedding interface.

Two implementations:

- SentenceTransformerClient — real semantic embeddings via a local model
  (free to run; downloads the model once on first use).
- HashEmbeddingClient — deterministic offline stand-in used by tests and by
  TECHCORP_OFFLINE mode: word-overlap similarity only, no semantics.

Vectors from different embedding models are NOT comparable — an index built
with one model must be queried with the same model. The course returns to
this rule in Module 07.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingClient(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors of `dimension` floats."""
        ...
