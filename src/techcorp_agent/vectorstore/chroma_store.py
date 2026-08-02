"""Persistent vector store on ChromaDB.

Scores: Chroma returns cosine *distance* (0 = identical); this wrapper converts
to similarity `1 - distance` so that, everywhere in the course, higher = closer.

The collection records which embedding model built it and refuses queries from
a different one — the most common silent retrieval bug (Module 07).
"""

from pathlib import Path

import chromadb

from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.schemas import Chunk, RetrievedChunk

DEFAULT_COLLECTION = "techcorp_docs"


class VectorStore:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        persist_dir: Path,
        collection_name: str = DEFAULT_COLLECTION,
    ):
        self._embeddings = embedding_client
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_client.model_name,
            },
        )
        indexed_with = (self._collection.metadata or {}).get("embedding_model")
        if indexed_with and indexed_with != embedding_client.model_name:
            raise ValueError(
                f"Collection '{collection_name}' was indexed with '{indexed_with}' but "
                f"you are querying with '{embedding_client.model_name}'. Vectors from "
                "different models are not comparable — rebuild the index "
                "(make clean-index && make index) or switch back to the original model."
            )

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """Embed and upsert chunks. Returns how many were written."""
        if not chunks:
            return 0
        vectors = self._embeddings.embed([chunk.text for chunk in chunks])
        self._collection.upsert(
            ids=[chunk.id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "doc_id": chunk.doc_id,
                    "doc_title": chunk.doc_title,
                    "category": chunk.category,
                    "index": chunk.index,
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def query(
        self,
        text: str,
        top_k: int = 4,
        category: str | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """Semantic search. Returns chunks sorted by similarity, best first."""
        if self.count() == 0:
            return []
        [query_vector] = self._embeddings.embed([text])
        result = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, self.count()),
            where={"category": category} if category else None,
            include=["documents", "metadatas", "distances"],
        )
        retrieved: list[RetrievedChunk] = []
        for chunk_id, document, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=True,
        ):
            score = 1.0 - float(distance)
            if min_score is not None and score < min_score:
                continue
            retrieved.append(
                RetrievedChunk(
                    chunk=Chunk(
                        id=chunk_id,
                        doc_id=str(metadata["doc_id"]),
                        doc_title=str(metadata["doc_title"]),
                        category=str(metadata["category"]),
                        index=int(metadata["index"]),
                        text=document,
                    ),
                    score=score,
                )
            )
        return retrieved

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate this collection (safe: only touches this collection)."""
        name = self._collection.name
        metadata = dict(self._collection.metadata or {})
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(name=name, metadata=metadata)
