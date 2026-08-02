# Module 06 Lab — TechCorp Semantic Search, No Black Boxes

## Scenario

TechCorp's support and HR teams keep answering the same questions, and the wiki's keyword search keeps failing them: an employee typing "Can I work from home?" finds nothing useful because the Remote Work Policy says "hybrid" and "office days", not "work from home". Your team lead wants a prototype search engine over the 13 policy documents — and, pointedly, wants it *without* installing a vector database yet: "I want to see every step in one file before we adopt infrastructure." You will build exactly that, then run the same four evaluation questions through semantic search and plain keyword search and report where each one wins.

You will implement `starter/search_engine.py`. The shared library already provides document loading, chunking, embedding clients, and `cosine_similarity` — your job is the search engine itself.

## Learning objectives

By the end you can:

- Build the full index-then-search pipeline: load → chunk → embed → store → embed query → rank → top-k
- Return search results with metadata (document title), text, and a similarity score
- Apply a score threshold and explain what it protects against
- Implement a keyword-overlap baseline and articulate, with evidence, when semantic search beats it and when it doesn't
- Recognize the query type that *no* search can answer (nothing relevant exists) and what to do about it

## Setup

```bash
uv sync                      # if you haven't already
```

Run commands from the repository root.

- **Run your work:** `uv run python course/06_semantic_search/starter/search_engine.py`
- **Test:** `uv run pytest course/06_semantic_search -q`
- **Peek at the target behavior anytime:** `uv run python course/06_semantic_search/solution/search_engine.py` (but attempt each task before reading solution code)

First run note: the real embedding model (`all-MiniLM-L6-v2`, ~90 MB) downloads once, then is cached. If the download is impossible, `build_search_engine` (already wired) falls back to the offline `HashEmbeddingClient` with a printed notice — everything still runs, but see "An honest note on results" below for what you lose.

## Tasks

Open `starter/search_engine.py`. Tasks 1 and 9 are already wired in `main()` — read them; tasks 2–8 are your TODOs.

### Task 1 — Load the TechCorp documents (already wired — verify)

`main()` calls `load_documents(settings.data_dir)`. Run the starter now: it should print `loaded 13 documents ...` and then stop at the first `NotImplementedError`. Open `src/techcorp_agent/documents/loader.py` and answer for yourself: why 13 and not 15? (Hint: `data/security_lab/` — and it must *stay* out of every index until Module 20.)

### Task 2 — Chunk the documents

In `SearchEngine.index`, split every document with `chunk_document(document)` and collect all resulting `Chunk` objects into one flat list. Each chunk already carries `doc_id`, `doc_title`, `category`, and `index` — that metadata is what makes results attributable later.

### Task 3 — Embed and store all chunks

Still in `index`: embed **all chunk texts in a single batch call** — `self.embedding_client.embed([...])` takes a list for a reason; one model call for 67 chunks is dramatically faster than 67 calls. Append chunks to `self.chunks` and vectors to `self.vectors`, keeping the two lists aligned (position i of one must correspond to position i of the other — that pairing *is* your index). Return the number of chunks added.

### Task 4 — Embed the query

In `SearchEngine.search`: embed the query text with the **same** client. `embed([query])` returns a one-element list — unpack it. (Different model for query vs corpus = meaningless comparisons. Same client object = guaranteed same model.)

### Task 5 — Rank chunks by cosine similarity

Score every stored chunk: `cosine_similarity(query_vector, chunk_vector)` for each pair from `zip(self.chunks, self.vectors)`. Wrap each as `RetrievedChunk(chunk=chunk, score=score)`.

### Task 6 — Return the top-k

Sort the scored results best-first and return only the first `top_k`. This list — title, text, score — is exactly what Module 08 will paste into an LLM prompt as context.

### Task 7 — Apply a score threshold

Before truncating to `top_k`: if `min_score` is not `None`, drop every result scoring below it. Returning an **empty list must be possible** — "nothing relevant found" is the honest answer for some queries, and you are about to meet one.

### Task 8 — Keyword search, the baseline

Implement `keyword_search`: tokenize the query with the provided `tokenize()` (lowercases, strips stopwords), score each chunk as `len(query_words & chunk_words) / len(query_words)`, skip zero-overlap chunks, sort, return top-k as `RetrievedChunk`s. Deliberately primitive — that's the point of a baseline.

### Task 9 — Run the evaluation queries and compare (already wired — analyze)

`main()` runs all four `TEST_QUERIES` through both search methods and prints title, score, and a preview for each result. Your job here is analysis, not code: run it and, for each query, write one sentence (really — say it out loud or into a scratch file) on which method won and why. Compare against the observations below.

## Checkpoints

### Checkpoint A — after Tasks 2-3

