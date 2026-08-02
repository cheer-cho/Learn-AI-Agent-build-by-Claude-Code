"""Module 07 solution — main entry: run the chunking experiment, write the report.

Run:
    uv run python course/07_vector_database/solution/run_experiment.py

Works offline: if the real sentence-transformers model cannot be loaded (or
TECHCORP_OFFLINE=true), it falls back to the deterministic hash client and
says so — hash numbers measure word overlap, not semantics.

Output: artifacts/chunking_report.md (plus a summary table on stdout).
Indexing happens in a throwaway temporary directory, never in .chroma/.
"""

import tempfile
from pathlib import Path

from techcorp_agent.config import get_settings
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient

# solution/ is not a package; load the sibling file explicitly.
experiment = import_from_path(
    "m07_solution_chunking_experiment", Path(__file__).parent / "chunking_experiment.py"
)


def resolve_embedding_client() -> EmbeddingClient:
    """Real sentence-transformers when available, hash fallback otherwise."""
    try:
        client = get_embedding_client()
        client.embed(["warmup"])  # force the lazy model load/download NOW
    except Exception as exc:  # model missing, no download possible, ...
        print(f"NOTICE: real embedding model unavailable ({type(exc).__name__}: {exc}).")
        client = HashEmbeddingClient()
    if isinstance(client, HashEmbeddingClient):
        print(
            "NOTICE: using offline hash embeddings — the hit-rates below measure "
            "word overlap, NOT semantics. Re-run without TECHCORP_OFFLINE for real numbers."
        )
    return client


def main() -> int:
    settings = get_settings()
    documents = load_documents(settings.data_dir)
    if not documents:
        print(f"No documents found under {settings.data_dir} — nothing to experiment on.")
        return 1
    questions = experiment.load_eval_questions()

    embeddings = resolve_embedding_client()
    print(f"Embedding model: {embeddings.model_name}")
    print(f"Corpus: {len(documents)} documents; questions: {len(questions)}\n")

    results = []
    with tempfile.TemporaryDirectory(prefix="m07_chunking_") as tmp_dir:
        for config in experiment.CONFIGS:
            print(f"Running config {config['name']!r} ...")
            results.append(
                experiment.run_config(
                    **config,
                    questions=questions,
                    documents=documents,
                    embeddings=embeddings,
                    persist_dir=Path(tmp_dir),
                )
            )

    print(f"\n{'Config':<14} {'Chunks':>6} {'Avg chars':>10} {'Hit-rate':>9} {'Dup rate':>9}")
    for result in results:
        print(
            f"{result['name']:<14} {result['chunk_count']:>6} "
            f"{result['avg_chunk_chars']:>10.0f} {result['hit_rate']:>8.0%} "
            f"{result['duplicate_rate']:>8.1%}"
        )

    report_path = experiment.write_report(results, settings.artifacts_dir / "chunking_report.md")
    print(f"\nReport written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
