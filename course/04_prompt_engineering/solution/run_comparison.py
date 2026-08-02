"""Module 04 solution — run all four labs offline and print a rubric score table.

Run from the repository root:

    uv run python course/04_prompt_engineering/solution/run_comparison.py

This script is fully offline. It sends each lab's prompts to a *scripted*
MockLLMClient loaded with two contrasting canned outputs per lab — a weak one
of the kind a vague/zero-shot prompt tends to produce, and a strong one of the
kind the engineered prompt tends to produce. The outputs are curated, not
generated, so the rubric comparison is deterministic and you can see the point
without an API key. With a real key (live mode, see lab.md) the same prompts
go to a real model and the differences become real rather than curated.
"""

from pathlib import Path

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage

_HERE = Path(__file__).resolve().parent
prompts = import_from_path("m04_solution_prompts", _HERE / "prompts.py")
rubric = import_from_path("m04_solution_rubric", _HERE / "rubric.py")

# --------------------------------------------------------------------------
# Canned outputs. WEAK_* imitates what a lazy prompt tends to get back;
# STRONG_* imitates what the engineered prompt tends to get back.
# --------------------------------------------------------------------------

WEAK_A = """\
Thank you for asking about a policy. Policies are very important documents for
any modern organization because they set expectations for employees, customers,
partners, vendors, contractors, and other stakeholders in a wide variety of
situations, and without policies an organization can drift into inconsistency.
A good policy should generally be clear, comprehensive, fair, well organized,
regularly reviewed, and communicated widely so that everyone understands what
is expected of them at all times and in all circumstances that may arise.
Organizations often keep customer records for 90 days, although some prefer 45
days depending on jurisdiction, industry norms, storage costs, and the general
appetite for risk that the leadership team happens to have in any given year.
It is also considered a best practice to consult legal counsel, review industry
standards, benchmark against competitors, survey stakeholders, run a pilot
program, gather feedback, iterate on the draft, and only then publish the
final version of the document through the appropriate internal channels.
Policies should additionally be stored in a central repository, version
controlled, translated where necessary, audited on a recurring schedule, and
retired gracefully when they no longer serve the needs of the business or its
customers, employees, or regulators. In conclusion, policies matter a great
deal, and writing one is an excellent first step toward organizational
maturity, resilience, accountability, and long-term operational excellence."""

STRONG_A = """\
Purpose
This policy explains how long TechCorp retains the personal data of European
customers and why. It supports our obligations under GDPR and gives customers
a clear, predictable standard for how their data is handled after they stop
using our services.

Scope
The policy covers personal data processed for European customers: account
details, order history, and support interactions. It applies to all TechCorp
systems and to vendors processing this data on our behalf.

Retention
Customer support data is retained for a 30-day period after account closure,
after which it is deleted from active systems. Data needed to meet legal or
contractual obligations is kept only as long as those obligations require,
consistent with GDPR storage-limitation principles.

Your Rights
European customers may request access, correction, deletion, or a portable
copy of their data at any time through the privacy request form. We honor
objections to processing based on legitimate interest, including marketing,
without requiring justification."""

WEAK_B = """\
Remote work is allowed at TechCorp. Employees should talk to their manager
about working from home and make sure they have a good internet connection.
Try to be online during normal business hours and keep your calendar up to
date. Security is important, so use the VPN. If you want to work from another
country for a while that is probably fine but check first. HR can answer any
other questions you might have about equipment or expenses."""

STRONG_B = """\
# Remote Work Policy

## Scope
This policy covers TechCorp employees working remotely on a recurring or
occasional basis. Fully remote roles negotiated at hiring are handled under
individual employment agreements instead.

## Your Options
Employees may work remotely up to three days per week by default, or request a
temporary fully-remote arrangement. Remote work from another country requires
manager approval before travel.

## What We Need From You
Submit a remote-work agreement through the HR portal, confirm your home
workspace meets the security checklist, and keep your working hours visible on
your team calendar.

## Timing
Standard requests are approved within 5 business days. Cross-border requests
take up to 10 business days because they require a compliance review.

## Escalation
Managers approve standard arrangements. Cross-border or fully-remote requests
require HR review, and disputes may be escalated to the department head."""

