"""Module 07 starter — the chunking experiment.

Work through lab.md (Lab A) and replace each TODO. The config list, the
eval-question loader, and main() are already wired — your job is the three
measurement functions. The script is runnable at every stage: unimplemented
steps stop with a pointer to the task instead of a crash.

Run it:
    uv run python course/07_vector_database/starter/chunking_experiment.py
Check it:
    uv run pytest course/07_vector_database -q
"""

import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.schemas import Document
from techcorp_agent.vectorstore.chroma_store import VectorStore

TOP_K = 4  # a hit = an expected source doc appears in the top-4 retrieved chunks
SHINGLE_SIZE = 8  # duplicate-content rate is measured over 8-word shingles
EVAL_CATEGORIES = ("answerable", "paraphrase")  # the retrievable questions

# The three configurations the lab compares (pre-implemented — add your own later).
CONFIGS: list[dict[str, Any]] = [
    {"name": "small-fixed", "strategy": "fixed", "chunk_size": 300, "overlap": 30},
    {"name": "medium-fixed", "strategy": "fixed", "chunk_size": 800, "overlap": 100},
    {"name": "paragraph", "strategy": "paragraph", "chunk_size": 1200, "overlap": 0},
]


def load_eval_questions(dataset_path: Path | None = None) -> list[dict[str, Any]]:
    """Pre-implemented: the answerable + paraphrase questions from the eval set.

    Returns dicts with `id`, `question`, and `expected_sources` (document ids).
    """
    path = dataset_path or (get_settings().data_dir / "evaluation" / "eval_dataset.json")
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    return [
        {
            "id": example["id"],
            "question": example["question"],
            "expected_sources": list(example["expected_sources"]),
        }
        for example in examples
        if example["category"] in EVAL_CATEGORIES
    ]


def duplicate_rate(chunks: list[str]) -> float:
    """Task 2: fraction of 8-word shingles that appear in more than one chunk."""
    # TODO: For each chunk text, build the SET of SHINGLE_SIZE-word windows
    #       (lowercase, split on whitespace) — a set, so a shingle repeated
    #       inside ONE chunk does not count as a duplicate.
    # TODO: Count each shingle across all chunk-sets (collections.Counter helps).
    # TODO: Return (occurrences of shingles seen in >1 chunk) / (all occurrences).
    #       Return 0.0 when there are no shingles at all (empty/short chunks).
    raise NotImplementedError("duplicate_rate — see lab.md Lab A, Task 2")


def run_config(
    name: str,
    strategy: str,
    chunk_size: int,
    overlap: int,
    questions: list[dict[str, Any]],
    *,
    documents: list[Document],
    embeddings: EmbeddingClient,
    persist_dir: Path,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Task 3: index one configuration in a throwaway collection and measure it.

    Must return a dict with the keys: name, strategy, chunk_size, overlap,
    chunk_count, avg_chunk_chars, hit_rate, duplicate_rate, failures,
    question_count, top_k, embedding_model.
    """
    # TODO: Chunk every document with chunk_document(document, strategy=...,
    #       chunk_size=..., overlap=...) and collect all chunks in one list.
    # TODO: Create a VectorStore in persist_dir with a config-specific
    #       collection_name (e.g. f"chunking_{name}".replace("-", "_")),
    #       call store.reset() so a re-run starts clean, then add the chunks.
    # TODO: For each question, store.query(question["question"], top_k=top_k).
    #       It is a HIT when any expected_sources id appears among the
    #       retrieved chunks' doc_ids; otherwise record a failure dict:
    #       {"id", "question", "expected_sources", "retrieved_doc_ids"}.
    # TODO: store.reset() again (throwaway collection), then return the
    #       metrics dict described in the docstring. hit_rate = hits/questions;
    #       duplicate_rate comes from your Task 2 function on the chunk texts.
    raise NotImplementedError("run_config — see lab.md Lab A, Task 3")


def write_report(results: list[dict[str, Any]], path: Path) -> Path:
    """Task 4: write the Markdown comparison report and return its path."""
    # TODO: Build a Markdown document that contains, at minimum:
    #       - which embedding client produced it (results[0]["embedding_model"])
    #         and the caveat that hash-embedding numbers measure word overlap,
    #         not semantics;
    #       - a comparison table with one row per config: name, strategy,
    #         chunk_size, overlap, chunk_count, avg_chunk_chars, hit_rate,
    #         duplicate_rate;
    #       - a failure-cases section listing, per config, each missed question
    #         with its expected sources and the doc_ids actually retrieved.
    # TODO: path.parent.mkdir(parents=True, exist_ok=True), write the text,
    #       and return the Path.
    raise NotImplementedError("write_report — see lab.md Lab A, Task 4")


# ---------------------------------------------------------------------------
# Pre-implemented runner — do not edit below this line.
# ---------------------------------------------------------------------------


def resolve_embedding_client() -> EmbeddingClient:
    """Real sentence-transformers when available, hash fallback otherwise."""
    try:
        client = get_embedding_client()
        client.embed(["warmup"])  # force the lazy model load/download NOW
    except Exception as exc:
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
    questions = load_eval_questions()
    embeddings = resolve_embedding_client()
    print(f"Embedding model: {embeddings.model_name}")
    print(f"Corpus: {len(documents)} documents; questions: {len(questions)}\n")

    results = []
    with tempfile.TemporaryDirectory(prefix="m07_starter_") as tmp_dir:
        for config in CONFIGS:
            print(f"Running config {config['name']!r} ...")
            results.append(
                run_config(
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

    report_path = write_report(results, settings.artifacts_dir / "chunking_report.md")
    print(f"\nReport written to {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/07_vector_database/lab.md and work through Lab A in order.")
        raise SystemExit(1) from None
