"""A read-only document-search tool wrapping the TechCorp vector store.

This is the same retrieval the RAG pipeline uses (Module 08), exposed as a
*tool* so the router can hand policy/warranty/privacy questions to it. It is
read-only: it queries the index and never writes to it.
"""

from pydantic import BaseModel, Field

from techcorp_agent.tools.base import ToolResult, ToolSpec
from techcorp_agent.vectorstore.chroma_store import VectorStore

SEARCH_DOCS_TOOL_NAME = "document_search"


class DocumentSearchArgs(BaseModel):
    query: str = Field(..., description="Natural-language question about TechCorp policy or docs.")
    top_k: int = Field(4, ge=1, le=10, description="How many chunks to return.")


def format_chunks(retrieved: list) -> str:
    """Render top chunks with their doc id and similarity score, best first."""
    lines: list[str] = []
    for item in retrieved:
        chunk = item.chunk
        snippet = " ".join(chunk.text.split())
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        lines.append(f"[{chunk.doc_id}] (score {item.score:.2f}) {snippet}")
    return "\n".join(lines)


class DocumentSearchTool:
    """Wraps a ``VectorStore`` so it can be invoked as a tool.

    Holding the store on the instance keeps the tool ``func`` a plain
    ``args -> ToolResult`` callable while still reaching the (stateful) index.
    """

    def __init__(self, store: VectorStore):
        self._store = store

    def run(self, args: DocumentSearchArgs) -> ToolResult:
        retrieved = self._store.query(args.query, top_k=args.top_k)
        if not retrieved:
            return ToolResult.failure(
                SEARCH_DOCS_TOOL_NAME,
                "No TechCorp documents matched that query — the index may be empty "
                "or the topic is out of scope.",
            )
        return ToolResult.success(SEARCH_DOCS_TOOL_NAME, format_chunks(retrieved))

    def as_tool(self) -> ToolSpec:
        return ToolSpec(
            name=SEARCH_DOCS_TOOL_NAME,
            description=(
                "Search TechCorp's internal documents (HR policies, returns, "
                "warranty, privacy, escalation). Use for company-specific policy "
                "or 'how does TechCorp handle...' questions. Do NOT use for math "
                "or for a specific order's status."
            ),
            args_schema=DocumentSearchArgs,
            func=self.run,
        )


def make_document_search_tool(store: VectorStore) -> ToolSpec:
    """Build the document-search tool bound to ``store``."""
    return DocumentSearchTool(store).as_tool()
