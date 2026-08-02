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


def test_defaults_are_safe():
    settings = _settings(openai_api_key="")
    assert settings.max_output_tokens > 0
    assert settings.cost_input_per_mtok >= 0
    assert settings.cost_output_per_mtok >= 0
