"""Module 18 tests — the TechCorp multi-agent supervisor system.

Fully offline and deterministic: a hash-embedding vector store built from the
real ``data/`` corpus plus scripted ``MockLLMClient``s so routing and answers
are exact. No API key, no network.

Coverage:
- each specialist answers an in-domain question with the correct sources;
- the supervisor routes policy/support/orders questions to the right specialist
  (asserted via ``last_specialist``);
- a specialist that raises degrades to a graceful supervisor answer, not a crash;
- the comparison counts LLM calls correctly and the supervisor uses MORE calls
  than the single agent (with synthesis on) — asserted and embraced;
- token totals sum correctly from usage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.agents import (
    OrdersSpecialist,
    PolicySpecialist,
    RunOutcome,
    SupervisorAgent,
    SupportSpecialist,
    run_comparison,
    single_agent_outcome,
    write_comparison_report,
)
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    """A hash-embedding store indexed from the real TechCorp corpus (offline)."""
    persist = tmp_path_factory.mktemp("m18_chroma")
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=persist,
        collection_name="m18_test",
    )
    for doc in load_documents(DATA_DIR):
        vs.add_chunks(chunk_document(doc))
    return vs


# -- specialists: in-domain answers with correct sources --------------------


def test_policy_specialist_answers_with_source(store):
    llm = MockLLMClient(
        responses=["TechCorp employees get 25 vacation days per year.\nSOURCES: hr-vacation"]
    )
    spec = PolicySpecialist(store, llm)
    result = spec.handle("How many vacation days do employees get each year?")
    assert result.specialist == "policy"
    assert result.sources == ["hr-vacation"]
    assert "25" in result.answer
    assert result.llm_calls == 1
    assert result.total_tokens > 0


def test_policy_specialist_covers_privacy_category(store):
    """Policy owns both employee_handbook AND privacy; a retention question
    retrieves a privacy doc within scope."""
    llm = MockLLMClient(
        responses=["Order records are kept 7 years for tax law.\nSOURCES: privacy-retention"]
    )
    spec = PolicySpecialist(store, llm)
    result = spec.handle("How long are order records kept after account deletion?")
    assert result.specialist == "policy"
    assert result.sources == ["privacy-retention"]


def test_support_specialist_answers_with_source(store):
    llm = MockLLMClient(
        responses=["There is a 15% restocking fee for opened items.\nSOURCES: support-returns"]
    )
    spec = SupportSpecialist(store, llm)
    result = spec.handle("Is there a restocking fee if I return an opened product?")
    assert result.specialist == "support"
    assert result.sources == ["support-returns"]
    assert result.llm_calls == 1


def test_support_specialist_is_escalation_aware(store):
    """The >$500 refund → Tier 2 fact is in the corpus (support-escalation) and
    the support specialist surfaces it when that chunk is in scope."""
    llm = MockLLMClient(
        responses=[
            "Refunds over $500 require Tier 2 manager approval, which has a "
            "48-hour SLA.\nSOURCES: support-escalation"
        ]
    )
    spec = SupportSpecialist(store, llm)
    # A question whose retrieval surfaces the escalation doc within scope.
    result = spec.handle("What approval is needed for a refund over $500 on a damaged item?")
    assert result.specialist == "support"
    assert "Tier 2" in result.answer
    assert result.sources == ["support-escalation"]


def test_policy_specialist_cannot_reach_support_docs(store):
    """A specialist is 'specialist' because its retrieval is category-scoped: the
    policy agent's retrieval never returns a product_support chunk."""
    spec = PolicySpecialist(store, MockLLMClient())
    chunks = spec._rag.retrieve("restocking fee refund warranty return")  # noqa: SLF001
    assert chunks, "expected some in-scope chunks"
    assert all(c.chunk.category in ("employee_handbook", "privacy") for c in chunks)


def test_orders_specialist_looks_up_known_order(store):
    spec = OrdersSpecialist(store, MockLLMClient())
    result = spec.handle("Where is my order TC-1234 right now?")
    assert result.specialist == "orders"
    assert "TC-1234" in result.answer
    assert "in_transit" in result.answer
    assert result.llm_calls == 0  # order lookup needs no LLM call
    assert result.sources == []


