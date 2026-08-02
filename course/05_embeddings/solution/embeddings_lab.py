"""Module 05 solution — embeddings lab.

Run it (works anywhere; falls back to the offline hash client if the real
model cannot be loaded or downloaded):

    uv run python course/05_embeddings/solution/embeddings_lab.py

It demonstrates five things:

1. Loading an embedding client and inspecting vector shape/dimension.
2. Embedding phrases and previewing the raw numbers.
3. Cosine similarity between chosen phrase pairs.
4. Ranking TechCorp documents against a query by meaning.
5. Semantic ranking vs naive keyword-overlap ranking — including one false
   positive and one false negative of keyword matching.
"""

import re

from techcorp_agent.config import get_settings
from techcorp_agent.embeddings.base import EmbeddingClient
from techcorp_agent.embeddings.factory import get_embedding_client
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.similarity import cosine_similarity, rank_by_similarity

# Phrases from concepts.md. The first two pairs mean nearly the same thing
# with almost no shared words; the last phrase is unrelated to both.
PHRASES = [
    "Employee vacation policy",
    "Staff time-off guidelines",
    "Forgot my password",
    "Account recovery",
    "TechCorp quarterly revenue report",
]

# Pairs to compare in Task 4: two same-meaning/different-wording pairs and
# two different-meaning pairs.
PAIRS = [
    ("Employee vacation policy", "Staff time-off guidelines"),
    ("Forgot my password", "Account recovery"),
    ("Employee vacation policy", "Forgot my password"),
    ("Staff time-off guidelines", "TechCorp quarterly revenue report"),
]

# A TechCorp help-desk query and five candidate documents. Deliberately
# constructed so keyword matching makes two characteristic mistakes:
# - DOCUMENTS[1] answers the query with zero shared words (false negative).
# - DOCUMENTS[2] shares words but does not answer it (false positive).
QUERY = "How many vacation days do employees get each year?"
DOCUMENTS = [
    "Employee vacation policy: full-time employees receive 20 paid vacation days per year.",
    "Staff time-off guidelines: permanent staff accrue four weeks of paid annual leave.",
    "Vacation photo contest: employees who post vacation photos get extra raffle entries.",
    "Forgot my password: use the account recovery page to reset your login credentials.",
    "TechCorp quarterly revenue grew four percent year over year.",
]

_WORD_RE = re.compile(r"[a-z0-9]+")


def load_client() -> EmbeddingClient:
    """Return the configured embedding client, with a safe offline fallback.

    get_embedding_client() normally returns the real SentenceTransformerClient
    (local, free, one-time ~90 MB download). If loading or downloading fails —
    no network, no disk space, broken install — fall back to the deterministic
    HashEmbeddingClient so the lab still runs, and say so loudly: hash vectors
    carry NO semantics, only word overlap.
    """
    try:
        client = get_embedding_client()
        client.embed(["warm-up"])  # force the lazy model load/download NOW
        return client
    except Exception as exc:
        print(f"NOTE: could not load the real embedding model ({exc!r}).")
        print("NOTE: falling back to HashEmbeddingClient — word overlap only, no semantics.\n")
        return HashEmbeddingClient()


def embed_phrases(client: EmbeddingClient, phrases: list[str]) -> dict[str, list[float]]:
    """Embed `phrases` in one batch and map each phrase to its vector.

    The dict shape is exactly what rank_by_similarity() wants for candidates.
    """
    vectors = client.embed(phrases)
    return dict(zip(phrases, vectors, strict=True))


def similarity_matrix(vectors: list[list[float]]) -> list[list[float]]:
    """All-pairs cosine similarity: entry [i][j] compares vectors[i] and [j].

    Cosine is symmetric, so the matrix is too, and every non-zero vector has
    similarity 1.0 with itself — a quick sanity check for the whole pipeline.
    """
    return [[cosine_similarity(a, b) for b in vectors] for a in vectors]


def keyword_score(query: str, text: str) -> float:
    """Naive keyword overlap: fraction of the query's words that appear in `text`.

    Case-insensitive, punctuation ignored, no synonyms, no meaning — this is
    the strawman that embeddings beat. Returns a value in [0.0, 1.0]
    (0.0 when the word sets are disjoint or the query has no words).
    """
    query_words = set(_WORD_RE.findall(query.lower()))
    text_words = set(_WORD_RE.findall(text.lower()))
    if not query_words:
        return 0.0
    return len(query_words & text_words) / len(query_words)


def compare_semantic_vs_keyword(
    client: EmbeddingClient, query: str, documents: list[str]
) -> dict[str, list[tuple[str, float]]]:
    """Rank `documents` against `query` two ways and return both rankings.

    Returns {"semantic": [...], "keyword": [...]} where each value is a list
    of (document, score) tuples sorted best-first.
    """
    query_vector = client.embed([query])[0]
    candidates = embed_phrases(client, documents)
    semantic = rank_by_similarity(query_vector, candidates)
    keyword = sorted(
        ((doc, keyword_score(query, doc)) for doc in documents),
        key=lambda item: item[1],
        reverse=True,
    )
    return {"semantic": semantic, "keyword": keyword}


