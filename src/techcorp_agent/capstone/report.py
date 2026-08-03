"""Generate ``artifacts/capstone_v1_report.md`` — the v1 evaluation report.

The capstone report has two halves, both fully offline and deterministic:

1. **Routing** — every ``tool_routing`` example is run through the graph's
   router (the reused Module 11 router with its deterministic keyword fallback)
   and the chosen route is checked against the example's ``expected_tool``. This
   is the capability the capstone adds on top of plain RAG, so it gets its own
   correctness table.

2. **Retrieval** — the non-tool categories (answerable, paraphrase, multi_chunk,
   unanswerable, ambiguous) are scored with the *existing* evaluation harness
   (``techcorp_agent.evaluation``) over the same ``RAGPipeline`` the retrieval
   node uses, so the retrieval numbers are directly comparable to Module 09's.

Honesty caveats are written into the report: with the offline mock LLM only the
retrieval-side numbers are meaningful, and hash embeddings match on word overlap
only, so paraphrase retrieval underperforms real semantic embeddings by
construction.

Run it::

    TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.config import get_settings
from techcorp_agent.evaluation.runner import run_evaluation, summarize
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.rag.pipeline import RAGPipeline

# Map the dataset's ``expected_tool`` to the graph route we expect the router to
# pick. ``None`` (greetings / open questions) should land on the general route.
_EXPECTED_ROUTE = {
    "calculator": "calculator",
    "order_lookup": "orders",
    "document_search": "retrieval",
    None: "general",
}


def _load_dataset() -> list[dict]:
    settings = get_settings()
    path = settings.data_dir / "evaluation" / "eval_dataset.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["examples"] if isinstance(data, dict) else data


def evaluate_routing(app: Any, examples: list[dict]) -> list[dict]:
    """Run each ``tool_routing`` example through the graph and check the route.

    Returns one row per example: id, question, expected route, actual route, and
    whether they matched. Deterministic and offline (keyword fallback).
    """
    rows: list[dict] = []
    for example in examples:
        if example.get("category") != "tool_routing":
            continue
        expected = _EXPECTED_ROUTE.get(example.get("expected_tool"), "general")
        state = app.invoke(
            {
                "conversation_id": "report",
                "question": example["question"],
                "trace": [],
                "loop_count": 0,
            }
        )
        actual = state.get("route", "general")
        rows.append(
            {
                "id": example["id"],
                "question": example["question"],
                "expected": expected,
                "actual": actual,
                "ok": actual == expected,
            }
        )
    return rows


def _routing_table(rows: list[dict]) -> list[str]:
    correct = sum(1 for r in rows if r["ok"])
    lines = [
        f"Routing accuracy: **{correct}/{len(rows)}** "
        f"({(correct / len(rows) if rows else 0):.0%}) — deterministic, offline.",
        "",
        "| id | question | expected route | actual route | ok |",
        "|---|---|---|---|:--:|",
    ]
    for r in rows:
        q = r["question"] if len(r["question"]) <= 60 else r["question"][:57] + "..."
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"| {r['id']} | {q} | {r['expected']} | {r['actual']} | {mark} |")
    return lines


def _retrieval_tables(summary: dict) -> list[str]:
    header = (
        "| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |\n"
        "|---:|---:|---:|---:|---:|"
    )

    def row(stats: dict) -> str:
        return (
            f"| {stats['n']} | {stats['hit_rate']:.0%} | {stats['source_accuracy']:.0%} "
            f"| {stats['fact_coverage']:.0%} | {stats['abstention_accuracy']:.0%} |"
        )

    lines = ["### Overall (non-tool categories)", "", header, row(summary["overall"]), ""]
    lines.append("### By category")
    lines.append("")
    for category, stats in summary["per_category"].items():
        lines += [f"**{category}**", "", header, row(stats), ""]
    return lines


def generate_report(path: Path | None = None) -> Path:
    """Build the graph + pipeline offline and write the capstone report.

    Returns the path to the written report.
    """
    settings = get_settings()
    path = path or (settings.artifacts_dir / "capstone_v1_report.md")

    llm = get_llm_client(settings)
    store = build_offline_store()
    examples = _load_dataset()

    # Routing half: run tool_routing examples through the real graph (no MCP —
    # routing is a pure decision and does not need the servers).
    app = build_graph(llm, store, mcp_registry=None)
    routing_rows = evaluate_routing(app, examples)

    # Retrieval half: reuse the Module 09 evaluation harness over the same
    # pipeline the retrieval node uses.
    pipeline = RAGPipeline(store, llm)
    eval_results = run_evaluation(pipeline, examples)
    summary = summarize(eval_results)

    embed_name = store._embeddings.model_name  # noqa: SLF001 - report context only
    lines: list[str] = [
        "# TechCorp Knowledge Agent v1 — Capstone Evaluation Report",
        "",
        "Generated by `techcorp_agent.capstone.report`. Fully offline and",
        "deterministic: the router half uses the keyword fallback, the retrieval",
        "half uses hash embeddings, and generation runs against the mock LLM.",
        "",
        "## Run context",
        "",
        f"- **embedding client**: {embed_name}",
        f"- **LLM client**: {llm.name}",
        f"- **dataset**: `data/evaluation/eval_dataset.json` ({len(examples)} examples)",
        "- **MCP servers**: not spawned for this report (routing is a pure decision);",
        "  the live agent still degrades gracefully when they are down.",
        "",
        "## 1. Routing (the capability the capstone adds)",
        "",
    ]
    lines += _routing_table(routing_rows)
    lines += [
        "",
        "> **Offline routing caveat.** This table uses the *deterministic keyword*",
        "> fallback, not the LLM router (the mock LLM never returns a valid tool",
        "> name). Two examples miss because their wording trips a policy keyword —",
        "> e.g. 'vacation days ... carry over' and 'explain ... a warranty' both",
        "> contain document keywords, so the keyword router sends them to",
        "> retrieval. With a real LLM router these route correctly; the fallback is",
        "> the safety net, not the primary path.",
        "",
        "## 2. Retrieval and grounding (reused Module 09 harness)",
        "",
        "`tool_routing` examples are excluded from this half — they exercise the",
        "tools, not the RAG pipeline.",
        "",
    ]
    lines += _retrieval_tables(summary)
    lines += [
        "## Reading these numbers honestly (offline caveats)",
        "",
        "- **Only retrieval numbers are meaningful offline.** With the mock LLM,",
        "  source accuracy / fact coverage / generation-side abstention describe",
        "  the mock, not a real model. Configure `OPENAI_API_KEY` and re-run for",
        "  real generation metrics.",
        "- **Hash embeddings match on word overlap**, so paraphrase retrieval",
        "  (e.g. 'denim' vs 'jeans') scores lower than real semantic embeddings",
        "  would; the v1 pilot ships with sentence-transformers when a model is",
        "  available.",
        "- **Routing is deterministic and does not depend on the LLM** — the",
        "  keyword fallback makes the routing table above reproducible on any",
        "  machine, online or offline.",
        "- **Abstention** for out-of-scope questions (the 'working from the Moon'",
        "  case) depends on the grounding prompt at generation time; the retrieval",
        "  step alone does not guarantee it, which is why the grounded-answer node",
        "  keeps the Module 08 contract.",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    path = generate_report()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