def test_orders_specialist_missing_id_is_graceful(store):
    spec = OrdersSpecialist(store, MockLLMClient())
    result = spec.handle("Where is my order?")
    assert result.specialist == "orders"
    assert "order id" in result.answer.lower()
    assert result.llm_calls == 0


# -- supervisor routing ------------------------------------------------------


def _supervisor_with_route(store, route_reply: str, *specialist_answers: str) -> SupervisorAgent:
    """A supervisor whose scripted mock returns ``route_reply`` first, then the
    given specialist answer(s)."""
    llm = MockLLMClient(responses=[route_reply, *specialist_answers])
    return SupervisorAgent(store, llm)


def test_supervisor_routes_policy_question(store):
    sup = _supervisor_with_route(
        store,
        "policy",
        "Employees get 25 vacation days per year.\nSOURCES: hr-vacation",
    )
    result = sup.answer("How many vacation days do employees get?")
    assert sup.last_specialist == "policy"
    assert result.specialist == "policy"
    assert result.sources == ["hr-vacation"]


def test_supervisor_routes_support_question(store):
    sup = _supervisor_with_route(
        store,
        "support",
        "Opened items carry a 15% restocking fee.\nSOURCES: support-returns",
    )
    result = sup.answer("Is there a restocking fee on opened returns?")
    assert sup.last_specialist == "support"
    assert result.sources == ["support-returns"]


def test_supervisor_routes_orders_question(store):
    # The order id is a strong keyword signal; even a bad route reply falls back.
    sup = _supervisor_with_route(store, "not-a-name")
    result = sup.answer("Where is my order TC-1234?")
    assert sup.last_specialist == "orders"
    assert "TC-1234" in result.answer


def test_supervisor_keyword_fallback_on_bad_route_reply(store):
    """Offline the mock never returns a valid specialist name, so the keyword
    fallback carries routing — a policy question still reaches the policy
    specialist."""
    sup = SupervisorAgent(store, MockLLMClient())  # echo mode -> invalid route reply
    result = sup.answer("What is the vacation policy and how many days do I get?")
    assert sup.last_specialist == "policy"
    assert result.specialist == "policy"


# -- graceful failure --------------------------------------------------------


def test_specialist_exception_yields_graceful_supervisor_answer(store):
    class _Boom:
        name = "policy"

        def handle(self, question: str):
            raise RuntimeError("specialist exploded")

    sup = SupervisorAgent(store, MockLLMClient())
    sup._specialists["policy"] = _Boom()  # noqa: SLF001 - injecting a failing leaf
    result = sup.answer("What is the vacation policy?")
    assert result.failed is True
    assert "rephrase" in result.answer.lower()
    # The routing call was really spent, so it still counts.
    assert result.llm_calls == 1
    # A crash never leaks fake sources.
    assert result.sources == []


# -- comparison: call counting, token totals, supervisor costs more ----------


def _single_agent_fn():
    """A stub single-agent system: one LLM call, fixed usage per question."""

    def fn(question: str) -> RunOutcome:
        return RunOutcome(
            answer=f"single-agent answer to: {question}",
            sources=[],
            llm_calls=1,
            input_tokens=100,
            output_tokens=20,
        )

    return fn


def test_comparison_counts_calls_and_tokens(store):
    """Supervisor (with synthesis on) makes MORE LLM calls than the single agent
    — assert and embrace it — and token totals sum from usage."""
    questions = [
        "How many vacation days do employees get?",
        "Is there a restocking fee on opened returns?",
    ]
    # Route + specialist + synthesis = 3 calls per RAG question for the
    # supervisor; the single-agent stub makes 1. Script route/answer/synth per Q.
    responses = [
        "policy",
        "25 vacation days per year.\nSOURCES: hr-vacation",
        "You get 25 vacation days a year.",
        "support",
        "15% restocking fee on opened items.\nSOURCES: support-returns",
        "Opened returns carry a 15% restocking fee.",
    ]
    sup = SupervisorAgent(store, MockLLMClient(responses=responses), synthesize_with_llm=True)

    results = run_comparison(questions, _single_agent_fn(), sup)

    single = results["single_agent"]
    multi = results["supervisor"]
    # Single agent: 2 questions * 1 call = 2.
    assert single["llm_calls"] == 2
    # Supervisor: 2 questions * 3 calls (route+specialist+synth) = 6.
    assert multi["llm_calls"] == 6
    # Embrace it: the supervisor costs strictly more calls and tokens.
    assert multi["llm_calls"] > single["llm_calls"]
    assert results["delta"]["extra_llm_calls"] == 4
    assert multi["total_tokens"] > 0
    # Token total is the sum of input + output for the system.
    assert multi["total_tokens"] == multi["input_tokens"] + multi["output_tokens"]
    assert single["total_tokens"] == 2 * (100 + 20)


