"""Module 17 solution — the advanced-retrieval experiment (reference).

This is the *complete* version of `starter/advanced_rag_lab.py`. It wires the
building blocks from `techcorp_agent.rag.advanced` into an A/B experiment that
re-runs the Module 09 evaluation under five retrieval configurations and reports
the measured hit@4 and latency of each.

Nothing here re-implements retrieval — all four techniques live in the shared
library (`src/techcorp_agent/rag/advanced.py`) so the same code the learner
tests is the code that gets measured. This file is only the harness.

Central rule (from the module spec): every improvement claim is backed by these
numbers. If a technique does not help on this corpus, the table says so — that
is a real finding, not a failure.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from techcorp_agent.config import Settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.evaluation.metrics import hit_rate_at_k
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.advanced import (
    AdvancedRAGPipeline,
    BM25Index,
    OverlapReranker,
    Reranker,
)
from techcorp_agent.schemas import Chunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

# Retrieval depth scored, matching the Module 09 baseline (hit@4).
TOP_K = 4

# Only the categories where *retrieval* is the thing under test. answerable is
# the bread-and-butter case; paraphrase is the baseline's weak spot (60%);
# multi_chunk needs several documents at once. unanswerable/ambiguous expect no
# sources (hit@k is vacuously 1.0 there), so they cannot move and are excluded.
SCORED_CATEGORIES = ("answerable", "paraphrase", "multi_chunk")

# A deterministic offline stand-in for a query-rewriting LLM. Real rewrites come
# from a live model; offline we script generic reformulations so the multi-query
# stage runs and dedups predictably. These are intentionally weak (they cannot
# invent corpus vocabulary), which is part of the honest offline story.
_OFFLINE_REWRITES = "policy details and rules\nrequirements and conditions"


def make_rewrite_llm() -> MockLLMClient:
    """A mock LLM that always returns the same two scripted rewrites."""
    # Enough scripted responses for every scored example; MockLLMClient pops one
    # per call, so we recycle by handing it a long list.
    return MockLLMClient(responses=[_OFFLINE_REWRITES] * 200)


@dataclass
class ConfigResult:
    """Measured outcome of one retrieval configuration."""

    name: str
    complexity: str
    hit_rate: float
    hit_by_category: dict[str, float]
    avg_latency_ms: float
    n: int
    per_example: list[tuple[str, str, float]] = field(default_factory=list)


def load_scored_examples(settings: Settings) -> list[dict]:
    """Load the evaluation examples whose retrieval we actually score."""
    dataset_path = settings.data_dir / "evaluation" / "eval_dataset.json"
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [ex for ex in payload["examples"] if ex["category"] in SCORED_CATEGORIES]


def build_index(
    documents, embeddings: EmbeddingClient, persist_dir: Path
) -> tuple[VectorStore, list[Chunk]]:
    """Chunk the corpus, index it in Chroma, and return the store + all chunks.

    The chunk list is what the BM25 index is built from, so the two retrievers
    see exactly the same units — a fair comparison.
    """
    store = VectorStore(embeddings, persist_dir=persist_dir)
    all_chunks: list[Chunk] = []
    for document in documents:
        chunks = chunk_document(document)
        all_chunks.extend(chunks)
        store.add_chunks(chunks)
    return store, all_chunks


def make_pipeline(
    name: str,
    store: VectorStore,
    bm25: BM25Index,
    answer_llm: LLMClient,
    reranker: Reranker,
) -> AdvancedRAGPipeline:
    """Construct the `AdvancedRAGPipeline` for a named configuration.

    The five configurations isolate each technique against the same baseline:

    - ``baseline``  — pure vector top-k (identical to Module 08).
    - ``+hybrid``   — add BM25 score fusion.
    - ``+rerank``   — add a reranker on top of hybrid.
    - ``+rewrite``  — add multi-query rewriting on top of hybrid.
    - ``all``       — hybrid + rewrite + rerank together.
    """
    use_hybrid = name != "baseline"
    use_rerank = name in ("+rerank", "all")
    use_rewrite = name in ("+rewrite", "all")
    return AdvancedRAGPipeline(
        store,
        answer_llm,
        top_k=TOP_K,
        bm25_index=bm25 if use_hybrid else None,
        use_hybrid=use_hybrid,
        reranker=reranker if use_rerank else None,
        rewrite_llm=make_rewrite_llm() if use_rewrite else None,
        use_multi_query=use_rewrite,
    )


CONFIGS: list[tuple[str, str]] = [
    ("baseline", "none (Module 08 vector top-k)"),
    ("+hybrid", "BM25 index + score fusion"),
    ("+rerank", "hybrid + reranker pass"),
    ("+rewrite", "hybrid + multi-query rewriting"),
    ("all", "hybrid + rewrite + rerank"),
]


def evaluate_config(
    name: str,
    complexity: str,
    pipeline: AdvancedRAGPipeline,
    examples: list[dict],
) -> ConfigResult:
    """Score one configuration: per-example hit@TOP_K plus retrieval latency."""
    per_example: list[tuple[str, str, float]] = []
    latencies: list[float] = []
    by_category: dict[str, list[float]] = {}

    for example in examples:
        start = time.perf_counter()
        retrieved = pipeline.retrieve(example["question"])
        latencies.append((time.perf_counter() - start) * 1000.0)

        doc_ids = [item.chunk.doc_id for item in retrieved]
        hit = hit_rate_at_k(example.get("expected_sources", []), doc_ids, TOP_K)
        per_example.append((example["id"], example["category"], hit))
        by_category.setdefault(example["category"], []).append(hit)

    hits = [h for _, _, h in per_example]
    return ConfigResult(
        name=name,
        complexity=complexity,
        hit_rate=sum(hits) / len(hits) if hits else 0.0,
        hit_by_category={cat: sum(vals) / len(vals) for cat, vals in sorted(by_category.items())},
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        n=len(per_example),
        per_example=per_example,
    )


def run_experiment(
    documents,
    embeddings: EmbeddingClient,
    examples: list[dict],
    persist_dir: Path,
    answer_llm: LLMClient | None = None,
    reranker: Reranker | None = None,
) -> list[ConfigResult]:
    """Build one index, then evaluate every configuration against it.

    `answer_llm` is only used for the (unscored here) generation step; retrieval
    is what we measure, so the offline mock is fine. `reranker` defaults to the
    deterministic `OverlapReranker` so the whole experiment runs offline; the
    runner swaps in a `CrossEncoderReranker` on the live path.
    """
    answer_llm = answer_llm or MockLLMClient()
    reranker = reranker or OverlapReranker()

    store, all_chunks = build_index(documents, embeddings, persist_dir)
    bm25 = BM25Index(all_chunks)

    results: list[ConfigResult] = []
    for name, complexity in CONFIGS:
        pipeline = make_pipeline(name, store, bm25, answer_llm, reranker)
        results.append(evaluate_config(name, complexity, pipeline, examples))
    return results


# --------------------------------------------------------------------------- #
# report writing
# --------------------------------------------------------------------------- #


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _delta(value: float, baseline: float) -> str:
    diff = value - baseline
    if abs(diff) < 1e-9:
        return "±0"
    return f"{diff:+.0%}"


def write_report(
    offline_results: list[ConfigResult],
    live_results: list[ConfigResult] | None,
    path: Path,
    context: dict,
) -> Path:
    """Write the retrieval-improvement report and return its path."""
    path = Path(path)
    baseline_off = offline_results[0].hit_rate
    lines: list[str] = [
        "# TechCorp Retrieval Improvement Report",
        "",
        "Module 17 re-runs the Module 09 retrieval evaluation under five",
        "configurations to measure — not assume — what each advanced-RAG",
        "technique does on the TechCorp corpus. Scored categories:",
        f"`{', '.join(SCORED_CATEGORIES)}` (the categories where retrieval is",
        "under test; unanswerable/ambiguous expect no sources, so hit@k is",
        "vacuously 1.0 there and they are excluded).",
        "",
        "**The rule for reading this report:** every number is measured against",
        "`data/evaluation/eval_dataset.json`. Where a technique did not help,",
        "the table says so. A flat or negative delta is a real finding.",
        "",
        "## Run context",
        "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in context.items())

    # Headline table = the real-embeddings run when available, else offline.
    headline = live_results or offline_results
    headline_label = (
        "sentence-transformers (real semantic embeddings)"
        if live_results
        else "hash embeddings (offline)"
    )
    baseline_head = headline[0].hit_rate

    lines += [
        "",
        f"## Headline: {headline_label}",
        "",
        "| config | complexity added | hit@4 | Δ vs baseline | latency ms/query |",
        "|---|---|---:|---:|---:|",
    ]
    for r in headline:
        lines.append(
            f"| `{r.name}` | {r.complexity} | {_pct(r.hit_rate)} | "
            f"{_delta(r.hit_rate, baseline_head)} | {r.avg_latency_ms:.1f} |"
        )

    # Per-category breakdown for the headline run — paraphrase is the story.
    categories = sorted({c for r in headline for c in r.hit_by_category})
    lines += [
        "",
        "### Per-category hit@4 (headline run)",
        "",
        "| config | " + " | ".join(categories) + " |",
        "|---|" + "|".join("---:" for _ in categories) + "|",
    ]
    for r in headline:
        cells = " | ".join(_pct(r.hit_by_category.get(cat, 0.0)) for cat in categories)
        lines.append(f"| `{r.name}` | {cells} |")

    if live_results:
        lines += [
            "",
            "## Offline reference: hash embeddings",
            "",
            "The same experiment with the deterministic hash embeddings the test",
            "suite uses. Hash embeddings match on word overlap only (no",
            "semantics), so absolute numbers differ from the headline — but this",
            "is the run every learner can reproduce with `TECHCORP_OFFLINE=true`.",
            "",
            "| config | hit@4 | Δ vs baseline | latency ms/query |",
            "|---|---:|---:|---:|",
        ]
        for r in offline_results:
            lines.append(
                f"| `{r.name}` | {_pct(r.hit_rate)} | {_delta(r.hit_rate, baseline_off)} "
                f"| {r.avg_latency_ms:.1f} |"
            )

    lines += [
        "",
        "## When is each technique worth it?",
        "",
        "- **Hybrid search (BM25 + vectors).** Worth it whenever queries carry",
        "  exact tokens the corpus also uses verbatim — product codes, policy",
        "  names, error strings. BM25 and dense embeddings fail *differently*:",
        "  BM25 is blind to synonyms, vectors dilute rare keywords. Fusing them",
        "  recovers the union. Cheap (an in-memory index), so it is usually the",
        "  first upgrade to reach for.",
        "- **Reranking (cross-encoder).** Worth it when retrieval returns the",
        "  right chunk but not in the top-k the generator sees — a precision fix,",
        "  not a recall fix. It cannot rescue a chunk retrieval never fetched.",
        "  Adds real latency (a transformer pass over the shortlist) and, live, a",
        "  model download, so adopt it only after measuring that ordering — not",
        "  coverage — is the bottleneck.",
        "- **Query rewriting / multi-query.** Worth it for paraphrase-heavy or",
        "  vague questions, where one alternate phrasing shares the corpus's",
        "  words. Cost is linear in the number of rewrites (N× the retrievals,",
        "  plus one LLM call to generate them), so it is the most expensive stage",
        "  per query.",
        "",
        "## Honest findings on THIS corpus",
        "",
    ]
    lines.extend(_findings(offline_results, live_results))
    lines += [
        "",
        "## Caveats",
        "",
        "- Retrieval latency here is wall-clock over a 13-document, in-memory",
        "  index on one machine; treat the ms numbers as *relative* costs",
        "  between configs, not production SLAs.",
        "- The offline rewrites are scripted and deliberately weak (a mock",
        "  cannot invent corpus vocabulary), so the offline multi-query row",
        "  understates what a real LLM rewrite achieves — compare it to the",
        "  headline run, not in isolation.",
        "- hit@4 measures *retrieval* only. Whether the generator then uses the",
        "  retrieved evidence faithfully is the Module 09 generation metrics'",
        "  job, unchanged here.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _findings(
    offline_results: list[ConfigResult], live_results: list[ConfigResult] | None
) -> list[str]:
    """Generate honest, data-driven bullets from the measured deltas."""
    runs = [("offline hash-embedding", offline_results)]
    if live_results:
        runs.append(("live sentence-transformer", live_results))

    bullets: list[str] = []
    for label, results in runs:
        by_name = {r.name: r for r in results}
        base = by_name["baseline"]
        if bullets:
            bullets.append("")
        bullets.append(f"On the **{label}** run (baseline hit@4 {_pct(base.hit_rate)}):")
        bullets.append("")
        for name in ("+hybrid", "+rerank", "+rewrite", "all"):
            r = by_name[name]
            diff = r.hit_rate - base.hit_rate
            if diff > 1e-9:
                verdict = f"HELPED ({_delta(r.hit_rate, base.hit_rate)})"
            elif diff < -1e-9:
                verdict = f"HURT ({_delta(r.hit_rate, base.hit_rate)}) — a real negative result"
            else:
                verdict = "NO CHANGE — did not move the needle on this corpus"
            # Call out the paraphrase category specifically.
            para = r.hit_by_category.get("paraphrase")
            base_para = base.hit_by_category.get("paraphrase")
            para_note = ""
            if para is not None and base_para is not None:
                pdiff = para - base_para
                if abs(pdiff) > 1e-9:
                    para_note = f" Paraphrase category: {_pct(base_para)} → {_pct(para)}."
                else:
                    para_note = f" Paraphrase category unchanged at {_pct(para)}."
            bullets.append(f"  - `{name}`: {verdict}.{para_note}")
    return bullets
