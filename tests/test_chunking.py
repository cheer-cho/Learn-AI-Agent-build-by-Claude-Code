import pytest

from techcorp_agent.documents.chunking import chunk_document, chunk_text, split_paragraphs
from techcorp_agent.schemas import Document


def make_document(content: str) -> Document:
    return Document(id="test-doc", title="Test Doc", category="employee_handbook", content=content)


def test_short_text_is_one_chunk():
    assert chunk_text("hello world", chunk_size=100) == ["hello world"]


def test_empty_text_yields_no_chunks():
    assert chunk_text("   ", chunk_size=100) == []


def test_chunks_respect_size_limit():
    text = " ".join(f"word{i}" for i in range(500))
    for chunk in chunk_text(text, chunk_size=200, overlap=20):
        assert len(chunk) <= 200


def test_overlap_carries_content_between_chunks():
    text = " ".join(f"word{i}" for i in range(300))
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    # Some trailing words of chunk N must reappear in chunk N+1.
    tail_words = chunks[0].split()[-3:]
    assert any(word in chunks[1] for word in tail_words)


def test_invalid_parameters_raise():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=100, overlap=100)


def test_paragraph_splitting_keeps_paragraphs_whole():
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird one."
    chunks = split_paragraphs(text, max_chars=1000)
    assert chunks == [text]  # all fit in one chunk, joined by blank lines


def test_paragraph_splitting_packs_up_to_limit():
    paragraphs = [f"Paragraph number {i} with some text." for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = split_paragraphs(text, max_chars=80)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 80


def test_chunk_document_produces_stable_ids():
    doc = make_document("\n\n".join(f"Paragraph {i}." for i in range(20)))
    chunks = chunk_document(doc, strategy="paragraph", chunk_size=60)
    assert chunks[0].id == "test-doc#0"
    assert all(chunk.doc_id == "test-doc" for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        chunk_document(make_document("text"), strategy="magic")
