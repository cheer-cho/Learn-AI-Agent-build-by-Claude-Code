"""Guardrails, safety, and cost control for the TechCorp agent (Module 20).

This package treats retrieved content and tool results as UNTRUSTED INPUT and
layers defenses around the RAG pipeline:

- :mod:`~techcorp_agent.safety.injection` — detect / demarcate / harden against
  prompt injection planted in documents.
- :mod:`~techcorp_agent.safety.validation` — validate questions in and answers
  out (citations, grounding, abstention format).
- :mod:`~techcorp_agent.safety.budget` — a per-session cost budget and a
  guarded model-call wrapper (token cap + timeout + budget).

All content is defensive: the learner attacks only their own local lab system
to learn how to protect it.
"""

from techcorp_agent.safety.budget import (
    BudgetExceeded,
    BudgetStatus,
    ModelCallTimeout,
    SessionBudget,
    guarded_complete,
)
from techcorp_agent.safety.injection import (
    InjectionFinding,
    detect_injection,
    harden_system_prompt,
    sanitize_context,
)
from techcorp_agent.safety.validation import (
    MAX_QUESTION_CHARS,
    MIN_QUESTION_CHARS,
    ValidationReport,
    validate_answer,
    validate_question,
)

__all__ = [
    # injection
    "InjectionFinding",
    "detect_injection",
    "sanitize_context",
    "harden_system_prompt",
    # validation
    "ValidationReport",
    "validate_question",
    "validate_answer",
    "MIN_QUESTION_CHARS",
    "MAX_QUESTION_CHARS",
    # budget
    "SessionBudget",
    "BudgetStatus",
    "BudgetExceeded",
    "ModelCallTimeout",
    "guarded_complete",
]
