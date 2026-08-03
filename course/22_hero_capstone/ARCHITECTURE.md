[🗺 Course Roadmap](../../ROADMAP.html) · [← Module 22 README](README.md) · [Demo Script →](DEMO_SCRIPT.md) · [Portfolio README →](PORTFOLIO_README.md) · [Interview Prep →](INTERVIEW_PREP.md)

# TechCorp Knowledge Agent v2 — Architecture

The system design a senior engineer would present. Every node name, package
name, and number below is traceable to the real code in
[`src/techcorp_agent/capstone_v2/`](../../src/techcorp_agent/capstone_v2/) or to a
generated report under [`artifacts/`](../../artifacts/). Nothing here is a slogan;
each design decision is stated with the trade-off that justified it.

> **One line.** v2 is a single deployable LangGraph that routes an untrusted
> question through a safety boundary, a multi-agent supervisor, one of six
> capability nodes, and a formatter — with durable memory, a human-approval gate
> on the one write action, and tracing threaded through the whole thing. It
> **integrates** twenty-one modules of packages and **reimplements none of them**.

---

## 1. Architecture diagram

Real node names (`boundary`, `supervisor`, `policy`, `support`, `orders`,
`calculator`, `ticket`, `general`, `formatter`) and real packages, straight from
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py).

```mermaid
flowchart TD
    START([START]) --> B[boundary node]

    B -->|blocked: bad input / injection / over budget| F[formatter node]
    B -->|ok| S[supervisor node]

    S -->|route=policy| P[policy node]
    S -->|route=support| SUP[support node]
    S -->|route=orders| O[orders node]
    S -->|route=calculator| C[calculator node]
    S -->|route=ticket| T[ticket node]
    S -->|route=general| G[general node]

    P -->|advanced RAG: hybrid + rerank,<br/>category-scoped| V[(Vector store<br/>ChromaDB / hash-embed)]
    SUP -->|advanced RAG: hybrid + rerank| V
    O -->|orders.get_order_status via MCP<br/>or local order tool| M[[MCP registry]]
    C -->|calculator.add via MCP<br/>or local calculator tool| M
    T -->|interrupt: human approves<br/>the write| H{{Human}}
    G -->|history-aware LLM reply| L[[LLM client]]

    P --> F
    SUP --> F
    O --> F
    C --> F
    T --> F
    G --> F

    F -->|output validation;<br/>append assistant turn to messages| E([END: answer + sources])

    subgraph XC [Cross-cutting]
      CK[(SqliteSaver checkpointer<br/>memory + resumable approval)]
      TR[LocalTracer<br/>every node appends to state trace]
    end

    S -.threaded by thread_id.- CK
    T -.paused state persisted.- CK
    F -.captured to runs.jsonl.- TR
```

The wiring above is exactly the `StateGraph` built at the bottom of
[`build_v2_graph`](../../src/techcorp_agent/capstone_v2/graph.py): `START →
boundary`; a conditional edge from `boundary` to either `supervisor` (ok) or
`formatter` (blocked); a conditional edge from `supervisor` fanning out to the six
route nodes; every route node edging to `formatter`; and `formatter → END`. The
checkpointer is attached in `graph.compile(checkpointer=...)`.

---

## 2. Component map — subsystem → course module → source package

Every capability is a package built in an earlier module and composed here. v2's
own code is glue: the graph wiring, `V2State`, the `ScopedRetriever`, and thin
CLI/API/report shims.

