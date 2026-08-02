"""Module 08 solution — MyRAGPipeline: retrieval → augmentation → generation.

This is the pipeline you build in lab.md, function by function. It is
behavior-identical to the shared library version in
`src/techcorp_agent/rag/pipeline.py` — the final step of the lab proves it.

Run it (fully offline, deterministic):
    uv run python course/08_rag/solution/my_rag.py
"""

import re
import tempfile
from pathlib import Path

from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import ChatMessage, Chunk, RAGAnswer, RetrievedChunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

# The grounding contract. Identical to the library's SYSTEM_PROMPT — and it
# must be: ABSTENTION_TEXT is imported so the abstention wording matches the
# library (and the tests) character for character.
SYSTEM_PROMPT = f"""You are TechCorp's internal knowledge assistant.

Rules you must follow:
1. Answer company-specific questions ONLY from the context documents supplied below.
2. If the context does not contain the answer, reply exactly:
   "{ABSTENTION_TEXT}"
3. Never invent policy details, numbers, or exceptions.
4. Keep the answer separate from the references.
5. End your reply with a final line of the form:
   SOURCES: <comma-separated source ids you actually used>
   or "SOURCES: none" when abstaining."""

# Matches the final "SOURCES: ..." line anywhere in the reply, any case.
_SOURCES_RE = re.compile(r"^\s*SOURCES:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Task 2: render retrieved chunks with their source ids for the prompt."""
    sections = []
    for retrieved in chunks:
        chunk = retrieved.chunk
        sections.append(f"[source: {chunk.doc_id}] {chunk.doc_title}\n{chunk.text}")
    return "\n\n---\n\n".join(sections)


def parse_answer(raw: str) -> tuple[str, list[str]]:
    """Task 5: split the model reply into (answer_text, source_ids)."""
    match = _SOURCES_RE.search(raw)
    if not match:
        return raw.strip(), []
    answer = raw[: match.start()].strip()
    sources_field = match.group(1).strip()
    if not sources_field or sources_field.lower() == "none":
        return answer, []
    sources = [s.strip() for s in sources_field.split(",") if s.strip()]
    # De-duplicate while preserving order.
    return answer, list(dict.fromkeys(sources))


class MyRAGPipeline:
    """Your own RAG pipeline — same contract as techcorp_agent.rag.RAGPipeline."""

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        top_k: int = 4,
        min_score: float | None = 0.05,
    ):
        self._store = store
        self._llm = llm
        self._top_k = top_k
        self._min_score = min_score

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        """Task 1: vector-search the store, keeping only chunks above the threshold."""
        return self._store.query(question, top_k=self._top_k, min_score=self._min_score)

    def build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
        """Task 3: assemble the grounded conversation — rules, evidence, question."""
        user_content = (
            f"Context documents:\n\n{build_context_block(chunks)}\n\nQuestion: {question}"
        )
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    def answer(self, question: str) -> RAGAnswer:
        """Tasks 4-8: the full pipeline — retrieve, generate, parse, verify."""
        chunks = self.retrieve(question)
        if not chunks:
            # Task 8: nothing relevant retrieved — abstain without spending a model call.
            return RAGAnswer(answer=ABSTENTION_TEXT, sources=[], abstained=True)

        result = self._llm.complete(self.build_messages(question, chunks))  # Task 4
        answer_text, sources = parse_answer(result.content)  # Task 5

        # Task 6: only credit sources that were actually in the supplied context.
        supplied_ids = {retrieved.chunk.doc_id for retrieved in chunks}
        sources = [s for s in sources if s in supplied_ids]

        # Task 7: an abstention carries no sources.
        abstained = ABSTENTION_TEXT.lower() in answer_text.lower()
        if abstained:
            sources = []
        return RAGAnswer(answer=answer_text, sources=sources, abstained=abstained)


# --------------------------------------------------------------------------
# Demo run: a three-chunk mini corpus and a scripted mock LLM, so every
# checkpoint output in lab.md is exact and reproducible offline.
# --------------------------------------------------------------------------

