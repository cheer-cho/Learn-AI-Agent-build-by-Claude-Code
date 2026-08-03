"""Compare the supervisor multi-agent system against the single-agent baseline.

THE HONESTY RULE of this module: multi-agent is not automatically better. The
only way to know is to run both systems on the same questions and read the
numbers — quality (does it answer, with the right sources?), token usage,
latency, and failure behavior. This module measures exactly that and writes a
Markdown report you can put in front of a skeptic.

What is measured, per system, over a list of questions:

- ``answers``      — the final text for each question (for eyeballing quality);
- ``sources``      — the cited source ids per question;
- ``llm_calls``    — total model calls. The supervisor makes MORE (a routing
  call per question on top of the specialist's answer call); this is not a bug
  to hide but the central cost of the pattern, so we count and report it;
- ``total_tokens`` — summed from real ``usage`` (input + output). Even against
  the offline mock, more calls = more tokens, and the mock computes usage
  deterministically, so the token delta between systems is real and repeatable;
- ``latency_s``    — wall-clock seconds. Offline this is dominated by retrieval,
  but the *shape* (supervisor ≥ single because it does strictly more work) is
  the lesson;
- ``failures``     — how many questions ended in a graceful failure answer.

Each system is described to ``run_comparison`` as a callable
``fn(question) -> RunOutcome`` so the two paths are measured through one code
path and cannot be scored on different rulers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field


class RunOutcome(BaseModel):
    """The normalized outcome of ONE system answering ONE question.

    Both the single agent and the supervisor are adapted to return this shape
    (see ``single_agent_outcome`` / ``supervisor_outcome``), so the harness
    scores them identically.
    """

    answer: str
    sources: list[str] = Field(default_factory=list)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class SystemMeasurement(BaseModel):
    """Aggregated measurements for one system across all questions."""

    name: str
    answers: list[str]
    sources: list[list[str]]
    llm_calls: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    latency_s: float
    failures: int


def run_comparison(
    questions: list[str],
    single_agent_fn: Callable[[str], RunOutcome],
    supervisor: object,
    llm_factory: Callable[[], object] | None = None,
) -> dict:
    """Run both systems over ``questions`` and return a comparison dict.

    Args:
        questions: the questions to run both systems on.
        single_agent_fn: ``fn(question) -> RunOutcome`` for the Module 14 single
            agent baseline (adapt it with ``single_agent_outcome``).
        supervisor: a ``SupervisorAgent``-like object with ``.answer(question)
            -> SupervisorResult`` (adapted internally via ``supervisor_outcome``).
        llm_factory: optional. If given, called once per system to obtain a
            FRESH LLM client, so the two systems do not share a scripted mock's
            response queue and each starts with a clean ``.calls`` log. Ignored
            here for measurement (each ``fn`` closes over its own client); kept
            in the signature because the lab wires fresh clients per system and
            this documents that contract.

    Returns:
        ``{"single_agent": {...}, "supervisor": {...}, "delta": {...}}`` where
        the per-system dicts are ``SystemMeasurement`` fields and ``delta``
        summarizes supervisor-minus-single for the headline numbers.
    """
    single = _measure("single_agent", questions, single_agent_fn)
    supervisor_fn = lambda q: supervisor_outcome(supervisor.answer(q))  # noqa: E731
    multi = _measure("supervisor", questions, supervisor_fn)

    delta = {
        "extra_llm_calls": multi.llm_calls - single.llm_calls,
        "extra_tokens": multi.total_tokens - single.total_tokens,
        "extra_latency_s": round(multi.latency_s - single.latency_s, 6),
        "extra_failures": multi.failures - single.failures,
    }
    return {
        "single_agent": single.model_dump(),
        "supervisor": multi.model_dump(),
        "delta": delta,
    }


def _measure(name: str, questions: list[str], fn: Callable[[str], RunOutcome]) -> SystemMeasurement:
    answers: list[str] = []
    sources: list[list[str]] = []
    llm_calls = in_tok = out_tok = failures = 0
    start = time.perf_counter()
    for question in questions:
        outcome = fn(question)
        answers.append(outcome.answer)
        sources.append(outcome.sources)
        llm_calls += outcome.llm_calls
        in_tok += outcome.input_tokens
        out_tok += outcome.output_tokens
        failures += 1 if outcome.failed else 0
    latency_s = time.perf_counter() - start
    return SystemMeasurement(
        name=name,
        answers=answers,
        sources=sources,
        llm_calls=llm_calls,
        total_tokens=in_tok + out_tok,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_s=round(latency_s, 6),
        failures=failures,
    )


# -- adapters: turn each system's native result into a RunOutcome -------------


def supervisor_outcome(result: object) -> RunOutcome:
    """Adapt a ``SupervisorResult`` to a ``RunOutcome``."""
    return RunOutcome(
        answer=result.answer,
        sources=list(result.sources),
        llm_calls=result.llm_calls,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        failed=result.failed,
    )


def single_agent_outcome(state: dict) -> RunOutcome:
    """Adapt the Module 14 single-agent graph's final ``AgentState`` to a
    ``RunOutcome``.

    The capstone graph does not itself total token usage, so the caller passes
    the observed ``llm_calls``/token counts alongside the final state (the lab
    wraps the graph with a fresh ``MockLLMClient`` and reads ``.calls`` +
    per-call usage). ``state`` here is expected to already carry those fields
    under ``_llm_calls`` / ``_input_tokens`` / ``_output_tokens`` if present;
    otherwise they default to 0 and the lab supplies them via the wrapper.
    """
    answer = state.get("answer", "") or ""
    return RunOutcome(
        answer=answer,
        sources=list(state.get("sources", []) or []),
        llm_calls=int(state.get("_llm_calls", 0)),
        input_tokens=int(state.get("_input_tokens", 0)),
        output_tokens=int(state.get("_output_tokens", 0)),
        failed=bool(state.get("_failed", False)),
    )


# -- report -------------------------------------------------------------------


def write_comparison_report(results: dict, path: Path) -> Path:
    """Write a Markdown comparison report and return its path.

    The report leads with the numbers, then states the honest conclusion the
    numbers support — including when the single agent is the better ship.
    """
    path = Path(path)
    single = results["single_agent"]
    multi = results["supervisor"]
    delta = results["delta"]
    n = len(single["answers"])

    lines: list[str] = [
        "# Multi-Agent vs Single-Agent Comparison",
        "",
        f"Both systems answered the same **{n}** questions, measured through one",
        "harness so they are scored on the same ruler. Offline numbers use the",
        "deterministic mock LLM: token counts and call counts are exact and",
        "repeatable; wall-clock latency varies run to run but its *shape* does not",
        "(the supervisor always does strictly more work).",
        "",
        "## Headline",
        "",
        "| metric | single agent | supervisor | delta |",
        "|---|---:|---:|---:|",
        f"| LLM calls | {single['llm_calls']} | {multi['llm_calls']} "
        f"| +{delta['extra_llm_calls']} |",
        f"| total tokens | {single['total_tokens']} | {multi['total_tokens']} "
        f"| +{delta['extra_tokens']} |",
        f"| latency (s) | {single['latency_s']:.4f} | {multi['latency_s']:.4f} "
        f"| {delta['extra_latency_s']:+.4f} |",
        f"| failures | {single['failures']} | {multi['failures']} | {delta['extra_failures']:+d} |",
        "",
        "## Per-question answers",
        "",
        "| # | single-agent sources | supervisor sources |",
        "|---:|---|---|",
    ]
    for i in range(n):
        s_src = ", ".join(single["sources"][i]) or "—"
        m_src = ", ".join(multi["sources"][i]) or "—"
        lines.append(f"| {i + 1} | {s_src} | {m_src} |")

    lines += [
        "",
        "## Reading this honestly",
        "",
        "- **The supervisor costs more, always.** It spends a routing LLM call on",
        "  every question before any specialist runs, so its call count and token",
        "  total are strictly higher than the single agent's. That is the price of",
        "  the pattern, not a defect to tune away.",
        "- **Quality is where multi-agent can pay off** — a focused specialist",
        "  prompt is less likely to be distracted by irrelevant tools/policy than",
        "  one prompt holding everything. Compare the source columns above: where",
        "  they match, the extra cost bought nothing here.",
        "- **Latency compounds** with each hop. One routing call + one specialist",
        "  call is two sequential round trips where the single agent had one.",
        "- **Read the offline latency number with care.** Against the mock, LLM",
        "  calls are effectively free, so wall-clock time is dominated by *vector",
        "  retrieval*, not by call count. The single-agent graph retrieves twice",
        "  per RAG question (once to summarize evidence, once inside the answer),",
        "  so it can post a *higher* offline latency than the supervisor even though",
        "  the supervisor makes more model calls. With a real network-bound LLM the",
        "  extra calls dominate and the supervisor is the slower system — the call",
        "  and token deltas above are the durable signal; treat offline latency as",
        "  indicative of shape, not a benchmark.",
        "- **Failure is contained**: a specialist crash becomes a graceful apology,",
        "  and the supervisor's failure count stays low — but debugging *why* a",
        "  specialist was chosen and then failed is a distributed-systems problem,",
        "  not a stack trace.",
        "",
        "### When to ship the single agent instead",
        "",
        "If the source columns match and the failure counts match, the supervisor",
        "spent extra calls, tokens, and latency to arrive at the same answers — ",
        "ship the single agent. Reach for the supervisor only when a domain's",
        "specialist measurably improves answer quality or when the single prompt",
        "has grown too large to route reliably (prompt bloat, tool confusion).",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
