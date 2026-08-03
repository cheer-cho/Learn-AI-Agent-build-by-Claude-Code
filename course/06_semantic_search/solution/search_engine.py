"""Module 06 solution — an in-memory semantic search engine over the TechCorp corpus.

Every stage of the pipeline is visible in this one file: load → chunk → embed →
store (plain Python lists) → embed query → cosine-rank → top-k. Module 07
replaces the lists with a persistent vector database; nothing else changes.

Run it:
    uv run python course/06_semantic_search/solution/search_engine.py
"""

import re

from techcorp_agent.config import get_settings
from techcorp_agent.documents import chunk_document, load_documents
from techcorp_agent.embeddings import (
    EmbeddingClient,
    HashEmbeddingClient,
    get_embedding_client,
)
from techcorp_agent.schemas import Chunk, Document, RetrievedChunk
from techcorp_agent.similarity import cosine_similarity

# The spec's four evaluation queries. Two share vocabulary with the corpus
# ("jeans", "broken"), one is a pure paraphrase ("work from home" vs the
# Remote Work Policy's "hybrid"/"office days"), and one has no relevant
# document at all ("recover my account") — each stresses a different part
# of the pipeline.
TEST_QUERIES = [
    "Can I work from home?",
    "How do I recover my account?",
    "Can I wear jeans at the office?",
    "What happens when a product arrives broken?",
]

_WORD_RE = re.compile(r"[a-z0-9]+")

# Words so common they carry no signal for keyword matching. Deliberately
# small — real systems use tuned stopword lists or TF-IDF weighting instead.
STOPWORDS = frozenset(
    """
    a an and are at be but by can could do does for from how i in is it its my
    of on or the that this to was what when where which who will with you your
    """.split()
)


def tokenize(text: str) -> set[str]:
    """Lowercased content words of `text` (stopwords removed), as a set."""
    return {word for word in _WORD_RE.findall(text.lower()) if word not in STOPWORDS}


class SearchEngine:
    """In-memory semantic search: chunks and their vectors live in two parallel
    lists, and every query is compared against every stored vector.

    That brute-force scan is O(number of chunks) per query — perfectly fine for
    TechCorp's 13 policy documents, and exactly the cost that motivates the
    vector database in Module 07.
    """

    def __init__(self, embedding_client: EmbeddingClient):
        self.embedding_client = embedding_client
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def index(self, documents: list[Document]) -> int:
        """Chunk and embed `documents`, adding them to the in-memory index.

        Returns the number of chunks added. Embedding happens in one batch —
        one model call for the whole corpus, not one per chunk.
        """
        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        if not chunks:
            return 0
        vectors = self.embedding_client.embed([chunk.text for chunk in chunks])
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float | None = None,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        """Embed `query` and return the `top_k` most similar chunks, best first.

        - `min_score` drops results below the threshold (they are near-misses,
          not answers — see concepts.md on thresholds).
        - `category` restricts the search to chunks whose metadata matches
          (e.g. "employee_handbook") — the stretch exercise.
        """
        [query_vector] = self.embedding_client.embed([query])
        results = [
            RetrievedChunk(chunk=chunk, score=cosine_similarity(query_vector, vector))
            for chunk, vector in zip(self.chunks, self.vectors, strict=True)
            if category is None or chunk.category == category
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        if min_score is not None:
            results = [result for result in results if result.score >= min_score]
        return results[:top_k]

    def keyword_search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        """Baseline for comparison: rank chunks by word overlap with the query.

        Score = |query words ∩ chunk words| / |query words|, stopwords removed.
        No embeddings involved — a chunk that answers the question in different
        words scores exactly 0. Chunks with no overlap are omitted entirely.
        """
        query_words = tokenize(query)
        if not query_words:
            return []
        results = [
            RetrievedChunk(
                chunk=chunk, score=len(query_words & tokenize(chunk.text)) / len(query_words)
            )
            for chunk in self.chunks
            if query_words & tokenize(chunk.text)
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:top_k]


def build_search_engine(documents: list[Document]) -> SearchEngine:
    """Index `documents` with real embeddings, falling back to hash embeddings.

    The sentence-transformers model downloads (~90 MB) on first use; if that
    is impossible (no network, no package), the engine still runs on the
    offline hash client — with a loud notice, because hash embeddings match
    words, not meaning, and the comparison queries behave very differently.
    """
    try:
        engine = SearchEngine(get_embedding_client())
        engine.index(documents)
    except Exception as exc:  # model download / import failure — stay usable offline
        print(
            f"[notice] real embedding model unavailable ({type(exc).__name__}); "
            "falling back to HashEmbeddingClient. Expect keyword-level results only —\n"
            "         paraphrase queries like 'Can I work from home?' will NOT match."
        )
        engine = SearchEngine(HashEmbeddingClient())
        engine.index(documents)
    return engine


def print_results(label: str, results: list[RetrievedChunk]) -> None:
    print(f"  {label}:")
    if not results:
        print("    (no results)")
    for rank, result in enumerate(results, start=1):
        preview = " ".join(result.chunk.text[:100].split())
        print(f"    {rank}. [{result.score:.3f}] {result.chunk.doc_title} — {preview}")


def main() -> int:
    settings = get_settings()
    documents = load_documents(settings.data_dir)  # security_lab excluded by default
    engine = build_search_engine(documents)
    print(f"model:  {engine.embedding_client.model_name}")
    print(f"corpus: {len(documents)} documents → {len(engine.chunks)} chunks in memory")

    for query in TEST_QUERIES:
        print(f"\n=== {query!r} ===")
        print_results("semantic", engine.search(query, top_k=3))
        print_results("keyword ", engine.keyword_search(query, top_k=3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
