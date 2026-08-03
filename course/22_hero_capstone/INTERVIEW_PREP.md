[🗺 Course Roadmap](../../ROADMAP.html) · [← Architecture](ARCHITECTURE.md) · [← Demo Script](DEMO_SCRIPT.md) · [← Portfolio README](PORTFOLIO_README.md)

# AI-Engineering Interview Prep — Module-by-Module Question Bank

Each entry is a **common interview question**, a **concise strong answer**, and a
**pointer to the exact code in this repo** that demonstrates it. Answer in your own
words; use the code as proof, not a script. The high-frequency topics are covered
in module order (00–22), followed by a short "hard questions" section built on the
honest findings this project produced.

> How to use this: for any topic, be able to (1) state the idea in one sentence,
> (2) name the trade-off, and (3) point at where you did it. The third is what
> separates a candidate who *read* about RAG from one who *shipped* it.

---

## Module 00–01 — Environment, tokens, context windows

**Q: What is a token, and why does the context window matter?**
A token is a sub-word unit; models bill and think in tokens, not characters or
words. The context window is the hard ceiling on tokens per request (prompt +
completion). It matters because every retrieved chunk, every prior turn, and every
instruction competes for that budget — and more context is not free: it costs money
and can *dilute* the signal (noise crowds out the answer). So you retrieve
selectively and summarize history rather than dumping everything in.
*Code:* [`src/techcorp_agent/costs.py`](../../src/techcorp_agent/costs.py) (token/cost
accounting), tokenization via `tiktoken` in the stack.

**Q: How do you keep an offline dev loop when the model costs money?**
A deterministic mock LLM and hash embeddings behind the same interfaces as the real
clients, toggled by an env var. The whole app runs with `TECHCORP_OFFLINE=true` and
no key.
*Code:* [`src/techcorp_agent/llm/mock_client.py`](../../src/techcorp_agent/llm/mock_client.py),
[`src/techcorp_agent/llm/factory.py`](../../src/techcorp_agent/llm/factory.py).

## Module 02–03 — Calling an LLM; framework trade-offs

**Q: What's in an LLM response beyond the text, and why care?**
Role, content, and **usage** (prompt/completion tokens) — usage is how you compute
cost and enforce a budget, and finish reasons tell you if you were truncated.
*Code:* [`src/techcorp_agent/llm/openai_client.py`](../../src/techcorp_agent/llm/openai_client.py),
usage consumed by [`safety/budget.py`](../../src/techcorp_agent/safety/budget.py).

**Q: When do you reach for a framework (LangChain/LangGraph) vs the raw SDK?**
Raw SDK when you want full control of one call. A framework when you need
composition, structured output, and stateful orchestration — which is exactly why
the agent is a LangGraph, not a pile of SDK calls. The trade-off is abstraction
overhead vs the wiring you'd otherwise hand-write.
*Code:* [`src/techcorp_agent/llm/base.py`](../../src/techcorp_agent/llm/base.py)
(a thin `LLMClient` interface both the real and mock clients implement).

## Module 04 — Prompt engineering

**Q: How do you make a prompt reliable, and how do you know it improved?**
Specificity, role framing, few-shot examples, and decomposition — then *score* the
variants against a rubric instead of eyeballing them. In this project the specialist
prompts are focused (each describes only its slice) precisely to reduce cross-domain
confusion, and they're hardened against injection.
*Code:* specialist prompts `_POLICY_PROMPT`/`_SUPPORT_PROMPT` in
[`src/techcorp_agent/agents/specialists.py`](../../src/techcorp_agent/agents/specialists.py),
hardened by `harden_system_prompt` in
[`src/techcorp_agent/safety/injection.py`](../../src/techcorp_agent/safety/injection.py).

## Module 05 — Embeddings: semantic vs keyword

**Q: Embeddings vs keyword search — when does each win?**
Embeddings match *meaning* (a query about "denim" finds a "jeans" policy); keyword
(BM25) matches *exact tokens* (product codes, error strings, policy names). They
fail differently — vectors dilute rare keywords, BM25 is blind to synonyms — so the
best retriever fuses both.
*Code:* embeddings in
[`src/techcorp_agent/embeddings/`](../../src/techcorp_agent/embeddings/) (`st_client.py`
live, `hash_client.py` offline); similarity math in
[`src/techcorp_agent/similarity.py`](../../src/techcorp_agent/similarity.py).

## Module 06–07 — Semantic search, vector DBs, chunking

**Q: What's the chunking trade-off?**
Chunks too large dilute the embedding and waste context; too small fragment the
answer across chunks and lose it. You pick a size (with overlap) that keeps a
coherent unit of meaning per chunk, and you *measure* retrieval to confirm.
*Code:* [`src/techcorp_agent/documents/chunking.py`](../../src/techcorp_agent/documents/chunking.py),
persisted index in [`src/techcorp_agent/vectorstore/chroma_store.py`](../../src/techcorp_agent/vectorstore/chroma_store.py).

