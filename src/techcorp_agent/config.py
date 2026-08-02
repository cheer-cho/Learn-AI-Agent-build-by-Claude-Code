"""Course configuration, loaded from environment variables / .env.

Central rule: with no API key configured (or TECHCORP_OFFLINE=true), the
course runs fully offline against deterministic mock adapters. Nothing in
the default test suite may require a paid API call.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider (any OpenAI-compatible endpoint)
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"

    # Embeddings (local sentence-transformers model)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Course behavior
    techcorp_offline: bool = False
    max_output_tokens: int = 1024

    # Cost guardrails (USD per 1M tokens; adjust to your provider's rates)
    cost_input_per_mtok: float = 1.00
    cost_output_per_mtok: float = 4.00

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    chroma_dir: Path = PROJECT_ROOT / ".chroma"
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"

    @property
    def offline(self) -> bool:
        """True when the course should use mock adapters instead of a real provider."""
        return self.techcorp_offline or not self.openai_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
