"""Module 03 — LangChain Fundamentals: starter.

Complete the four labs by replacing each ``# TODO`` block. Work through them in
order — lab.md walks you through every step.

The helper ``get_lc_model`` is ALREADY IMPLEMENTED for you: it returns a fake,
scripted LangChain chat model when you are offline (or when you pass scripted
responses), and a real ChatOpenAI when an API key is configured. Every lab
builds on it — read it before you start.

Run your work at any time (it must always run, even half-finished):

    uv run python course/03_langchain/starter/langchain_labs.py
"""

from __future__ import annotations

import json

from langchain_core.language_models import BaseChatModel, FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from techcorp_agent.config import get_settings
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage

SYSTEM_PROMPT = "You are TechCorp's internal assistant. Answer briefly and factually."

DEFAULT_OFFLINE_REPLY = (
    "[offline fake model] No API key configured; this reply is scripted. "
    "Set OPENAI_API_KEY in .env to talk to a real provider."
)

# ---------------------------------------------------------------------------
# Shared helper — ALREADY IMPLEMENTED. Every lab depends on it.
# ---------------------------------------------------------------------------


def get_lc_model(scripted_responses: list[str] | None = None) -> BaseChatModel:
    """Return a LangChain chat model that works with or without an API key.

    - scripted_responses given  -> FakeListChatModel that replays them in order
      (cycling), fully deterministic. This is what the tests use.
    - no script, offline mode   -> FakeListChatModel with one canned reply, so
      every lab stays runnable without a key.
    - no script, key configured -> a real ChatOpenAI bound to the same settings
      that Module 02's raw client uses (.env: OPENAI_API_KEY / _BASE_URL / _MODEL).
    """
    if scripted_responses is not None:
        if not scripted_responses:
            raise ValueError("scripted_responses must contain at least one reply")
        return FakeListChatModel(responses=list(scripted_responses))

    settings = get_settings()
    if settings.offline:
        return FakeListChatModel(responses=[DEFAULT_OFFLINE_REPLY])

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.0,
        max_tokens=settings.max_output_tokens,
    )


# ---------------------------------------------------------------------------
# Lab A — SDK versus LangChain: the same request, two stacks.
# ---------------------------------------------------------------------------


def ask_raw_sdk(question: str, client: LLMClient | None = None) -> str:
    """Module 02 path: our own small adapter over the provider SDK (or the mock)."""
    client = client or get_llm_client()
    # TODO: Lab A (raw path) — build a system + user message pair with
    # techcorp_agent's ChatMessage, call client.complete(...), and return the
    # reply's .content string.
    raise NotImplementedError("Lab A: implement ask_raw_sdk")


def ask_langchain(question: str, model: BaseChatModel | None = None) -> str:
    """LangChain path: same request through the framework's chat-model interface."""
    model = model or get_lc_model()
    # TODO: Lab A (LangChain path) — invoke the model with a SystemMessage
    # (SYSTEM_PROMPT) and a HumanMessage (question), then return the reply text
    # (the AIMessage's .text property).
    raise NotImplementedError("Lab A: implement ask_langchain")


# ---------------------------------------------------------------------------
# Lab B — a reusable TechCorp policy-document prompt template.
# ---------------------------------------------------------------------------

POLICY_VARIABLES = ("policy_type", "audience", "length", "constraints", "output_format")


def build_policy_prompt() -> ChatPromptTemplate:
    """Prompt template for drafting a TechCorp policy document.

    Must require exactly the five POLICY_VARIABLES. Missing any of them must
    fail loudly (KeyError) at render time — LangChain does this for you.
    """
    # TODO: Lab B — return ChatPromptTemplate.from_messages([...]) with a
    # system message describing TechCorp's policy writer, and a user message
    # that uses all five placeholders: {policy_type}, {audience}, {length},
    # {constraints}, {output_format}.
    raise NotImplementedError("Lab B: implement build_policy_prompt")


def render_policy_request(**variables: str):
    """Fill the template and return the concrete messages LangChain would send."""
    return build_policy_prompt().format_messages(**variables)


# ---------------------------------------------------------------------------
# Lab C — structured output: text in, typed PolicySummary out.
# ---------------------------------------------------------------------------


class PolicySummary(BaseModel):
    title: str
    audience: str
    key_rules: list[str]
    exceptions: list[str]


def build_summary_parser() -> PydanticOutputParser:
    """Parser that turns a JSON reply into a validated PolicySummary."""
    # TODO: Lab C — return a PydanticOutputParser bound to PolicySummary.
    raise NotImplementedError("Lab C: implement build_summary_parser")


