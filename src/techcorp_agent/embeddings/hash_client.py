"""Deterministic offline embeddings via feature hashing.

Each word (and word bigram) is hashed to a fixed dimension and counted, then
the vector is L2-normalized. Texts sharing words get similar vectors; texts
with disjoint words do not.

This is NOT semantic: "vacation" and "time off" share no words, so this
client scores them as unrelated — a real embedding model would not. That
limitation is exactly what Module 05 teaches; the hash client exists so the
plumbing can be tested offline, not to replace real embeddings.
"""

import hashlib
import math
import re

_WORD_RE = re.compile(r"[a-z0-9]+")


def _bucket(token: str, dimension: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dimension


class HashEmbeddingClient:
    def __init__(self, dimension: int = 384):
        if dimension < 8:
            raise ValueError("dimension must be at least 8")
        self.dimension = dimension
        self.model_name = f"hash-embedding-{dimension}d"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        words = _WORD_RE.findall(text.lower())
        bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
        for token in words + bigrams:
            vector[_bucket(token, self.dimension)] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector
