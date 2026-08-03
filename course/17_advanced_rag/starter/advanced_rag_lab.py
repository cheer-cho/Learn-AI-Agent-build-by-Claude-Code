"""Module 17 starter — implement the advanced-retrieval building blocks.

Work through lab.md and replace each TODO. You are re-implementing the three
core primitives that turn naive top-k retrieval into a hybrid, reranked,
multi-query pipeline:

    1. hybrid_fuse   — min-max normalized weighted fusion of two score maps
    2. overlap_rerank — deterministic token-overlap reranking
    3. parse_rewrites — turn an LLM's reply into a deduped multi-query list

The heavier machinery (the Chroma-backed vector search, the BM25 index, the
`AdvancedRAGPipeline` that chains the stages) already lives in the shared
library `techcorp_agent.rag.advanced`. You import and reuse it — the point of
the lab is the retrieval *logic*, not the plumbing.

Run it:
    TECHCORP_OFFLINE=true uv run python course/17_advanced_rag/starter/advanced_rag_lab.py
Check it:
    uv run pytest course/17_advanced_rag -q
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """A simple lowercase word/number tokenizer (already done — reuse it)."""
    return _WORD_RE.findall(text.lower())


def min_max_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Scale a {id: score} map into [0, 1] by min-max.

    Task 2a. Vector similarities and BM25 scores live on different scales, so
    before fusing them you must put both on a common [0, 1] axis.

    Rules:
    - Empty input → empty dict.
    - When every value is (nearly) equal, the range is zero: return 1.0 for
      every id (each was retrieved, so it is a full match on its own scale).
    - Otherwise map each value v to (v - lo) / (hi - lo).
    """
    # TODO: implement min-max normalization per the docstring.
    #   lo, hi = min(...), max(...); guard hi - lo < 1e-12.
    raise NotImplementedError("min_max_normalize — see lab.md Task 2")


def hybrid_fuse(
    vector_scores: dict[str, float],
    bm25_scores: dict[str, float],
    alpha: float = 0.5,
) -> dict[str, float]:
    """Fuse normalized vector and BM25 score maps into one {id: fused} map.

    Task 2b. Normalize each side with `min_max_normalize`, then combine:

        fused = alpha * norm_vector + (1 - alpha) * norm_bm25

    An id missing from one side contributes 0 on that side (it was not
    retrieved there). The returned map has every id that appeared in either
    input.
    """
    # TODO: normalize both maps, then for every id in the union compute the
    #       weighted sum. Missing id on a side → 0.0 for that side.
    raise NotImplementedError("hybrid_fuse — see lab.md Task 2")


def overlap_rerank(query: str, texts: dict[str, str], top_k: int) -> list[tuple[str, float]]:
    """Rerank {id: text} by query/text token overlap; return top_k (id, score).

    Task 3. Score each text by the fraction of DISTINCT query tokens it
    contains: |query_tokens ∩ text_tokens| / |query_tokens|. Sort best-first,
    keep the top_k. An empty query returns the first top_k ids in input order.

    This is an honest *approximation* of a cross-encoder — it rewards literal
    word overlap and, like BM25, is blind to synonyms. The real quality signal
    comes from the CrossEncoderReranker in the shared library; this is the
    offline, deterministic stand-in you can test without downloads.
    """
    # TODO: build a set of query tokens; for each id score the overlap fraction;
    #       sort by score descending; return the top_k (id, score) pairs.
    raise NotImplementedError("overlap_rerank — see lab.md Task 3")


def parse_rewrites(original: str, llm_reply: str, n: int) -> list[str]:
    """Turn a query-rewrite LLM reply into [original, *rewrites].

    Task 4. The LLM returns one rewrite per line. Build the multi-query list:

    - the original question is always first (never trade it away);
    - then up to `n` rewrites from the reply, in order;
    - drop any rewrite equal (case-insensitively) to the original or to an
      earlier rewrite — running the same query twice only wastes a retrieval.
    """
    # TODO: split llm_reply into non-empty stripped lines; dedup case-insensitively
    #       against the original and earlier picks; keep at most n rewrites.
    raise NotImplementedError("parse_rewrites — see lab.md Task 4")


def main() -> int:
    """A tiny smoke run so the starter is runnable at every stage."""
    print("Module 17 starter — finish the lab, then run the experiment:")
    print("  TECHCORP_OFFLINE=true uv run python course/17_advanced_rag/solution/run_experiment.py")
    try:
        fused = hybrid_fuse({"a": 0.9, "b": 0.1}, {"b": 5.0, "c": 2.0}, alpha=0.5)
        print("hybrid_fuse ->", fused)
    except NotImplementedError as exc:
        print(f"(not implemented yet: {exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