| Subsystem | Course module | Source package | Reused symbol(s) in v2 |
|---|---|---|---|
| Safety boundary (validation, injection scan, budget) | 20 | [`safety/`](../../src/techcorp_agent/safety/) | `validate_question`, `detect_injection`, `harden_system_prompt`, `validate_answer`, `SessionBudget`/`BudgetExceeded` |
| Multi-agent supervisor + specialists | 18 | [`agents/`](../../src/techcorp_agent/agents/) | `SupervisorAgent`, `_POLICY_PROMPT`/`_SUPPORT_PROMPT`, the supervisor's keyword/regex fallback lists |
| Advanced RAG (hybrid + rerank) | 17 | [`rag/advanced.py`](../../src/techcorp_agent/rag/advanced.py) | `build_bm25_index`, `hybrid_search`, `OverlapReranker` |
| Grounding contract (cite or abstain) | 08 | [`rag/pipeline.py`](../../src/techcorp_agent/rag/pipeline.py) | `build_context_block`, `parse_answer`, `ABSTENTION_TEXT` |
| Durable multi-turn memory | 15 | [`memory/`](../../src/techcorp_agent/memory/) | `checkpointing._make_checkpointer` (SqliteSaver), `long_term.inject_preferences` |
| Streaming (CLI + HTTP) | 16, 21 | [`streaming/`](../../src/techcorp_agent/streaming/) | `stream_agent_events`, `AgentEvent`, `INTERRUPT_KEY` |
| Human approval for the write | 16 | [`streaming/approval.py`](../../src/techcorp_agent/streaming/approval.py) | `interrupt`, `create_ticket`, `ACTION_CREATE_TICKET` |
| MCP tools + graceful degradation | 12–14 | [`mcp_servers/`](../../src/techcorp_agent/mcp_servers/), [`capstone/mcp_bridge.py`](../../src/techcorp_agent/capstone/mcp_bridge.py) | `SyncMCPRegistry`, `_try_mcp_order`, `_try_mcp_calculator`, local `make_order_lookup_tool`/`make_calculator_tool` |
| Tracing / observability | 19 | [`tracing/`](../../src/techcorp_agent/tracing/) | `LocalTracer`, `run_experiment`, `_parse_trace_line`, `_tokens_from_llm` |
| Deployment (FastAPI service) | 21 | [`apps/api/`](../../apps/api/) patterns → [`capstone_v2/app_service.py`](../../src/techcorp_agent/capstone_v2/app_service.py) | `build_v2_app()` reusing Module 21's lifespan / health-vs-ready / SSE patterns |

**The v2-only code** (the joints, not the parts):
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py) (wiring),
[`state.py`](../../src/techcorp_agent/capstone_v2/state.py) (`V2State`),
[`retrieval.py`](../../src/techcorp_agent/capstone_v2/retrieval.py) (`ScopedRetriever`
= category scope × advanced RAG),
[`checkpoint.py`](../../src/techcorp_agent/capstone_v2/checkpoint.py),
[`cli.py`](../../src/techcorp_agent/capstone_v2/cli.py),
[`report.py`](../../src/techcorp_agent/capstone_v2/report.py), and
[`__init__.py`](../../src/techcorp_agent/capstone_v2/__init__.py) (`build_v2_store`).

---

## 3. Request lifecycle, end to end

Trace a single turn through the compiled graph. State is `V2State` (a
`TypedDict, total=False`); nodes return only the keys they change.

1. **Entry.** The CLI, the REPL, or `POST /chat` invokes the graph with a minimal
   state `{"question": ..., "trace": []}` and a config
   `{"configurable": {"thread_id": conversation_id}}`. The `thread_id` is the
   memory + resumable-approval key; the checkpointer loads any prior state for
   that thread before the run.

2. **`boundary` node** (safety, Module 20). Runs on the untrusted edge, before any
   model call. It (a) `validate_question(question)` — reject empty/oversized/bad
   input; (b) `session_budget.check_before_call()` — refuse if the session is over
   its hard limit; (c) `detect_injection(question)` — refuse a blatant direct
   prompt-injection. Any of these sets `blocked=True`, writes a safe `answer`, and
   appends the user turn to `messages`. A clean turn sets `blocked=False`. This
   node makes **zero** model calls.

3. **Branch.** `boundary_decision` sends a blocked turn straight to `formatter`
   (short-circuit, no model spend) and a clean turn to `supervisor`.

4. **`supervisor` node** (routing, Module 18). Picks exactly one route in this
   order: an explicit "create a ticket" phrase → `ticket` (the write action); a
   bare math expression (`_MATH_RE`) → `calculator`; no specialist signal at all
   (greeting/chit-chat) → `general`; otherwise it calls
   `SupervisorAgent.route(question)` (one LLM call online; a deterministic
   keyword/regex fallback offline) → `policy` / `support` / `orders`.

