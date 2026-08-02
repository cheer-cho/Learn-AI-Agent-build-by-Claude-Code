from techcorp_agent.config import Settings
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.llm.mock_client import MockLLMClient


def test_offline_settings_produce_mock_client(offline_settings: Settings):
    client = get_llm_client(offline_settings)
    assert isinstance(client, MockLLMClient)


def test_missing_key_produces_mock_client():
    settings = Settings(_env_file=None, openai_api_key="", techcorp_offline=False)
    assert isinstance(get_llm_client(settings), MockLLMClient)


def test_no_hardcoded_secrets_in_source():
    """No file under src/ may contain anything that looks like a real API key."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "sk-proj-" not in text, f"possible hard-coded key in {path}"
        assert "sk-ant-" not in text, f"possible hard-coded key in {path}"
