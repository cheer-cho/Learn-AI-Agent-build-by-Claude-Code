# Module 07 Lab — Vector Databases and the Chunking Experiment

## Scenario

Module 06 shipped a working search engine — and re-embedded all 13 policy documents every single time it started. Your team lead has seen enough: "Persist the vectors, and while you're at it, settle the chunk-size argument with numbers, not opinions." So this module has two labs. In **Lab A** you build the experiment that answers *what chunk size retrieves best on TechCorp's corpus?* by measuring three configurations against the evaluation questions and writing up the result. In **Lab B** you take a guided tour of the persistent ChromaDB store the rest of the course will run on — add chunks, query, filter, rebuild, and prove the index survives a process restart.

You will implement three measurement functions in `starter/chunking_experiment.py` (Lab A) and drive the shared `VectorStore` from a scratch file you create (Lab B). The shared library already provides document loading, chunking, embedding clients, and the ChromaDB wrapper — your job is the experiment and the tour.

## Learning objectives

By the end you can:

- Index chunks into a persistent ChromaDB collection and query them semantically
- Measure a chunking configuration's retrieval hit-rate against a fixed evaluation set, plus its chunk count, average chunk length, and duplicate-content rate
- Explain, with your own numbers, why there is no universal best chunk size
- Filter a vector query by metadata (`category`) and say why a filter is a guarantee where a score is only a tendency
- Rebuild a collection safely with `reset()` (never `rm -rf`) and prove persistence across a process restart
- State the embedding-model compatibility rule and recognize the silent failure the store's guard prevents

## Setup

```bash
uv sync                      # if you haven't already (Module 00)
```

Run commands from the repository root.

- **Run your Lab A work:** `uv run python course/07_vector_database/starter/chunking_experiment.py`
- **Test:** `uv run pytest course/07_vector_database -q`
- **See the target behavior anytime:** `uv run python course/07_vector_database/solution/run_experiment.py` (attempt each task before reading solution code)

First run note: the real embedding model (`all-MiniLM-L6-v2`, ~90 MB) downloads once, then is cached. To skip the download entirely, set `TECHCORP_OFFLINE=true` — the run falls back to the deterministic `HashEmbeddingClient` and says so loudly, because **hash numbers measure word overlap, not semantics** (see "An honest note on results" below).

---

## Lab A — The chunking experiment

**Scenario.** Fix an evaluation set, vary the configuration, measure — the only defensible way to choose a chunk size. Open `starter/chunking_experiment.py`. The three configurations, the eval-question loader, and `main()` are already wired; you implement `duplicate_rate`, `run_config`, and `write_report`.

The three configurations under test (already defined in `CONFIGS`) are:

| `name` | `strategy` | `chunk_size` | `overlap` |
|---|---|---:|---:|
| `small-fixed` | `fixed` | 300 | 30 |
| `medium-fixed` | `fixed` | 800 | 100 |
| `paragraph` | `paragraph` | 1200 | 0 |

A **hit** is defined by `TOP_K = 4`: the question's expected source document appears among the top-4 retrieved chunks. The questions come from `load_eval_questions()` — the `answerable` and `paraphrase` categories of `data/evaluation/eval_dataset.json` (the only ones with an expected retrievable source; 15 questions total). The other categories are not retrieval questions and say nothing about chunking quality.

### Task 1 — Read the wiring (already done — understand it)

Read `load_eval_questions()` (filters to `EVAL_CATEGORIES = ("answerable", "paraphrase")`, returns dicts with `id`, `question`, `expected_sources`) and `main()` (resolves the embedding client, loops `CONFIGS` inside one `tempfile.TemporaryDirectory`, prints the summary table, then calls `write_report`). Note that all indexing happens in a **throwaway temp directory** — never in the repo's `.chroma/`.

### Task 2 — `duplicate_rate(chunks)`

