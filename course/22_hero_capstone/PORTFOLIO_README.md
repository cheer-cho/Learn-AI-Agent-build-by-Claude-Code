[🗺 Course Roadmap](../../ROADMAP.html) · [← Architecture](ARCHITECTURE.md) · [← Demo Script](DEMO_SCRIPT.md) · [Interview Prep →](INTERVIEW_PREP.md)

---

> **This is a template.** Copy it to the root of your published repo as
> `README.md` and fill in every `<…>` placeholder (your name, links,
> screenshots). It describes the **TechCorp Knowledge Agent** as a portfolio
> project — not the course. Delete this quote block before publishing.

---

# TechCorp Knowledge Agent

A production-style, multi-agent knowledge assistant over a company knowledge base —
retrieval-augmented, tool-using, memory-persistent, safety-guarded, and deployed
behind a streaming HTTP API. Built as one integrated LangGraph application, it
routes a question through a safety boundary, a multi-agent supervisor, and one of
six capability nodes (grounded RAG, order lookup, calculator, an approval-gated
write, or a general reply), then returns a cited, validated answer. **It runs
end-to-end offline with no API key**, so anyone can clone it and see it work in one
command.

*By <your name> · [LinkedIn](<link>) · [Portfolio](<link>) · Live demo: <link or "clone & run below">*

---

## Features

- **Grounded RAG with citations and abstention.** Answers cite the source document
  or abstain — it never invents policy. (Measured abstention accuracy: 100% on the
  evaluation set.)
- **Advanced retrieval, measured — not assumed.** Category-scoped hybrid search
  (BM25 + dense vectors) with reranking, defaulted on where it is measured to help.
  On the offline embedding run, reranking took paraphrase-query hit@4 from **60% to
  100%**; the same report honestly shows it was a wash on a live semantic corpus.
- **Multi-agent routing.** A supervisor routes each question to a policy or support
  specialist, a deterministic tool (calculator / order lookup), an approval-gated
  write, or a general reply — each with a focused, injection-hardened prompt.
- **Durable multi-turn memory.** Conversations are checkpointed to SQLite and keyed
  by thread id, so follow-ups resolve against earlier turns and a conversation
  survives a process restart.
- **Human-in-the-loop approval on the one write.** Creating a support ticket pauses
  the graph for a human decision before anything is written; reads are never gated.
- **Tools over MCP with graceful degradation.** Calculator and order-status tools
  run over Model Context Protocol servers, with an automatic fallback to in-process
  local tools when a server is unavailable — no crash, ever.
- **Guardrails.** Input validation, direct prompt-injection blocking at the
  untrusted edge, a per-session cost budget, and output validation that drops any
  citation to a document that was not actually retrieved.
- **Streaming everywhere.** A node-by-node event feed in the CLI and Server-Sent
  Events over HTTP, from one shared normalizer.
- **Observability + a regression report.** Every node emits a structured trace;
  runs are captured to disk; and a one-command evaluation report scores routing,
  retrieval, and integration smoke checks.
- **Production HTTP service.** A FastAPI app with `/health`, `/ready`,
  `/chat`, and `/chat/stream`, loading the index and graph once at startup and
  logging metadata only (never questions, answers, or secrets).

---

## Architecture

One LangGraph: `boundary → supervisor → {policy | support | orders | calculator |
ticket | general} → formatter`, with a SQLite checkpointer for memory and resumable
approval and a tracer threaded through every node.

```
             ┌───────────┐   blocked   ┌────────────┐
  question ─▶│ boundary  │────────────▶│ formatter  │──▶ answer + sources
             │ (safety)  │             └────────────┘
             └─────┬─────┘                   ▲
                ok │                          │
             ┌─────▼──────┐   route   ┌───────┴────────────────────────┐
             │ supervisor │──────────▶│ policy · support (advanced RAG)│
             │ (routing)  │           │ orders · calculator (MCP/local)│
             └────────────┘           │ ticket (human approval)        │
                                       │ general (LLM reply)            │
                                       └────────────────────────────────┘
        SQLite checkpointer (memory + resumable approval)  ·  tracer on every node
```

Full component map, request lifecycle, and the trade-off behind every design
decision: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Orchestration | LangGraph (stateful graph, checkpointing, interrupts) |
| LLM framework | LangChain |
| Tools protocol | Model Context Protocol (MCP) |
| Vector store | ChromaDB (with a deterministic hash-embedding backend for offline runs) |
| Embeddings | sentence-transformers (live) / hash embeddings (offline) |
| Retrieval | dense vectors + BM25 (`rank-bm25`) hybrid, with reranking |
| API | FastAPI + Uvicorn (Server-Sent Events for streaming) |
| Persistence | SQLite (LangGraph `SqliteSaver`) |
| Tokenization / cost | tiktoken |
| Tooling | uv (env + deps), pytest, ruff |

