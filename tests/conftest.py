"""Shared fixtures for the course test suite.

Everything here is offline: deterministic embeddings, scripted mock LLM,
temporary directories. No fixture may require an API key or a network call.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import Settings
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient

SAMPLE_DOC = """---
id: {doc_id}
title: {title}
category: {category}
tags: [test]
last_updated: 2026-01-15
---
# {title}

{body}
"""


def write_doc(directory: Path, doc_id: str, title: str, category: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{doc_id}.md"
    path.write_text(
        SAMPLE_DOC.format(doc_id=doc_id, title=title, category=category, body=body),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def doc_writer():
    """Fixture handle to write_doc, so test modules avoid importing conftest."""
    return write_doc


@pytest.fixture
def offline_settings(tmp_path) -> Settings:
    """Settings forced offline and isolated from the developer's real .env."""
    return Settings(
        _env_file=None,
        openai_api_key="",
        techcorp_offline=True,
        data_dir=tmp_path / "data",
        chroma_dir=tmp_path / "chroma",
        artifacts_dir=tmp_path / "artifacts",
    )


@pytest.fixture
def hash_embeddings() -> HashEmbeddingClient:
    return HashEmbeddingClient(dimension=128)


@pytest.fixture
def sample_corpus(tmp_path) -> Path:
    """A tiny document corpus with distinct topics for retrieval tests."""
    data_dir = tmp_path / "data"
    write_doc(
        data_dir / "employee_handbook",
        "test-remote-work",
        "Remote Work Policy",
        "employee_handbook",
        "Employees may work remotely up to three days per week. "
        "Remote work from another country requires manager approval.",
    )
    write_doc(
        data_dir / "employee_handbook",
        "test-dress-code",
        "Dress Code",
        "employee_handbook",
        "Business casual is the default dress code. Jeans are allowed at headquarters.",
    )
    write_doc(
        data_dir / "product_support",
        "test-refunds",
        "Refund Policy",
        "product_support",
        "Damaged products qualify for a full refund within thirty days of delivery. "
        "Refunds are processed to the original payment method.",
    )
    return data_dir
