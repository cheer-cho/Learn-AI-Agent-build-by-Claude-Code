"""Module 05 starter — embeddings lab.

Your job: implement the four functions marked with `# TODO:` below, following
the tasks in ../lab.md. The file already runs:

    uv run python course/05_embeddings/starter/embeddings_lab.py

It prints which steps still need work and demonstrates each one you finish.
Check your progress with:

    uv run pytest course/05_embeddings/tests/test_my_work.py -q
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
# constructed so keyword matching makes two characteristic mistakes —
# your job in Task 7 is to find them.
QUERY = "How many vacation days do employees get each year?"
DOCUMENTS = [
    "Employee vacation policy: full-time employees receive 20 paid vacation days per year.",
    "Staff time-off guidelines: permanent staff accrue four weeks of paid annual leave.",
    "Vacation photo contest: employees who post vacation photos get extra raffle entries.",
    "Forgot my password: use the account recovery page to reset your login credentials.",
    "TechCorp quarterly revenue grew four percent year over year.",
]

# Splits any text into lowercase word tokens: _WORD_RE.findall(text.lower())
_WORD_RE = re.compile(r"[a-z0-9]+")


def load_client() -> EmbeddingClient:
    """Return the configured embedding client, with a safe offline fallback.

    Provided for you (this is Task 1 — read it, then use it in main()):
    get_embedding_client() normally returns the real SentenceTransformerClient
    (local, free, one-time ~90 MB download). If loading or downloading fails,
    fall back to the deterministic HashEmbeddingClient so the lab still runs —
    but remember: hash vectors carry NO semantics, only word overlap.
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
    """Embed `phrases` and map each phrase to its vector (Task 2 in lab.md).

    Requirements:
    - Call client.embed() ONCE with the whole list (batching is the normal,
      efficient way to embed).
    - Return a dict: {phrase: vector} in the same order — exactly the shape
      rank_by_similarity() wants for its candidates.
    """
    # TODO: Embed all phrases in one client.embed(...) call.
    # TODO: Return a dict pairing each phrase with its vector.
    raise NotImplementedError("Task 2: implement embed_phrases")


def similarity_matrix(vectors: list[list[float]]) -> list[list[float]]:
    """All-pairs cosine similarity matrix (Task 4 in lab.md).

    Requirements:
    - Entry [i][j] is cosine_similarity(vectors[i], vectors[j]).
    - The result is square (N x N for N vectors), symmetric, and every
      non-zero vector scores 1.0 against itself (the diagonal).
    """
    # TODO: Build the N x N list-of-lists using cosine_similarity.
    raise NotImplementedError("Task 4: implement similarity_matrix")


def keyword_score(query: str, text: str) -> float:
    """Naive keyword overlap score in [0.0, 1.0] (Task 6 in lab.md).

    Requirements:
    - Tokenize both strings with _WORD_RE.findall(s.lower()) and use SETS of
      words (case-insensitive, punctuation ignored).
    - Return the fraction of the query's words that also appear in `text`.
    - Disjoint word sets (or an empty query) score exactly 0.0.
    """
    # TODO: Build the two word sets.
    # TODO: Return |query_words & text_words| / |query_words| (0.0 if query is empty).
    raise NotImplementedError("Task 6: implement keyword_score")


def compare_semantic_vs_keyword(
    client: EmbeddingClient, query: str, documents: list[str]
) -> dict[str, list[tuple[str, float]]]:
    """Rank `documents` against `query` two ways (Tasks 6/7 in lab.md).

    Requirements:
    - "semantic": embed the query, embed the documents (reuse embed_phrases!),
      and rank with rank_by_similarity().
    - "keyword": score every document with keyword_score() and sort best-first.
    - Return {"semantic": [(doc, score), ...], "keyword": [(doc, score), ...]},
      BOTH lists sorted best-first.
    """
    # TODO: Embed the query (client.embed takes a list — grab element [0]).
    # TODO: Build the semantic ranking with rank_by_similarity.
    # TODO: Build the keyword ranking with keyword_score + sorted(..., reverse=True).
    # TODO: Return both in one dict.
    raise NotImplementedError("Tasks 6/7: implement compare_semantic_vs_keyword")


def try_plot_2d(labels: list[str], vectors: list[list[float]]) -> str | None:
    """OPTIONAL: project vectors to 2D with PCA and save a scatter plot.

    Provided for you. Runs only if matplotlib AND scikit-learn are already
    installed; otherwise prints a friendly skip message and returns None.
    Do NOT install anything for this — the lab is complete without the plot.
    Remember: a 2D picture of a 384-dimensional space is only an approximation
    (see lab.md).
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
    print("Module 05 — Embeddings Lab (starter)\n")

    client = load_client()
    print("Task 1 — load an embedding client")
    print(f"  model: {client.model_name}")
    print(f"  dimension: {client.dimension}\n")

    def show_embeddings() -> None:
        by_phrase = embed_phrases(client, PHRASES)
        first = by_phrase[PHRASES[0]]
        print(f"  {len(PHRASES)} phrases -> {len(by_phrase)} vectors of {len(first)} floats each")
        preview = ", ".join(f"{v:+.4f}" for v in first[:5])
        print(f"  {PHRASES[0]!r} starts with [{preview}, ...]")

    def show_pairs() -> None:
        by_phrase = embed_phrases(client, PHRASES)
        for a, b in PAIRS:
            print(f"  {cosine_similarity(by_phrase[a], by_phrase[b]):+.3f}  {a!r} vs {b!r}")
        matrix = similarity_matrix([by_phrase[p] for p in PHRASES])
        print(f"  (self-check: matrix diagonal is all {matrix[0][0]:.1f}, matrix is symmetric)")

    def show_ranking() -> None:
        query_vector = client.embed([QUERY])[0]
        for doc, score in rank_by_similarity(query_vector, embed_phrases(client, DOCUMENTS)):
            print(f"  {score:+.3f}  {doc}")

    def show_comparison() -> None:
        rankings = compare_semantic_vs_keyword(client, QUERY, DOCUMENTS)
        print("  semantic (best first):")
        for doc, score in rankings["semantic"]:
            print(f"    {score:+.3f}  {doc[:70]}")
        print("  keyword (best first):")
        for doc, score in rankings["keyword"]:
            print(f"    {score:.3f}  {doc[:70]}")
        print("  --> Task 7: which document is keyword's FALSE POSITIVE?")
        print("      Which one is its FALSE NEGATIVE? (answers in lab.md checkpoint 7)")

    def show_plot() -> None:
        by_phrase = embed_phrases(client, PHRASES)
        try_plot_2d(PHRASES, [by_phrase[p] for p in PHRASES])

    steps = [
        ("Task 2/3 — embed phrases and inspect shape", show_embeddings),
        ("Task 4 — cosine similarity between pairs", show_pairs),
        (f"Task 5 — rank documents against: {QUERY!r}", show_ranking),
        ("Task 6/7 — semantic vs keyword ranking", show_comparison),
        ("Optional — 2D projection of the phrase vectors", show_plot),
    ]
    for label, step in steps:
        print(label)
        try:
            step()
        except NotImplementedError as todo:
            print(f"  [not done yet] {todo}")
        print()


if __name__ == "__main__":
    main()
