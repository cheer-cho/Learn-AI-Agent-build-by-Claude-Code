"""Module 04 solution — prompt builders for the four labs.

Each function returns a plain string prompt. Building prompts in code (instead
of typing them ad hoc) is the habit this module teaches: it makes prompts
testable, reviewable, and reusable — the prompt templates built here are reused
by the RAG modules later in the course.
"""

# Lab A — the required constraints for the specific policy prompt.
SPECIFIC_POLICY_CONSTRAINTS: dict = {
    "word_limit": 200,
    "audience": "European customers",
    "regulation": "GDPR",
    "retention_days": 30,
    "headings": ["Purpose", "Scope", "Retention", "Your Rights"],
}

# Lab B — one example policy, adapted from data/product_support/refund_damaged_products.md.
# The point of the example is its ORGANIZATION (headings, order, style), not its topic.
EXAMPLE_REFUND_POLICY = """\
# Refunds for Damaged Products

## Scope
This policy covers TechCorp products that arrive damaged at the moment of
delivery. Damage after delivery is handled under the Warranty Policy instead.

## Your Options
You are entitled to a full refund (including original shipping) or a free
replacement. Either option must be requested within 30 days of delivery.

## What We Need From You
Submit your order number (format TC-XXXX), photo evidence of the damage, and a
short description through the support portal.

## Timing
Approved refunds are processed within 5-10 business days to the original
payment method. Replacements dispatch within 2 business days of approval.

## Escalation
Tier 1 agents approve claims up to $500. Refunds exceeding $500 require Tier 2
manager approval, which can add up to 48 hours.
"""

# Lab C — three exemplar TechCorp support responses. Every exemplar shows the
# same tone (empathetic opening), the same format (What happened / What we'll
# do / Next steps), and mentions the escalation rule when money is involved.
FEW_SHOT_EXEMPLARS: list[str] = [
    """\
Hi Priya, thanks for reaching out — I'm sorry your monitor arrived with a
cracked panel; that's a frustrating way to start.

What happened: your TC-4821 order arrived damaged in transit.
What we'll do: you qualify for a full refund or a free expedited replacement.
Next steps: reply with one clear photo of the damage and tell me which option
you prefer. Since this item is under $500 I can approve it myself today; no
Tier 2 escalation is needed.

— TechCorp Support""",
    """\
Hi Marcus, thanks for reaching out — I'm sorry the refund hasn't appeared yet;
waiting on money you're owed is stressful.

What happened: your refund for order TC-3377 was approved and processed.
What we'll do: refunds always go to the original payment method and can take a
few extra days to show on your statement after processing.
Next steps: if it hasn't appeared within 10 business days of approval, reply
here and I will escalate to a Tier 2 manager for a payment trace.

— TechCorp Support""",
    """\
Hi Elena, thanks for reaching out — I'm sorry the replacement was the wrong
model; twice-shipped mistakes shouldn't happen.

What happened: order TC-9102 received an incorrect replacement unit.
What we'll do: we will ship the correct model with expedited handling at no
cost and send a prepaid label for the incorrect one.
Next steps: confirm your shipping address. Because the combined value exceeds
$500, this goes to a Tier 2 manager, which can add up to 48 hours.

— TechCorp Support""",
]

# Lab C — the style elements the few-shot answer must reproduce.
SUPPORT_STYLE_MARKERS: list[str] = [
    "thanks for reaching out",
    "I'm sorry",
    "What happened:",
    "What we'll do:",
    "Next steps:",
    "Tier 2",
    "— TechCorp Support",
]

# Lab D — the five labeled sections a decomposed review must produce.
DECOMPOSED_SECTIONS: list[str] = [
    "Applicable Requirements",
    "Current-Policy Observations",
    "Gaps",
    "Recommendations",
    "Implementation Steps",
]


def build_vague_prompt() -> str:
    """Lab A baseline: the prompt everyone writes first."""
    return "Write a policy."