5. **One capability node runs.**
   - `policy` / `support` — `ScopedRetriever.retrieve` fuses BM25 with vector
     search, keeps only in-scope chunks, reranks to `top_k`, then
     `answer_from_chunks` runs the specialist's hardened prompt over them under the
     Module 08 grounding contract (cite only supplied sources, abstain cleanly).
     History (a recap + preferences) rides alongside the strict prompt.
   - `orders` — extract an order id; look it up via MCP `orders.get_order_status`
     if the registry has it, else the local order tool. An unknown id returns a
     safe message, never a crash.
   - `calculator` — compute via MCP `calculator.add` if available, else the local
     calculator tool. The result is a raw number, never attributed to documents.
   - `ticket` — build a one-line summary, then `interrupt(payload)`. **The graph
     pauses here**; the paused state is checkpointed. Nothing is written until a
     `Command(resume="approve"|"reject")` arrives. On approve, `create_ticket`
     mints a deterministic `TCK-XXXX`.
   - `general` — a plain history-aware LLM reply under a hardened system prompt.

6. **`formatter` node** (Modules 14, 20). Gives every route one output shape.
   Knowledge routes carry `sources`; tool/general/ticket routes do not. It runs
   `validate_answer` — if an answer cites a doc it did not retrieve, it drops the
   citations (a conservative, honest degrade) rather than the answer. It appends
   the assistant turn to `messages` so the next turn sees it in history.

7. **Persistence.** After the node returns, the checkpointer writes the full state
   (including the grown `messages`) to SQLite under the `thread_id`. Every node
   also appended a structured line to `state["trace"]`; `traced_invoke` (or the
   `--dev` flag) surfaces that trace, and `traced_invoke` also writes one JSON run
   line via `LocalTracer`.

---

## 4. Design decisions and their trade-offs

Every join in the diagram was a decision. Each is stated with the trade-off — and,
where one exists, the **measured** number that settled it.

### 4.1 Advanced RAG on by default (`advanced_rag=True`)

- **On:** category-scoped hybrid search (BM25 + vector) + `OverlapReranker`.
- **Off:** plain category-filtered vector top-k, identical to v1.

