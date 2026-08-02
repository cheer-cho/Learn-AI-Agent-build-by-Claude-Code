"""Module 03 learner tests — mirrors test_solution.py against starter/.

Auto-skips while starter/langchain_labs.py still contains TODO markers.
Once you finish the labs, these tests become your completion gate:

    uv run pytest course/03_langchain/tests/test_my_work.py -q
"""

import json
from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/langchain_labs.py still has TODO markers — finish lab.md first",
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


@pytest.fixture(scope="module")
def labs():
    return import_from_path("m03_starter_langchain_labs", STARTER_DIR / "langchain_labs.py")


def test_lab_a_both_paths_return_the_same_scripted_content(labs):
    question = "How many remote days per week does TechCorp allow?"
    scripted = "TechCorp allows up to three remote days per week."

    raw_reply = labs.ask_raw_sdk(question, client=MockLLMClient(responses=[scripted]))
    lc_reply = labs.ask_langchain(question, model=labs.get_lc_model(scripted_responses=[scripted]))

    assert raw_reply == scripted
    assert lc_reply == scripted
    assert raw_reply == lc_reply


def test_lab_b_template_renders_all_five_variables(labs):
    prompt = labs.build_policy_prompt()
    assert set(prompt.input_variables) == set(labs.POLICY_VARIABLES)

    messages = prompt.format_messages(**POLICY_REQUEST)
    rendered = " ".join(message.content for message in messages)
    for value in POLICY_REQUEST.values():
        assert value in rendered


def test_lab_b_template_rejects_missing_variables(labs):
    prompt = labs.build_policy_prompt()
    with pytest.raises(KeyError):
        prompt.format_messages(policy_type="remote work")  # four variables missing


def test_lab_c_returns_a_populated_policy_summary_from_scripted_json(labs):
    model = labs.get_lc_model(scripted_responses=[SUMMARY_JSON])
    summary = labs.summarize_policy(labs.SAMPLE_POLICY_TEXT, model=model)

    assert isinstance(summary, labs.PolicySummary)
    assert summary.title == "Remote Work Policy"
    assert summary.audience == "All TechCorp employees"
    assert len(summary.key_rules) == 2
    assert summary.exceptions == ["On-call engineers must stay near the office"]


def test_lab_d_chain_invoke_returns_policy_summary_end_to_end(labs):
    chain = labs.build_policy_chain(model=labs.get_lc_model(scripted_responses=[SUMMARY_JSON]))
    result = chain.invoke(POLICY_REQUEST)

    assert isinstance(result, labs.PolicySummary)
    assert result.title == "Remote Work Policy"
    assert result.key_rules
    assert result.exceptions
