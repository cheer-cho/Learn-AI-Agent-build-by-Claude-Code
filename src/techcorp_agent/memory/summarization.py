"""Token-budget management for a growing conversation history (Module 15, Lab B).

The v1 capstone answered one question at a time, so it never had to worry about
how long the conversation was. The moment we add memory (``checkpointing.py``),
every turn we replay grows the prompt — and a prompt is a finite context window
(Module 01). Left unchecked the history eventually overflows the budget and the
call gets expensive, slow, or rejected.

Two levers, both taught here:

- **Trimming** would simply drop old turns — cheap, but it *forgets* whatever it
  drops (zero fidelity for the dropped span).
- **Summarization** replaces the older turns with one compact summary message and
  keeps the most recent turns verbatim. It trades *fidelity for budget*: the gist
  of the old turns survives in far fewer tokens, while the recent turns — the ones
  a follow-up most likely refers to — stay exact.

Everything here is deterministic and offline-friendly: token counts use the same
~4-chars-per-token estimate the mock client uses, and the summary itself is a
plain LLM call (a scripted :class:`MockLLMClient` supplies the summary text in
tests and labs).
"""

from __future__ import annotations

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage

# The same rough estimate the offline mock uses (see llm/mock_client.py). Real
# providers count with a tokenizer (Module 01's tiktoken); ~4 chars/token is
# plenty for teaching the *shape* of budget management offline.
_CHARS_PER_TOKEN = 4

_SUMMARY_PREFIX = "Summary of earlier conversation: "


def estimate_history_tokens(messages: list[ChatMessage]) -> int:
    """Estimate how many tokens ``messages`` would cost as a prompt.

    Sums a per-message char count (role label + content) and divides by the
    ~4-chars-per-token constant. Deterministic, no tokenizer download, and
    consistent with the mock client's accounting so tests can reason exactly.
    """
    total_chars = 0
    for message in messages:
        # Count the role too: a real chat prompt spends tokens on role framing.
        total_chars += len(message.role) + len(message.content)
    return max(0, total_chars // _CHARS_PER_TOKEN)


def _is_summary(message: ChatMessage) -> bool:
    """True when a message is one we previously produced via summarization."""
    return message.role == "system" and message.content.startswith(_SUMMARY_PREFIX)


def summarize_history(
    llm: LLMClient,
    messages: list[ChatMessage],
    keep_recent: int = 4,
) -> list[ChatMessage]:
    """Compress older turns into one summary message, keep the recent ones verbatim.

    Returns a new message list of the form::

        [<summary system message>, <the last `keep_recent` messages unchanged>]

    The recent tail is preserved *exactly* — a follow-up like "what if I stay
    longer than that?" almost always refers to the latest turns, so those must
    keep full fidelity. Everything before the tail is handed to the LLM and
    replaced by a single ``system`` summary message.

    If there is nothing to compress (``len(messages) <= keep_recent``), the list
    is returned unchanged. An existing summary message at the head is folded into
    the new summary rather than summarized twice.
    """
    if keep_recent < 0:
        raise ValueError("keep_recent must be >= 0")
    if len(messages) <= keep_recent:
        return list(messages)

    older = messages[: len(messages) - keep_recent] if keep_recent else list(messages)
    recent = messages[len(messages) - keep_recent :] if keep_recent else []

    # Render the older turns for the summarizer prompt.
    transcript = "\n".join(f"{m.role}: {m.content}" for m in older)
    summary_messages = [
        ChatMessage(
            role="system",
            content=(
                "You compress a conversation so it fits a token budget. "
                "Summarize the following earlier turns in 2-3 sentences, preserving "
                "any facts, numbers, and decisions a later follow-up might rely on. "
                "Do not add new information."
            ),
        ),
        ChatMessage(role="user", content=transcript),
    ]
    summary_text = llm.complete(summary_messages, temperature=0.0).content.strip()

    summary_message = ChatMessage(role="system", content=f"{_SUMMARY_PREFIX}{summary_text}")
    return [summary_message, *recent]


def apply_budget(
    llm: LLMClient,
    messages: list[ChatMessage],
    max_tokens: int,
    keep_recent: int = 4,
) -> tuple[list[ChatMessage], bool]:
    """Keep ``messages`` under ``max_tokens``, summarizing older turns if needed.

    Returns ``(messages, was_summarized)``:

    - if the estimated size is already within budget, the list is returned
      unchanged and ``was_summarized`` is ``False``;
    - otherwise older turns are collapsed via :func:`summarize_history` and the
      (smaller) list is returned with ``was_summarized=True``.

    This is the single entry point the memory graph calls before each LLM turn:
    "trim-or-summarize under a budget" is a one-liner for the learner.
    """
    if estimate_history_tokens(messages) <= max_tokens:
        return list(messages), False
    return summarize_history(llm, messages, keep_recent=keep_recent), True
