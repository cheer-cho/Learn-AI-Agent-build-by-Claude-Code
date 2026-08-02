import pytest

from techcorp_agent.similarity import cosine_similarity, rank_by_similarity


def test_identical_vectors_score_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_orthogonal_vectors_score_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_opposite_vectors_score_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_magnitude_is_ignored():
    assert cosine_similarity([1.0, 1.0], [10.0, 10.0]) == pytest.approx(1.0)


def test_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_zero_vector_scores_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_ranking_orders_best_first():
    query = [1.0, 0.0]
    candidates = {
        "opposite": [-1.0, 0.0],
        "same": [2.0, 0.0],
        "orthogonal": [0.0, 1.0],
    }
    ranked = rank_by_similarity(query, candidates)
    assert [key for key, _ in ranked] == ["same", "orthogonal", "opposite"]