def build_specific_prompt(constraints: dict) -> str:
    """Lab A: the same request with role, context, constraints, and output format.

    `constraints` uses the keys in SPECIFIC_POLICY_CONSTRAINTS:
    word_limit, audience, regulation, retention_days, headings.
    """
    headings = " / ".join(constraints["headings"])
    return (
        "You are a policy writer at TechCorp, a consumer electronics company.\n"
        f"Write a customer data retention policy for {constraints['audience']}.\n"
        "\n"
        "Constraints:\n"
        f"- Stay within a {constraints['word_limit']}-word limit.\n"
        f"- The policy operates under {constraints['regulation']}; name it explicitly.\n"
        f"- State a {constraints['retention_days']}-day retention period for "
        "customer support data after account closure.\n"
        f"- Use exactly these headings, in this order: {headings}.\n"
        "- Use only the facts given above. If a detail is not provided here, "
        "do not invent it.\n"
    )


def build_one_shot_prompt(example: str, target: str) -> str:
    """Lab B: one example ("shot") whose structure the model must transfer to `target`."""
    return (
        "You are a policy writer at TechCorp.\n"
        "Below is one example of a TechCorp policy. Study its organization: the\n"
        "headings it uses, their order, and the level of detail under each.\n"
        "\n"
        "=== EXAMPLE POLICY ===\n"
        f"{example}\n"
        "=== END EXAMPLE ===\n"
        "\n"
        f"Now write a {target} using the SAME headings in the SAME order,\n"
        "adapting the content under each heading to the new topic. Do not copy\n"
        "facts from the example; only reuse its structure.\n"
    )


def build_few_shot_prompt(examples: list[str], question: str) -> str:
    """Lab C: several exemplar support responses, then a new customer question."""
    blocks = []
    for i, example in enumerate(examples, start=1):
        blocks.append(f"=== EXAMPLE RESPONSE {i} ===\n{example}\n")
    joined = "\n".join(blocks)
    return (
        "You are a TechCorp customer support agent. Below are example responses\n"
        "that show our required tone (empathetic, personal), our format\n"
        "(What happened / What we'll do / Next steps), and our escalation rule\n"
        "(amounts over $500 go to a Tier 2 manager). Match all three exactly.\n"
        "\n"
        f"{joined}\n"
        "=== NEW CUSTOMER MESSAGE ===\n"
        f"{question}\n"
        "\n"
        "Write the support response in the same style as the examples.\n"
    )


def build_decomposed_prompt(policy_text: str) -> str:
    """Lab D: one prompt that forces five separate, labeled outputs.

    Instead of asking the model to reveal hidden reasoning, we ask for explicit
    intermediate outputs we can check one by one: requirements first, then
    observations, then the gap analysis that depends on both, and so on.
    """
    numbered = "\n".join(f"{i}. {label}" for i, label in enumerate(DECOMPOSED_SECTIONS, start=1))
    return (
        "You are a compliance analyst at TechCorp reviewing an internal policy\n"
        "against GDPR. Work through the review as five separate steps and\n"
        "output each step under its own numbered heading, exactly these:\n"
        "\n"
        f"{numbered}\n"
        "\n"
        "Rules for each section:\n"
        "1. Applicable Requirements — list only the GDPR requirements relevant\n"
        "   to this policy, each as one bullet citing the concept it comes from.\n"
        "2. Current-Policy Observations — neutral statements of what the policy\n"
        "   text below actually says. Quote or closely paraphrase; no judgment yet.\n"
        "3. Gaps — for each gap, name the requirement (from section 1) and the\n"
        "   observation (from section 2) it conflicts with. This is your\n"
        "   structured rationale: every gap must trace to evidence above.\n"
        "4. Recommendations — one concrete change per gap.\n"
        "5. Implementation Steps — an ordered, assignable task list.\n"
        "\n"
        "Use only the policy text below as evidence about TechCorp; do not\n"
        "invent policy details that are not written here.\n"
        "\n"
        "=== POLICY UNDER REVIEW ===\n"
        f"{policy_text}\n"
        "=== END POLICY ===\n"
    )
