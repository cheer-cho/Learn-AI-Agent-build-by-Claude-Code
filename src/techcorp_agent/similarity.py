"""Vector similarity measures."""

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors, in [-1, 1] (1 = same direction).

    Cosine compares direction and ignores magnitude, which is why it is the
    default choice for comparing text embeddings.
    """
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    if va.shape != vb.shape:
        raise ValueError(f"Vector dimensions differ: {va.shape} vs {vb.shape}")
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0.0:
        return 0.0
    return float(np.dot(va, vb) / norm)


def rank_by_similarity(
    query_vector: list[float], candidates: dict[str, list[float]]
) -> list[tuple[str, float]]:
    """Rank candidate vectors by cosine similarity to the query, best first."""
    scored = [(key, cosine_similarity(query_vector, vec)) for key, vec in candidates.items()]
    return sorted(scored, key=lambda item: item[1], reverse=True)
