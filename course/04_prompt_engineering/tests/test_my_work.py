"""Module 04 — tests for YOUR work in starter/.

These are skipped while starter files still contain TODO markers. Once you
remove every TODO by completing the code, they run automatically and become
your completion gate: `uv run pytest course/04_prompt_engineering -q`.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER),
    reason="starter/ still contains TODO markers — complete the lab first",
)

FIVE_SECTIONS = [
    "Applicable Requirements",
    "Current-Policy Observations",
    "Gaps",
    "Recommendations",
    "Implementation Steps",
]


@pytest.fixture(scope="module")
def prompts():
    return import_from_path("m04_starter_prompts", STARTER / "prompts.py")


@pytest.fixture(scope="module")
def rubric():
    return import_from_path("m04_starter_rubric", STARTER / "rubric.py")


# ---------------------------------------------------------------- prompt builders


def test_vague_prompt_is_vague(prompts):
    assert prompts.build_vague_prompt().strip() == "Write a policy."


def test_specific_prompt_contains_all_constraints_verbatim(prompts):
    prompt = prompts.build_specific_prompt(prompts.SPECIFIC_POLICY_CONSTRAINTS)
    assert "200-word" in prompt
    assert "GDPR" in prompt
    assert "30-day" in prompt
    assert "European customers" in prompt
    for heading in ["Purpose", "Scope", "Retention", "Your Rights"]:
        assert heading in prompt, f"missing required heading: {heading}"


def test_one_shot_prompt_contains_example_and_target(prompts):
    example = prompts.EXAMPLE_REFUND_POLICY
    target = "remote-work policy for TechCorp employees"
    prompt = prompts.build_one_shot_prompt(example, target)
    assert example in prompt
    assert target in prompt


def test_few_shot_prompt_contains_all_exemplars_and_question(prompts):
    question = "My package arrived crushed, what now?"
    prompt = prompts.build_few_shot_prompt(prompts.FEW_SHOT_EXEMPLARS, question)
    assert len(prompts.FEW_SHOT_EXEMPLARS) == 3
    for exemplar in prompts.FEW_SHOT_EXEMPLARS:
        assert exemplar in prompt
    assert question in prompt


def test_decomposed_prompt_names_all_five_sections(prompts):
    policy = "Support tickets are retained indefinitely."
    prompt = prompts.build_decomposed_prompt(policy)
    assert policy in prompt
    for label in FIVE_SECTIONS:
        assert label in prompt, f"missing section label: {label}"


# ---------------------------------------------------------------- rubric scorers


def test_score_word_limit_pass_and_fail(rubric):
    assert rubric.score_word_limit("one two three", 5) == 1.0
    assert rubric.score_word_limit("one two three four five six", 5) == 0.0
    assert rubric.score_word_limit("", 5) == 0.0


def test_score_required_headings_counts_fraction(rubric):
    text = "## Purpose\nstuff\n## Scope\nstuff"
    assert rubric.score_required_headings(text, ["Purpose", "Scope"]) == 1.0
    assert rubric.score_required_headings(text, ["Purpose", "Your Rights"]) == 0.5
    assert rubric.score_required_headings("nothing here", ["Purpose"]) == 0.0


def test_score_sections_present_checks_all_five_labels(rubric):
    full = "\n".join(f"{i}. {label}: ..." for i, label in enumerate(FIVE_SECTIONS, start=1))
    assert rubric.score_sections_present(full, FIVE_SECTIONS) == 1.0
    partial = "1. Applicable Requirements\n2. Gaps"
    assert rubric.score_sections_present(partial, FIVE_SECTIONS) == 2 / 5
    assert rubric.score_sections_present("a plain paragraph", FIVE_SECTIONS) == 0.0


def test_score_no_unsupported_claims_is_approximate_number_check(rubric):
    context = "Retention is a 30-day period under GDPR."
    assert rubric.score_no_unsupported_claims("We retain data for 30 days.", context) == 1.0
    assert rubric.score_no_unsupported_claims("We retain data for 90 days.", context) == 0.0
    mixed = rubric.score_no_unsupported_claims("30 days normally, 90 for backups.", context)
    assert mixed == 0.5
    assert rubric.score_no_unsupported_claims("We keep data briefly.", context) == 1.0


def test_score_output_and_total_score(rubric):
    text = "## Purpose\nA 30-day retention policy."
    scores = rubric.score_output(
        text, word_limit=50, headings=["Purpose"], context="30-day retention"
    )
    assert scores == {"word_limit": 1.0, "headings": 1.0, "supported_claims": 1.0}
    assert rubric.total_score(scores) == 1.0
    assert rubric.total_score({}) == 0.0
