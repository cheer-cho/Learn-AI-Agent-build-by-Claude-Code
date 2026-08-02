"""Load TechCorp Markdown documents with YAML frontmatter.

Expected file shape:

    ---
    id: hr-remote-work
    title: Remote Work Policy
    category: employee_handbook
    tags: [remote, hybrid]
    last_updated: 2026-01-15
    ---
    # Remote Work Policy
    ...

Files without frontmatter (like data/README.md) are skipped.
The data/security_lab/ corpus is deliberately excluded by default: it contains
planted prompt-injection documents for Module 20 and must never end up in the
main index by accident.
"""

from pathlib import Path

import yaml

from techcorp_agent.schemas import Document

FRONTMATTER_DELIMITER = "---"
SECURITY_LAB_DIR = "security_lab"


def load_document(path: Path) -> Document | None:
    """Parse one Markdown file; returns None when it has no valid frontmatter."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith(FRONTMATTER_DELIMITER):
        return None
    try:
        _, frontmatter_text, body = text.split(FRONTMATTER_DELIMITER, 2)
    except ValueError:
        return None
    metadata = yaml.safe_load(frontmatter_text)
    if not isinstance(metadata, dict) or "id" not in metadata:
        return None
    return Document(
        id=str(metadata["id"]),
        title=str(metadata.get("title", path.stem)),
        category=str(metadata.get("category", "uncategorized")),
        tags=[str(tag) for tag in metadata.get("tags", [])],
        last_updated=metadata.get("last_updated"),
        path=str(path),
        content=body.strip(),
    )


def load_documents(
    data_dir: Path,
    categories: list[str] | None = None,
    include_security_lab: bool = False,
) -> list[Document]:
    """Load every frontmatter document under data_dir, sorted by id."""
    documents: list[Document] = []
    for path in sorted(data_dir.rglob("*.md")):
        if not include_security_lab and SECURITY_LAB_DIR in path.parts:
            continue
        document = load_document(path)
        if document is None:
            continue
        if categories and document.category not in categories:
            continue
        documents.append(document)
    seen: dict[str, str] = {}
    for document in documents:
        if document.id in seen:
            raise ValueError(
                f"Duplicate document id '{document.id}' in {document.path} and {seen[document.id]}"
            )
        seen[document.id] = document.path
    return documents