Return the fraction of `SHINGLE_SIZE`-word (8-word) shingles that appear in more than one chunk. For each chunk text, build the **set** of 8-word windows (lowercase, split on whitespace) — a set, so a shingle repeated inside *one* chunk does not count. Count every shingle across all per-chunk sets (`collections.Counter` helps), then return `(occurrences of shingles seen in >1 chunk) / (all occurrences)`. Return `0.0` when there are no shingles at all (empty or too-short chunks). This is what makes the cost of overlap visible.

### Task 3 — `run_config(...)`

Index one configuration in a throwaway collection and measure it. In order:

1. Chunk every document with `chunk_document(document, strategy=strategy, chunk_size=chunk_size, overlap=overlap)` and collect all chunks into one list.
2. Build a `VectorStore(embeddings, persist_dir=Path(persist_dir), collection_name=...)` with a config-specific collection name (e.g. `f"chunking_{name}".replace("-", "_")` — Chroma collection names can't contain hyphens). Call `store.reset()` first so a re-run starts clean, then `store.add_chunks(chunks)`.
3. For each question, `store.query(question["question"], top_k=top_k)`. It is a **hit** when any of `question["expected_sources"]` appears among the retrieved chunks' `doc_id`s; otherwise append a failure dict with keys `id`, `question`, `expected_sources`, `retrieved_doc_ids`.
4. `store.reset()` again to leave the throwaway collection empty, then return the metrics dict with **exactly** these keys: `name`, `strategy`, `chunk_size`, `overlap`, `chunk_count`, `avg_chunk_chars`, `hit_rate` (`hits / question_count`), `duplicate_rate` (from Task 2 on the chunk texts), `failures`, `question_count`, `top_k`, `embedding_model` (`embeddings.model_name`).

### Task 4 — `write_report(results, path)`

Build a Markdown report and write it to `path`, returning the `Path`. At minimum it must contain:

- **Which embedding client produced it** — `results[0]["embedding_model"]` — and the caveat that hash-embedding numbers measure word overlap, not semantics.
- A **comparison table**, one row per config: `name`, `strategy`, `chunk_size`, `overlap`, `chunk_count`, `avg_chunk_chars`, `hit_rate`, `duplicate_rate`.
- A **failure-cases section**: per config, each missed question with its expected sources and the `doc_id`s actually retrieved.

`mkdir(parents=True, exist_ok=True)` on `path.parent` before writing.

### Task 5 — Generate the report and read it

```bash
uv run python course/07_vector_database/solution/run_experiment.py
# then read artifacts/chunking_report.md
```

(Point the same command at your starter file once your three functions are in: `uv run python course/07_vector_database/starter/chunking_experiment.py`.) Read the report and answer for yourself, in a scratch note: which config would *you* ship, and what did each one cost? There is no single right answer — that's the whole point.

### Checkpoint A1 — the summary table

Running the experiment prints a summary table before writing the report. With offline hash embeddings (`TECHCORP_OFFLINE=true`), yours must match this in **structure** (chunk counts and duplicate rates are deterministic; hit-rates measure word overlap here, not semantics):

```text
NOTICE: using offline hash embeddings — the hit-rates below measure word overlap, NOT semantics. Re-run without TECHCORP_OFFLINE for real numbers.
Embedding model: hash-embedding-384d
Corpus: 13 documents; questions: 15

Running config 'small-fixed' ...
Running config 'medium-fixed' ...
Running config 'paragraph' ...

Config         Chunks  Avg chars  Hit-rate  Dup rate
small-fixed       155        283      87%     0.1%
medium-fixed       63        709      87%    12.0%
paragraph          41        966      87%     0.0%

Report written to .../artifacts/chunking_report.md
```

The three numbers to internalize: smaller chunks ⇒ **more** chunks (`155` vs `41`); `medium-fixed`'s 100-character overlap on 800-character chunks duplicates **~12%** of shingles, while `paragraph` (no overlap, respects structure) duplicates **~0%**; and `small-fixed`'s 30-character overlap barely registers (`0.1%`) because it's smaller than the 8-word measuring window.

### Checkpoint A2 — the report artifact

`artifacts/chunking_report.md` exists and opens with a heading, states the embedding client and the "word overlap" caveat, carries the comparison table (all three config names present), and lists the failure cases per config. Offline, the recurring misses to expect are `eval-012` ("staff time-off guidelines") and `eval-013` ("sync my work files to my own Dropbox account") — questions whose wording shares few literal words with their source doc, which is exactly the paraphrase gap hash embeddings can't cross.

### Checkpoint A3 — tests green

```bash
uv run pytest course/07_vector_database -q
```

While `TODO` markers remain in `starter/chunking_experiment.py`, `test_my_work.py` skips — that skip disappearing is your progress bar. `test_solution.py` always runs (offline, temp dirs, no writes to the repo's `artifacts/` or `.chroma/`).

---

## Lab B — The ChromaDB tour

**Scenario.** Before the later modules trust the persistent store, you should drive every part of it once. There is no starter file for this lab — create a scratch file (git-ignored), e.g. `course/07_vector_database/chroma_tour.py`, and work the seven steps. This is exploration, not a graded gate; the tests in `test_solution.py` assert the same `VectorStore` behaviors, so consult them if a step surprises you.

The store lives in `src/techcorp_agent/vectorstore/chroma_store.py`. Read it first — especially the `score = 1.0 - float(distance)` line (Chroma returns cosine *distance*; the wrapper converts so higher = closer everywhere in the course) and the constructor's `embedding_model` guard.

Start your scratch file with:

```python
from pathlib import Path
from techcorp_agent.config import get_settings
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.vectorstore.chroma_store import VectorStore

persist_dir = Path("course/07_vector_database/.tour_chroma")  # a throwaway dir
embeddings = get_embedding_client()  # or HashEmbeddingClient() offline
documents = load_documents(get_settings().data_dir)
chunks = [
    c
    for d in documents
    for c in chunk_document(d, strategy="paragraph", chunk_size=1200, overlap=0)
]
```

### Step 1 — Create a persistent collection

Construct `VectorStore(embeddings, persist_dir=persist_dir, collection_name="tour")`. Because the client is a `chromadb.PersistentClient`, the directory is written to disk immediately.

### Step 2 — Add chunks

`store.add_chunks(chunks)` returns the number written. With the paragraph config it's **41**.

### Step 3 — Store source metadata (already handled — confirm)

`add_chunks` writes `doc_id`, `doc_title`, `category`, and `index` alongside each vector (read it in `chroma_store.py`). You'll use that metadata in steps 5 and 6.

### Step 4 — Query semantically

`store.query("vacation days", top_k=2)` returns `RetrievedChunk`s sorted best-first, each with a `.score` (already converted to similarity). Print `score`, `chunk.doc_id`, `chunk.category` for each.

### Step 5 — Filter by category

`store.query("how long is data kept", top_k=2, category="privacy")` restricts ranking to `privacy` chunks. The corpus categories are `employee_handbook`, `privacy`, and `product_support`. A filter is a **guarantee** (no other category can appear); a score is only a tendency.

### Step 6 — Delete and rebuild safely

`store.reset()` deletes and recreates **this collection only** — never the whole persist directory, which may hold other collections. Confirm `store.count() == 0` after, and that `store.query("vacation", top_k=2) == []`. (This is exactly what `scripts/build_index.py` does before re-indexing.) Re-add the chunks to continue.

### Step 7 — Prove persistence across a restart

Persistence only counts if it survives a *new process*. `del store` in your script proves nothing (same process). Do it properly: index in one command, then reopen in a **separate** command:

```bash
# Command 1 — index and exit (write a tiny script or a -c one-liner that does steps 1-2)
# Command 2 — reopen the SAME persist_dir + collection_name and print the count:
uv run python -c "
from pathlib import Path
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.vectorstore.chroma_store import VectorStore
s = VectorStore(get_embedding_client(), persist_dir=Path('course/07_vector_database/.tour_chroma'), collection_name='tour')
print('count after reopen:', s.count())
"
```

The count is still there — the vectors were on disk the whole time. Clean up with `rm -rf course/07_vector_database/.tour_chroma` when done.

### Checkpoint B — observable output

With offline hash embeddings, steps 2, 4, 5, and 6 produce output shaped like this (scores are word-overlap here; real embeddings rank the same documents higher and more coherently):

```text
added 41
count 41
# query "vacation days":
0.419 hr-vacation employee_handbook
0.221 hr-vacation employee_handbook
# query "how long is data kept" filtered category="privacy":
0.255 privacy-gdpr privacy
0.223 privacy-retention privacy
after reset count 0
```

The exact scores shift with the model; what must hold is: `add_chunks` reports 41, results come back sorted descending, and every result of the filtered query is in the `privacy` category.

---

## An honest note on results — when the numbers mean semantics

These are real observations from running the solution against this corpus:

- **All three configs hit-rate at 87% with hash embeddings** — but that number measures *word overlap*, not meaning, so treat it as a plumbing check, not an evaluation. Re-run without `TECHCORP_OFFLINE` for numbers that reflect real semantic retrieval; the spread between configurations only becomes meaningful with the real model.
- **Chunk counts and duplicate rates are structural, not semantic** — they're identical whichever client runs, because they come from the chunker, not the embeddings. `medium-fixed`'s ~12% duplicate rate is a genuine, model-independent cost of its 100-character overlap.
- **The recurring offline failures (`eval-012`, `eval-013`) are the paraphrase gap** — "staff time-off guidelines" shares almost no literal words with the vacation policy; only real embeddings bridge that. If your report shows these misses and the model line says `hash-embedding-384d`, that's expected, not a bug.

## Debugging hints

- **`ValueError: Collection '...' was indexed with '...' but you are querying with '...'`** → the embedding-model guard fired: you opened an existing collection with a different client (e.g. real model after an offline run left `hash-embedding-384d` on disk). Rebuild with `reset()` or delete the persist dir; never mix models in one collection.
- **Chroma error on the collection name** → hyphens aren't allowed in collection names. Use `f"chunking_{name}".replace("-", "_")`.
- **Hit-rate is `0%` everywhere** → you compared `expected_sources` (doc ids) against something other than `item.chunk.doc_id`, or forgot to `add_chunks` before querying. Print one `retrieved` list and eyeball the `doc_id`s.
- **`duplicate_rate` above 1.0 or counting within-chunk repeats** → you used a list instead of a **set** of shingles per chunk, so a phrase repeated inside one chunk inflated the count.
- **Report written but tests still skip** → a literal `TODO` string remains in `starter/chunking_experiment.py`; delete resolved marker comments.
- **Second run's numbers doubled / collection not clean** → you skipped the `store.reset()` before `add_chunks`, so a re-run upserted on top of the previous run.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repository root with `uv run`, not bare `python` from inside the module directory.

## Stretch exercise

Add a fourth configuration to `CONFIGS` — for example `{"name": "large-fixed", "strategy": "fixed", "chunk_size": 1500, "overlap": 300}` — and re-run with the **real** model (no `TECHCORP_OFFLINE`). Watch its duplicate rate climb (300/1500 overlap duplicates far more than medium's 100/800) and check whether the extra context helps or hurts hit-rate. Then, zero-code: open `artifacts/chunking_report.md`, pick the config you would ship for a RAG prompt that pays per token in Module 08, and write one sentence justifying it against a different config — that argument, backed by the table, is the deliverable this module was really about.

When everything passes, go through [checklist.md](checklist.md).
