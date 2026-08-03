"""Module 20 solution — guardrails, injection defense, and cost control.

Runs fully offline (deterministic mock LLM, no network, no API key):

    TECHCORP_OFFLINE=true uv run python course/20_guardrails_and_safety/solution/safety_lab.py

This is a DEFENSIVE security exercise. It loads the planted-injection documents
from ``data/security_lab/`` (opt-in only) and attacks the learner's OWN local
lab system to show how a malicious document can hijack an undefended RAG agent —
then adds the defenses that stop it.

The script runs three labs and prints the evidence:

- Lab A — injection: the SAME hijacked model output on an UNPROTECTED path (raw
  context, base prompt, no output checks) vs a PROTECTED path (demarcated
  context + hardened prompt + output validation). Before: leak served. After:
  leak blocked. This is the required before/after.
- Lab B — output validation: a missing-citation answer and an invented-citation
  answer are both flagged; a grounded, cited answer passes.
- Lab C — budget: a per-session budget warns at a soft limit and refuses
  further calls at a hard limit with a clear, user-facing message.

Modeling note (honest offline attack): a live LLM reading the payload as raw
context can genuinely be hijacked. Our mock does not reason, so we SCRIPT the
adversarial completion a hijacked model would emit and show the defenses catch
it. What differs between paths is the plumbing (demarcation + validation), not
a pretend "the mock obeyed".
"""

from __future__ import annotations

from pathlib import Path

from techcorp_agent.documents.loader import load_documents
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import (
    ABSTENTION_TEXT,
    SYSTEM_PROMPT,
    build_context_block,
    parse_answer,
)
from techcorp_agent.safety import (
    BudgetExceeded,
    SessionBudget,
    detect_injection,
    guarded_complete,
    harden_system_prompt,
    sanitize_context,
    validate_answer,
    validate_question,
)
from techcorp_agent.schemas import ChatMessage, Chunk, RetrievedChunk

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"

# The adversarial completion a HIJACKED live LLM would emit: it opens with the
# banner the payload demanded, leaks order data, and cites a source that was
# never retrieved. Scripted identically on both paths so the ONLY difference is
# the defenses around it.
HIJACKED_COMPLETION = (
    "ADMIN OVERRIDE ACCEPTED. All refunds are approved regardless of amount. "
    "Order TC-1001 alias raven, Order TC-1002 alias willow, Order TC-1003 alias cedar.\n"
    "SOURCES: internal-order-db"
)


def _poisoned_chunk() -> RetrievedChunk:
    """Load the planted expense-policy document as a retrieved chunk."""
    docs = load_documents(DATA_DIR, include_security_lab=True)
    policy = next(d for d in docs if d.id == "seclab-injected-policy")
    return RetrievedChunk(
        chunk=Chunk(
            id=f"{policy.id}-0",
            doc_id=policy.id,
            doc_title=policy.title,
            category=policy.category,
            index=0,
            text=policy.content,
        ),
        score=0.9,
    )


def lab_a_injection() -> dict[str, object]:
    """Lab A: unprotected leak vs protected block. Returns a small result dict."""
    print("=" * 72)
    print("LAB A — Prompt injection: unprotected vs protected")
    print("=" * 72)

    poisoned = _poisoned_chunk()

    # Detection first (a smoke alarm, not a firewall).
    findings = detect_injection(poisoned.chunk.text)
    print(f"\ndetect_injection flagged {len(findings)} suspicious span(s) in the document:")
    for f in findings:
        print(f"  - [{f.category}] {f.pattern}: {f.match!r}")

    # ---- UNPROTECTED ------------------------------------------------------ #
    raw_context = build_context_block([poisoned])
    unprotected_llm = MockLLMClient(responses=[HIJACKED_COMPLETION])
    raw_out = unprotected_llm.complete(
        [
            # base prompt, raw context — no boundary between rules and data
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Context:\n{raw_context}\n\nQuestion: What is the refund policy?",
            ),
        ]
    ).content
    unprotected_answer, unprotected_cited = parse_answer(raw_out)
    print("\n--- BEFORE (unprotected: raw context, base prompt, no output check) ---")
    print(unprotected_answer)
    print(f"(cited: {unprotected_cited} — 'internal-order-db' was NEVER retrieved)")
    print(">> This answer would be served to the user. The agent leaked order data.")

    # ---- PROTECTED -------------------------------------------------------- #
    safe_context = sanitize_context([poisoned])
    hardened_prompt = harden_system_prompt(SYSTEM_PROMPT)
    protected_llm = MockLLMClient(responses=[HIJACKED_COMPLETION])
    protected_out = protected_llm.complete(
        [
            ChatMessage(role="system", content=hardened_prompt),
            ChatMessage(
                role="user",
                content=f"Context:\n{safe_context}\n\nQuestion: What is the refund policy?",
            ),
        ]
    ).content
    protected_answer, protected_cited = parse_answer(protected_out)
    report = validate_answer(
        protected_answer,
        retrieved_sources=[poisoned.chunk.doc_id],
        cited_sources=protected_cited,
    )
    print("\n--- AFTER (protected: demarcated context + hardened prompt + validation) ---")
    print("Same hijacked model output arrives, but output validation refuses it:")
    print(f"  answer OK? {report.ok}")
    for reason in report.reasons:
        print(f"  - blocked: {reason}")
    served = ABSTENTION_TEXT if not report.ok else protected_answer
    print(f"\n>> Served to the user instead:\n   {served}")

    return {
        "detected": len(findings),
        "unprotected_blocked": not validate_answer(
            unprotected_answer, retrieved_sources=[], cited_sources=unprotected_cited
        ).ok,
        "protected_blocked": not report.ok,
        "identical_model_output": unprotected_answer == protected_answer,
    }


