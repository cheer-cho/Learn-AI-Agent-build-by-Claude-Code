"""Module 20 starter — guardrails, injection defense, and cost control.

Work through the TODOs, then run (fully offline):

    TECHCORP_OFFLINE=true uv run python course/20_guardrails_and_safety/starter/safety_lab.py

Your completion gate (tests auto-skip until every TODO is gone):

    uv run pytest course/20_guardrails_and_safety -q

This is a DEFENSIVE security exercise on your OWN local lab system. You COMPOSE
already-built pieces from ``techcorp_agent.safety`` — you do not reimplement the
detector, sanitizer, validator, or budget:

- ``detect_injection`` / ``sanitize_context`` / ``harden_system_prompt``
- ``validate_question`` / ``validate_answer``
- ``SessionBudget`` / ``guarded_complete`` / ``BudgetExceeded``

Your job is the WIRING: run the unprotected vs protected paths, validate
answers, and enforce a per-session budget — then read the before/after.
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

# The adversarial completion a HIJACKED live LLM would emit: opens with the
# banner the payload demanded, leaks order data, and cites a source that was
# never retrieved. Scripted identically on both paths so the only difference is
# the defenses around it. (Do not change this — the labs depend on it.)
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

    # TODO (Lab A.1): call detect_injection on the poisoned chunk text and
    #                 print how many suspicious spans it found. Assign to
    #                 `findings` (a list) so the return dict below works.
    findings = []  # TODO: detect_injection(poisoned.chunk.text)
    print(f"\ndetect_injection flagged {len(findings)} suspicious span(s).")

    # ---- UNPROTECTED PATH ------------------------------------------------- #
    # Raw context + base prompt + NO output validation. This is the "before".
    raw_context = build_context_block([poisoned])
    unprotected_llm = MockLLMClient(responses=[HIJACKED_COMPLETION])
    raw_out = unprotected_llm.complete(
        [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Context:\n{raw_context}\n\nQuestion: What is the refund policy?",
            ),
        ]
    ).content
    unprotected_answer, unprotected_cited = parse_answer(raw_out)
    print("\n--- BEFORE (unprotected) ---")
    print(unprotected_answer)
    print(f"(cited: {unprotected_cited})")

    # ---- PROTECTED PATH --------------------------------------------------- #
    # TODO (Lab A.2): build the protected context and prompt:
    #   - safe_context   = sanitize_context([poisoned])
    #   - hardened_prompt = harden_system_prompt(SYSTEM_PROMPT)
    safe_context = raw_context  # TODO: replace with sanitize_context([poisoned])
    hardened_prompt = SYSTEM_PROMPT  # TODO: replace with harden_system_prompt(SYSTEM_PROMPT)

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

    # TODO (Lab A.3): validate the protected answer. The poisoned chunk's doc_id
    #   is the only legitimately retrieved source. Assign the ValidationReport
    #   to `report`.
    report = validate_answer(  # this call is correct — just uncomment the args
        protected_answer,
        retrieved_sources=[poisoned.chunk.doc_id],
        cited_sources=protected_cited,
    )
    print("\n--- AFTER (protected) ---")
    print(f"answer OK? {report.ok}")
    for reason in report.reasons:
        print(f"  - blocked: {reason}")
    served = ABSTENTION_TEXT if not report.ok else protected_answer
    print(f">> Served to the user instead:\n   {served}")

    return {
        "detected": len(findings),
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
    # TODO (Lab B.1): build a `missing` report for an answer that makes a
    #   company-specific claim ("Employees get 25 vacation days per year.") but
    #   cites NOTHING (cited_sources=[]). It should be blocked.
    missing = grounded  # TODO: validate_answer(..., cited_sources=[])
    # TODO (Lab B.2): build an `invented` report where cited_sources names a
    #   source NOT in retrieved_sources (e.g. cite "internal-order-db" while only
    #   "ps-refunds" was retrieved). It should be blocked.
    invented = grounded  # TODO: validate_answer(..., cited_sources=["internal-order-db"])
    abstain_ok = validate_answer(ABSTENTION_TEXT, retrieved_sources=[], cited_sources=[])

    for label, report in [
        ("grounded + cited", grounded),
        ("missing citation", missing),
        ("invented citation", invented),
        ("clean abstention", abstain_ok),
    ]:
        print(f"[{'PASS' if report.ok else 'BLOCK'}] {label}")

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

    # TODO (Lab C.1): create a SessionBudget with a small soft/hard limit so a
    #   couple of offline calls trip it. Use soft_limit_usd=0.003,
    #   hard_limit_usd=0.004.
    budget = None  # TODO: SessionBudget(soft_limit_usd=0.003, hard_limit_usd=0.004)

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
            # TODO (Lab C.2): call guarded_complete(llm, [<user message>], budget,
            #   max_output_tokens=2048). Capture (result, warning). If `warning`
            #   is truthy, set warned=True and print it.
            _, warning = guarded_complete(
                llm,
                [ChatMessage(role="user", content=question)],
                budget,
                max_output_tokens=2048,
            )
            status = budget.status()
            print(f"call {i}: ${status.cost_usd:.6f} spent")
            if warning:
                warned = True
                print(f"   {warning}")
        except BudgetExceeded as exc:
            refused = True
            print(f"call {i}: REFUSED — {exc}")
            break

    return {"warned": warned, "refused": refused}


def main() -> int:
    # Guardrail #0 — input validation. (Already wired; confirm it runs.)
    assert validate_question("").ok is False
    assert validate_question("How many vacation days do I get?").ok is True

    a = lab_a_injection()
    b = lab_b_output_validation()
    c = lab_c_budget()

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Lab A  detected payload spans:      {a['detected']}")
    print(f"Lab A  protected answer blocked?    {a['protected_blocked']}")
    print(f"Lab B  missing citation blocked?    {b['missing_blocked']}")
    print(f"Lab B  invented citation blocked?   {b['invented_blocked']}")
    print(f"Lab C  soft-limit warning fired?    {c['warned']}")
    print(f"Lab C  hard-limit refused a call?   {c['refused']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