def test_comparison_without_synthesis_ties_on_calls_but_costs_latency(store):
    """With synthesis OFF the supervisor spends route + specialist = 2 calls per
    RAG question, exactly matching a 2-call single agent — the honest 'not
    automatically more calls, but never fewer' result."""
    questions = ["How many vacation days do employees get?"]

    def single_two_calls(_q: str) -> RunOutcome:
        return RunOutcome(answer="x", llm_calls=2, input_tokens=50, output_tokens=10)

    sup = SupervisorAgent(
        store,
        MockLLMClient(responses=["policy", "25 days.\nSOURCES: hr-vacation"]),
        synthesize_with_llm=False,
    )
    results = run_comparison(questions, single_two_calls, sup)
    assert results["supervisor"]["llm_calls"] == 2
    assert results["single_agent"]["llm_calls"] == 2
    assert results["delta"]["extra_llm_calls"] == 0


def test_single_agent_outcome_adapter():
    state = {
        "answer": "hello",
        "sources": ["hr-vacation"],
        "_llm_calls": 2,
        "_input_tokens": 300,
        "_output_tokens": 40,
    }
    outcome = single_agent_outcome(state)
    assert outcome.answer == "hello"
    assert outcome.sources == ["hr-vacation"]
    assert outcome.llm_calls == 2
    assert outcome.total_tokens == 340


def test_write_comparison_report(store, tmp_path):
    questions = ["How many vacation days do employees get?"]
    sup = SupervisorAgent(
        store, MockLLMClient(responses=["policy", "25 days.\nSOURCES: hr-vacation"])
    )
    results = run_comparison(questions, _single_agent_fn(), sup)
    path = write_comparison_report(results, tmp_path / "cmp.md")
    text = path.read_text(encoding="utf-8")
    assert "Multi-Agent vs Single-Agent Comparison" in text
    assert "LLM calls" in text
    assert "ship the single agent" in text.lower()


def test_supervisor_abstains_out_of_domain(store):
    """An out-of-scope question: weak chunks may be retrieved, but the grounded
    prompt makes the specialist abstain, and the pipeline drops any sources."""
    sup = _supervisor_with_route(store, "policy", f"{ABSTENTION_TEXT}\nSOURCES: none")
    result = sup.answer("What is TechCorp's policy for working from the Moon?")
    assert result.specialist == "policy"
    assert ABSTENTION_TEXT in result.answer
    assert result.sources == []
    # Route call + one specialist call (weak chunks were retrieved and judged).
    assert result.llm_calls == 2


def test_specialist_abstains_without_call_when_nothing_retrieved(store):
    """When retrieval returns NOTHING in scope, the specialist abstains without
    spending an LLM call at all (Module 08) — llm_calls is 0.

    Hash embeddings rarely return a truly empty set against the real corpus, so
    we exercise the empty-retrieval branch of the specialist's grounded pipeline
    directly — the honest 'no chunks -> no model call -> abstain' contract."""
    llm = MockLLMClient()
    spec = SupportSpecialist(store, llm)
    answer, sources, calls, in_tok, out_tok = spec._rag._pipeline.answer_from_chunks(  # noqa: SLF001
        "anything", []
    )
    assert ABSTENTION_TEXT in answer
    assert sources == []
    assert calls == 0
    assert in_tok == 0 and out_tok == 0
    assert llm.calls == []  # no model call was made
