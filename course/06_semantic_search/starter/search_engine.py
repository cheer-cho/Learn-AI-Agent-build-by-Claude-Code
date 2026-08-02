"""Module 06 starter — an in-memory semantic search engine over the TechCorp corpus.

Work through lab.md and replace each TODO. The script is runnable at every
stage: unimplemented steps stop with a pointer to the task instead of a crash.

Run it:
    uv run python course/06_semantic_search/starter/search_engine.py
Check it:
    uv run pytest course/06_semantic_search -q
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

# The spec's four evaluation queries — run all of them in main() and compare
# semantic vs keyword results (lab.md Task 9).
TEST_QUERIES = [
    "Can I work from home?",
    "How do I recover my account?",
    "Can I wear jeans at the office?",
    "What happens when a product arrives broken?",
]

_WORD_RE = re.compile(r"[a-z0-9]+")

# Words so common they carry no signal for keyword matching (provided for you).
STOPWORDS = frozenset(
    """
    a an and are at be but by can could do does for from how i in is it its my
    of on or the that this to was what when where which who will with you your
    """.split()
)


def tokenize(text: str) -> set[str]:
    """Lowercased content words of `text` (stopwords removed), as a set.

    Provided for you — use it in keyword_search (Task 8).
    """
    return {word for word in _WORD_RE.findall(text.lower()) if word not in STOPWORDS}


class SearchEngine:
    """In-memory semantic search: chunks and their embedding vectors live in
    two parallel lists; every query is compared against every stored vector."""

    def __init__(self, embedding_client: EmbeddingClient):
        self.embedding_client = embedding_client
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def index(self, documents: list[Document]) -> int:
        """Tasks 2-3: chunk and embed `documents` into the in-memory index.

        Must return the number of chunks added.
        """
        # TODO: Chunk every document with chunk_document(document) and collect
        #       all chunks into one flat list.
        # TODO: Embed all chunk texts in ONE batch call:
        #       self.embedding_client.embed([chunk.text for chunk in chunks])
        #       (one model call for the whole corpus, not one per chunk).
        # TODO: Append the chunks to self.chunks and the vectors to
        #       self.vectors (keep the two lists aligned!), then return the
        #       number of chunks added.
        raise NotImplementedError("SearchEngine.index — see lab.md Tasks 2-3")

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """Tasks 4-7: embed the query, rank all chunks by cosine similarity,
        and return the best `top_k` as RetrievedChunk objects, best first."""
        # TODO: Task 4 — embed the query: self.embedding_client.embed([query])
        #       returns a list with ONE vector in it.
        # TODO: Task 5 — score every stored chunk: build a RetrievedChunk with
        #       score=cosine_similarity(query_vector, chunk_vector) for each
        #       chunk/vector pair (zip the two parallel lists).
        # TODO: Task 6 — sort by score, highest first.
        # TODO: Task 7 — if min_score is not None, drop results scoring below
        #       it. Then return only the first top_k results.
        raise NotImplementedError("SearchEngine.search — see lab.md Tasks 4-7")

    def keyword_search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        """Task 8: the comparison baseline — rank chunks by word overlap.

        Score each chunk as |query words ∩ chunk words| / |query words|,
        using tokenize() on both sides. Skip chunks with no overlap at all.
        Return the best `top_k` as RetrievedChunk objects, best first.
        """
        # TODO: Tokenize the query; if it has no content words, return [].
        # TODO: For each chunk with a non-empty overlap, build a RetrievedChunk
        #       scored as len(overlap) / len(query_words).
        # TODO: Sort by score descending and return the first top_k.
        raise NotImplementedError("SearchEngine.keyword_search — see lab.md Task 8")


def build_search_engine(documents: list[Document]) -> SearchEngine:
    """Index `documents` with real embeddings, falling back to hash embeddings.

    Already wired: if the sentence-transformers model cannot be loaded (no
    network / no package), you still get a runnable engine — with a notice,
    because hash embeddings match words, not meaning.
    """
    try:
        engine = SearchEngine(get_embedding_client())
        engine.index(documents)
    except NotImplementedError:
        raise
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
    """Task 9: display title, score, and a text preview for each result."""
    print(f"  {label}:")
    if not results:
        print("    (no results)")
    for rank, result in enumerate(results, start=1):
        preview = " ".join(result.chunk.text[:100].split())
        print(f"    {rank}. [{result.score:.3f}] {result.chunk.doc_title} — {preview}")


def main() -> int:
    settings = get_settings()
    documents = load_documents(settings.data_dir)  # Task 1 (security_lab excluded)
    print(f"loaded {len(documents)} documents from {settings.data_dir}")

    engine = build_search_engine(documents)  # Tasks 2-3
    print(f"model:  {engine.embedding_client.model_name}")
    print(f"corpus: {len(documents)} documents → {len(engine.chunks)} chunks in memory")

    for query in TEST_QUERIES:  # Task 9
        print(f"\n=== {query!r} ===")
        print_results("semantic", engine.search(query, top_k=3))
        print_results("keyword ", engine.keyword_search(query, top_k=3))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/06_semantic_search/lab.md and work through the tasks in order.")
        raise SystemExit(1) from None