**Q: Why a persistent vector DB (ChromaDB) instead of an in-memory array?**
Persistence (index once, query many), metadata filtering (retrieve only a
category), and a swappable backend. This project indexes once at startup and filters
retrieval by document category per specialist.
*Code:* `build_v2_store` in
[`src/techcorp_agent/capstone_v2/__init__.py`](../../src/techcorp_agent/capstone_v2/__init__.py);
category-scoped queries in
[`retrieval.py`](../../src/techcorp_agent/capstone_v2/retrieval.py).

## Module 08 — RAG: grounding, citation, abstention

**Q: How do you stop a RAG system from hallucinating?**
The grounding contract: retrieve first, answer *only* from the retrieved context,
cite the source, and **abstain** when nothing supports an answer — never invent. You
also filter citations to sources that were actually supplied, and drop citations on
an abstention.
*Code:* `build_context_block`, `parse_answer`, `ABSTENTION_TEXT` in
[`src/techcorp_agent/rag/pipeline.py`](../../src/techcorp_agent/rag/pipeline.py);
enforced in `ScopedRetriever.answer_from_chunks`
([`retrieval.py`](../../src/techcorp_agent/capstone_v2/retrieval.py)) and again in
the formatter's `validate_answer`
([`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py)). Abstention accuracy is
100% in [`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md).

## Module 09 — Retrieval evaluation

**Q: How do you evaluate a RAG system, and why split retrieval from generation?**
Score them separately because they fail separately. Retrieval: **hit rate@k** (did
the right chunk make the top-k?) and source accuracy. Generation: fact coverage and
abstention correctness. If hit@k is low, fix retrieval; if hit@k is high but answers
are wrong, fix the prompt/model. Conflating them hides the real bug.
*Code:* metrics in [`src/techcorp_agent/evaluation/metrics.py`](../../src/techcorp_agent/evaluation/metrics.py),
runner in [`src/techcorp_agent/evaluation/runner.py`](../../src/techcorp_agent/evaluation/runner.py);
v2 report split in [`capstone_v2/report.py`](../../src/techcorp_agent/capstone_v2/report.py)
(a routing table *and* a retrieval table).

## Module 10 — LangGraph: state, routing, bounded loops

**Q: Why a graph instead of a chain, and how do you keep it from looping forever?**
A graph gives you explicit state, conditional routing, and joins that a linear chain
can't express. Bounded loops: a hard `max_loops` cap on any retry seam makes the
graph provably finite. Shared state uses reducers so parallel writes merge instead
of clobbering.
*Code:* `V2State` with reducers (`messages` appends, `trace` uses `operator.add`) in
[`capstone_v2/state.py`](../../src/techcorp_agent/capstone_v2/state.py); `max_loops`
and the conditional edges in
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py).

## Module 11 — Tools and routing

**Q: How does an agent decide which tool to use, and what happens when a tool fails?**
A router (LLM-chosen or deterministic) selects the tool; the tool has a typed
schema so inputs are validated. Failure must degrade gracefully — an unknown order
or a calc error returns a clean message, not a stack trace.
*Code:* [`src/techcorp_agent/tools/router.py`](../../src/techcorp_agent/tools/router.py),
typed tools in [`src/techcorp_agent/tools/`](../../src/techcorp_agent/tools/)
(`calculator.py`, `orders.py`), each returning a `ToolResult` that carries `ok`/`error`.

## Module 12–13 — MCP: tools as a protocol