WEAK_C = """\
Your refund request has been received. Please allow some time for processing.
Note that photo evidence is required for damaged product claims, so send that
if you have not. Next steps: you will hear back from us in due course. Regards."""

STRONG_C = """\
Hi Jordan, thanks for reaching out — I'm sorry your soundbar arrived with a
dented casing; unboxing damage is disappointing and we'll make it right.

What happened: your order arrived damaged in transit, which qualifies under
our damaged-products policy.
What we'll do: you can choose a full refund, including original shipping, or a
free expedited replacement.
Next steps: reply with one clear photo of the dent and your order number, and
tell me which option you prefer. Because this item is over $500, approval goes
to a Tier 2 manager, which can add up to 48 hours — I'll flag it now so it
moves quickly.

— TechCorp Support"""

WEAK_D = """\
Overall this retention policy looks mostly reasonable but has some compliance
issues. Keeping support tickets forever is probably not great under European
privacy law, and the policy should mention deletion rights somewhere. There is
also no owner listed. My recommendations: clean up the wording, add a deletion
process, and have legal take a look at the telemetry section. Some
requirements around storage limitation likely apply here too, and the backup
handling could be a problem, so those parts should be reviewed and fixed."""

STRONG_D = """\
1. Applicable Requirements
- Storage limitation: personal data may be kept no longer than needed for its
  purpose (GDPR storage-limitation principle).
- Right to erasure: customers can request deletion of their data.
- Purpose limitation: data collected for support cannot be silently reused.
- Accountability: retention rules must have a named owner and review cycle.

2. Current-Policy Observations
- The policy states support tickets are "retained indefinitely for quality
  purposes."
- Backups are rotated on a 90-day cycle.
- Telemetry is kept for 24 months with no stated purpose.
- No section describes how customer deletion requests affect retained data.
- No policy owner or review schedule is named.

3. Gaps
- Indefinite ticket retention (observation) conflicts with storage limitation
  (requirement).
- Missing deletion-request handling (observation) conflicts with the right to
  erasure (requirement).
- Telemetry retention without a stated purpose (observation) conflicts with
  purpose limitation (requirement).
- Missing owner and review cycle (observation) conflicts with accountability
  (requirement).

4. Recommendations
- Replace indefinite ticket retention with a fixed 30-day period after account
  closure.
- Add a deletion-request procedure covering active systems and the 90-day
  backup cycle.
- Either document the purpose for 24 months of telemetry or shorten it.
- Name a policy owner and an annual review date.

5. Implementation Steps
- Draft the revised retention schedule and circulate to Legal.
- Build the deletion-request runbook, including backup expiry handling.
- Update the telemetry data map with purpose and lawful basis.
- Assign the policy owner and add the review date to the compliance calendar."""

# The Lab D policy under review — deliberately flawed so a review finds gaps.
POLICY_UNDER_REVIEW = """\
TechCorp Customer Data Retention Policy (draft)

Support tickets and their attachments are retained indefinitely for quality
purposes. Backups are rotated on a 90-day cycle. Product telemetry linked to
customer accounts is kept for 24 months. Account records are kept for a 30-day
period after account closure. Marketing preferences are stored until changed
by the customer."""

CUSTOMER_QUESTION = (
    "My new soundbar arrived today and the casing is dented. It cost $649. "
    "What are my options? — Jordan"
)

EXAMPLE_HEADINGS = ["Scope", "Your Options", "What We Need From You", "Timing", "Escalation"]


def _ask(client: MockLLMClient, prompt: str) -> str:
    return client.complete([ChatMessage(role="user", content=prompt)]).content


def run_lab_a() -> dict[str, dict[str, float]]:
    """Vague vs specific: same request, radically different constraint scores."""
    client = MockLLMClient(responses=[WEAK_A, STRONG_A])
    constraints = prompts.SPECIFIC_POLICY_CONSTRAINTS
    vague_out = _ask(client, prompts.build_vague_prompt())
    specific_prompt = prompts.build_specific_prompt(constraints)
    specific_out = _ask(client, specific_prompt)
    kwargs = {
        "word_limit": constraints["word_limit"],
        "headings": constraints["headings"],
        # "unsupported claims" is approximated against the facts the prompt
        # itself provided — the only controlled context in this lab.
        "context": specific_prompt,
    }
    return {
        "weak (vague)": rubric.score_output(vague_out, **kwargs),
        "strong (specific)": rubric.score_output(specific_out, **kwargs),
    }


