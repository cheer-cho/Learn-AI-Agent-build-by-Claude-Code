# Multi-Agent vs Single-Agent Comparison

Both systems answered the same **6** questions, measured through one
harness so they are scored on the same ruler. Offline numbers use the
deterministic mock LLM: token counts and call counts are exact and
repeatable; wall-clock latency varies run to run but its *shape* does not
(the supervisor always does strictly more work).

## Headline

| metric | single agent | supervisor | delta |
|---|---:|---:|---:|
| LLM calls | 10 | 16 | +6 |
| total tokens | 5776 | 6262 | +486 |
| latency (s) | 0.0252 | 0.0048 | -0.0204 |
| failures | 0 | 0 | +0 |

## Per-question answers

| # | single-agent sources | supervisor sources |
|---:|---|---|
| 1 | — | — |
| 2 | — | — |
| 3 | — | — |
| 4 | — | — |
| 5 | — | — |
| 6 | — | — |

## Reading this honestly

- **The supervisor costs more, always.** It spends a routing LLM call on
  every question before any specialist runs, so its call count and token
  total are strictly higher than the single agent's. That is the price of
  the pattern, not a defect to tune away.
- **Quality is where multi-agent can pay off** — a focused specialist
  prompt is less likely to be distracted by irrelevant tools/policy than
  one prompt holding everything. Compare the source columns above: where
  they match, the extra cost bought nothing here.
- **Latency compounds** with each hop. One routing call + one specialist
  call is two sequential round trips where the single agent had one.
- **Read the offline latency number with care.** Against the mock, LLM
  calls are effectively free, so wall-clock time is dominated by *vector
  retrieval*, not by call count. The single-agent graph retrieves twice
  per RAG question (once to summarize evidence, once inside the answer),
  so it can post a *higher* offline latency than the supervisor even though
  the supervisor makes more model calls. With a real network-bound LLM the
  extra calls dominate and the supervisor is the slower system — the call
  and token deltas above are the durable signal; treat offline latency as
  indicative of shape, not a benchmark.
- **Failure is contained**: a specialist crash becomes a graceful apology,
  and the supervisor's failure count stays low — but debugging *why* a
  specialist was chosen and then failed is a distributed-systems problem,
  not a stack trace.

### When to ship the single agent instead

If the source columns match and the failure counts match, the supervisor
spent extra calls, tokens, and latency to arrive at the same answers — 
ship the single agent. Reach for the supervisor only when a domain's
specialist measurably improves answer quality or when the single prompt
has grown too large to route reliably (prompt bloat, tool confusion).