_MINI_CHUNKS = [
    Chunk(
        id="hr-dress-code#0",
        doc_id="hr-dress-code",
        doc_title="Dress Code Policy",
        category="employee_handbook",
        index=0,
        text="Business casual is the default dress code. Jeans are allowed at headquarters.",
    ),
    Chunk(
        id="hr-remote-work#0",
        doc_id="hr-remote-work",
        doc_title="Remote Work Policy",
        category="employee_handbook",
        index=0,
        text="Hybrid employees work from a TechCorp office a minimum of two days per week.",
    ),
    Chunk(
        id="support-refund-damaged#0",
        doc_id="support-refund-damaged",
        doc_title="Refunds for Damaged Products",
        category="product_support",
        index=0,
        text="Products that arrive damaged qualify for a full refund within thirty days of delivery.",
    ),
]


def build_mini_store() -> VectorStore:
    """Index the three-chunk mini corpus with deterministic hash embeddings."""
    persist_dir = Path(tempfile.gettempdir()) / ".chroma-module08" / "mini"
    store = VectorStore(
        HashEmbeddingClient(),
        persist_dir=persist_dir,
        collection_name="module08_mini",
    )
    store.reset()  # start clean on every run
    store.add_chunks(_MINI_CHUNKS)
    return store


def main() -> int:
    store = build_mini_store()
    question = "Can I wear jeans at headquarters?"
    # Hash embeddings score by word overlap; 0.10 filters out coincidental noise.
    min_score = 0.10

    print("--- Step 1: retrieve ---")
    pipeline = MyRAGPipeline(store, MockLLMClient(), min_score=min_score)
    retrieved = pipeline.retrieve(question)
    print(f"question: {question}")
    for item in retrieved:
        print(f"  {item.chunk.doc_id:<24} score={item.score:.3f}")

    print("\n--- Step 2: context block ---")
    print(build_context_block(retrieved))

    print("\n--- Step 3: grounded messages ---")
    for message in pipeline.build_messages(question, retrieved):
        first_line = message.content.splitlines()[0]
        print(f"[{message.role:<6}] {first_line}")

    print("\n--- Steps 4-7: grounded answer ---")
    llm = MockLLMClient(
        responses=["Yes — jeans are allowed at headquarters.\nSOURCES: hr-dress-code"]
    )
    result = MyRAGPipeline(store, llm, min_score=min_score).answer(question)
    print(f"answer:    {result.answer}")
    print(f"sources:   {result.sources}")
    print(f"abstained: {result.abstained}")

    print("\n--- Hallucinated citation is filtered ---")
    llm = MockLLMClient(
        responses=["Jeans are allowed at headquarters.\nSOURCES: hr-dress-code, fashion-blog-2026"]
    )
    result = MyRAGPipeline(store, llm, min_score=min_score).answer(question)
    print(f"sources:   {result.sources}  (fashion-blog-2026 was never supplied)")

    print("\n--- Step 8: nothing retrieved → abstain without an LLM call ---")
    llm = MockLLMClient(responses=["this response must never be used"])
    result = MyRAGPipeline(store, llm, min_score=min_score).answer(
        "What is on the cafeteria menu on Fridays?"
    )
    print(f"answer:    {result.answer}")
    print(f"sources:   {result.sources}")
    print(f"abstained: {result.abstained}")
    print(f"LLM calls: {len(llm.calls)}")

    print("\n--- Final: your pipeline vs the shared library ---")
    script = "Yes — jeans are allowed at headquarters.\nSOURCES: hr-dress-code"
    mine = MyRAGPipeline(store, MockLLMClient(responses=[script]), min_score=min_score)
    library = RAGPipeline(store, MockLLMClient(responses=[script]), min_score=min_score)
    same = mine.answer(question) == library.answer(question)
    print(f"identical RAGAnswer from both pipelines: {same}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