def summarize_policy(policy_text: str, model: BaseChatModel | None = None) -> PolicySummary:
    """Ask the model for a structured summary and parse it — one stage at a time.

    Offline path: pass ``model=get_lc_model(scripted_responses=[<valid JSON>])``.
    Live providers can skip the parser entirely with
    ``model.with_structured_output(PolicySummary)`` — see concepts.md.
    """
    # TODO: Lab C — build the parser, then a ChatPromptTemplate whose system
    # message embeds parser.get_format_instructions() (use .partial(...) or an
    # extra input variable) and whose user message carries {policy_text}.
    # Run the three stages by hand: prompt.invoke -> model.invoke ->
    # parser.parse(reply.text). Return the PolicySummary.
    raise NotImplementedError("Lab C: implement summarize_policy")


# ---------------------------------------------------------------------------
# Lab D — chain composition: prompt | model | parser as one runnable.
# ---------------------------------------------------------------------------


def build_policy_chain(model: BaseChatModel | None = None) -> Runnable:
    """Compose Lab B's request prompt, a model, and Lab C's parser into one runnable.

    Input: a dict with the five POLICY_VARIABLES.
    Output: a typed PolicySummary.
    """
    model = model or get_lc_model()
    # TODO: Lab D — build the parser, build a prompt that (a) asks for the
    # policy using all five POLICY_VARIABLES and (b) embeds the parser's format
    # instructions, then return: prompt | model | parser
    raise NotImplementedError("Lab D: implement build_policy_chain")


# ---------------------------------------------------------------------------
# Demo data + one observable main() per lab. No TODOs below this line —
# these run your functions and print what they produce.
# ---------------------------------------------------------------------------

SAMPLE_POLICY_TEXT = (
    "Employees may work remotely up to three days per week. Working remotely "
    "from another country requires manager approval. On-call engineers must "
    "stay within commuting distance of the office during their rotation."
)

SAMPLE_SUMMARY_JSON = json.dumps(
    {
        "title": "Remote Work Policy",
        "audience": "All TechCorp employees",
        "key_rules": [
            "Up to three remote days per week",
            "Cross-border remote work requires manager approval",
        ],
        "exceptions": ["On-call engineers must stay near the office"],
    }
)

SAMPLE_REQUEST = {
    "policy_type": "remote work",
    "audience": "all TechCorp employees",
    "length": "one page",
    "constraints": "no legal jargon; cite the employee handbook",
    "output_format": "markdown with numbered sections",
}


def main_lab_a() -> None:
    print("=== Lab A — SDK versus LangChain ===")
    question = "How many remote days per week does TechCorp allow?"
    scripted = "TechCorp allows up to three remote days per week."

    raw_reply = ask_raw_sdk(question, client=MockLLMClient(responses=[scripted]))
    lc_reply = ask_langchain(question, model=get_lc_model(scripted_responses=[scripted]))

    print(f"question       : {question}")
    print(f"raw SDK path   : {raw_reply}")
    print(f"LangChain path : {lc_reply}")
    print(f"identical      : {raw_reply == lc_reply}\n")


def main_lab_b() -> None:
    print("=== Lab B — Policy prompt template ===")
    for message in render_policy_request(**SAMPLE_REQUEST):
        print(f"[{message.type}] {message.content}")

    try:
        render_policy_request(policy_type="remote work")  # four variables missing
    except KeyError as exc:
        print(f"\nmissing variables rejected -> KeyError: {str(exc)[:90]}...")
    print()


def main_lab_c() -> None:
    print("=== Lab C — Structured output ===")
    model = get_lc_model(scripted_responses=[SAMPLE_SUMMARY_JSON])
    summary = summarize_policy(SAMPLE_POLICY_TEXT, model=model)
    print(f"type       : {type(summary).__name__}")
    print(f"title      : {summary.title}")
    print(f"key_rules  : {summary.key_rules}")
    print(f"exceptions : {summary.exceptions}\n")


def main_lab_d() -> None:
    print("=== Lab D — Chain composition (prompt | model | parser) ===")
    chain = build_policy_chain(model=get_lc_model(scripted_responses=[SAMPLE_SUMMARY_JSON]))
    result = chain.invoke(SAMPLE_REQUEST)
    print(f"chain output : {result!r}")
    print(f"first rule   : {result.key_rules[0]}\n")


def main() -> None:
    for name, lab in [
        ("A", main_lab_a),
        ("B", main_lab_b),
        ("C", main_lab_c),
        ("D", main_lab_d),
    ]:
        try:
            lab()
        except NotImplementedError as todo:
            print(f"[Lab {name}] not implemented yet -> {todo}. See lab.md.\n")


if __name__ == "__main__":
    main()
