# Module 19 — Lab

Instrument the capstone agent, view its traces, turn the Module 09 dataset into a repeatable experiment, then deliberately break a prompt and **catch the regression** in a before/after comparison. Work in `starter/observability_lab.py`; the shared tracing package (`src/techcorp_agent/tracing/`) does the heavy lifting.

The golden rule for this whole lab: **you don't argue that a change is an improvement — you measure it, on a fixed dataset, and you catch the regression before it ships.**

Everything runs offline. Run the reference any time to see the target output:

```bash
TECHCORP_OFFLINE=true uv run python course/19_observability_and_evaluation/solution/observability_lab.py
```

---

## Lab A — Instrument the agent and view its traces

Open `lab_a_trace_agent` in the starter. The one TODO wires the capstone graph into the tracer:

```python
state = trace_agent(build_graph(llm, store), question, tracer, llm=llm)
```

`trace_agent` invokes the graph, then reads the node lines the graph already writes into `state["trace"]` (`[node=router] tool=document_search route=retrieval`) back out as ordered steps — you do **not** re-instrument the shared graph. It records the route, the answer and sources, the tokens (approximated from the mock client's `.calls`), and the wall-clock latency, and appends one JSON line to `artifacts/traces/runs.jsonl`.

Run it. Lab A traces four questions that hit four different routes:

```
=== Lab A — instrument the agent ===
  traced: route=retrieval  q='How many vacation days do TechCorp employees get each year?'
  traced: route=calculator q='What is 17.5% of 8,400?'
  traced: route=orders     q='Where is my order TC-1234 right now?'
  traced: route=general    q='Hi there, thanks for the help!'
```

Now **view the traces** with the viewer:

```bash
uv run python scripts/view_traces.py
```

```
                             Agent traces (54 runs)
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ run id   ┃ name                   ┃ route      ┃ tokens ┃ latency ms ┃ error ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│ b7704d0d │ techcorp-agent         │ retrieval  │ 1143   │ 2.8        │       │
│ 4619c8a6 │ techcorp-agent         │ calculator │ 252    │ 0.6        │       │
│ 8321f43f │ techcorp-agent         │ orders     │ 256    │ 0.7        │       │
│ a8978e54 │ techcorp-agent         │ general    │ 301    │ 0.5        │       │
```

(If `rich` isn't importable, you get a clean ASCII table instead — same columns.) The viewer also prints a **p50/p95 latency** summary at the bottom.

Then **drill into one run** with `--run` and an id prefix to see its ordered steps:

```bash
uv run python scripts/view_traces.py --run b7704d0d
```

```
run_id:    b7704d0d-fb93-4ea9-8c44-78b32f223e5a
name:      techcorp-agent
inputs:    {"question": "How many vacation days do TechCorp employees get each year?"}
tokens:    1143    latency ms: 2.8

steps:
   1. [router] tool=document_search route=retrieval
   2. [retrieval] loop=1 chunks=4 abstained=False sources=[]
   3. [formatter] route=retrieval sources=[]
   4. [route] retrieval
```

> **Checkpoint A.** You can point at a JSONL trace log, see one line per run in the viewer, and expand a single run into the exact ordered nodes it visited — the router's decision, the retrieval node's chunk count, the formatter. That is *what the agent did*, on the record.

---

## Lab B — Build the dataset and run a baseline experiment

You already have a dataset: `data/evaluation/eval_dataset.json` from Module 09. `load_examples()` reads it. In the live LangSmith path you'd *upload* it once; offline you load it directly — same 33 examples.

Now run it as an **experiment**. `run_experiment(name, pipeline_fn, examples, tracer)` runs each example through your pipeline, traces it, and scores it with the deterministic Module 09 metrics (it skips `tool_routing` examples, which need the tool agent, not RAG — the same exclusion the Module 09 runner makes). Complete the TODO in `make_grounded_pipeline`: the baseline keeps the citation rule, so the model reply ends with a `SOURCES:` line:

```python
raw = f"{body}\nSOURCES: {top_source}"
```

Then wire the baseline experiment:

```python
baseline = run_experiment("baseline", baseline_fn, examples, tracer)
```

The baseline aggregates (offline, hash embeddings + mock LLM):

```
=== Lab B — baseline experiment ===
  scored 25 examples
    hit_rate=0.84  source_accuracy=0.60  fact_coverage=1.00  abstention_accuracy=1.00
```

> **Checkpoint B.** You have a baseline number, on the record, for every metric. This is the thing a regression is measured *against* — without it, "better" is a feeling.

Remember the honesty caveat from Module 09: offline, the generation-side numbers describe the *mock*, not a real model — only `hit_rate` is meaningful. The machinery is real and reproducible; the absolute values change with a real model.

---

## Lab C — Deliberately worsen the prompt, and catch it

This is the point of the module. You'll simulate a well-meaning "let's simplify the system prompt" edit that quietly **drops the citation rule** (rule 5: "end with `SOURCES:`") — and prove that observability catches the damage.

**Do not edit any shared code.** The shared `RAGPipeline` and its prompt are used by Modules 08, 09, 14, 17 — mutating them would break everyone. Instead you *compose*: `make_grounded_pipeline(store, drop_citation_rule=True)` wraps the pipeline and changes only the one thing under test. Complete the sabotage TODO — the candidate reply carries **no** `SOURCES:` line:

```python
raw = body  # no SOURCES line -> the model "forgot" to cite
```

Run the candidate as a second experiment and compare:

```python
candidate = run_experiment("no-citation-rule", candidate_fn, examples, tracer)
report = compare_experiments(baseline, candidate)
```

`compare_experiments` catches it:

```
=== Lab C — deliberately worsen the prompt, then catch it ===
  candidate: dropped the citation rule (no SOURCES line) — no shared code edited
    hit_rate=0.84  source_accuracy=0.28  fact_coverage=1.00  abstention_accuracy=1.00

--- Regression report ---
  REGRESSION: 'no-citation-rule' is worse than 'baseline' on 8 example(s): eval-001, eval-002, eval-003, eval-005, eval-009 (+3 more).
  per-metric deltas (candidate - baseline):
    hit_rate               +0.000
    source_accuracy        -0.320  <-- worse
    fact_coverage          +0.000
    abstention_accuracy    +0.000
  regressed examples: 8
    - eval-001 (answerable) delta=-0.250
    - eval-002 (answerable) delta=-0.250
    - eval-003 (answerable) delta=-0.250
    - eval-005 (answerable) delta=-0.250
    - eval-009 (answerable) delta=-0.250
```

Read what happened: `hit_rate` didn't move (retrieval is unchanged — dropping the citation rule doesn't affect which chunks are fetched), but `source_accuracy` fell **0.32** because grounded answers now cite nothing, and the report names the exact eight examples that broke. That is the completion criterion made concrete.

> **Checkpoint C.** You can answer "how do you know your change improved the agent?" — or in this case, *broke* it — with a table and a named list of regressed examples, not a vibe.

---

## Lab D — Optional: see the same runs in LangSmith (live)

Everything above works with no account. If you have a free [LangSmith](https://smith.langchain.com) key, you can mirror the same runs to the UI. Exact setup:

1. Sign up at smith.langchain.com (free tier) and create an API key.
2. In your `.env` (copied from `.env.example`), set:
   ```bash
   LANGSMITH_API_KEY=lsv2_...        # your key
   LANGSMITH_PROJECT=techcorp-agent  # the project name to write to
   ```
3. Construct the bridge and pass it to the tracer:
   ```python
   from techcorp_agent.tracing import LangSmithBridge, LocalTracer, langsmith_enabled

   bridge = LangSmithBridge()  # no-op if no key
   tracer = LocalTracer(TRACE_PATH, bridge=bridge)  # local write + UI mirror
   print("live:", langsmith_enabled())
   ```
4. Re-run the labs (drop `TECHCORP_OFFLINE=true` if you want a real model too). Each local run is mirrored to LangSmith; open your project to see runs, per-run inputs/outputs, and the step waterfall.

The mirror is best-effort: a LangSmith outage never breaks or delays the local JSONL write, which remains the source of truth. With no key set, `LangSmithBridge` holds no client and every mirror call is a silent no-op — which is why none of the tests need an account.

---

## Debugging hints

- **`view_traces.py` says "No runs found."** You haven't recorded any runs yet, or you're pointing at the wrong file. Run Lab A first, or pass `--path artifacts/traces/runs.jsonl` explicitly.
- **`--run` says "Ambiguous id."** Two run ids share your prefix; use a longer prefix (the full 8-char short id from the table is usually enough).
- **Aggregates look flat but you expected a regression.** Read the per-example `regressions` list, not just the deltas — a change can break some examples and improve others so the aggregate barely moves. `compare_experiments` compares per example for exactly this reason.
- **The regression wasn't caught.** Check your Lab C TODO: the sabotaged branch must produce a reply with **no** `SOURCES:` line. If both branches cite, both experiments score the same and there's nothing to catch.
- **Token count is `-` in the viewer for experiment rows.** Expected — the experiment pipeline is deterministic and makes no LLM call for those rows, so there's no usage to record. The Lab A agent runs (which do call the mock LLM) show token counts.

---

## Stretch goals

- **Richer percentiles in the viewer.** The viewer prints p50/p95 latency. Add p90 and p99, or a per-route latency breakdown, so you can see whether one route (say retrieval) dominates the slow tail.
- **Layer the LLM judge on top of the deterministic gate.** For the `paraphrase` category, where `fact_coverage`'s substring check scores correct paraphrases as 0, call `llm_judge(...)` and feed it through `combine_scores(deterministic, judge)`. Confirm the judge can *refine* a passing score but never rescues a deterministic failure — score a made-up answer that fails the gate and watch `combine_scores` still return `passed=False`.
- **Cost per experiment.** Multiply the traced token usage by Module 02's per-1M-token rates (`techcorp_agent.costs`) and print an estimated dollar cost per experiment, so a "the numbers improved" claim comes with a "…and it cost $X" caveat.
