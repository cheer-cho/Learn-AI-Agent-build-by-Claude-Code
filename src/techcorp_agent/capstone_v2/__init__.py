"""TechCorp Knowledge Agent **v2** — the hero-capstone package (Module 22).

v2 is the production rollout Act 3 of the story demands. It *integrates the whole
course* into one deployable agent and reimplements none of it — every capability
is a package built in an earlier module, composed here:

- :mod:`techcorp_agent.capstone_v2.state`      — :class:`V2State`, the extended
  LangGraph state (memory ``messages`` + trace reducers).
- :mod:`techcorp_agent.capstone_v2.graph`      — :func:`build_v2_graph`, the
  integrated graph: safety boundary → supervisor routing → advanced-RAG
  specialists / MCP orders / approval-gated ticket / general → validated output,
  all checkpointed for multi-turn memory and resumable approval.
- :mod:`techcorp_agent.capstone_v2.retrieval`  — category-scoped hybrid+rerank
  retrievers (Module 17) for the policy/support routes.
- :mod:`techcorp_agent.capstone_v2.checkpoint` — the memory/approval checkpointer.
- :mod:`techcorp_agent.capstone_v2.app_service` — :func:`build_v2_app`, the
  FastAPI service (reuses Module 21's patterns).
- :mod:`techcorp_agent.capstone_v2.cli`        — the offline REPL / one-shot CLI.
- :mod:`techcorp_agent.capstone_v2.report`     — regenerates the v2 eval report.

The small piece of glue that belongs to v2 is :func:`build_v2_store`: it indexes
the real ``data/`` corpus into a hash-embedding vector store so the whole agent —
CLI, API, tests, report — runs end to end with no API key and no network.
"""

from __future__ import annotations

from pathlib import Path

from techcorp_agent.capstone_v2.graph import build_v2_graph
from techcorp_agent.capstone_v2.state import V2State
from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.vectorstore.chroma_store import VectorStore

__all__ = ["V2State", "build_v2_graph", "build_v2_store"]

# A distinct collection so v2's offline index never collides with the v1 index or
# a real sentence-transformers index a learner may have built for other modules.
_V2_COLLECTION = "capstone_v2"


def build_v2_store(
    persist_dir: Path | None = None,
    dimension: int = 256,
    data_dir: Path | None = None,
) -> VectorStore:
    """Build (indexing once) a hash-embedding store over the real ``data/`` corpus.

    Deterministic and offline — the same call powers the CLI, the API, the tests,
    and the report without a network or an API key. The corpus is indexed only if
    the collection is empty, so repeated runs are cheap.

    Args:
        persist_dir: where Chroma persists; defaults to ``<.chroma>/capstone_v2``.
        dimension: hash-embedding dimensionality (256 is a good offline default).
        data_dir: corpus root; defaults to the project ``data/`` directory.
    """
    settings = get_settings()
    persist_dir = persist_dir or (settings.chroma_dir / _V2_COLLECTION)
    data_dir = data_dir or settings.data_dir
    store = VectorStore(
        HashEmbeddingClient(dimension=dimension),
        persist_dir=persist_dir,
        collection_name=_V2_COLLECTION,
    )
    if store.count() == 0:
        for doc in load_documents(data_dir):
            store.add_chunks(chunk_document(doc))
    return store
