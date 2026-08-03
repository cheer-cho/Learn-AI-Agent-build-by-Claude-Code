"""Three focused specialist agents for the TechCorp multi-agent system (Module 18).

Each specialist owns ONE domain, a SMALL tool set, and a PRIVATE, focused
system prompt. That focus is the whole point of the pattern: instead of one
agent whose prompt has to describe every policy, every support edge case, and
every order rule at once (prompt bloat), each specialist's prompt describes
only its slice — so the model has less to confuse itself with (Module 11's
tool-confusion, made structural).

Design choice — plain callable classes, not LangGraph subgraphs
---------------------------------------------------------------
Every specialist here is a single deterministic pass: retrieve-then-answer
(policy, support) or look-up-then-format (orders). There is no branching, no
retry, no shared cross-node state *inside* a specialist. A LangGraph subgraph
would add nodes, edges, and a state schema to express a straight line — pure
ceremony that hides the teaching point. So each specialist is a small class
with a ``handle(question) -> SpecialistResult`` method. The supervisor
(``supervisor.py``) is where the graph-shaped coordination lives; keep the
leaves simple. (If a specialist later grows its own retry/verify loop — e.g.
Module 17's iterative retrieval — promoting *that one* to a subgraph is the
right call. Simpler is better until it isn't.)

All three run fully offline against a hash-embedding store and a scripted or
echo ``MockLLMClient``.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import RetrievedChunk
from techcorp_agent.tools.orders import make_order_lookup_tool
from techcorp_agent.vectorstore.chroma_store import VectorStore

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)


class SpecialistResult(BaseModel):
    """The normalized outcome of one specialist handling one question.

    Mirrors the ``ToolResult`` philosophy (Module 11): a specialist returns a
    result object, never raises past its own boundary for an *expected* outcome
    (unknown order, nothing retrieved). Unexpected bugs still raise — that is
    the supervisor's ``try/except`` teaching point, not something we swallow
    here.
    """

    specialist: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class _CategoryScopedRAG:
    """A RAGPipeline whose retrieval is restricted to an allow-list of categories.

    This is the mechanism that makes a specialist *specialist*: the policy agent
    literally cannot retrieve a product-support chunk, so it cannot be distracted
    by one. We do not modify the shared ``VectorStore``; we query each allowed
    category and merge by score, then hand the merged chunks to the ordinary
    grounded-answer path (same abstention + source-crediting contract as
    Module 08).
    """

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        categories: list[str],
        system_prompt: str,
        top_k: int = 4,
        min_score: float = 0.05,
    ):
        self._store = store
        self._llm = llm
        self._categories = categories
        self._top_k = top_k
        self._min_score = min_score
        # A private RAGPipeline carrying this specialist's focused system prompt.
        self._pipeline = _PromptedRAGPipeline(
            store, llm, system_prompt, top_k=top_k, min_score=min_score
        )

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        merged: list[RetrievedChunk] = []
        for category in self._categories:
            merged.extend(
                self._store.query(
                    question,
                    top_k=self._top_k,
                    category=category,
                    min_score=self._min_score,
                )
            )
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[: self._top_k]

    def answer(self, question: str) -> tuple[str, list[str], int, int, int]:
        """Return (answer, sources, llm_calls, input_tokens, output_tokens).

        Retrieving nothing abstains without an LLM call, so ``llm_calls`` is 0
        and the token counts are 0 — an honesty the comparison depends on.
        """
        chunks = self.retrieve(question)
        return self._pipeline.answer_from_chunks(question, chunks)


class _PromptedRAGPipeline(RAGPipeline):
    """A RAGPipeline that uses a specialist-specific system prompt and lets the
    caller supply pre-retrieved (category-scoped) chunks.

    Reuses the parent's grounding contract verbatim — abstention detection and
    "only credit supplied sources" — so the honesty guarantees are inherited,
    not re-implemented.
    """

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        system_prompt: str,
        top_k: int = 4,
        min_score: float = 0.05,
    ):
        super().__init__(store, llm, top_k=top_k, min_score=min_score)
        self._system_prompt = system_prompt

    def answer_from_chunks(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> tuple[str, list[str], int, int, int]:
        from techcorp_agent.rag.pipeline import (
            build_context_block,
            parse_answer,
        )
        from techcorp_agent.schemas import ChatMessage

        if not chunks:
            # Abstain without spending a model call (Module 08).
            return ABSTENTION_TEXT, [], 0, 0, 0
        messages = [
            ChatMessage(role="system", content=self._system_prompt),
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
        usage = result.usage
        in_tok = usage.input_tokens if usage else 0
        out_tok = usage.output_tokens if usage else 0
        return answer_text, sources, 1, in_tok, out_tok


# -- specialist system prompts (PRIVATE to each specialist) -------------------
#
# Each is deliberately narrow. Compare their combined length to a single agent's
# prompt that would have to hold all of this at once — that bloat is what the
# pattern trades graph complexity to avoid.

_POLICY_PROMPT = f"""You are TechCorp's HR & Privacy Policy specialist.

