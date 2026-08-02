"""Module 08 solution — the six RAG scenarios over the real TechCorp corpus.

Builds a throwaway index of data/ in the system temp directory, then runs the
six scenarios the module's tests also cover: fully answerable, partially
answerable, unanswerable, conflicting chunks, low-similarity abstention, and
a multi-chunk question.

The pipeline is the shared `techcorp_agent.rag.RAGPipeline` — behavior-identical
to `solution/my_rag.MyRAGPipeline`, which is Module 08's whole point.

Run it (fully offline by default):
    uv run python course/08_rag/solution/demo.py

Offline (no OPENAI_API_KEY) the demo uses hash embeddings and a scripted mock
LLM whose replies follow the SOURCES protocol, so you see realistic pipeline
behavior without spending credits. With a key it uses your configured
embedding model and provider for real.
"""

import tempfile
from pathlib import Path

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.vectorstore.chroma_store import VectorStore

# (title, question, min_score, scripted offline reply — follows the SOURCES protocol)
SCENARIOS = [
    (
        "1. Fully answerable",
        "How many days per week must hybrid employees work from the office?",
        0.05,
        "Hybrid employees in office-based roles must work from a TechCorp office "
        "a minimum of 2 days per week.\nSOURCES: hr-remote-work",
    ),
    (
        "2. Partially answerable",
        "What is the home office stipend, and is there a preferred vendor list?",
        0.05,
        "The home office stipend is $500 per year, claimable through the expense "
        "system for desks, chairs, monitors, and similar equipment. The provided "
        "documents do not mention a preferred vendor list.\nSOURCES: hr-remote-work",
    ),
    (
        "3. Unanswerable",
        "What is TechCorp's current stock price?",
        0.05,
        f"{ABSTENTION_TEXT}\nSOURCES: none",
    ),
    (
        "4. Conflicting chunks",
        "Is there a restocking fee when a product arrives damaged, or do I get a full refund?",
        0.05,
        "The two policies differ: the standard return policy charges a 15% "
        "restocking fee on opened voluntary returns, but products that arrive "
        "damaged fall under the damaged-products policy, which grants a full "
        "refund with no restocking fee.\nSOURCES: support-returns, support-refund-damaged",
    ),
    (
        "5. Low-similarity retrieval",
        "Does TechCorp allow pet iguanas in offices?",
        0.30,  # raised threshold: weak word-overlap matches must not count as evidence
        "this reply must never be used — retrieval should come back empty",
    ),
    (
        "6. Multi-chunk question",
        "How long can I work remotely from another country, and what approvals do I need?",
        0.05,
        "You may work from another country for up to 30 calendar days per year "
        "with manager approval and 60 days advance notice; longer stays need "
        "joint Legal and HR approval and are only allowed from countries with a "
        "TechCorp entity. Domestic hybrid rules still apply.\n"
        "SOURCES: hr-international-remote, hr-remote-work",
    ),
]


def build_index() -> VectorStore:
    """Index the real data/ corpus into a throwaway directory under /tmp."""
    settings = get_settings()
    embeddings = (
        HashEmbeddingClient() if settings.offline else get_embedding_client(settings)
    )
    persist_dir = Path(tempfile.gettempdir()) / ".chroma-module08" / "corpus"
    store = VectorStore(embeddings, persist_dir=persist_dir, collection_name="module08_demo")
    store.reset()

    documents = load_documents(settings.data_dir)
    total = sum(store.add_chunks(chunk_document(doc)) for doc in documents)
    print(f"indexed {len(documents)} documents → {total} chunks ({embeddings.model_name})")
    return store


def get_scenario_llm(scripted_reply: str) -> LLMClient:
    """Scripted mock offline; the real configured provider when a key is set."""
    settings = get_settings()
    if settings.offline:
        return MockLLMClient(responses=[scripted_reply])
    return get_llm_client(settings)


def main() -> int:
    store = build_index()
    settings = get_settings()
    mode = "scripted mock (offline)" if settings.offline else f"live ({settings.openai_model})"
    print(f"LLM: {mode}")

    for title, question, min_score, scripted_reply in SCENARIOS:
        pipeline = RAGPipeline(store, get_scenario_llm(scripted_reply), min_score=min_score)
        retrieved = pipeline.retrieve(question)
        result = pipeline.answer(question)

        print(f"\n=== {title} (min_score={min_score}) ===")
        print(f"question:  {question}")
        print(f"retrieved: {[r.chunk.doc_id for r in retrieved]}")
        print(f"answer:    {result.answer}")
        print(f"sources:   {result.sources}")
        print(f"abstained: {result.abstained}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
