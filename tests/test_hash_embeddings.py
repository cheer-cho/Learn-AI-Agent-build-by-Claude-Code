from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.similarity import cosine_similarity


def test_deterministic():
    client = HashEmbeddingClient(dimension=128)
    [a] = client.embed(["remote work policy"])
    [b] = client.embed(["remote work policy"])
    assert a == b


def test_dimension_and_normalization():
    client = HashEmbeddingClient(dimension=64)
    [vector] = client.embed(["employee vacation guidelines"])
    assert len(vector) == 64
    assert abs(sum(v * v for v in vector) - 1.0) < 1e-9


def test_word_overlap_beats_disjoint_text():
    client = HashEmbeddingClient(dimension=256)
    query, overlapping, unrelated = client.embed(
        [
            "remote work from another country",
            "remote work policy for employees",
            "quarterly financial revenue report",
        ]
    )
    assert cosine_similarity(query, overlapping) > cosine_similarity(query, unrelated)


def test_empty_text_yields_zero_vector():
    client = HashEmbeddingClient(dimension=32)
    [vector] = client.embed([""])
    assert all(v == 0.0 for v in vector)