You answer questions about the employee handbook (remote work, vacation, sick
leave, equipment, dress code) and privacy/data policy (retention, deletion,
GDPR). You do NOT handle product support or order status — those go to other
specialists.

Rules:
1. Answer ONLY from the context documents supplied below.
2. If the context does not contain the answer, reply exactly:
   "{ABSTENTION_TEXT}"
3. Never invent policy details, numbers, or exceptions.
4. End with a final line: SOURCES: <comma-separated ids you used>, or
   "SOURCES: none" when abstaining."""

_SUPPORT_PROMPT = f"""You are TechCorp's Product Support specialist.

You answer product-support questions: returns, restocking fees, refunds for
damaged products, warranty coverage, and support escalation. You do NOT handle
HR/privacy policy or order-status lookups.

Escalation awareness (important): any refund over $500 requires Tier 2 manager
approval (48-hour SLA). When a question involves a refund that could exceed
$500, you MUST state the Tier 2 approval requirement if the supplied context
supports it.

Rules:
1. Answer ONLY from the context documents supplied below.
2. If the context does not contain the answer, reply exactly:
   "{ABSTENTION_TEXT}"
3. Never invent policy details, numbers, or exceptions.
4. End with a final line: SOURCES: <comma-separated ids you used>, or
   "SOURCES: none" when abstaining."""


class PolicySpecialist:
    """HR + Privacy policy specialist: RAG over employee_handbook + privacy.

    Small tool set: exactly one capability — grounded retrieval scoped to two
    document categories. No calculator, no order lookup. It cannot answer a math
    or order question, and that is the design, not a gap.
    """

    name = "policy"
    categories = ["employee_handbook", "privacy"]

    def __init__(self, store: VectorStore, llm: LLMClient):
        self._rag = _CategoryScopedRAG(store, llm, self.categories, _POLICY_PROMPT)

    def handle(self, question: str) -> SpecialistResult:
        return _rag_result(self.name, self._rag, question)


class SupportSpecialist:
    """Product-support specialist: RAG over product_support with refund/escalation
    awareness.

    The '>$500 refunds need Tier 2 approval' fact lives in the corpus
    (``support-escalation``); the private prompt tells the specialist to surface
    it. Small tool set: one grounded-retrieval capability scoped to
    product_support.
    """

    name = "support"
    categories = ["product_support"]

    def __init__(self, store: VectorStore, llm: LLMClient):
        self._rag = _CategoryScopedRAG(store, llm, self.categories, _SUPPORT_PROMPT)

    def handle(self, question: str) -> SpecialistResult:
        return _rag_result(self.name, self._rag, question)


class OrdersSpecialist:
    """Order-status specialist: a single order-lookup tool plus formatting.

    No RAG, no LLM call at all in the offline path — it extracts an order id,
    calls the read-only order tool, and formats the record. Handling an unknown
    order or a missing id is an ordinary result (a helpful message), never an
    exception. This is the 'small tool set' point at its extreme: one tool.
    """

    name = "orders"

    def __init__(self, store: VectorStore | None = None, llm: LLMClient | None = None):
        # store/llm accepted for a uniform constructor signature across
        # specialists; this specialist needs neither.
        self._tool = make_order_lookup_tool()

    def handle(self, question: str) -> SpecialistResult:
        match = _ORDER_ID_RE.search(question)
        if not match:
            return SpecialistResult(
                specialist=self.name,
                answer=(
                    "I could not find an order id in your question. Order ids look "
                    "like TC-1234 — please include one and I'll look it up."
                ),
            )
        order_id = match.group(0).upper()
        result = self._tool.run({"order_id": order_id})
        text = result.output if result.ok else (result.error or "order lookup failed")
        return SpecialistResult(specialist=self.name, answer=text)


def _rag_result(name: str, rag: _CategoryScopedRAG, question: str) -> SpecialistResult:
    """Run a category-scoped RAG specialist and record its LLM call + usage.

    A specialist that retrieves nothing abstains WITHOUT an LLM call (Module 08),
    so ``llm_calls`` is 0 in that case — which the comparison honestly reflects.
    Token usage comes straight off the real ``ChatResult.usage`` the model
    returned, not a recomputation.
    """
    answer, sources, llm_calls, in_tok, out_tok = rag.answer(question)
    return SpecialistResult(
        specialist=name,
        answer=answer,
        sources=sources,
        llm_calls=llm_calls,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )
