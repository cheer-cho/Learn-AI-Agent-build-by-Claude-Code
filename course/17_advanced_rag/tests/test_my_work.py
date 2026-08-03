"""Module 17 tests — your starter implementation.

These auto-skip while starter/advanced_rag_lab.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/17_advanced_rag -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/advanced_rag_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m17_starter_advanced_rag_lab", STARTER_DIR / "advanced_rag_lab.py")


# --- min-max normalization ----------------------------------------------------


def test_min_max_normalize_scales_to_unit_range(my_work):
    out = my_work.min_max_normalize({"a": 0.0, "b": 5.0, "c": 10.0})
    assert out["a"] == pytest.approx(0.0)
    assert out["b"] == pytest.approx(0.5)
    assert out["c"] == pytest.approx(1.0)


def test_min_max_normalize_equal_values_all_one(my_work):
    assert my_work.min_max_normalize({"a": 3.0, "b": 3.0}) == {"a": 1.0, "b": 1.0}
    assert my_work.min_max_normalize({}) == {}


# --- hybrid fusion ------------------------------------------------------------


def test_hybrid_fuse_unions_ids_and_weights(my_work):
    fused = my_work.hybrid_fuse({"a": 0.9, "b": 0.1}, {"b": 5.0, "c": 2.0}, alpha=0.5)
    assert set(fused) == {"a", "b", "c"}
    # `a` only in vectors, `c` only in bm25, `b` in both — `b` should rank top.
    assert fused["b"] == max(fused.values())


def test_hybrid_fuse_alpha_zero_is_pure_bm25(my_work):
    fused = my_work.hybrid_fuse({"a": 1.0}, {"a": 1.0, "b": 2.0}, alpha=0.0)
    # alpha=0 ignores vectors entirely; b (higher bm25) must win.
    assert fused["b"] > fused["a"]


# --- overlap rerank -----------------------------------------------------------


def test_overlap_rerank_orders_by_overlap(my_work):
    texts = {
        "warranty": "the warranty period is 24 months",
        "vacation": "employees accrue 25 vacation days per year",
    }
    ranked = my_work.overlap_rerank("how many vacation days", texts, top_k=2)
    assert ranked[0][0] == "vacation"
    assert ranked[0][1] >= ranked[1][1]


def test_overlap_rerank_trims_and_handles_empty_query(my_work):
    texts = {"a": "one", "b": "two", "c": "three"}
    assert len(my_work.overlap_rerank("one two", texts, top_k=2)) == 2
    empty = my_work.overlap_rerank("", texts, top_k=2)
    assert [i for i, _ in empty] == ["a", "b"]


# --- query rewrite parsing ----------------------------------------------------


def test_parse_rewrites_keeps_original_first(my_work):
    out = my_work.parse_rewrites("vacation days?", "time off\nannual leave", n=2)
    assert out == ["vacation days?", "time off", "annual leave"]


def test_parse_rewrites_dedups_and_caps(my_work):
    out = my_work.parse_rewrites("vacation days?", "vacation days?\ntime off\ntime off\nleave", n=2)
    assert out == ["vacation days?", "time off", "leave"]
