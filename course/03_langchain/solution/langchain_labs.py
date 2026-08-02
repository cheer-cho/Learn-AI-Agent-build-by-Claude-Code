"""Module 03 — LangChain Fundamentals: reference solution.

Four labs in one file:

- Lab A: the same request through our own adapter (Module 02) and through LangChain.
- Lab B: a reusable TechCorp policy-document prompt template.
- Lab C: structured output with PydanticOutputParser (fully offline).
- Lab D: prompt | model | parser composed into a single runnable chain.

Everything runs offline:

    uv run python course/03_langchain/solution/langchain_labs.py
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
# Shared helper — every lab depends on this.
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
    result = client.complete(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=question),
        ]
    )
    return result.content


def ask_langchain(question: str, model: BaseChatModel | None = None) -> str:
    """LangChain path: same request through the framework's chat-model interface."""
    model = model or get_lc_model()
    reply = model.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(question)])
    return reply.text


# ---------------------------------------------------------------------------
# Lab B — a reusable TechCorp policy-document prompt template.
# ---------------------------------------------------------------------------

POLICY_VARIABLES = ("policy_type", "audience", "length", "constraints", "output_format")


def build_policy_prompt() -> ChatPromptTemplate:
    """Prompt template for drafting a TechCorp policy document.

    Five required variables: policy_type, audience, length, constraints,
    output_format. Missing any of them raises KeyError at render time.
    """
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are TechCorp's internal policy writer. Draft policy documents "
                "that are clear, specific, and safe to publish company-wide.",
            ),
            (
                "user",
                "Draft a {policy_type} policy for {audience}.\n"
                "Target length: {length}.\n"
                "Hard constraints: {constraints}.\n"
                "Return the document as: {output_format}.",
            ),
        ]
    )


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
    return PydanticOutputParser(pydantic_object=PolicySummary)


def summarize_policy(policy_text: str, model: BaseChatModel | None = None) -> PolicySummary:
    """Ask the model for a structured summary and parse it — one stage at a time.

    Offline path: pass ``model=get_lc_model(scripted_responses=[<valid JSON>])``.
    Live providers can skip the parser entirely with
    ``model.with_structured_output(PolicySummary)`` — see concepts.md.
    """
    parser = build_summary_parser()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract a structured summary of the policy below.\n{format_instructions}",
            ),
            ("user", "{policy_text}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    model = model or get_lc_model()
    messages = prompt.invoke({"policy_text": policy_text})  # stage 1: render
    reply = model.invoke(messages)  # stage 2: generate
    return parser.parse(reply.text)  # stage 3: validate


# ---------------------------------------------------------------------------
# Lab D — chain composition: prompt | model | parser as one runnable.
# ---------------------------------------------------------------------------


def build_policy_chain(model: BaseChatModel | None = None) -> Runnable:
    """Compose Lab B's request prompt, a model, and Lab C's parser into one runnable.

    Input: a dict with the five POLICY_VARIABLES.
    Output: a typed PolicySummary.
    """
    parser = build_summary_parser()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are TechCorp's internal policy writer. Draft the requested "
                "policy, then respond ONLY with its structured summary.\n"
                "{format_instructions}",
            ),
            (
                "user",
                "Draft a {policy_type} policy for {audience}.\n"
                "Target length: {length}.\n"
                "Hard constraints: {constraints}.\n"
                "Return the document as: {output_format}.",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    model = model or get_lc_model()
    return prompt | model | parser


# ---------------------------------------------------------------------------
# Demo data + one observable main() per lab.
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
    print(f"identical      : {raw_reply == lc_reply}")
    print("(same request, same reply — only the plumbing differs)\n")


def main_lab_b() -> None:
    print("=== Lab B — Policy prompt template ===")
    messages = render_policy_request(**SAMPLE_REQUEST)
    for message in messages:
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
    print(f"audience   : {summary.audience}")
    print(f"key_rules  : {summary.key_rules}")
    print(f"exceptions : {summary.exceptions}")
    print("(a validated Pydantic object, not a raw string)\n")


def main_lab_d() -> None:
    print("=== Lab D — Chain composition (prompt | model | parser) ===")
    chain = build_policy_chain(model=get_lc_model(scripted_responses=[SAMPLE_SUMMARY_JSON]))
    result = chain.invoke(SAMPLE_REQUEST)
    print(f"chain input  : {SAMPLE_REQUEST}")
    print(f"chain output : {result!r}")
    print(f"first rule   : {result.key_rules[0]}")
    print("(one invoke ran render -> generate -> validate)\n")


def main() -> None:
    main_lab_a()
    main_lab_b()
    main_lab_c()
    main_lab_d()


if __name__ == "__main__":
    main()
