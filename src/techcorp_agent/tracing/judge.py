"""LLM-as-judge — used to *refine*, never to *replace*, deterministic checks.

A model-based evaluator ("is this answer faithful and complete?") catches things
substring metrics miss: a correct paraphrase, a subtly wrong number, a confident
non-answer. But the spec rule for this course is absolute — **the judge is never
the only validation.** Three reasons, spelled out for learners:

1. **Circularity.** Grading an LLM's output with an LLM can reward the same blind
   spot that produced the error; a deterministic check has no such shared bias.
2. **Drift.** Judge scores wander as the judge model, its prompt, or its
   temperature change, so a "score went up" claim built on the judge alone is not
   reproducible across runs.
3. **Cost.** Every judged example is an extra model call; on a large dataset that
   is real money and latency, so the judge earns its place only where the cheap
   deterministic checks can't see.

So the contract in :func:`combine_scores` is: **deterministic checks gate** (a
deterministic failure is a failure, full stop), and the judge only *refines* the
score of examples that already passed the gate.

Offline, :func:`llm_judge` drives a scripted ``MockLLMClient`` through a
constrained rubric prompt and parses a strict ``SCORE`` / ``REASONING`` reply, so
the whole thing runs deterministically with no key.
"""

from __future__ import annotations

import re
from typing import Any

from techcorp_agent.schemas import ChatMessage

# A deliberately constrained rubric: one integer score and one line of reasoning.
# Constraining the output format is what makes the reply parseable offline and
# keeps a real judge from rambling (and running up tokens).
JUDGE_SYSTEM_PROMPT = """You are a strict evaluation judge for a company knowledge assistant.

Score how well the ANSWER responds to the QUESTION given the EVIDENCE, on a
0-5 integer scale:
  5 = fully correct, faithful to the evidence, and complete
  3 = partially correct or missing some required detail
  0 = wrong, unsupported by the evidence, or a non-answer

Rules:
- Judge ONLY against the supplied evidence. Reward faithful use of it.
- An honest "I don't have enough information" for an unanswerable question is
  correct behaviour; score it 5, not 0.
- Reply in EXACTLY this format and nothing else:
  SCORE: <integer 0-5>
  REASONING: <one sentence>"""

_SCORE_RE = re.compile(r"SCORE:\s*(\d+)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASONING:\s*(.*)", re.IGNORECASE | re.DOTALL)

# The judge's 0-5 scale, normalised onto 0.0-1.0 to compose with the
# deterministic metrics (which already live on 0.0-1.0).
_MAX_SCORE = 5


def build_judge_messages(question: str, answer: str, evidence: str) -> list[ChatMessage]:
    """The constrained rubric prompt sent to the judge model."""
    user = (
        f"QUESTION:\n{question}\n\n"
        f"EVIDENCE:\n{evidence or '(no evidence supplied)'}\n\n"
        f"ANSWER:\n{answer}"
    )
    return [
        ChatMessage(role="system", content=JUDGE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user),
    ]


def llm_judge(llm: Any, question: str, answer: str, evidence: str) -> dict[str, Any]:
    """Score one (question, answer, evidence) triple with an LLM judge.

    Returns ``{"score": float in [0,1], "reasoning": str, "raw_score": int}``.
    Offline, drive this with a scripted ``MockLLMClient`` so the score is exact;
    with a real key it calls the configured judge model. A malformed reply (no
    parseable ``SCORE``) is scored ``0.0`` with an explanatory reasoning rather
    than raising — a judge that can't answer is a *low* signal, not a crash.
    """
    result = llm.complete(build_judge_messages(question, answer, evidence), temperature=0.0)
    raw = result.content
    score_match = _SCORE_RE.search(raw)
    reason_match = _REASON_RE.search(raw)
    if not score_match:
        return {
            "score": 0.0,
            "raw_score": 0,
            "reasoning": f"unparseable judge reply: {raw[:120]!r}",
        }
    raw_score = max(0, min(_MAX_SCORE, int(score_match.group(1))))
    reasoning = reason_match.group(1).strip() if reason_match else ""
    return {
        "score": raw_score / _MAX_SCORE,
        "raw_score": raw_score,
        "reasoning": reasoning,
    }


def combine_scores(deterministic: dict[str, Any], judge: dict[str, Any] | None) -> dict[str, Any]:
    """Combine deterministic checks (the gate) with an optional judge (the refiner).

    Contract, in order:

    1. **The gate.** ``deterministic`` must carry a boolean ``passed`` (did every
       required deterministic check hold?). If it is ``False``, the combined
       result is a failure — ``passed=False``, ``score=0.0`` — **regardless of
       what the judge said.** The judge can never rescue a deterministic failure.
    2. **The refiner.** Only when the gate passes does the judge shape the score:
       the final score is the judge's normalised score (falling back to the
       deterministic score when no judge ran). The judge never *fails* an example
       the gate passed — it only adjusts the magnitude of a passing score.

    Returns ``{"passed", "score", "gate", "judge_score", "reasoning"}``.
    """
    gate_passed = bool(deterministic.get("passed", False))
    det_score = float(deterministic.get("score", 1.0 if gate_passed else 0.0))

    if not gate_passed:
        return {
            "passed": False,
            "score": 0.0,
            "gate": "deterministic-fail",
            "judge_score": (judge or {}).get("score"),
            "reasoning": "deterministic check failed; judge score ignored by policy",
        }

    if judge is None:
        return {
            "passed": True,
            "score": det_score,
            "gate": "deterministic-pass",
            "judge_score": None,
            "reasoning": "no judge run; deterministic score stands",
        }

    return {
        "passed": True,
        "score": float(judge.get("score", det_score)),
        "gate": "deterministic-pass",
        "judge_score": judge.get("score"),
        "reasoning": judge.get("reasoning", ""),
    }