Add a temporary `print` or just run the tests: indexing must report 13 documents → ~67 chunks (exact count depends on chunking defaults — anything between 60 and 75 means it's working; 13 means you embedded whole documents, not chunks).

### Checkpoint B — after Tasks 4-6

`uv run python course/06_semantic_search/starter/search_engine.py` prints ranked semantic results for all four queries. With the real model, "Can I wear jeans at the office?" must show **Dress Code Policy** on top with a score near 0.67, and every list must be sorted descending.

### Checkpoint C — after Tasks 7-8 (full run)

Expected output with real embeddings (yours must match in structure; scores to within a few thousandths):

```text
model:  sentence-transformers/all-MiniLM-L6-v2
corpus: 13 documents → 67 chunks in memory

=== 'Can I work from home?' ===
  semantic:
    1. [0.432] International Remote Work Policy — # International Remote Work Policy ## Purpose Employees...
    2. [0.430] Remote Work Policy — TechCorp provides a **home office stipend of $500 per year**...
    3. [0.367] International Remote Work Policy — Any arrangement exceeding 30 calendar days in a year...
  keyword :
    1. [1.000] Dress Code Policy — TechCorp does **not maintain a dress code for remote work**...
    2. [1.000] International Remote Work Policy — 1. **Manager approval**, recorded in the HR portal...
    3. [1.000] Remote Work Policy — TechCorp provides a **home office stipend of $500 per year**...

=== 'How do I recover my account?' ===
  semantic:
    1. [0.382] Data Retention Policy — Account profile data — name, email, addresses, preferences...
    2. [0.343] Data Deletion Process — - The account is immediately deactivated and removed...
    3. [0.325] Data Deletion Process — # Data Deletion Process ## Purpose This document describes...
  keyword :
    1. [0.500] Equipment Use Policy — **Company data must never be stored in personal cloud...
    ...

=== 'Can I wear jeans at the office?' ===
  semantic:
    1. [0.672] Dress Code Policy — The following are not appropriate in any TechCorp workplace...
    ...

=== 'What happens when a product arrives broken?' ===
  semantic:
    1. [0.551] Refunds for Damaged Products — # Refunds for Damaged Products ## Scope This policy covers...
    ...
```

### Checkpoint D — tests green

```bash
uv run pytest course/06_semantic_search -q
```

While TODO markers remain, `test_my_work.py` skips — that skip disappearing is your progress bar. The tests index the real corpus with the deterministic hash client, so they are fast, offline, and reproducible.

## An honest note on results — which queries need real embeddings

These are real observations from running the solution against this corpus (do the same run yourself), not marketing:

- **"Can I wear jeans at the office?"** and **"What happens when a product arrives broken?"** work well with *both* methods — but only because the corpus happens to contain the literal words "jeans" and "broken". Keyword search is genuinely fine when the user speaks the document's language.
- **"Can I work from home?"** is the semantic showcase — with a subtlety. "work" and "home" are common words, so keyword search doesn't return nothing: it returns a **three-way tie at 1.000** (any chunk containing both words maxes out), and a tie means the ranking is arbitrary — the top keyword "hit" is the *Dress Code* Policy's remote-work aside. Real embeddings instead rank remote-work policy content coherently at 0.37–0.43. Keyword failure here isn't silence; it's confident noise.
- **"How do I recover my account?"** works with *neither* — because **no account-recovery document exists in this corpus**. The word "recover" appears in no document at all; keyword search matches only the generic word "account" (equipment and privacy chunks, wrong topic, 0.500), and semantic search returns the nearest wrong neighborhood — account *deletion* — at low scores (0.33–0.38, versus 0.55–0.67 for genuinely on-topic hits on other queries). This is the query that justifies Task 7: with `min_score=0.45`, semantic search correctly returns *nothing*.
- **With the hash fallback** (`TECHCORP_OFFLINE=true`), "semantic" results degrade below the keyword baseline: the jeans query's top hash hit is the Remote Work Policy and the broken-product query's is the International Remote Work Policy — filler-word hash collisions outvote the one meaningful word. If you see nonsense rankings and the model line says `hash-embedding-384d`, that is why. The tests are written around this honestly: they assert the strong claims through `keyword_search` and only overlap-guaranteed facts through hash-based `search` (read the comment at the top of `tests/test_solution.py`).

## Debugging hints

- **`ValueError: Vector dimensions differ`** → you embedded query and corpus with different clients (or re-created the client between index and search). One `SearchEngine`, one `embedding_client`, both phases.
- **Every score is ~0.99** → you embedded the same text list twice (e.g. queries instead of chunk texts), or compared each vector with itself. Print `self.chunks[0].text[:60]` and the query — they should differ.
- **`zip()` results look shuffled / scores attach to wrong chunks** → `self.chunks` and `self.vectors` fell out of alignment; append both in the same order in `index`, never sort one without the other. (`zip(..., strict=True)` catches length drift — use it.)
- **13 chunks total** → you skipped `chunk_document` and embedded whole documents. Checkpoint A catches this.
- **Indexing takes minutes** → you called `embed()` once per chunk inside a loop. Batch it: one call, list in, list out.
- **`min_score` returns k results anyway** → you truncated to `top_k` *before* filtering, or filtered with `>` on the boundary (use `>=`).
- **`test_my_work.py` still skipping after you finished** → a literal `TODO` string remains somewhere in `starter/search_engine.py` — delete resolved marker comments.
- **First run downloads slowly / hangs on `Loading weights`** → the one-time model download. Subsequent runs load from cache in ~2 s. No network at all? The fallback notice appears and hash results kick in.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repository root with `uv run`, not bare `python` from inside the module directory.

## Stretch exercise — category filter via metadata

An HR chatbot shouldn't retrieve GDPR chunks. Add a `category: str | None = None` parameter to `search` that, when set, only scores chunks whose `chunk.category` matches (filter *before* ranking, so irrelevant categories never compete). Then compare:

```python
engine.search("How long are records kept?", top_k=3)
engine.search("How long are records kept?", top_k=3, category="privacy")
engine.search("How long are records kept?", top_k=3, category="employee_handbook")
```

The unfiltered query straddles privacy retention and HR equipment records; the filtered ones commit. Notice you implemented "metadata filtering" — a headline vector-database feature — in one `if`. The solution includes this parameter if you want to compare. Second stretch, zero code: rephrase "Can I work from home?" three ways ("remote work rules?", "do I have to come to the office?", "wfh policy") and watch the top-3 reshuffle — that instability is why evaluation queries exist.

When everything passes, go through [checklist.md](checklist.md).
