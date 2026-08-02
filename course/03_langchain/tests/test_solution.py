"""Module 03 solution tests — everything here runs offline.

The default suite uses scripted fake models only. The single @pytest.mark.live
test is excluded by the project-wide `-m "not live"` addopts and only runs on
demand with a real API key: `uv run pytest course/03_langchain -m live`.
"""

import json
from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]
labs = import_from_path(
    "m03_solution_langchain_labs", MODULE_DIR / "solution" / "langchain_labs.py"
)

POLICY_REQUEST = {
    "policy_type": "remote work",
    "audience": "all TechCorp employees",
    "length": "one page",
    "constraints": "no legal jargon",
    "output_format": "markdown with numbered sections",
}

SUMMARY_JSON = json.dumps(
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


def test_lab_a_both_paths_return_the_same_scripted_content():
    question = "How many remote days per week does TechCorp allow?"
    scripted = "TechCorp allows up to three remote days per week."

    raw_reply = labs.ask_raw_sdk(question, client=MockLLMClient(responses=[scripted]))
    lc_reply = labs.ask_langchain(question, model=labs.get_lc_model(scripted_responses=[scripted]))

    assert raw_reply == scripted
    assert lc_reply == scripted
    assert raw_reply == lc_reply


def test_lab_b_template_renders_all_five_variables():
    prompt = labs.build_policy_prompt()
    assert set(prompt.input_variables) == set(labs.POLICY_VARIABLES)

    messages = prompt.format_messages(**POLICY_REQUEST)
    rendered = " ".join(message.content for message in messages)
    for value in POLICY_REQUEST.values():
        assert value in rendered


def test_lab_b_template_rejects_missing_variables():
    prompt = labs.build_policy_prompt()
    with pytest.raises(KeyError):
        prompt.format_messages(policy_type="remote work")  # four variables missing


def test_lab_c_returns_a_populated_policy_summary_from_scripted_json():
    model = labs.get_lc_model(scripted_responses=[SUMMARY_JSON])
    summary = labs.summarize_policy(labs.SAMPLE_POLICY_TEXT, model=model)

    assert isinstance(summary, labs.PolicySummary)
    assert summary.title == "Remote Work Policy"
    assert summary.audience == "All TechCorp employees"
    assert len(summary.key_rules) == 2
    assert summary.exceptions == ["On-call engineers must stay near the office"]


def test_lab_d_chain_invoke_returns_policy_summary_end_to_end():
    chain = labs.build_policy_chain(model=labs.get_lc_model(scripted_responses=[SUMMARY_JSON]))
    result = chain.invoke(POLICY_REQUEST)

    assert isinstance(result, labs.PolicySummary)
    assert result.title == "Remote Work Policy"
    assert result.key_rules
    assert result.exceptions


def test_get_lc_model_rejects_an_empty_script():
    with pytest.raises(ValueError):
        labs.get_lc_model(scripted_responses=[])


@pytest.mark.live
def test_live_with_structured_output_returns_policy_summary():
    """Optional: verify a real provider's native structured output.

    Runs only with `-m live` and a configured OPENAI_API_KEY (spends credits).
    """
    from techcorp_agent.config import get_settings

    settings = get_settings()
    if settings.offline:
        pytest.skip("No API key configured — set OPENAI_API_KEY in .env")

    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.0,
    )
    structured = model.with_structured_output(labs.PolicySummary)
    result = structured.invoke("Summarize this TechCorp policy: " + labs.SAMPLE_POLICY_TEXT)

    assert isinstance(result, labs.PolicySummary)
    assert result.title
    assert result.key_rules
