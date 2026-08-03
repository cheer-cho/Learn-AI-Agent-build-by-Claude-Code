"""Module 17 solution — run the retrieval experiment and write the artifact.

Runs the five-configuration retrieval experiment over the real TechCorp corpus
and writes `artifacts/retrieval_improvement_report.md`.

Two runs are attempted:

1. **Offline (hash embeddings)** — always runs, reproducible anywhere. This is
   the row every learner can regenerate with `TECHCORP_OFFLINE=true`.
2. **Live (sentence-transformers)** — real semantic embeddings, downloaded once
   and free. Skipped (with a notice) when unavailable or when
   TECHCORP_OFFLINE=true forces offline. When present, it becomes the report's
   headline table, and the cross-encoder reranker is used instead of the
   offline overlap approximation.

Run it:
    # offline only (fast, reproducible):
    TECHCORP_OFFLINE=true uv run python course/17_advanced_rag/solution/run_experiment.py

    # include the live sentence-transformers headline (downloads models once):
    uv run python course/17_advanced_rag/solution/run_experiment.py

Indexing happens in throwaway temporary directories — never in .chroma/.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.embeddings.st_client import SentenceTransformerClient

lab = import_from_path(
    "m17_solution_advanced_rag_lab", Path(__file__).parent / "advanced_rag_lab.py"
)


def _print_table(title: str, results: list) -> None:
    print(f"\n{title}")
    print(f"{'config':<10} {'hit@4':>7} {'Δbase':>7} {'ms/q':>8}   complexity")
    base = results[0].hit_rate
    for r in results:
        print(
            f"{r.name:<10} {r.hit_rate:>6.0%} {r.hit_rate - base:>+6.0%} "
            f"{r.avg_latency_ms:>7.1f}   {r.complexity}"
        )


def _run_offline(settings: Settings, documents, examples) -> list:
    """The always-available hash-embedding run (with the overlap reranker)."""
    print("=== OFFLINE run: hash embeddings + overlap reranker ===")
    with tempfile.TemporaryDirectory(prefix="m17-offline-") as tmp:
        results = lab.run_experiment(
            documents,
            HashEmbeddingClient(),
            examples,
            persist_dir=Path(tmp),
        )
    _print_table("offline hash-embedding hit@4:", results)
    return results


def _run_live(settings: Settings, documents, examples) -> list | None:
    """The real sentence-transformers run + cross-encoder reranker, or None."""
    if settings.techcorp_offline:
        print("\nNOTICE: TECHCORP_OFFLINE=true — skipping the live headline run.")
        return None
    print("\n=== LIVE run: sentence-transformers + cross-encoder reranker ===")
    try:
        from techcorp_agent.rag.advanced import CrossEncoderReranker

        embeddings = SentenceTransformerClient(settings)
        embeddings.embed(["warm up the model"])  # force the lazy load/download now
        reranker = CrossEncoderReranker()
        reranker._load()  # force the cross-encoder download now; fail fast if offline
    except Exception as exc:  # noqa: BLE001 — any load failure means "no live run"
        print(f"NOTICE: live models unavailable ({type(exc).__name__}: {exc}).")
        print("NOTICE: reporting the offline run as the headline instead.")
        return None

    with tempfile.TemporaryDirectory(prefix="m17-live-") as tmp:
        results = lab.run_experiment(
            documents,
            embeddings,
            examples,
            persist_dir=Path(tmp),
            reranker=reranker,
        )
    _print_table("live sentence-transformer hit@4:", results)
    return results


def main() -> int:
    settings = get_settings()
    documents = load_documents(settings.data_dir)
    examples = lab.load_scored_examples(settings)
    print(f"corpus:   {len(documents)} documents")
    print(f"examples: {len(examples)} scored ({', '.join(lab.SCORED_CATEGORIES)})\n")

    offline_results = _run_offline(settings, documents, examples)
    live_results = _run_live(settings, documents, examples)

    headline = "sentence-transformers" if live_results else "hash embeddings (offline)"
    report_path = lab.write_report(
        offline_results,
        live_results,
        settings.artifacts_dir / "retrieval_improvement_report.md",
        context={
            "headline embeddings": headline,
            "offline embeddings": HashEmbeddingClient().model_name,
            "live embeddings": settings.embedding_model if live_results else "not run",
            "reranker (offline)": "OverlapReranker (token-overlap approximation)",
            "reranker (live)": (
                "cross-encoder/ms-marco-MiniLM-L-6-v2" if live_results else "not run"
            ),
            "k (retrieval depth scored)": lab.TOP_K,
            "documents indexed": len(documents),
            "examples scored": len(examples),
        },
    )
    print(f"\nreport: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
