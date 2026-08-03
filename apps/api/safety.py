"""Safety at the API boundary: input/output validation and a per-session budget.

Module 20 ("Guardrails & Safety") teaches these controls at the graph level; the
production service re-applies them at its *edge*, because the HTTP boundary is
where untrusted input actually arrives. Three cheap, deterministic, offline-safe
controls live here:

- :func:`validate_input` — reject empty / oversized questions with a clear reason,
  before any model or retrieval work is spent on them.
- :func:`validate_output` — a last-line check that the agent's answer is a
  non-empty string; a blank answer becomes a safe fallback, never an empty 200.
- :class:`SessionBudget` — a per-``conversation_id`` request counter, so a single
  session cannot loop the service forever. This is the "budget enforcement" seam
  Module 20 introduces, kept intentionally tiny (a turn count) so it runs offline.

Design note (ties to Module 20's PII lesson): none of these functions log the raw
question or answer. They return *decisions and reasons*; the caller decides what,
if anything, to log — and the app only logs metadata (lengths, ids), never
content. Keeping secrets and user text out of logs is a guardrail, not an
afterthought.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Boundary limits. Small enough to be obvious in a lab; a real deployment would
# read these from configuration per environment (see concepts.md).
MAX_QUESTION_CHARS = 4000
MAX_TURNS_PER_SESSION = 50

# The safe answer we substitute when the agent returns nothing usable, so a
# degraded turn is still a clean, honest 200 rather than a blank body.
EMPTY_ANSWER_FALLBACK = (
    "I couldn't produce an answer for that. Please try rephrasing your question."
)


@dataclass
class ValidationResult:
    """The outcome of a boundary check.

    ``ok`` is the go/no-go; ``reason`` is a short, user-safe explanation (never
    the raw input) suitable for a 400 response body and a structured log line.
    """

    ok: bool
    reason: str = ""


def validate_input(question: object) -> ValidationResult:
    """Check an incoming question before spending any model/retrieval work on it.

    Rejects three classes of bad input with a clear reason:
    - not a string / missing (defends against malformed JSON payloads);
    - empty or whitespace-only (nothing to answer);
    - longer than :data:`MAX_QUESTION_CHARS` (a crude abuse / cost guard).
    """
    if not isinstance(question, str):
        return ValidationResult(False, "question must be a string")
    stripped = question.strip()
    if not stripped:
        return ValidationResult(False, "question must not be empty")
    if len(question) > MAX_QUESTION_CHARS:
        return ValidationResult(
            False, f"question is too long (max {MAX_QUESTION_CHARS} characters)"
        )
    return ValidationResult(True)


def validate_output(answer: object) -> str:
    """Return a guaranteed-non-empty answer string.

    The agent already degrades gracefully (a down tool becomes a message, not a
    crash), but a formatter edge case could still yield an empty string. This is
    the last line: an empty or non-string answer becomes the safe fallback, so
    the service never returns a blank 200 body.
    """
    if isinstance(answer, str) and answer.strip():
        return answer
    return EMPTY_ANSWER_FALLBACK


@dataclass
class SessionBudget:
    """A per-session turn counter — the simplest possible budget enforcer.

    Each ``conversation_id`` gets a running count of how many turns it has spent.
    Once a session exceeds :data:`MAX_TURNS_PER_SESSION`, further requests are
    refused at the boundary. In-process and non-durable on purpose: it shows the
    *shape* of budget enforcement (Module 20 measures tokens/cost; here we count
    turns) without adding an external store to a teaching service.
    """

    max_turns: int = MAX_TURNS_PER_SESSION
    _counts: dict[str, int] = field(default_factory=dict)

    def check_and_consume(self, conversation_id: str) -> ValidationResult:
        """Record one turn for ``conversation_id``; refuse once over budget."""
        used = self._counts.get(conversation_id, 0)
        if used >= self.max_turns:
            return ValidationResult(
                False,
                f"session budget exhausted (max {self.max_turns} turns per conversation)",
            )
        self._counts[conversation_id] = used + 1
        return ValidationResult(True)

    def turns_used(self, conversation_id: str) -> int:
        """How many turns ``conversation_id`` has spent (for /metrics, tests)."""
        return self._counts.get(conversation_id, 0)
