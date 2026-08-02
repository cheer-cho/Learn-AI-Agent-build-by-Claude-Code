"""Split documents into retrievable chunks.

There is no universally best chunk size — Module 07's lab measures several
configurations against the evaluation questions. These utilities are the
knobs that experiment turns.
"""

import re

from techcorp_agent.schemas import Chunk, Document

_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def chunk_text(text: str, chunk_size: int = 800, overlap: int | None = None) -> list[str]:
    """Split text into chunks of at most `chunk_size` characters with `overlap`
    characters carried between consecutive chunks, breaking on word boundaries.

    When `overlap` is omitted it defaults to an eighth of `chunk_size`, so any
    chunk_size works out of the box."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap is None:
        overlap = chunk_size // 8
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Prefer to break at the last whitespace inside the window.
            window = text[start:end]
            last_space = window.rfind(" ")
            if last_space > chunk_size // 2:
                end = start + last_space
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return [chunk for chunk in chunks if chunk]


def split_paragraphs(text: str, max_chars: int = 1200) -> list[str]:
    """Paragraph-aware splitting: keep paragraphs whole, packing consecutive
    ones together up to `max_chars`. Oversized paragraphs fall back to
    chunk_text."""
    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(chunk_text(paragraph, chunk_size=max_chars, overlap=0))
            continue
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def chunk_document(
    document: Document,
    strategy: str = "paragraph",
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[Chunk]:
    """Chunk one document. Strategies: 'paragraph' (default) or 'fixed'."""
    if strategy == "paragraph":
        pieces = split_paragraphs(document.content, max_chars=chunk_size)
    elif strategy == "fixed":
        pieces = chunk_text(document.content, chunk_size=chunk_size, overlap=overlap)
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy!r} (use 'paragraph' or 'fixed')")
    return [
        Chunk(
            id=f"{document.id}#{index}",
            doc_id=document.id,
            doc_title=document.title,
            category=document.category,
            index=index,
            text=piece,
        )
        for index, piece in enumerate(pieces)
    ]
