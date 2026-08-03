"""Render the local JSONL trace log readably (Module 19).

The counterpart to ``techcorp_agent.tracing.LocalTracer``: it reads
``artifacts/traces/runs.jsonl`` (one run per line) and prints a table — run id,
name, route, tokens, latency, error — using ``rich`` when available and a plain
ASCII fallback otherwise. ``--run <id>`` expands one run into its full ordered
step list, which is how you *debug* a single agent invocation offline.

Usage::

    uv run python scripts/view_traces.py
    uv run python scripts/view_traces.py --path artifacts/traces/runs.jsonl
    uv run python scripts/view_traces.py --run <run_id-or-prefix>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("artifacts/traces/runs.jsonl")


def load_runs(path: Path) -> list[dict[str, Any]]:
    """Read every JSON line from the trace log, skipping any blank/corrupt line."""
    if not path.exists():
        return []
    runs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def _route_of(run: dict[str, Any]) -> str:
    """The chosen route for a run, if it recorded one (from the output or a step)."""
    output = run.get("output")
    if isinstance(output, dict) and output.get("route"):
        return str(output["route"])
    for step in run.get("steps", []):
        if step.get("node") == "route" and step.get("data"):
            return str(step["data"])
    return "-"


def _tokens_of(run: dict[str, Any]) -> str:
    usage = run.get("token_usage") or {}
    total = usage.get("total_tokens")
    if total is None and usage:
        total = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    return str(total) if total else "-"


def _latency_of(run: dict[str, Any]) -> str:
    latency = run.get("latency_ms")
    return f"{latency:.1f}" if isinstance(latency, (int, float)) else "-"


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (p50/p95) over ``values``; 0.0 on empty input."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[rank]


def render_table(runs: list[dict[str, Any]]) -> None:
    """Print the run summary table (rich if importable, plain ASCII otherwise)."""
    if not runs:
        print("No runs found. Run the agent under a LocalTracer first (looked in the trace log).")
        return

    latencies = [r["latency_ms"] for r in runs if isinstance(r.get("latency_ms"), (int, float))]
    header = ["run id", "name", "route", "tokens", "latency ms", "error"]
    rows = [
        [
            str(r.get("run_id", ""))[:8],
            str(r.get("name", "")),
            _route_of(r),
            _tokens_of(r),
            _latency_of(r),
            (r.get("error") or "")[:40],
        ]
        for r in runs
    ]

    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Agent traces ({len(runs)} runs)")
        for col in header:
            table.add_column(col, overflow="fold")
        for row in rows:
            table.add_row(*row)
        console = Console()
        console.print(table)
        if latencies:
            console.print(
                f"latency p50={_percentile(latencies, 50):.1f} ms  "
                f"p95={_percentile(latencies, 95):.1f} ms  "
                f"(n={len(latencies)})"
            )
    except ImportError:
        _render_plain(header, rows)
        if latencies:
            print(
                f"\nlatency p50={_percentile(latencies, 50):.1f} ms  "
                f"p95={_percentile(latencies, 95):.1f} ms  (n={len(latencies)})"
            )


def _render_plain(header: list[str], rows: list[list[str]]) -> None:
    """A dependency-free table for when ``rich`` is unavailable."""
    widths = [len(col) for col in header]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*row))


def render_run(runs: list[dict[str, Any]], run_ref: str) -> int:
    """Print the full step list of the run whose id starts with ``run_ref``."""
    matches = [r for r in runs if str(r.get("run_id", "")).startswith(run_ref)]
    if not matches:
        print(f"No run found with id starting '{run_ref}'.")
        return 1
    if len(matches) > 1:
        print(f"Ambiguous id '{run_ref}' matches {len(matches)} runs; use a longer prefix.")
        return 1

    run = matches[0]
    print(f"run_id:    {run.get('run_id')}")
    print(f"name:      {run.get('name')}")
    print(f"timestamp: {run.get('timestamp')}")
    print(f"inputs:    {json.dumps(run.get('inputs', {}), ensure_ascii=False)}")
    print(f"tokens:    {_tokens_of(run)}    latency ms: {_latency_of(run)}")
    if run.get("error"):
        print(f"ERROR:     {run['error']}")
    print("\nsteps:")
    for i, step in enumerate(run.get("steps", []), start=1):
        data = step.get("data")
        detail = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else data
        print(f"  {i:>2}. [{step.get('node')}] {detail if detail is not None else ''}")
    print("\noutput:")
    print(f"  {json.dumps(run.get('output'), ensure_ascii=False, indent=2)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the local agent trace log.")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH, help="Path to runs.jsonl.")
    parser.add_argument("--run", dest="run_ref", default=None, help="Show one run by id prefix.")
    args = parser.parse_args(argv)

    runs = load_runs(args.path)
    if args.run_ref:
        return render_run(runs, args.run_ref)
    render_table(runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
