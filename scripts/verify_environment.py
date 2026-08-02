"""Verify the course environment: what's ready, what needs configuration.

Run:  make verify   (or: uv run python scripts/verify_environment.py)

Exit code 0 when everything required is ready. Optional items (API key,
LangSmith) report their status without failing the check.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

READY = "ready"
OPTIONAL = "optional — not configured"
MISSING = "NEEDS ATTENTION"

REQUIRED_PACKAGES = [
    "openai",
    "langchain",
    "langgraph",
    "chromadb",
    "mcp",
    "pydantic",
    "yaml",
    "numpy",
    "pytest",
]


def check_python() -> tuple[str, str]:
    version = sys.version_info
    if version >= (3, 11):
        return READY, f"Python {version.major}.{version.minor}.{version.micro}"
    return MISSING, f"Python {version.major}.{version.minor} found — need 3.11+"


def check_packages() -> tuple[str, str]:
    missing = []
    for name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return MISSING, f"missing: {', '.join(missing)} — run: make setup"
    return READY, f"all {len(REQUIRED_PACKAGES)} required packages import"


def check_env_file() -> tuple[str, str]:
    if (PROJECT_ROOT / ".env").exists():
        return READY, ".env exists"
    return MISSING, "no .env file — run: cp .env.example .env"


def check_llm_provider() -> tuple[str, str]:
    from techcorp_agent.config import get_settings

    settings = get_settings()
    if settings.techcorp_offline:
        return READY, "offline mode forced (TECHCORP_OFFLINE=true) — mock LLM in use"
    if not settings.openai_api_key:
        return (
            OPTIONAL,
            "no OPENAI_API_KEY — offline mock mode active (fine for most labs)",
        )
    from techcorp_agent.llm.base import ProviderError
    from techcorp_agent.llm.openai_client import OpenAIChatClient
    from techcorp_agent.schemas import ChatMessage

    try:
        result = OpenAIChatClient(settings).complete(
            [ChatMessage(role="user", content="Reply with the single word: ready")],
            max_tokens=10,
        )
        return READY, f"live provider responded (model: {result.model})"
    except ProviderError as exc:
        return MISSING, str(exc)


def check_offline_mode() -> tuple[str, str]:
    from techcorp_agent.llm.mock_client import MockLLMClient
    from techcorp_agent.schemas import ChatMessage

    result = MockLLMClient(responses=["ok"]).complete([ChatMessage(role="user", content="ping")])
    if result.content == "ok" and result.usage is not None:
        return READY, "mock LLM works — default tests run without API credits"
    return MISSING, "mock LLM misbehaving — reinstall with: make setup"


def check_dataset() -> tuple[str, str]:
    from techcorp_agent.documents.loader import load_documents

    data_dir = PROJECT_ROOT / "data"
    if not data_dir.exists():
        return MISSING, "data/ directory missing"
    docs = load_documents(data_dir)
    if len(docs) >= 13:
        return READY, f"{len(docs)} TechCorp documents load cleanly"
    return MISSING, f"only {len(docs)} documents found — expected 13+"


def check_vector_store() -> tuple[str, str]:
    import tempfile

    from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
    from techcorp_agent.schemas import Chunk
    from techcorp_agent.vectorstore.chroma_store import VectorStore

    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(HashEmbeddingClient(dimension=32), persist_dir=Path(tmp))
        store.add_chunks(
            [
                Chunk(
                    id="probe#0",
                    doc_id="probe",
                    doc_title="Probe",
                    category="employee_handbook",
                    index=0,
                    text="verification probe",
                )
            ]
        )
        if store.query("verification probe", top_k=1):
            return READY, "ChromaDB writes and queries locally"
    return MISSING, "ChromaDB probe failed — reinstall with: make setup"


def check_langsmith() -> tuple[str, str]:
    import os

    if os.environ.get("LANGSMITH_API_KEY"):
        return READY, "LangSmith key present (used from Module 19)"
    return OPTIONAL, "no LangSmith key — local trace fallback used in Module 19"


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    checks = [
        ("Python version", check_python),
        ("Required packages", check_packages),
        (".env file", check_env_file),
        ("LLM provider", check_llm_provider),
        ("Offline mode", check_offline_mode),
        ("TechCorp dataset", check_dataset),
        ("Vector store", check_vector_store),
        ("LangSmith (optional)", check_langsmith),
    ]

    print(f"\nTechCorp AI Agents Lab — environment check\n{'=' * 60}")
    failures = 0
    for label, check in checks:
        try:
            status, detail = check()
        except Exception as exc:  # a check must never crash the report
            status, detail = MISSING, f"unexpected error: {exc}"
        if status == MISSING:
            failures += 1
        print(f"  [{status:<26}] {label}: {detail}")

    print("=" * 60)
    if failures:
        print(f"{failures} item(s) need attention — see TROUBLESHOOTING.md")
        return 1
    print("Everything required is ready. Start with course/00_setup/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