> The pinned versions live in [`pyproject.toml`](../../pyproject.toml). If you
> re-target this project, quote *your* lockfile, not this table.

---

## Quickstart

Runs fully offline — no API key, no network.

```bash
# 1. Clone
git clone <your-repo-url> && cd <your-repo>

# 2. Set up the environment (uv sync + a smoke check)
make setup

# 3. Verify it works end to end, offline
make verify

# 4. Ask the agent a question from the CLI (offline, local tools, dev trace)
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.cli \
    --question "What is 17.5% of 8,400?" --dev --no-mcp
# → The result is 1470.  (routed to the calculator, not attributed to any document)

# 5. Interactive multi-turn REPL (durable memory; --stream to watch nodes fire)
uv run python -m techcorp_agent.capstone_v2.cli

# 6. Run the HTTP service
uv run uvicorn techcorp_agent.capstone_v2.app_service:app --reload
#   GET  /health           → liveness
#   GET  /ready            → readiness (503 until the graph is warm)
#   POST /chat             → {question, conversation_id?} → {answer, sources, route, conversation_id}
#   POST /chat/stream      → the same turn as Server-Sent Events

# Example request:
curl -X POST localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question": "How much international remote work is allowed?"}'

# 7. Regenerate the evaluation report
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.report
# → artifacts/capstone_v2_report.md

# For real (non-mock) generation, put OPENAI_API_KEY in .env and drop TECHCORP_OFFLINE.
```

---

## Screenshots

> Replace these markers with real captures before publishing.

- `<!-- screenshot: CLI --dev trace showing boundary → supervisor → calculator → formatter -->`
- `<!-- screenshot: the approval interrupt prompt (approve? [y/N]) and the resulting TCK-XXXX -->`
- `<!-- screenshot: a cited policy answer with its Sources: line -->`
- `<!-- screenshot: the /chat/stream SSE event feed in the browser or curl -->`
- `<!-- screenshot: the generated artifacts/capstone_v2_report.md tables -->`

---

## What I learned / engineering decisions

> Prompts to answer in your own words — this section is where an interviewer looks
> first. Keep each to two or three sentences; ground every claim in the code or the
> report.

- **Integration over invention.** *Describe how the whole app reuses packages you
  built one capability at a time and adds new code only at the joints (graph wiring,
  state, the scoped retriever, thin CLI/API glue) — and why that matters.*
- **Measuring an upgrade instead of assuming it.** *Explain the advanced-RAG
  result: it helped offline (paraphrase 60%→100%) and was a wash live, so you
  shipped it as a defaulted flag. What did that teach you about "best practices"?*
- **The cost of multi-agent routing.** *One extra LLM call to route buys specialist
  focus. When is that trade worth paying, and how would you decide on real traffic?*
- **Where safety lives.** *Why validation and injection blocking run on the
  untrusted edge before any model call, and why you still harden downstream prompts
  and validate output — defense in depth.*
- **Gating the write, not the reads.** *Why only ticket creation is behind a human
  approval, and how the checkpointer makes that approval resumable.*
- **Failing safe.** *How graceful degradation (a down MCP server, an unknown order,
  an LLM error) turns into a clean message instead of a stack trace.*
- **Honest evaluation.** *What the offline numbers do and do not mean, and why
  stating that limitation is part of the deliverable.*
- **A limitation you'd fix next.** *Pick one — e.g. the single-process in-memory
  index — and say how you'd externalize it and what you'd measure to justify it.*

---

## Testing

```bash
uv run pytest -q                                  # full offline suite
uv run pytest course/22_hero_capstone -q          # the capstone module
uv run pytest tests/test_capstone_v2.py -q         # the integrated system
```

---

## Notes

- **No API key required.** The default path uses a deterministic mock LLM, hash
  embeddings, a temp SQLite checkpointer, and local stdio MCP servers — so the
  project clones-and-runs. Add `OPENAI_API_KEY` for real generation.
- **Honest metrics.** Offline, only the retrieval-side numbers are meaningful;
  generation quality describes the mock. The evaluation report says so in its own
  caveats section. See [`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md)
  and [`artifacts/retrieval_improvement_report.md`](../../artifacts/retrieval_improvement_report.md).

## License

`<your license>`

---

*Companion docs: [ARCHITECTURE.md](ARCHITECTURE.md) · [DEMO_SCRIPT.md](DEMO_SCRIPT.md) · [INTERVIEW_PREP.md](INTERVIEW_PREP.md)*
