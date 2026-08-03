"""Category-scoped retrieval for the v2 knowledge routes (Modules 17 + 18 + 08).

The policy and support routes each need two things at once:

- **Specialist scope (Module 18).** A policy answer must not be built from a
  product-support chunk and vice-versa; each route retrieves only from its own
  document categories. We reuse the Module 18 specialist prompts and category
  lists verbatim so the focus is identical to the standalone specialists.
- **Advanced retrieval (Module 17).** When ``advanced_rag`` is on, retrieval
  fuses BM25 with vector search and then reranks — the configuration the Module
  17 report found best offline (hybrid + rerank took paraphrase retrieval from
  60% to 100%). When it is off, retrieval is plain vector top-k, matching v1.

The class here is a thin **retriever**: it produces the ranked chunks and, on
request, runs the specialist's grounded-answer prompt over them. It reimplements
neither hybrid search nor the grounding contract — it composes
:func:`techcorp_agent.rag.advanced.hybrid_search`, the ``OverlapReranker``, and
the Module 08 ``parse_answer``/citation-filtering that the specialists already
use — so the honesty guarantees (cite only supplied sources, abstain cleanly)
are inherited, not copied.
"""

from __future__ import annotations

from techcorp_agent.agents.specialists import _POLICY_PROMPT, _SUPPORT_PROMPT
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.rag.advanced import OverlapReranker, build_bm25_index, hybrid_search
from techcorp_agent.rag.pipeline import (
    ABSTENTION_TEXT,
    build_context_block,
    parse_answer,
)
from techcorp_agent.safety.injection import harden_system_prompt
from techcorp_agent.schemas import ChatMessage, RetrievedChunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

# Which document categories each knowledge route may retrieve from. These mirror
# the Module 18 specialists exactly (PolicySpecialist / SupportSpecialist).
_CATEGORIES = {
    "policy": ["employee_handbook", "privacy"],
    "support": ["product_support"],
}
_PROMPTS = {"policy": _POLICY_PROMPT, "support": _SUPPORT_PROMPT}


class ScopedRetriever:
    """Retrieve within a specialist's categories, optionally with the Module 17
    hybrid+rerank upgrade, and answer with that specialist's hardened prompt.

    Args:
        store: the shared vector store.
        llm: the answer-generation LLM.
        categories: the document categories this retriever is scoped to.
        system_prompt: the specialist's focused system prompt (Module 18),
            hardened against injection at construction (Module 20).
        advanced_rag: turn on hybrid search + reranking.
        top_k: chunks handed to the grounded-answer prompt.
        rerank_pool: shortlist size fetched before the reranker trims to ``top_k``.
        min_score: the cosine floor for the plain-vector path (v1 default).
    """

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        categories: list[str],
        system_prompt: str,
        *,
        advanced_rag: bool = True,
        top_k: int = 4,
        rerank_pool: int = 10,
        min_score: float = 0.05,
    ):
        self._store = store
        self._llm = llm
        self._categories = categories
        self._system_prompt = harden_system_prompt(system_prompt)
        self._advanced = advanced_rag
        self._top_k = top_k
        self._rerank_pool = rerank_pool
        self._min_score = min_score
        self._reranker = OverlapReranker() if advanced_rag else None
        # A BM25 index scoped to this specialist's categories, built once. When
        # advanced_rag is off we never touch it.
        self._bm25 = _build_scoped_bm25(categories) if advanced_rag else None

    def _in_scope(self, chunk: RetrievedChunk) -> bool:
        return chunk.chunk.category in self._categories

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        """Return ranked, category-scoped chunks for ``question``.

        Advanced path: hybrid-fuse the category BM25 index with vector search,
        keep only in-scope chunks (the vector side is corpus-wide, so we filter),
        then rerank down to ``top_k``. Plain path: a category-filtered vector
        top-k per category, merged by score — identical to the Module 18
        specialist's ``_CategoryScopedRAG``.
        """
        if self._advanced and self._bm25 is not None:
            pool = max(self._top_k, self._rerank_pool)
            fused = hybrid_search(self._store, self._bm25, question, top_k=pool * 2)
            scoped = [c for c in fused if self._in_scope(c)][:pool]
            if self._reranker is not None and scoped:
                scoped = self._reranker.rerank(question, scoped, top_k=self._top_k)
            return scoped[: self._top_k]

        merged: list[RetrievedChunk] = []
        for category in self._categories:
            merged.extend(
                self._store.query(
                    question, top_k=self._top_k, category=category, min_score=self._min_score
                )
            )
        merged.sort(key=lambda c: c.score, reverse=True)
        return merged[: self._top_k]

    def answer_from_chunks(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[ChatMessage] | None = None,
    ) -> tuple[str, list[str]]:
        """Ground an answer in ``chunks`` using the specialist prompt.

        Reuses the Module 08 contract: abstain without a model call when there is
        nothing to ground in, credit only sources that were actually supplied,
        and drop citations on an abstention. ``history`` (a recap + preferences)
        rides alongside the strict system/user prompt so the answer is
        conversational without breaking grounding.
        """
        if not chunks:
            return ABSTENTION_TEXT, []
        messages = [
            ChatMessage(role="system", content=self._system_prompt),
            *(history or []),
            ChatMessage(
                role="user",
                content=(
                    f"Context documents:\n\n{build_context_block(chunks)}\n\nQuestion: {question}"
                ),
            ),
        ]
        result = self._llm.complete(messages)
        answer_text, sources = parse_answer(result.content)
        supplied = {c.chunk.doc_id for c in chunks}
        sources = [s for s in sources if s in supplied]
        if ABSTENTION_TEXT.lower() in answer_text.lower():
            sources = []
        return answer_text, sources


def build_specialist_retrievers(
    store: VectorStore, llm: LLMClient, *, advanced_rag: bool = True
) -> dict[str, ScopedRetriever]:
    """Build the policy + support retrievers used by the v2 knowledge routes."""
    return {
        name: ScopedRetriever(
            store,
            llm,
            _CATEGORIES[name],
            _PROMPTS[name],
            advanced_rag=advanced_rag,
        )
        for name in ("policy", "support")
    }


def _build_scoped_bm25(categories: list[str]):
    """Build a BM25 index over only the given document categories.

    BM25 needs the raw ``Chunk`` objects, which the vector store does not expose,
    so we recompute them from the corpus with the same loader + chunker the store
    was built from (deterministic, offline). Scoping the index to the
    specialist's categories is what keeps hybrid retrieval from surfacing an
    out-of-domain chunk on the lexical side.
    """
    from techcorp_agent.config import get_settings

    settings = get_settings()
    chunks = []
    for doc in load_documents(settings.data_dir):
        for chunk in chunk_document(doc):
            if chunk.category in categories:
                chunks.append(chunk)
    return build_bm25_index(chunks)
