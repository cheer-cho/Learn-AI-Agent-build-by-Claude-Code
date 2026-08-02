"""Shared data models used across all course modules."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ChatResult(BaseModel):
    """Normalized result of one chat completion, regardless of provider."""

    content: str
    model: str
    usage: TokenUsage | None = None
    raw: Any = Field(default=None, exclude=True, repr=False)


class Document(BaseModel):
    """One TechCorp source document (a Markdown file with frontmatter)."""

    id: str
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    last_updated: date | None = None
    path: str = ""
    content: str


class Chunk(BaseModel):
    """A retrievable piece of a document."""

    id: str
    doc_id: str
    doc_title: str
    category: str
    index: int
    text: str


class RetrievedChunk(BaseModel):
    """A chunk returned by vector search, with its similarity score (higher = closer)."""

    chunk: Chunk
    score: float


class RAGAnswer(BaseModel):
    """A grounded answer: the text, the sources it used, and whether it abstained."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    abstained: bool = False
