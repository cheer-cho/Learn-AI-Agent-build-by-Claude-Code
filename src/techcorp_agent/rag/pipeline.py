"""The TechCorp RAG pipeline: retrieval → augmentation → generation.

This is the reference implementation learners build up to in Module 08 and
that later modules (evaluation, capstones, advanced RAG) reuse. Contract:

- Company-specific claims may come only from the supplied context.
- When the evidence is insufficient, the answer is the abstention text.
- Every generated answer carries the source document ids it used, parsed
  from a final "SOURCES:" line the prompt demands.
"""

import re

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage, RAGAnswer, RetrievedChunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

ABSTENTION_TEXT = (
    "I do not have enough information in the provided TechCorp documents "
    "to answer that question."
)

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

_SOURCES_RE = re.compile(r"^\s*SOURCES:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks with their source ids for the prompt."""
    sections = []
    for retrieved in chunks:
        chunk = retrieved.chunk
        sections.append(f"[source: {chunk.doc_id}] {chunk.doc_title}\n{chunk.text}")
    return "\n\n---\n\n".join(sections)


def parse_answer(raw: str) -> tuple[str, list[str]]:
    """Split the model reply into (answer_text, source_ids)."""
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


class RAGPipeline:
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
        return self._store.query(question, top_k=self._top_k, min_score=self._min_score)

    def build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
        user_content = (
            f"Context documents:\n\n{build_context_block(chunks)}\n\n"
            f"Question: {question}"
        )
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    def answer(self, question: str) -> RAGAnswer:
        chunks = self.retrieve(question)
        if not chunks:
            # Nothing relevant retrieved — abstain without spending a model call.
            return RAGAnswer(answer=ABSTENTION_TEXT, sources=[], abstained=True)

        result = self._llm.complete(self.build_messages(question, chunks))
        answer_text, sources = parse_answer(result.content)

        # Only credit sources that were actually in the supplied context.
        supplied_ids = {retrieved.chunk.doc_id for retrieved in chunks}
        sources = [s for s in sources if s in supplied_ids]

        abstained = ABSTENTION_TEXT.lower() in answer_text.lower()
        if abstained:
            sources = []
        return RAGAnswer(answer=answer_text, sources=sources, abstained=abstained)
