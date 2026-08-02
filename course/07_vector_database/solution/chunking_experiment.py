"""Module 07 solution — the chunking experiment.

Index the TechCorp corpus under several chunking configurations, ask the
evaluation questions against each throwaway index, and measure which
configuration puts the right document in the top results. There is no
universally best chunk size — this file is how you find out what is best
*for this corpus and these questions*.

The main entry point is run_experiment.py in the same directory.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.schemas import Document
from techcorp_agent.vectorstore.chroma_store import VectorStore

TOP_K = 4  # a hit = an expected source doc appears in the top-4 retrieved chunks
SHINGLE_SIZE = 8  # duplicate-content rate is measured over 8-word shingles
EVAL_CATEGORIES = ("answerable", "paraphrase")  # the retrievable questions

# The three configurations the lab compares. Feel free to add your own.
CONFIGS: list[dict[str, Any]] = [
    {"name": "small-fixed", "strategy": "fixed", "chunk_size": 300, "overlap": 30},
    {"name": "medium-fixed", "strategy": "fixed", "chunk_size": 800, "overlap": 100},
    {"name": "paragraph", "strategy": "paragraph", "chunk_size": 1200, "overlap": 0},
]


def load_eval_questions(dataset_path: Path | None = None) -> list[dict[str, Any]]:
    """Load the answerable + paraphrase questions from the evaluation dataset.

    Returns dicts with `id`, `question`, and `expected_sources` (document ids).
    The other categories (unanswerable, tool_routing, ...) are not retrieval
    questions, so they say nothing about chunking quality.
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


def _shingles(text: str) -> set[tuple[str, ...]]:
    """The set of SHINGLE_SIZE-word windows in `text` (lowercased)."""
    words = text.lower().split()
    return {
        tuple(words[i : i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)
    }


def duplicate_rate(chunks: list[str]) -> float:
    """Fraction of 8-word shingles that appear in more than one chunk.

    Overlap between consecutive chunks stores the same sentences twice; this
    measures how much of the index is that duplication. 0.0 = every shingle
    is unique to one chunk; 1.0 = every shingle appears in multiple chunks.
    """
    per_chunk = [_shingles(text) for text in chunks]
    counts: Counter[tuple[str, ...]] = Counter()
    for shingle_set in per_chunk:
        counts.update(shingle_set)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    duplicated = sum(count for count in counts.values() if count > 1)
    return duplicated / total


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
    """Index `documents` under one chunking configuration in a throwaway
    collection, run every question, and return the metrics as a dict.

    Metric keys: name, strategy, chunk_size, overlap, chunk_count,
    avg_chunk_chars, hit_rate, duplicate_rate, failures, question_count,
    top_k, embedding_model.
    """
    chunks = []
    for document in documents:
        chunks.extend(
            chunk_document(document, strategy=strategy, chunk_size=chunk_size, overlap=overlap)
        )

    # Throwaway collection: one per config name, reset before and after so a
    # re-run never mixes chunks from two configurations.
    collection_name = f"chunking_{name}".replace("-", "_")
    store = VectorStore(embeddings, persist_dir=Path(persist_dir), collection_name=collection_name)
    store.reset()
    store.add_chunks(chunks)

    hits = 0
    failures: list[dict[str, Any]] = []
    for question in questions:
        retrieved = store.query(question["question"], top_k=top_k)
        retrieved_doc_ids = [item.chunk.doc_id for item in retrieved]
        if any(source in retrieved_doc_ids for source in question["expected_sources"]):
            hits += 1
        else:
            failures.append(
                {
                    "id": question["id"],
                    "question": question["question"],
                    "expected_sources": question["expected_sources"],
                    "retrieved_doc_ids": retrieved_doc_ids,
                }
            )
    store.reset()  # leave the throwaway collection empty

    return {
        "name": name,
        "strategy": strategy,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunk_count": len(chunks),
        "avg_chunk_chars": (sum(len(c.text) for c in chunks) / len(chunks)) if chunks else 0.0,
        "hit_rate": (hits / len(questions)) if questions else 0.0,
        "duplicate_rate": duplicate_rate([c.text for c in chunks]),
        "failures": failures,
        "question_count": len(questions),
        "top_k": top_k,
        "embedding_model": embeddings.model_name,
    }


def write_report(results: list[dict[str, Any]], path: Path) -> Path:
    """Write the Markdown comparison report for a list of run_config results."""
    if not results:
        raise ValueError("write_report needs at least one result")
    first = results[0]
    embedding_model = str(first.get("embedding_model", "unknown"))
    is_hash = embedding_model.startswith("hash-embedding")
    client_kind = (
        "offline hash client (word-overlap only)" if is_hash else "sentence-transformers"
    )

    lines = [
        "# Module 07 — Chunking Experiment Report",
        "",
        f"- **Embedding client:** `{embedding_model}` ({client_kind})",
        f"- **Questions:** {first.get('question_count', '?')} "
        "(answerable + paraphrase, from `data/evaluation/eval_dataset.json`)",
        f"- **Hit criterion:** an expected source document appears among the "
        f"top-{first.get('top_k', TOP_K)} retrieved chunks",
        f"- **Duplicate-content rate:** fraction of {SHINGLE_SIZE}-word shingles "
        "appearing in more than one chunk",
        "",
        "> **Embedding-client caveat:** hash-embedding numbers measure *word overlap*, "
        "not semantics. Only sentence-transformers results reflect real semantic "
        "retrieval quality; hash results are a plumbing check, not an evaluation.",
        "",
        "## Comparison",
        "",
        "| Config | Strategy | Chunk size | Overlap | Chunks | Avg chunk chars | Hit-rate | Duplicate rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result['name']} | {result['strategy']} | {result['chunk_size']} "
            f"| {result['overlap']} | {result['chunk_count']} "
            f"| {result['avg_chunk_chars']:.0f} | {result['hit_rate']:.0%} "
            f"| {result['duplicate_rate']:.1%} |"
        )

    lines += ["", "## Observed failure cases", ""]
    for result in results:
        failures = result.get("failures", [])
        lines.append(f"### {result['name']} — {len(failures)} missed")
        lines.append("")
        if not failures:
            lines.append("No misses: every question found its expected source in the top results.")
        for failure in failures:
            expected = ", ".join(failure["expected_sources"])
            retrieved = ", ".join(dict.fromkeys(failure["retrieved_doc_ids"])) or "(nothing)"
            lines.append(
                f"- **{failure['id']}** — \"{failure['question']}\" "
                f"(expected `{expected}`; retrieved docs: `{retrieved}`)"
            )
        lines.append("")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
