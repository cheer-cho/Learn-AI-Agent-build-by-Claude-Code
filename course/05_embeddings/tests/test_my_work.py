"""Tests for YOUR work in starter/embeddings_lab.py.

These auto-skip while starter/embeddings_lab.py still contains TODO markers.
Once you remove the TODOs, they run — and passing them all means you have
completed Module 05. Run with:

    uv run pytest course/05_embeddings/tests/test_my_work.py -q

Fully offline: every test uses the deterministic HashEmbeddingClient — no
model download, no network, no API key.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/embeddings_lab.py still contains TODO markers — finish the lab first",
)

lab = import_from_path("m05_starter_embeddings_lab", STARTER_DIR / "embeddings_lab.py")


@pytest.fixture
def client() -> HashEmbeddingClient:
    # The default 384 dimensions keep hash collisions rare enough that the
    # ordering assertions below are stable (they flip at very small dims).
    return HashEmbeddingClient(dimension=384)


class TestEmbedPhrases:
    def test_maps_every_phrase_to_a_vector(self, client):
        result = lab.embed_phrases(client, lab.PHRASES)
        assert isinstance(result, dict)
        assert list(result.keys()) == lab.PHRASES

    def test_vectors_have_client_dimension(self, client):
        result = lab.embed_phrases(client, lab.PHRASES)
        for vector in result.values():
            assert len(vector) == client.dimension

    def test_vector_entries_are_floats(self, client):
        result = lab.embed_phrases(client, ["Employee vacation policy"])
        vector = result["Employee vacation policy"]
        assert all(isinstance(value, float) for value in vector)


class TestSimilarityMatrix:
    TEXTS = ["reset my password", "reset your password today", "employee vacation policy"]

    def _matrix(self, client):
        return lab.similarity_matrix(client.embed(self.TEXTS))

    def test_square_shape(self, client):
        matrix = self._matrix(client)
        assert len(matrix) == len(self.TEXTS)
        assert all(len(row) == len(self.TEXTS) for row in matrix)

    def test_diagonal_is_one(self, client):
        matrix = self._matrix(client)
        for i in range(len(self.TEXTS)):
            assert matrix[i][i] == pytest.approx(1.0)

    def test_symmetric(self, client):
        matrix = self._matrix(client)
        for i in range(len(self.TEXTS)):
            for j in range(len(self.TEXTS)):
                assert matrix[i][j] == pytest.approx(matrix[j][i])

    def test_word_overlap_scores_higher_than_disjoint(self, client):
        matrix = self._matrix(client)
        # texts 0 and 1 share "reset"/"password"; text 2 shares nothing.
        assert matrix[0][1] > matrix[0][2]


class TestKeywordScore:
    def test_disjoint_word_sets_score_zero(self):
        assert lab.keyword_score("vacation days", "quarterly revenue report") == 0.0

    def test_more_overlap_scores_higher(self):
        query = "how do I reset my password"
        partial = lab.keyword_score(query, "password requirements for new accounts")
        fuller = lab.keyword_score(query, "to reset your password, open the portal")
        assert 0.0 < partial < fuller

    def test_all_query_words_present_scores_one(self):
        assert lab.keyword_score("reset password", "How to reset a forgotten password.") == 1.0

    def test_case_and_punctuation_insensitive(self):
        assert lab.keyword_score("PASSWORD", "password!") == lab.keyword_score(
            "password", "password"
        )


class TestCompareSemanticVsKeyword:
    QUERY = "reset my password"
    DOCUMENTS = [
        "How to reset your password from the login page.",
        "Employee vacation policy and paid leave.",
        "The password field rejects passwords over 64 characters.",
    ]

    def _rankings(self, client):
        return lab.compare_semantic_vs_keyword(client, self.QUERY, self.DOCUMENTS)

    def test_returns_both_rankings(self, client):
        rankings = self._rankings(client)
        assert set(rankings.keys()) == {"semantic", "keyword"}

    def test_each_ranking_covers_all_documents(self, client):
        rankings = self._rankings(client)
        for name in ("semantic", "keyword"):
            assert sorted(doc for doc, _ in rankings[name]) == sorted(self.DOCUMENTS)

    def test_both_rankings_sorted_best_first(self, client):
        rankings = self._rankings(client)
        for name in ("semantic", "keyword"):
            scores = [score for _, score in rankings[name]]
            assert scores == sorted(scores, reverse=True)

    def test_word_overlap_document_ranks_first_with_hash_client(self, client):
        # With the hash client, "semantic" reduces to word overlap too, so the
        # document sharing the most query words must win both rankings.
        rankings = self._rankings(client)
        assert rankings["semantic"][0][0] == self.DOCUMENTS[0]
        assert rankings["keyword"][0][0] == self.DOCUMENTS[0]


class TestLabConstants:
    def test_documents_contain_a_keyword_trap(self):
        # The module's teaching data must keep its two deliberate traps:
        # a relevant document with zero query-word overlap (false negative) ...
        assert lab.keyword_score(lab.QUERY, lab.DOCUMENTS[1]) == 0.0
        # ... and an irrelevant document that DOES share query words (false positive).
        assert lab.keyword_score(lab.QUERY, lab.DOCUMENTS[2]) > 0.0