def run_lab_b() -> dict[str, dict[str, float]]:
    """One-shot structure transfer: does the output reuse the example's headings?"""
    client = MockLLMClient(responses=[WEAK_B, STRONG_B])
    zero_shot = "Write a remote-work policy for TechCorp."
    one_shot = prompts.build_one_shot_prompt(
        prompts.EXAMPLE_REFUND_POLICY, "remote-work policy for TechCorp employees"
    )
    weak_out = _ask(client, zero_shot)
    strong_out = _ask(client, one_shot)
    kwargs = {"headings": EXAMPLE_HEADINGS}
    return {
        "weak (zero-shot)": rubric.score_output(weak_out, **kwargs),
        "strong (one-shot)": rubric.score_output(strong_out, **kwargs),
    }


def run_lab_c() -> dict[str, dict[str, float]]:
    """Few-shot style: does the answer match tone, format, and escalation rule?"""
    client = MockLLMClient(responses=[WEAK_C, STRONG_C])
    zero_shot = f"Answer this customer: {CUSTOMER_QUESTION}"
    few_shot = prompts.build_few_shot_prompt(prompts.FEW_SHOT_EXEMPLARS, CUSTOMER_QUESTION)
    weak_out = _ask(client, zero_shot)
    strong_out = _ask(client, few_shot)
    kwargs = {"section_labels": prompts.SUPPORT_STYLE_MARKERS}
    return {
        "weak (zero-shot)": rubric.score_output(weak_out, **kwargs),
        "strong (few-shot)": rubric.score_output(strong_out, **kwargs),
    }


def run_lab_d() -> dict[str, dict[str, float]]:
    """Decomposed review: are all five labeled sections actually present?"""
    client = MockLLMClient(responses=[WEAK_D, STRONG_D])
    blob = f"Review this policy for GDPR compliance:\n{POLICY_UNDER_REVIEW}"
    decomposed = prompts.build_decomposed_prompt(POLICY_UNDER_REVIEW)
    weak_out = _ask(client, blob)
    strong_out = _ask(client, decomposed)
    kwargs = {"section_labels": prompts.DECOMPOSED_SECTIONS}
    return {
        "weak (one blob)": rubric.score_output(weak_out, **kwargs),
        "strong (decomposed)": rubric.score_output(strong_out, **kwargs),
    }


def run_all() -> dict[str, dict[str, dict[str, float]]]:
    """Run every lab comparison; returns {lab: {variant: {criterion: score}}}."""
    return {
        "Lab A — vague vs specific": run_lab_a(),
        "Lab B — zero-shot vs one-shot": run_lab_b(),
        "Lab C — zero-shot vs few-shot": run_lab_c(),
        "Lab D — one blob vs decomposed": run_lab_d(),
    }


def print_table(results: dict[str, dict[str, dict[str, float]]]) -> None:
    for lab, variants in results.items():
        names = list(variants)
        criteria = list(variants[names[0]])
        print(f"\n=== {lab} " + "=" * max(1, 58 - len(lab)))
        header = f"{'criterion':<22}" + "".join(f"{name:>22}" for name in names)
        print(header)
        print("-" * len(header))
        for criterion in criteria:
            row = f"{criterion:<22}"
            for name in names:
                row += f"{variants[name][criterion]:>22.2f}"
            print(row)
        row = f"{'TOTAL':<22}"
        for name in names:
            row += f"{rubric.total_score(variants[name]):>22.2f}"
        print(row)


def main() -> None:
    print("Module 04 — prompt comparison (offline, scripted mock outputs)")
    print("Scores are deterministic rubric checks in [0, 1]; higher is better.")
    results = run_all()
    print_table(results)
    print(
        "\nNote: outputs above are curated canned responses so the contrast is\n"
        "visible offline. Set OPENAI_API_KEY in .env and adapt this script to\n"
        "get_llm_client() for real model outputs (see lab.md, live mode)."
    )


if __name__ == "__main__":
    main()
