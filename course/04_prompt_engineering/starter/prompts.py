"""Module 04 starter — prompt builders for the four labs.

Complete every function marked with `# TODO:`. Each function returns a plain
string prompt. Follow lab.md step by step; the tests in
course/04_prompt_engineering/tests/test_my_work.py become your completion gate
once the TODO markers are gone.
"""

# Lab A — the required constraints for the specific policy prompt.
# Your build_specific_prompt() receives this dict (or one shaped like it).
SPECIFIC_POLICY_CONSTRAINTS: dict = {
    "word_limit": 200,
    "audience": "European customers",
    "regulation": "GDPR",
    "retention_days": 30,
    "headings": ["Purpose", "Scope", "Retention", "Your Rights"],
}

# Lab B — write your one example policy here, adapted from
# data/product_support/refund_damaged_products.md. Keep clear headings —
# the whole lab is about transferring its STRUCTURE to a new topic.
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

# Lab C — write THREE exemplar TechCorp support responses. Each one must show:
#   - empathetic tone (a personal, apologetic opening),
#   - a specific format (e.g. What happened / What we'll do / Next steps),
#   - the escalation rule (amounts over $500 go to a Tier 2 manager).
# TODO: Replace the placeholders with three full exemplar responses.
FEW_SHOT_EXEMPLARS: list[str] = [
    "TODO: exemplar support response 1",
    "TODO: exemplar support response 2",
    "TODO: exemplar support response 3",
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
    """Lab A baseline: return exactly the vague request "Write a policy."."""
    # TODO: Return the vague baseline prompt.
    raise NotImplementedError


def build_specific_prompt(constraints: dict) -> str:
    """Lab A: build the constrained version of the same request.

    The returned prompt must contain, verbatim:
      - a role instruction (who the model is writing as),
      - the audience (constraints["audience"]),
      - the phrase "<word_limit>-word" (e.g. "200-word"),
      - the regulation name (constraints["regulation"], e.g. "GDPR"),
      - the phrase "<retention_days>-day" (e.g. "30-day"),
      - every heading in constraints["headings"],
      - an instruction not to invent facts that were not provided.
    """
    # TODO: Assemble and return the specific prompt from the constraints dict.
    raise NotImplementedError


def build_one_shot_prompt(example: str, target: str) -> str:
    """Lab B: one example whose structure the model must transfer to `target`.

    The returned prompt must contain the full `example` text, the `target`
    subject, and an instruction to reuse the example's headings and order
    while writing new content (not to copy the example's facts).
    """
    # TODO: Build and return the one-shot prompt.
    raise NotImplementedError


def build_few_shot_prompt(examples: list[str], question: str) -> str:
    """Lab C: several exemplar responses, then the new customer question.

    The returned prompt must contain every exemplar in `examples`, the
    `question`, and an instruction to match the exemplars' tone, format,
    and escalation rule.
    """
    # TODO: Build and return the few-shot prompt.
    raise NotImplementedError


def build_decomposed_prompt(policy_text: str) -> str:
    """Lab D: one prompt that forces five separate, labeled outputs.

    The returned prompt must contain `policy_text`, name all five labels in
    DECOMPOSED_SECTIONS, ask for each as its own labeled section, and require
    that gaps reference the requirements and observations they trace to
    (explicit intermediate outputs — not hidden reasoning).
    """
    # TODO: Build and return the decomposed review prompt.
    raise NotImplementedError
