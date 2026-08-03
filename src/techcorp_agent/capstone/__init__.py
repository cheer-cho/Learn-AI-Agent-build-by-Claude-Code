"""TechCorp Knowledge Agent v1 — the mid-course capstone package.

This package *composes* the shared building blocks from Modules 02-13 into one
runnable agent; it deliberately reimplements none of them. It is the codebase
Modules 15-22 extend (memory, streaming, advanced RAG, guardrails, deployment),
so it is kept small and modular:

- :mod:`techcorp_agent.capstone.state`  — the LangGraph ``AgentState``.
- :mod:`techcorp_agent.capstone.graph`  — ``build_graph`` (router -> route nodes
  -> formatter), reusing the RAG pipeline, the tools router, the local tools, and
  the MCP registry.
- :mod:`techcorp_agent.capstone.cli`    — an offline-capable REPL / one-shot CLI.
- :mod:`techcorp_agent.capstone.report` — regenerates the v1 evaluation report.

The one small piece of *new* glue that belongs to the capstone is
:func:`build_offline_store`: it indexes the real ``data/`` corpus into a hash-
embedding vector store so the whole agent — CLI, tests, report — runs end to end
with no API key and no network.
"""

from __future__ import annotations

from pathlib import Path

from techcorp_agent.capstone.graph import build_graph
from techcorp_agent.capstone.state import AgentState
from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.vectorstore.chroma_store import VectorStore

__all__ = ["AgentState", "build_graph", "build_offline_store"]

# A distinct collection so the capstone's offline index never collides with a
# real sentence-transformers index a learner may have built for other modules.
_CAPSTONE_COLLECTION = "capstone_v1"


def build_offline_store(
    persist_dir: Path | None = None,
    dimension: int = 256,
    data_dir: Path | None = None,
) -> VectorStore:
    """Build (indexing once) a hash-embedding store over the real ``data/`` corpus.

    Deterministic and offline: hash embeddings need no model download, so the
    same call powers the CLI, the tests, and the report without a network or an
    API key. The corpus is indexed only if the collection is empty, so repeated
    runs are cheap.

    Args:
        persist_dir: where Chroma persists; defaults to ``<.chroma>/capstone_v1``.
        dimension: hash-embedding dimensionality (256 is a good offline default).
        data_dir: corpus root; defaults to the project ``data/`` directory.
    """
    settings = get_settings()
    persist_dir = persist_dir or (settings.chroma_dir / _CAPSTONE_COLLECTION)
    data_dir = data_dir or settings.data_dir
    store = VectorStore(
        HashEmbeddingClient(dimension=dimension),
        persist_dir=persist_dir,
        collection_name=_CAPSTONE_COLLECTION,
    )
    if store.count() == 0:
        for doc in load_documents(data_dir):
            store.add_chunks(chunk_document(doc))
    return store
