"""Environment-backed configuration without embedded credentials."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings shared by API and command-line jobs."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    neo4j_uri: str = "bolt://localhost:17687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    app_api_key: str = ""
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "qwen2.5-7b-instruct"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 30
    query_timeout_seconds: float = 5


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process; tests may clear this cache."""
    return Settings()
