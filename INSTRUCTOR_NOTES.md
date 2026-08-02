# Instructor Notes

Design decisions behind this course, for anyone maintaining or teaching it.

## Architecture principles

- **One continuous system.** Every module extends `src/techcorp_agent/` or the
  capstone apps; nothing is built and thrown away. If a module needs a new
  capability, it lands in the shared package with tests.
- **Explain before abstracting.** Raw SDK (02) before LangChain (03); manual
  similarity (05) before the vector store (07); single agent (11) before
  multi-agent (18). Learners should always know what the framework is saving them.
- **Offline-first.** `Settings.offline` selects deterministic mocks
  (`MockLLMClient`, `HashEmbeddingClient`). The default pytest run must never
  require credits; live tests carry the `live` marker.
- **Trade-offs, not advocacy.** No tool is presented as automatically superior;
  every `concepts.md` has a trade-offs section, and Module 17/18 upgrades must
  be *measured* against the Module 09 baseline before being claimed as wins.

## Dataset invariants (do not break)

Evaluation examples and module tests assert on specific facts in `data/`
(e.g. jeans allowed at HQ, 30-day international remote limit, TC-1234
in_transit, TC-9999 intentionally nonexistent). If you edit a policy document,
run the full suite and update `data/evaluation/eval_dataset.json` together.
`data/security_lab/` contains planted prompt-injection docs for Module 20 and
must stay out of the main index (`load_documents` excludes it by default).

## Version pinning

`requirements.lock` is exported from `uv.lock` (`uv export --format
requirements-txt --no-hashes -o requirements.lock`). Upgrading LangChain /
LangGraph / MCP majors: re-run the whole suite; module content quotes real
APIs and may need text updates too.

## Grading / self-assessment

Each module's `checklist.md` is the acceptance gate; rubrics for prompts,
retrieval, RAG answers, and routing live in the relevant modules' concepts
files. Progress tracking is the learner's own `ROADMAP.html` checkboxes.
