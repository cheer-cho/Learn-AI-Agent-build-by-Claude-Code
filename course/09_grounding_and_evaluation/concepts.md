# Module 09 Concepts — Grounding, Attribution, and Evaluation

In Module 08 you built a RAG pipeline that retrieves TechCorp documents, stuffs them into the prompt, and asks the model to answer *only* from that context, ending with a `SOURCES:` line or the abstention text. It ran. It looked convincing. That is exactly the danger: a RAG system that looks convincing and is quietly wrong is worse than one that obviously fails, because nobody catches it. This module replaces "it looks fine" with a number — and teaches you to read that number honestly.

## 1. RAG still fails — seven ways, with a TechCorp face on each

"We use RAG so it won't hallucinate" is a half-truth. Retrieval reduces one failure mode by introducing several new ones. Every one of these is a real thing that goes wrong in a real corpus:

| # | Failure | What breaks | TechCorp example |
|---|---|---|---|
| 1 | **Correct document not indexed** | The evidence exists but never entered the vector store | The `hr-international-remote` policy PDF was never added to `data/`, so no query can ever find the 30-day rule. |
| 2 | **Poorly formed chunks** | Chunking split or merged text so the answer is no longer contiguous | The vacation *carry-over* sentence got cut from the "25 days per year" sentence, so a chunk answers half the question. |
| 3 | **Wrong evidence retrieved** | Top-k returns plausible-but-irrelevant chunks | "How long do I have?" pulls the *warranty* window instead of the *return* window — both mention "days". |
| 4 | **Miscalibrated similarity threshold** | `min_score` is set so retrieval fires (or abstains) at the wrong point | Threshold too low: the Moon-office question retrieves loosely-related HR text instead of abstaining. Too high: a valid paraphrase falls below the cutoff and gets nothing. |
| 5 | **Model ignores the context** | The evidence was retrieved and supplied, but the model answered from its own priors | The refund chunk says "30 days"; the model confidently writes "90 days" from generic training data. |
| 6 | **Conflicting sources** | Two retrieved chunks disagree and the model picks one silently | An old handbook chunk says "20 vacation days", the current one says "25" — the model averages or guesses. |
| 7 | **Unsupported answer** | The answer contains claims no retrieved chunk backs | The reply invents a "gym membership reimbursement" that appears in no TechCorp document. |

Failures 1–4 are **retrieval** problems. Failures 5–7 are **generation** problems. That split is the whole point of the module.

## 2. The central split: retrieval evaluation vs generation evaluation

You cannot fix what you cannot localize. If the assistant gives a bad answer, there are two very different root causes, and they need two very different fixes:

- **Retrieval evaluation** — *Did the system fetch the required evidence?* If the right chunk was never retrieved, no amount of prompt-tuning saves you; you fix chunking, embeddings, top-k, or the threshold. This is measured **before** the LLM runs, against the retrieved chunk ids.
- **Generation evaluation** — *Did the answer use that evidence faithfully?* Given that the right chunk *was* retrieved, did the model cite it, include the facts, and abstain when it should? If retrieval is fine but the answer is wrong, you fix the prompt or the model. This is measured **on the returned answer**.

Measuring only end-to-end ("was the final answer good?") tells you the system is broken but not *where*. Splitting the score turns a shrug into a work ticket assigned to the right layer.

## 3. The metrics you implement (real names, real semantics)

These are the four functions in `src/techcorp_agent/evaluation/metrics.py`. Your lab versions must match them exactly — the tests pin the same boundary cases against both.

### `hit_rate_at_k(expected_sources, retrieved_doc_ids, k)` — RETRIEVAL

Returns `1.0` if any expected document id appears among the **top-k** retrieved doc ids (in rank order, best first), else `0.0`. This is the retrieval question in one number: was the evidence in reach of the generator at all?

- `retrieved_doc_ids` is the chunk-level list, so duplicates from a multi-chunk document are fine and count toward `k`.
- **Vacuous case:** empty `expected_sources` returns `1.0`. Unanswerable/ambiguous examples require *no* evidence, so retrieval cannot have missed any — those examples are judged by `abstention_correct`, not this metric. Read a category's hit rate with that in mind (an `unanswerable` hit rate of 100% means "correctly required nothing", not "retrieved brilliantly").

### `source_accuracy(expected_sources, cited_sources)` — GENERATION

Citation **precision**: the fraction of the answer's cited sources that were expected. Boundary rules encode a policy, not just arithmetic:

- both empty → `1.0` (a correct abstention cites nothing, and nothing needed citing);
- nothing cited while sources *were* expected → `0.0` (a grounded answer must cite its evidence — a missing citation is a failure, not a free pass);
- citations present but none expected → `0.0` (citing sources for an unanswerable question means the system pretended to have evidence).

