"""Module 04 — tests for the reference solution (always run, fully offline)."""

from pathlib import Path

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]
SOLUTION = MODULE_DIR / "solution"

prompts = import_from_path("m04_solution_prompts", SOLUTION / "prompts.py")
rubric = import_from_path("m04_solution_rubric", SOLUTION / "rubric.py")
run_comparison = import_from_path("m04_solution_run_comparison", SOLUTION / "run_comparison.py")

FIVE_SECTIONS = [
    "Applicable Requirements",
    "Current-Policy Observations",
    "Gaps",
    "Recommendations",
    "Implementation Steps",
]


# ---------------------------------------------------------------- prompt builders


def test_vague_prompt_is_vague():
    assert prompts.build_vague_prompt().strip() == "Write a policy."


def test_specific_prompt_contains_all_constraints_verbatim():
    prompt = prompts.build_specific_prompt(prompts.SPECIFIC_POLICY_CONSTRAINTS)
    assert "200-word" in prompt
    assert "GDPR" in prompt
    assert "30-day" in prompt
    assert "European customers" in prompt
    for heading in ["Purpose", "Scope", "Retention", "Your Rights"]:
        assert heading in prompt, f"missing required heading: {heading}"


def test_one_shot_prompt_contains_example_and_target():
    example = prompts.EXAMPLE_REFUND_POLICY
    target = "remote-work policy for TechCorp employees"
    prompt = prompts.build_one_shot_prompt(example, target)
    assert example in prompt
    assert target in prompt


def test_few_shot_prompt_contains_all_exemplars_and_question():
    question = "My package arrived crushed, what now?"
    prompt = prompts.build_few_shot_prompt(prompts.FEW_SHOT_EXEMPLARS, question)
    assert len(prompts.FEW_SHOT_EXEMPLARS) == 3
    for exemplar in prompts.FEW_SHOT_EXEMPLARS:
        assert exemplar in prompt
    assert question in prompt


def test_decomposed_prompt_names_all_five_sections():
    policy = "Support tickets are retained indefinitely."
    prompt = prompts.build_decomposed_prompt(policy)
    assert policy in prompt
    for label in FIVE_SECTIONS:
        assert label in prompt, f"missing section label: {label}"


# ---------------------------------------------------------------- rubric scorers


def test_score_word_limit_pass_and_fail():
    assert rubric.score_word_limit("one two three", 5) == 1.0
    assert rubric.score_word_limit("one two three four five six", 5) == 0.0
    assert rubric.score_word_limit("", 5) == 0.0


def test_score_required_headings_counts_fraction():
    text = "## Purpose\nstuff\n## Scope\nstuff"
    assert rubric.score_required_headings(text, ["Purpose", "Scope"]) == 1.0
    assert rubric.score_required_headings(text, ["Purpose", "Your Rights"]) == 0.5
    assert rubric.score_required_headings("nothing here", ["Purpose"]) == 0.0


def test_score_sections_present_checks_all_five_labels():
    full = "\n".join(f"{i}. {label}: ..." for i, label in enumerate(FIVE_SECTIONS, start=1))
    assert rubric.score_sections_present(full, FIVE_SECTIONS) == 1.0
    partial = "1. Applicable Requirements\n2. Gaps"
    assert rubric.score_sections_present(partial, FIVE_SECTIONS) == 2 / 5
    assert rubric.score_sections_present("a plain paragraph", FIVE_SECTIONS) == 0.0


def test_score_no_unsupported_claims_is_approximate_number_check():
    context = "Retention is a 30-day period under GDPR."
    assert rubric.score_no_unsupported_claims("We retain data for 30 days.", context) == 1.0
    assert rubric.score_no_unsupported_claims("We retain data for 90 days.", context) == 0.0
    mixed = rubric.score_no_unsupported_claims("30 days normally, 90 for backups.", context)
    assert mixed == 0.5
    # No numeric claims at all -> nothing to flag.
    assert rubric.score_no_unsupported_claims("We keep data briefly.", context) == 1.0


def test_score_output_and_total_score():
    text = "## Purpose\nA 30-day retention policy."
    scores = rubric.score_output(
        text, word_limit=50, headings=["Purpose"], context="30-day retention"
    )
    assert scores == {"word_limit": 1.0, "headings": 1.0, "supported_claims": 1.0}
    assert rubric.total_score(scores) == 1.0
    assert rubric.total_score({}) == 0.0


# ---------------------------------------------------------------- offline comparison


def test_run_comparison_specific_outscores_vague_in_every_lab():
    results = run_comparison.run_all()
    assert len(results) == 4
    for lab, variants in results.items():
        weak_name = next(name for name in variants if name.startswith("weak"))
        strong_name = next(name for name in variants if name.startswith("strong"))
        weak = rubric.total_score(variants[weak_name])
        strong = rubric.total_score(variants[strong_name])
        assert strong > weak, f"{lab}: expected {strong_name} to outscore {weak_name}"


def test_run_comparison_lab_a_specific_meets_all_constraints():
    variants = run_comparison.run_lab_a()
    strong = variants["strong (specific)"]
    assert strong["word_limit"] == 1.0
    assert strong["headings"] == 1.0
    assert strong["supported_claims"] == 1.0