def try_plot_2d(labels: list[str], vectors: list[list[float]]) -> str | None:
    """OPTIONAL: project vectors to 2D with PCA and save a scatter plot.

    Runs only if matplotlib AND scikit-learn are already installed; otherwise
    prints a friendly skip message and returns None. Do NOT install anything
    for this — the lab is complete without the plot. Remember: a 2D picture of
    a 384-dimensional space is only an approximation (see lab.md).
    """
    try:
        import matplotlib

        matplotlib.use("Agg")  # no display needed; we only save a file
        import matplotlib.pyplot as plt
        from sklearn.decomposition import PCA
    except ImportError:
        print("  matplotlib and/or scikit-learn not installed — skipping the 2D plot.")
        print("  That is fine: this task is optional. Do not add dependencies for it.")
        return None

    coords = PCA(n_components=2).fit_transform(vectors)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(coords[:, 0], coords[:, 1])
    for (x, y), label in zip(coords, labels, strict=True):
        ax.annotate(label, (x, y), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_title("Phrase embeddings, PCA-projected to 2D (approximation!)")
    out_dir = get_settings().artifacts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "m05_embeddings_2d.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved plot to {out_path}")
    return str(out_path)


def main() -> None:
    print("Module 05 — Embeddings Lab (solution)\n")

    # Task 1 — load an embedding client (with fallback so this runs anywhere).
    client = load_client()
    is_semantic = not isinstance(client, HashEmbeddingClient)
    print("Task 1 — load an embedding client")
    print(f"  model: {client.model_name}")
    print(f"  dimension: {client.dimension}\n")

    # Tasks 2 & 3 — embed phrases and inspect vector shape.
    by_phrase = embed_phrases(client, PHRASES)
    first = by_phrase[PHRASES[0]]
    print("Task 2/3 — embed phrases and inspect shape")
    print(f"  {len(PHRASES)} phrases -> {len(by_phrase)} vectors of {len(first)} floats each")
    preview = ", ".join(f"{v:+.4f}" for v in first[:5])
    print(f"  {PHRASES[0]!r} starts with [{preview}, ...]\n")

    # Task 4 — cosine similarity between chosen pairs.
    print("Task 4 — cosine similarity between pairs")
    for a, b in PAIRS:
        score = cosine_similarity(by_phrase[a], by_phrase[b])
        print(f"  {score:+.3f}  {a!r} vs {b!r}")
    matrix = similarity_matrix([by_phrase[p] for p in PHRASES])
    print(f"  (self-check: matrix diagonal is all {matrix[0][0]:.1f}, matrix is symmetric)\n")

    # Task 5 — rank documents against the query by meaning.
    print(f"Task 5 — rank documents against: {QUERY!r}")
    query_vector = client.embed([QUERY])[0]
    for doc, score in rank_by_similarity(query_vector, embed_phrases(client, DOCUMENTS)):
        print(f"  {score:+.3f}  {doc}")
    print()

    # Tasks 6 & 7 — semantic vs keyword, with keyword's mistakes called out.
    print("Task 6/7 — semantic ranking vs keyword-overlap ranking")
    rankings = compare_semantic_vs_keyword(client, QUERY, DOCUMENTS)
    semantic_rank = {doc: i + 1 for i, (doc, _) in enumerate(rankings["semantic"])}
    semantic_score = dict(rankings["semantic"])
    for kw_rank, (doc, kw_score) in enumerate(rankings["keyword"], start=1):
        sem_rank = semantic_rank[doc]
        note = ""
        if kw_score == 0.0 and sem_rank <= 2:
            note = "  <-- keyword FALSE NEGATIVE (relevant, but zero shared words)"
        elif kw_rank <= 2 and sem_rank > 2:
            note = "  <-- keyword FALSE POSITIVE (shared words, wrong topic)"
        print(
            f"  keyword #{kw_rank} ({kw_score:.2f}) | "
            f"semantic #{sem_rank} ({semantic_score[doc]:+.3f})  {doc[:58]}...{note}"
        )
    if not is_semantic:
        print("  NOTE: hash fallback active — 'semantic' above is word overlap too,")
        print("  so keyword's mistakes cannot show. Re-run with the real model to see them.")
    print()

    # Optional — 2D projection (only if matplotlib + scikit-learn exist).
    print("Optional — 2D projection of the phrase vectors")
    try_plot_2d(PHRASES, [by_phrase[p] for p in PHRASES])


if __name__ == "__main__":
    main()
