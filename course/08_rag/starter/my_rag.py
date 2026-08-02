"""Module 08 starter — build your own RAG pipeline: retrieval → augmentation → generation.

Work through lab.md and replace each TODO. The script is runnable at every
stage: unimplemented steps stop with a pointer to the task instead of a crash.

Run it:
    uv run python course/08_rag/starter/my_rag.py
Check it:
    uv run pytest course/08_rag -q
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

# The grounding contract, prewritten. Note that ABSTENTION_TEXT is imported
# from techcorp_agent.rag: your pipeline's abstention wording must match the
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

# Prewritten: matches a "SOURCES: ..." line anywhere in the reply, any case.
# match.group(1) is everything after the colon.
_SOURCES_RE = re.compile(r"^\s*SOURCES:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Task 2: render retrieved chunks with their source ids for the prompt."""
    # TODO: For each retrieved chunk, render a section of the form
    #           [source: <doc_id>] <doc_title>
    #           <chunk text>
    #       (the doc_id/doc_title/text live on `retrieved.chunk`), then join
    #       the sections with "\n\n---\n\n" and return the result.
    raise NotImplementedError("build_context_block — see lab.md Task 2")


def parse_answer(raw: str) -> tuple[str, list[str]]:
    """Task 5: split the model reply into (answer_text, source_ids)."""
    # TODO: Find the SOURCES line with _SOURCES_RE.search(raw).
    #       - No match → return (raw.strip(), []).
    #       - Otherwise the answer is everything before the match, stripped.
    #       - If the sources field is empty or "none" (any case) → no sources.
    #       - Otherwise split on commas, strip whitespace, drop empties, and
    #         de-duplicate while preserving order.
    raise NotImplementedError("parse_answer — see lab.md Task 5")


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
        # TODO: Query self._store with the question, passing top_k=self._top_k
        #       and min_score=self._min_score, and return the result.
        raise NotImplementedError("retrieve — see lab.md Task 1")

    def build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
        """Task 3: assemble the grounded conversation — rules, evidence, question."""
        # TODO: Return two ChatMessages:
        #       1. a "system" message containing SYSTEM_PROMPT;
        #       2. a "user" message of the form
        #              Context documents:
        #
        #              <build_context_block(chunks)>
        #
        #              Question: <question>
        raise NotImplementedError("build_messages — see lab.md Task 3")

    def answer(self, question: str) -> RAGAnswer:
        """Tasks 4-8: the full pipeline — retrieve, generate, parse, verify."""
        # TODO: Task 8 — retrieve first; if NOTHING came back, return an
        #       abstaining RAGAnswer (answer=ABSTENTION_TEXT, sources=[],
        #       abstained=True) WITHOUT calling the LLM.
        # TODO: Task 4 — otherwise call self._llm.complete(...) with the
        #       grounded messages and parse_answer(...) the reply's content.
        # TODO: Task 6 — keep only source ids that are among the retrieved
        #       chunks' doc_ids (the model may cite documents it never saw).
        # TODO: Task 7 — the reply abstained if ABSTENTION_TEXT appears in the
        #       answer text (compare case-insensitively); an abstention carries
        #       no sources. Return the finished RAGAnswer.
        raise NotImplementedError("answer — see lab.md Tasks 4-8")


# --------------------------------------------------------------------------
# Demo run (prewritten): a three-chunk mini corpus and a scripted mock LLM,
# so every checkpoint output in lab.md is exact and reproducible offline.
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
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/08_rag/lab.md and work through the tasks in order.")
        raise SystemExit(1) from None