**Q: What's MCP and why use it over in-process function calls?**
Model Context Protocol standardizes tools as servers behind a protocol, so tools are
language-agnostic, independently deployable, and swappable without touching the
agent. The cost is a process boundary and a connection to manage — so you build a
registry over multiple servers and handle *partial* failure (one server down doesn't
kill the rest).
*Code:* MCP servers in [`src/techcorp_agent/mcp_servers/`](../../src/techcorp_agent/mcp_servers/),
the `SyncMCPRegistry` bridge in
[`src/techcorp_agent/capstone/mcp_bridge.py`](../../src/techcorp_agent/capstone/mcp_bridge.py);
v2 uses MCP when available and falls back to local tools otherwise
(`orders_node`/`calculator_node` in [`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py)).

## Module 14 — Composition (v1 capstone)

**Q: How do you integrate retrieval + tools + routing into one app?**
A router-and-formatter graph: route to a capability, run it, format one consistent
output shape. v1 proved the composition; v2 is the *integration* that adds the
production layers on top.
*Code:* v1 graph in [`src/techcorp_agent/capstone/graph.py`](../../src/techcorp_agent/capstone/graph.py),
reused by v2 (`_try_mcp_order`, `_ORDER_ID_RE`).

## Module 15 — Memory and persistence

**Q: How does an agent "remember" across turns, and what's the catch?**
A checkpointer persists the whole graph state (including the message transcript)
keyed by a thread id, so a follow-up resolves against earlier turns and the
conversation survives a restart. The catch: the prompt grows every turn, so you
**summarize** older turns under a token budget — trading some fidelity for a bounded,
affordable prompt.
*Code:* SqliteSaver construction reused in
[`capstone_v2/checkpoint.py`](../../src/techcorp_agent/capstone_v2/checkpoint.py)
(from [`memory/checkpointing.py`](../../src/techcorp_agent/memory/checkpointing.py));
summarization in [`memory/summarization.py`](../../src/techcorp_agent/memory/summarization.py);
proven by `test_multi_turn_memory_survives_new_graph_on_same_sqlite`.

## Module 16 — Streaming and human-in-the-loop

**Q: Streaming vs an interrupt — what's the difference?**
Streaming is *output* incrementally (tokens/events) for responsiveness; an interrupt
is a *pause* for a human decision before a risky action. They're orthogonal — this
agent does both. The interrupt gates the one write (ticket creation): the graph
pauses *before* writing, the paused state is checkpointed, and it resumes on
approve/reject.
*Code:* `stream_agent_events` in
[`src/techcorp_agent/streaming/events.py`](../../src/techcorp_agent/streaming/events.py);
`interrupt` + `create_ticket` in
[`src/techcorp_agent/streaming/approval.py`](../../src/techcorp_agent/streaming/approval.py);
wired in the `ticket_node` of [`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py).

## Module 17 — Advanced RAG (hybrid search, reranking)

**Q: What's hybrid search + reranking, and does it always help?**
Hybrid fuses BM25 (exact tokens) with dense vectors (meaning) to recover the union
of what each misses; reranking then reorders the shortlist so the best chunk lands
in the top-k the generator sees — a *precision* fix, not a recall fix. **It does not
always help.** On this project's offline embedding run, reranking took paraphrase
hit@4 from **60% → 100%**; but on the live semantic corpus (already at 100%) hybrid
and rerank were a **wash**, and query rewriting *hurt* (-11%). So it's a defaulted
flag, on where measured to help.
*Code:* `build_bm25_index`, `hybrid_search`, `OverlapReranker` in
[`src/techcorp_agent/rag/advanced.py`](../../src/techcorp_agent/rag/advanced.py);
composed in `ScopedRetriever`
([`retrieval.py`](../../src/techcorp_agent/capstone_v2/retrieval.py)); numbers in
[`artifacts/retrieval_improvement_report.md`](../../artifacts/retrieval_improvement_report.md).

## Module 18 — Multi-agent systems

**Q: When is multi-agent worth it, and what does it cost?**
It buys specialist focus — each agent's prompt describes only its domain, cutting
cross-domain confusion. It costs one LLM call to route before a specialist answers,
plus latency. Worth it when focus reduces errors enough to pay for the routing call;
you *measure* that, you don't assume it. This project keeps synthesis off so it never
pays a *second* call to reword an already-correct answer.
*Code:* `SupervisorAgent` in
[`src/techcorp_agent/agents/supervisor.py`](../../src/techcorp_agent/agents/supervisor.py),
comparison harness in
[`src/techcorp_agent/agents/comparison.py`](../../src/techcorp_agent/agents/comparison.py);
routing accuracy (6/8 offline, keyword fallback) in
[`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md).

## Module 19 — Observability and evaluation

**Q: How do you debug and regression-test an agent in production?**
Structured tracing on every node (what ran, which route, token usage) captured to
disk, plus a repeatable evaluation harness that runs a dataset and reports metrics —
so a regression shows up as a number, not a user complaint.
*Code:* `LocalTracer` + `run_experiment` in
[`src/techcorp_agent/tracing/`](../../src/techcorp_agent/tracing/); every v2 node
appends to `state["trace"]`, surfaced by `traced_invoke`
([`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py)) and the report
([`capstone_v2/report.py`](../../src/techcorp_agent/capstone_v2/report.py)).

## Module 20 — Guardrails and safety