The default is **on** because that is the configuration the Module 17 report
([`artifacts/retrieval_improvement_report.md`](../../artifacts/retrieval_improvement_report.md))
found best **offline**: on the hash-embedding run, `+rerank` took the paraphrase
category from **60% → 100%** hit@4 and overall hit@4 from **83% → 100%** (`+hybrid`
alone: 83% → 94%). The v2 evaluation report
([`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md)) then
measures the integrated system under this config at **96% hit rate@k** over 25
scored examples.

The honest caveat — and the reason the flag exists rather than being hard-coded —
is the **live** result in the same Module 17 report: on the sentence-transformer
corpus, `+hybrid`, `+rerank`, and `all` were **no change** (baseline was already
100% hit@4), and `+rewrite` actually **hurt** (-11%). So the rule is: *hash
embeddings need the help; measure before assuming it helps live.* Cost of "on": a
BM25 index to build per specialist and a reranking pass per query.

### 4.2 Multi-agent supervisor vs one router

The supervisor spends **one LLM call to route** before a specialist answers — a
real token cost v1's keyword router did not pay (offline, the deterministic
keyword/regex fallback carries routing, which is why the routing table in the v2
report is reproducible: **6/8 = 75%**, with the two misses being known
policy-vs-support / explain-a-term keyword collisions, exactly as in v1). The
trade-off: focused specialist prompts (each describes only its slice) reduce prompt
bloat and cross-domain confusion — you pay a routing call and latency to buy that
focus. v2 deliberately keeps synthesis **off** (specialists pass answers through
with attribution) so it never pays a *second* call to reword an already-correct
answer. Module 18's comparison harness
([`agents/comparison.py`](../../src/techcorp_agent/agents/comparison.py)) is how you
decide whether the trade is worth it on real traffic.

### 4.3 Memory via a SQLite checkpointer

The graph is compiled with a `SqliteSaver` (Module 15's exact construction, reused
verbatim in [`checkpoint.py`](../../src/techcorp_agent/capstone_v2/checkpoint.py)),
so the whole state — including the growing `messages` transcript — is written to
SQLite every turn and reloaded by `thread_id`. This is what makes a multi-turn
thread survive a **new graph on the same file** and even a process restart. Two
costs: disk, and a prompt that grows with the conversation. Module 15's
**summarization** ([`memory/summarization.py`](../../src/techcorp_agent/memory/summarization.py))
caps the second — older turns are summarized under a token budget so the recap
stays bounded. The trade-off is fidelity (a summary loses detail) vs cost (an
unbounded transcript is expensive and eventually overflows the context window). A
checkpointer is *always* attached, because the approval interrupt (below) cannot
work without one; with no `db_path` an in-memory `MemorySaver` is used for a single
process or a test.

### 4.4 Human-approval interrupt on the one write action

Ticket creation is the only write in the whole agent, so it — and only it — is
gated behind `interrupt(payload)` in the `ticket` node. The graph pauses *before*
anything is created, the paused state is checkpointed, and the write happens only
on `Command(resume="approve")`. The rule (Module 16) is that **writes,
escalations, and spending** deserve a gate; **reads do not** — so retrieval,
calculator, orders, and general stay un-gated. The trade-off is safety (no
hallucinated ticket ever reaches a real support queue) vs speed (an approved ticket
waits for a human round-trip). Gating reads would add friction with zero safety
benefit.

### 4.5 Safety boundary treats input — and retrieved text — as untrusted

The boundary refuses a **direct** injection in the user's own question (the
cheapest, clearest block). But injection **planted in a retrieved document** is a
different vector, so v2 does not rely on one layer: the specialist prompts are run
through `harden_system_prompt`, and `validate_answer` in the formatter drops any
citation to a doc that was not actually retrieved. Defense-in-depth means no single
filter has to be perfect. The trade-off is coverage vs false positives — an
over-eager injection filter refuses a legitimate question — so the boundary refuses
only blatant direct payloads and leaves the subtle document-borne case to the
hardened prompts and output validation downstream.

### 4.6 In-process index vs an external vector DB

v2 indexes the corpus into an in-process store (`build_v2_store` — hash embeddings
offline; the same code path backs ChromaDB with real embeddings) built **once** at
startup and stashed on `app.state`, not rebuilt per request. For a 13-document
corpus this is the right call: no network hop, deterministic, and it runs with no
API key. The trade-off is that an in-process index does not scale horizontally or
share across replicas the way an external vector DB (a managed Chroma / pgvector /
Pinecone) would. The diagram's `Vector store` node is exactly the seam you would
cut to externalize it; the retrieval code already speaks to a `VectorStore`
interface, so swapping the backing store does not touch the graph.

### 4.7 One integrated service vs many small services

v2 ships **one** FastAPI app
([`app_service.py`](../../src/techcorp_agent/capstone_v2/app_service.py)) that loads
the index and compiled graph once in a lifespan handler, exposes `/health`
(liveness), `/ready` (readiness, 503 until the graph is warm), `/chat`, and
`/chat/stream` (SSE), and logs metadata only — never the raw question, answer, or
any key. One service is simple to deploy and reason about. The trade-off is that
the supervisor, the retrievers, and the tool backends cannot be scaled
independently the way separate services could. The node boundaries in the graph
are where you would split it if a subsystem became a bottleneck.

---

## 5. Honest limitations

These are the things to say out loud before an interviewer says them for you.

- **Offline, only retrieval numbers are meaningful.** With the mock LLM,
  generation-side quality describes the mock, not a real model — the v2 report says
  so explicitly. The **96% hit rate@k** is a retrieval measurement; the mock's
  answers are echoes. Configure a real key and re-run for real generation metrics.
- **Hash embeddings match on word overlap, not meaning.** That is precisely why
  advanced RAG helps offline and why the live numbers differ. Do not generalize the
  offline paraphrase win to a production semantic-embedding corpus without
  measuring — the Module 17 report is a real negative result on the live corpus.
- **Routing offline is keyword-driven, ~75%.** The mock never returns a valid
  specialist name, so the deterministic fallback carries routing, and a couple of
  policy-vs-support / explain-a-term questions trip keyword collisions. A real LLM
  router routes on intent.
- **The corpus is small (13 documents) and fictional.** Retrieval latency numbers
  are wall-clock over an in-memory index on one machine — relative costs between
  configs, not production SLAs.
- **The approval gate depends on a checkpointer.** Remove it and the write cannot
  pause; that coupling is by design, but it is a constraint to know.
- **`create_ticket` writes nothing external.** It returns a deterministic
  `TCK-XXXX` id — the write action is real end-to-end in the graph but mocked at the
  boundary of the (nonexistent) support system.
- **Single-process index.** See §4.6 — this is a deliberate scoping choice, not a
  scale story.

---

## Related documents

- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — the five-minute live walkthrough.
- [PORTFOLIO_README.md](PORTFOLIO_README.md) — the publishable project README.
- [INTERVIEW_PREP.md](INTERVIEW_PREP.md) — module-by-module interview question bank.
- [concepts.md](concepts.md) — the module's teaching version of this architecture.
