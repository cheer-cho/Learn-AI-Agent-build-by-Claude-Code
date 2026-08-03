"""The SupervisorAgent: route one question to one specialist, then synthesize.

This is the coordinator half of the supervisor pattern. Its job is deliberately
small:

1. **Route** the question to exactly one specialist — an LLM-constrained choice
   with a deterministic keyword fallback (the same defense the Module 11 tools
   router uses: if the model returns anything that is not a valid specialist
   name, ignore it and route on surface patterns).
2. **Hand off** only the question (plus minimal context) to that specialist —
   NOT the whole conversation. Shared-vs-private state is a real teaching point:
   the supervisor keeps the conversation; the specialist sees only what it needs
   to do its one job. Less context = fewer tokens, fewer ways to leak or
   confuse.
3. **Synthesize** the final answer. Here synthesis is pass-through +
   attribution (which specialist answered, and its sources). We deliberately do
   NOT spend a second LLM call to "rewrite" a correct grounded answer — see
   ``synthesize`` for the trade-off.
4. **Degrade gracefully**: if a specialist raises (a real bug, not an expected
   abstention), the supervisor catches it, apologizes, and suggests rephrasing —
   it never crashes the whole system because one leaf failed.

``last_specialist`` records who handled the most recent question, which the
tests assert on and a trace/dashboard would surface.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from techcorp_agent.agents.specialists import (
    OrdersSpecialist,
    PolicySpecialist,
    SpecialistResult,
    SupportSpecialist,
)
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.vectorstore.chroma_store import VectorStore

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)

# Surface-pattern signals for the deterministic fallback. Order matters: an
# explicit order id is the strongest signal, then support words, then policy.
_SUPPORT_WORDS = (
    "refund",
    "return",
    "returns",
    "restocking",
    "warranty",
    "damaged",
    "broken",
    "replacement",
    "escalation",
    "tier 2",
)
_POLICY_WORDS = (
    "policy",
    "vacation",
    "remote",
    "sick leave",
    "dress code",
    "denim",
    "jeans",
    "stipend",
    "equipment",
    "privacy",
    "gdpr",
    "retention",
    "deletion",
    "data",
    "handbook",
)

_VALID = ("policy", "support", "orders")


class SupervisorResult(BaseModel):
    """The supervisor's answer for one question, with attribution and accounting.

    ``llm_calls``/tokens include the supervisor's OWN routing call (and any
    synthesis call, if enabled) plus the specialist's call — the full cost of
    the multi-agent path, so the comparison is honest.
    """

    answer: str
    specialist: str
    sources: list[str] = Field(default_factory=list)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _route_prompt(question: str) -> list[ChatMessage]:
    system = (
        "You are a routing supervisor. Choose exactly ONE specialist to answer "
        "the user's question:\n"
        "- policy: HR handbook (remote work, vacation, sick leave, equipment, "
        "dress code) and privacy/data policy (retention, deletion, GDPR).\n"
        "- support: product support — returns, restocking, refunds for damaged "
        "products, warranty, support escalation.\n"
        "- orders: the status of a specific order named by its id (TC-####).\n\n"
        "Reply with ONLY the specialist name: policy, support, or orders. No "
        "punctuation, no explanation."
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=question),
    ]


def keyword_route(question: str) -> str:
    """Deterministically pick a specialist from surface patterns.

    Always returns a valid specialist name (defaults to 'policy' — the broadest
    knowledge domain — when nothing else matches), because the supervisor must
    always hand off to *someone*. Never calls a model, so it is the reliable
    floor under the LLM router.
    """
    text = question.lower()
    if _ORDER_ID_RE.search(question):
        return "orders"
    if any(w in text for w in _SUPPORT_WORDS):
        return "support"
    if any(w in text for w in _POLICY_WORDS):
        return "policy"
    return "policy"


class SupervisorAgent:
    """Coordinator over the three specialists.

    Args:
        store: the shared vector store the RAG specialists retrieve from.
        llm: the application LLM (mock offline). Used for the routing call and,
            when ``synthesize_with_llm`` is set, an optional synthesis call.
        synthesize_with_llm: OFF by default. When on, the supervisor spends an
            extra LLM call to rewrite the specialist's answer. See ``synthesize``
            for why pass-through is usually the better default.
    """

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        *,
        synthesize_with_llm: bool = False,
    ):
        self._llm = llm
        self._synthesize_with_llm = synthesize_with_llm
        self._specialists = {
            "policy": PolicySpecialist(store, llm),
            "support": SupportSpecialist(store, llm),
            "orders": OrdersSpecialist(store, llm),
        }
        self.last_specialist: str | None = None

    # -- routing ------------------------------------------------------------

    def route(self, question: str) -> tuple[str, int, int, int]:
        """Pick a specialist; return (name, llm_calls, input_tokens, output_tokens).

        LLM-constrained choice with a keyword fallback: if the model's reply is
        not one of the valid names, we route deterministically. Offline the mock
        never returns a valid name, so the fallback carries routing — which is
        exactly why it exists (and why routing works with no API key).
        """
        result = self._llm.complete(_route_prompt(question), temperature=0.0)
        reply = result.content.strip().strip(".").lower()
        chosen = reply if reply in _VALID else keyword_route(question)
        usage = result.usage
        return (
            chosen,
            1,
            usage.input_tokens if usage else 0,
            usage.output_tokens if usage else 0,
        )

    # -- synthesis ----------------------------------------------------------

    def synthesize(
        self, question: str, specialist_result: SpecialistResult
    ) -> tuple[str, int, int, int]:
        """Turn a specialist's result into the final user-facing answer.

        Default is pass-through + attribution: the specialist already produced a
        grounded, source-cited answer, so rewriting it with another LLM call
        would spend tokens and latency to (at best) reword something already
        correct — and at worst paraphrase away a precise policy number or drop a
        citation. The honest default is to relay it and name the specialist.

        The ``synthesize_with_llm`` path exists so the lab can MEASURE that
        trade-off: it adds a real second LLM call (more tokens, more latency) for
        a smoother single voice. Whether that is worth it is exactly the kind of
        thing the comparison in ``comparison.py`` makes you answer with numbers.

        Returns (answer, synth_llm_calls, input_tokens, output_tokens).
        """
        answer = specialist_result.answer
        if not self._synthesize_with_llm:
            return answer, 0, 0, 0

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are TechCorp's assistant. Rewrite the specialist's answer "
                    "below into one clear reply for the user. Do not add facts, do "
                    "not drop any cited sources or numbers."
                ),
            ),
            ChatMessage(
                role="user",
                content=f"Question: {question}\n\nSpecialist answer:\n{answer}",
            ),
        ]
        result = self._llm.complete(messages, temperature=0.0)
        usage = result.usage
        return (
            result.content,
            1,
            usage.input_tokens if usage else 0,
            usage.output_tokens if usage else 0,
        )

    # -- the public entry point --------------------------------------------

    def answer(self, question: str) -> SupervisorResult:
        """Route → hand off → synthesize, accounting for every LLM call.

        Graceful degradation: an *expected* outcome (unknown order, nothing
        retrieved → abstain) is a normal answer. An *unexpected* specialist crash
        is caught here and turned into an apology, so one broken leaf never takes
        down the supervisor. The routing call still counts against the cost even
        when the specialist then fails — that token was really spent.
        """
        specialist_name, route_calls, route_in, route_out = self.route(question)
        self.last_specialist = specialist_name
        specialist = self._specialists[specialist_name]

        try:
            result = specialist.handle(question)
        except Exception as exc:  # noqa: BLE001 - a leaf bug must not crash the system
            return SupervisorResult(
                answer=(
                    f"Sorry — I ran into a problem while handling that with the "
                    f"{specialist_name} specialist ({exc}). Could you rephrase your "
                    "question and try again?"
                ),
                specialist=specialist_name,
                sources=[],
                llm_calls=route_calls,
                input_tokens=route_in,
                output_tokens=route_out,
                failed=True,
            )

        final_answer, synth_calls, synth_in, synth_out = self.synthesize(question, result)

        return SupervisorResult(
            answer=final_answer,
            specialist=specialist_name,
            sources=result.sources,
            llm_calls=route_calls + result.llm_calls + synth_calls,
            input_tokens=route_in + result.input_tokens + synth_in,
            output_tokens=route_out + result.output_tokens + synth_out,
        )