### `fact_coverage(expected_facts, answer_text)` — GENERATION

The fraction of expected fact strings that appear, **case-insensitively as substrings**, in the answer. This is a **deterministic approximation of answer completeness** — and you must understand its blindness: it only credits a fact when the answer contains the fact string *verbatim* (ignoring case). A correct paraphrase — "you get twenty-five days off" for the expected fact `"25 vacation days per year"` — scores `0`. That is the price of a check that is free, instant, and never lies about what it matched. Treat the number as a **floor**, not a ceiling. Empty `expected_facts` → `1.0` (nothing was required). Module 19 layers a model-based evaluator on top to catch the paraphrases this cannot.

### `abstention_correct(should_abstain, abstained)` — GENERATION

`True` exactly when the two flags agree. Both failure directions matter and are scored symmetrically: answering an unanswerable question is a hallucination risk; abstaining on an answerable one makes the assistant useless. This is the metric that judges the categories where `hit_rate_at_k` is vacuous.

> The instructions also list an **unsupported-claim count** as a goal. In this deterministic harness that concern is covered structurally rather than by a separate counter: `source_accuracy` penalizes citations that were not expected, and `abstention_correct` penalizes answering when the system should have stayed silent — together they flag the "answer contains claims no source backs" failure (#7). A dedicated unsupported-claim detector needs semantic judgment and arrives with the model-based evaluator in Module 19.

## 4. Deterministic checks vs model-based evaluators

There are two families of evaluator:

- **Deterministic checks** — plain string/set operations: substring match, set membership, boolean equality. Cheap, instant, repeatable to the bit, and *honest about their own blindness*. All four metrics above are deterministic. Their weakness is literalism: they cannot see a paraphrase or judge tone.
- **Model-based evaluators ("LLM as judge")** — an LLM scores the answer for faithfulness, relevance, or completeness. They see paraphrases and nuance the substring check misses. Their weakness: they cost money, they are non-deterministic, and *they can hallucinate the grade* — the same failure you are trying to measure, now in your ruler.

The course spec is strict about this and so is `metrics.py`'s own docstring: **model-based evaluation must never be the only validation method.** A deterministic baseline gates every evaluation in this course; a model-based evaluator (Module 19) may be layered *on top*, never *instead*. A ruler you cannot trust to be the same length twice is not a ruler.

## 5. The report and its run context

The deliverable is `artifacts/evaluation_report.md` (written by `write_report`). Its most important section is not the numbers — it is the **run context**: which embedding client and which LLM produced them. A hit rate of 88% from hash embeddings and the mock LLM means something completely different from 88% with real semantic embeddings and a real model. Numbers without their run context are worse than no numbers, because they invite false comparison. This is why later modules (17 for retrieval upgrades, 19 for observability) re-run the *same* harness and diff against the Module 09 baseline — same dataset, same metrics, context recorded each time.

## Common misconceptions

- **"RAG means no hallucination."** RAG changes the *shape* of the failures (Section 1), it does not remove them. Failure #5 is the model ignoring perfectly good retrieved context.
- **"One end-to-end score tells me if it works."** It tells you *that* it broke, never *where*. Retrieval vs generation is the diagnostic split.
- **"`fact_coverage` measures whether the answer is correct."** No — it measures whether specific strings appear. A right paraphrase scores 0; a wrong answer that happens to contain the substring scores 1. It is a floor.
- **"A high `unanswerable` hit rate means retrieval is good there."** It is vacuously 1.0 — no evidence was required. That category is really judged by abstention accuracy.
- **"The LLM judge is more accurate, so use it alone."** It is non-deterministic and can hallucinate the grade. Deterministic checks stay as the required baseline; the judge is additive.
- **"88% is 88%."** Only within the same run context. Compare numbers only across identical embedding + LLM configurations.

## Trade-offs to internalize

- **Deterministic vs model-based.** Deterministic: free, instant, reproducible, literal (misses paraphrase). Model-based: sees meaning, costs money/latency, and can be wrong. The rule resolves the trade-off: deterministic is mandatory, model-based is optional-on-top.
- **Substring `fact_coverage` vs semantic completeness.** The substring check is a cheap floor you can run on every commit; true completeness needs the Module 19 judge. Cheap-and-honest beats expensive-and-unrun.
- **Threshold calibration (failure #4).** A stricter `min_score` abstains more (safer, but refuses answerable questions); a looser one answers more (helpful, but risks retrieving junk). Evaluation is how you pick the point instead of guessing — you *measure* the trade rather than argue about it.

Next: [lab.md](lab.md) — measure it.