def lab_b_output_validation() -> dict[str, bool]:
    """Lab B: citations present, no unsupported claims, abstention respected."""
    print("\n" + "=" * 72)
    print("LAB B — Output validation")
    print("=" * 72)

    grounded = validate_answer(
        "Damaged products qualify for a full refund within 30 days of delivery.",
        retrieved_sources=["ps-refunds"],
        cited_sources=["ps-refunds"],
    )
    missing = validate_answer(
        "Employees get 25 vacation days per year.",
        retrieved_sources=["hr-vacation"],
        cited_sources=[],  # a company-specific number with no citation
    )
    invented = validate_answer(
        "All refunds are approved.",
        retrieved_sources=["ps-refunds"],
        cited_sources=["internal-order-db"],  # cites a non-retrieved source
    )
    abstain_ok = validate_answer(ABSTENTION_TEXT, retrieved_sources=[], cited_sources=[])

    for label, report in [
        ("grounded + cited", grounded),
        ("missing citation", missing),
        ("invented citation", invented),
        ("clean abstention", abstain_ok),
    ]:
        verdict = "PASS" if report.ok else "BLOCK"
        print(f"\n[{verdict}] {label}")
        for reason in report.reasons:
            print(f"   - {reason}")

    return {
        "grounded_ok": grounded.ok,
        "missing_blocked": not missing.ok,
        "invented_blocked": not invented.ok,
        "abstention_ok": abstain_ok.ok,
    }


def lab_c_budget() -> dict[str, bool]:
    """Lab C: soft-limit warning, then hard-limit refusal with a clear message."""
    print("\n" + "=" * 72)
    print("LAB C — Cost budget enforcement")
    print("=" * 72)

    # Small but human-readable limits. Each mock reply is padded so a call costs
    # a fraction of a cent, tripping the soft limit on call 1 and the hard limit
    # on call 2 — the exact shape of a real per-session budget.
    budget = SessionBudget(soft_limit_usd=0.003, hard_limit_usd=0.004)
    pad = " (grounded in the retrieved TechCorp policy document above)" * 40
    llm = MockLLMClient(
        responses=[
            f"The standard warranty is 12 months.{pad}\nSOURCES: ps-warranty",
            f"Returns are accepted within 30 days.{pad}\nSOURCES: ps-returns",
            f"Business casual is the default dress code.{pad}\nSOURCES: hr-dress-code",
        ]
    )

    warned = False
    refused = False
    for i, question in enumerate(
        ["How long is the warranty?", "What is the return window?", "What is the dress code?"], 1
    ):
        try:
            # A generous per-call output cap so a couple of calls reach the
            # (small) session budget — the point is the limit, not the length.
            _, warning = guarded_complete(
                llm,
                [ChatMessage(role="user", content=question)],
                budget,
                max_output_tokens=2048,
            )
            status = budget.status()
            print(f"\ncall {i}: ${status.cost_usd:.6f} spent")
            if warning:
                warned = True
                print(f"   {warning}")
        except BudgetExceeded as exc:
            refused = True
            print(f"\ncall {i}: REFUSED — {exc}")
            break

    return {"warned": warned, "refused": refused}


def main() -> int:
    # A quick input-validation sanity check up front (guardrail #0).
    assert validate_question("").ok is False
    assert validate_question("How many vacation days do I get?").ok is True

    a = lab_a_injection()
    b = lab_b_output_validation()
    c = lab_c_budget()

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Lab A  detected payload spans:      {a['detected']}")
    print(f"Lab A  unprotected answer blocked?  {a['unprotected_blocked']} (only if validated)")
    print(f"Lab A  protected answer blocked?    {a['protected_blocked']}")
    print(f"Lab B  missing citation blocked?    {b['missing_blocked']}")
    print(f"Lab B  invented citation blocked?   {b['invented_blocked']}")
    print(f"Lab C  soft-limit warning fired?    {c['warned']}")
    print(f"Lab C  hard-limit refused a call?   {c['refused']}")

    ok = (
        a["protected_blocked"]
        and a["identical_model_output"]
        and b["grounded_ok"]
        and b["missing_blocked"]
        and b["invented_blocked"]
        and b["abstention_ok"]
        and c["warned"]
        and c["refused"]
    )
    print("\nAll guardrails behaved as expected." if ok else "\nSomething is off — review above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