**Q: How do you defend against prompt injection, and where do the checks go?**
Defense in depth. On the untrusted edge: validate input, block blatant *direct*
injection, and enforce a cost budget — all before any model call, so a bad request
is cheap to refuse. Downstream: harden specialist prompts against injection planted
*in retrieved documents*, and validate output (drop any citation to a doc that
wasn't retrieved). No single layer has to be perfect.
*Code:* `validate_question`, `detect_injection`, `harden_system_prompt`,
`validate_answer`, `SessionBudget` in
[`src/techcorp_agent/safety/`](../../src/techcorp_agent/safety/); wired at the
`boundary_node` and `formatter_node` of
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py). All safety smoke checks
pass in [`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md).

## Module 21 — Deployment

**Q: How do you ship an agent as a service, and what's health vs readiness?**
Load the expensive things (index, compiled graph) **once** at startup in a lifespan
handler, not per request. `/health` is liveness (is the process up?); `/ready` is
readiness (is the graph warm? — 503 until it is). Orchestrators restart on liveness
failure and pull-from-load-balancer on readiness failure. Log metadata only — never
the raw question, answer, or a secret.
*Code:* `build_v2_app()` in
[`src/techcorp_agent/capstone_v2/app_service.py`](../../src/techcorp_agent/capstone_v2/app_service.py)
(reusing Module 21's patterns in [`apps/api/`](../../apps/api/)); endpoints
`/health`, `/ready`, `/chat`, `/chat/stream`.

## Module 22 — Integration (the hero capstone)

**Q: Walk me through how these pieces become one production app.**
One LangGraph: `boundary → supervisor → {policy, support, orders, calculator,
ticket, general} → formatter`, compiled with a SQLite checkpointer for memory and
resumable approval, with a tracer on every node. Each node *delegates* to a package
built earlier — the integration adds new code only at the joints (wiring, state, the
scoped retriever, thin glue). The whole thing runs offline with no key.
*Code:* `build_v2_graph` in
[`src/techcorp_agent/capstone_v2/graph.py`](../../src/techcorp_agent/capstone_v2/graph.py);
full design in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Hard questions (use the honest findings)

These separate people who ship from people who follow tutorials. The strongest
answer to each is a *negative* result you can defend with a number.

**Q: When would you NOT use RAG?**
When the answer isn't in a document — arithmetic, live lookups, real-time state.
This agent routes math to a deterministic calculator and order status to a tool, and
never attributes a computed number to a document. RAG is for grounding in a corpus;
forcing everything through it invents citations for things that have none.
*Code:* the `calculator`/`orders` routes in
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py) (`sources=[]` for tool
results).

**Q: When would advanced RAG (hybrid/rerank/rewrite) NOT be worth it?**
When your baseline retrieval is already saturating. On the live semantic-embedding
corpus in this project, hybrid and rerank were a **wash** (baseline already 100%
hit@4) and query rewriting **hurt** (-11%). Advanced techniques earn their
complexity only where measurement shows a gap — here, on the offline hash embeddings
(60% → 100% on paraphrase), not live.
*Code:* [`artifacts/retrieval_improvement_report.md`](../../artifacts/retrieval_improvement_report.md).

**Q: When would you NOT go multi-agent?**
When a single focused prompt already routes and answers well — you'd be paying a
routing call and latency for no accuracy gain. Multi-agent wins when specialist
focus measurably reduces confusion; otherwise one router is cheaper. Measure with a
comparison harness before adopting it.
*Code:* [`src/techcorp_agent/agents/comparison.py`](../../src/techcorp_agent/agents/comparison.py).

**Q: When would you NOT use an agent at all?**
When the task is deterministic and single-step — a lookup, a calculation, a
templated transform. An agent adds routing, tool selection, and non-determinism; if
a plain function does the job, use the function. The value of an agent is *choosing*
among capabilities under uncertainty, which a fixed pipeline doesn't need.

**Q: Your offline metrics look great — are they real?**
Only the retrieval-side ones. With the mock LLM, generation quality describes the
mock, not a real model — the evaluation report says so in its own caveats. I quote
the retrieval hit rate (96% hit@k) and the routing table (deterministic, 6/8), and I
never claim the mock's echoed answers are good prose. Stating that limitation is
part of the deliverable.
*Code:* the "Reading these numbers honestly" section of
[`artifacts/capstone_v2_report.md`](../../artifacts/capstone_v2_report.md).

**Q: What breaks first at scale, and how would you fix it?**
The in-process, single-replica index. It's right for a 13-document corpus and wrong
for millions — it doesn't shard or share across replicas. I'd externalize it to a
managed vector DB; the retrieval code already speaks to a `VectorStore` interface, so
the graph wouldn't change. See §4.6 of [ARCHITECTURE.md](ARCHITECTURE.md).

**Q: How do you keep costs from running away?**
A per-session budget enforced at the boundary *before* any model call, so an
exhausted session makes zero further billable calls (it fails closed). Plus history
summarization to keep the prompt bounded, and synthesis kept off so the agent never
pays a second LLM call to reword a correct answer.
*Code:* `SessionBudget.check_before_call()` at the boundary
([`safety/budget.py`](../../src/techcorp_agent/safety/budget.py),
[`graph.py`](../../src/techcorp_agent/capstone_v2/graph.py)).

---

## Related documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — the system design and every trade-off.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — the five-minute live walkthrough.
- [PORTFOLIO_README.md](PORTFOLIO_README.md) — the publishable project README.
