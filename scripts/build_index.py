"""Build (or rebuild) the TechCorp vector index from the document corpus.

Run:  make index          (rebuild from scratch: make clean-index && make index)

Uses the configured embedding client: real sentence-transformers by default,
hash embeddings when TECHCORP_OFFLINE=true.
"""

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.vectorstore.chroma_store import VectorStore


def main() -> int:
    settings = get_settings()
    documents = load_documents(settings.data_dir)
    if not documents:
        print(f"No documents found under {settings.data_dir} — nothing to index.")
        return 1

    embeddings = get_embedding_client(settings)
    print(f"Embedding model: {embeddings.model_name}")

    store = VectorStore(embeddings, persist_dir=settings.chroma_dir)
    store.reset()

    total_chunks = 0
    for document in documents:
        chunks = chunk_document(document, strategy="paragraph", chunk_size=800)
        total_chunks += store.add_chunks(chunks)
        print(f"  indexed {document.id:<28} ({len(chunks)} chunks)")

    print(f"\nDone: {len(documents)} documents → {total_chunks} chunks in {settings.chroma_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
