"""Module 09 solution — evaluate the RAG pipeline over the real TechCorp corpus.

Builds a fresh index over data/ (in a temporary Chroma directory, so your
`make index` store is untouched), runs every non-tool_routing example from
data/evaluation/eval_dataset.json through the pipeline, and writes
artifacts/evaluation_report.md.

Runs fully offline: with no OPENAI_API_KEY the LLM is the deterministic mock
(generation metrics become placeholders — the report says so), and if the
sentence-transformers model cannot be loaded/downloaded the script falls
back to hash embeddings with a notice.

Run it:
    uv run python course/09_grounding_and_evaluation/solution/run_eval.py
"""

import json
import tempfile
from pathlib import Path

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.evaluation import run_evaluation, summarize, write_report
from techcorp_agent.evaluation.runner import SKIPPED_CATEGORY
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.rag.pipeline import RAGPipeline
from techcorp_agent.vectorstore.chroma_store import VectorStore

TOP_K = 4


def load_examples(settings: Settings) -> list[dict]:
    """Read the shared evaluation dataset from data/evaluation/."""
    dataset_path = settings.data_dir / "evaluation" / "eval_dataset.json"
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return payload["examples"]


def choose_embedding_client(settings: Settings) -> EmbeddingClient:
    """The configured embedding client, or hash embeddings if it cannot load.

    The sentence-transformers model needs a one-time download; on a machine
    without network access that fails, and the evaluation must still run —
    with a clear notice, because hash retrieval scores mean something very
    different (word overlap only, no semantics).
    """
    client = get_embedding_client(settings)
    try:
        client.embed(["embedding warm-up"])  # force the lazy model load now
        return client
    except Exception as exc:  # noqa: BLE001 — any load failure means "go offline"
        print(f"NOTICE: could not load '{client.model_name}' ({exc}).")
        print(
            "NOTICE: falling back to hash embeddings — retrieval scores below "
            "measure word overlap only, and paraphrase questions will fail."
        )
        return HashEmbeddingClient()


def _print_summary(summary: dict) -> None:
    overall = summary["overall"]
    print(
        f"overall (n={overall['n']}): hit rate@{TOP_K} {overall['hit_rate']:.0%} | "
        f"source accuracy {overall['source_accuracy']:.0%} | "
        f"fact coverage {overall['fact_coverage']:.0%} | "
        f"abstention accuracy {overall['abstention_accuracy']:.0%}"
    )
    for category, stats in summary["per_category"].items():
        print(
            f"  {category:<12} (n={stats['n']}): hit rate {stats['hit_rate']:.0%} | "
            f"abstention {stats['abstention_accuracy']:.0%}"
        )


def run(settings: Settings) -> Path:
    """Build the index, run the evaluation, write the report. Returns its path."""
    examples = load_examples(settings)
    skipped = sum(1 for example in examples if example["category"] == SKIPPED_CATEGORY)
    documents = load_documents(settings.data_dir)

    embeddings = choose_embedding_client(settings)
    llm = get_llm_client(settings)
    print(f"embeddings: {embeddings.model_name}")
    print(f"llm:        {llm.name}")
    print(f"corpus:     {len(documents)} documents")
    print(f"dataset:    {len(examples)} examples ({skipped} tool_routing, skipped)\n")

    # A throwaway index directory: the evaluation must not depend on (or
    # corrupt) whatever .chroma/ state a previous module left behind.
    with tempfile.TemporaryDirectory(prefix="m09-eval-chroma-") as chroma_dir:
        store = VectorStore(embeddings, persist_dir=Path(chroma_dir))
        total_chunks = sum(store.add_chunks(chunk_document(doc)) for doc in documents)
        print(f"indexed:    {total_chunks} chunks\n")

        pipeline = RAGPipeline(store, llm, top_k=TOP_K)
        results = run_evaluation(pipeline, examples, k=TOP_K)

    summary = summarize(results)
    report_path = settings.artifacts_dir / "evaluation_report.md"
    write_report(
        results,
        summary,
        report_path,
        context={
            "embedding client": embeddings.model_name,
            "llm": llm.name,
            "k (retrieval depth scored)": TOP_K,
            "documents indexed": len(documents),
            "examples evaluated": len(results),
            "tool_routing examples skipped": skipped,
        },
    )

    _print_summary(summary)
    print(f"\nreport: {report_path}")
    return report_path


def main() -> int:
    run(get_settings())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
