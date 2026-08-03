from techcorp_agent.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_offline_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TECHCORP_OFFLINE", raising=False)
    assert _settings(openai_api_key="").offline is True


def test_online_when_key_present():
    assert _settings(openai_api_key="sk-test", techcorp_offline=False).offline is False


def test_offline_flag_overrides_key():
    assert _settings(openai_api_key="sk-test", techcorp_offline=True).offline is True


def test_empty_env_values_fall_back_to_defaults(tmp_path, monkeypatch):
    """A fresh .env copied from .env.example has blank values like
    `TECHCORP_OFFLINE=` — these must mean 'use the default', not crash.

    Isolate from the ambient environment: an OS-level env var (e.g. CI exports
    TECHCORP_OFFLINE=true) takes precedence over a blank .env value, which would
    mask exactly the .env parsing this test checks."""
    for name in ("OPENAI_API_KEY", "TECHCORP_OFFLINE", "MAX_OUTPUT_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=\nTECHCORP_OFFLINE=\nMAX_OUTPUT_TOKENS=\n", encoding="utf-8"
    )
    settings = Settings(_env_file=env_file)
    assert settings.techcorp_offline is False
    assert settings.max_output_tokens == 1024


def test_defaults_are_safe():
    settings = _settings(openai_api_key="")
    assert settings.max_output_tokens > 0
    assert settings.cost_input_per_mtok >= 0
    assert settings.cost_output_per_mtok >= 0
