from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    cors_origin_regex: str | None = None
    trusted_hosts: list[str] = ["*"]
    root_path: str = ""

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # OpenAI
    openai_api_key: str
    agent_model: str = "gpt-5"
    agent_model_reasoning: str = "medium"
    agent_model_text_verbosity: str = "low"

    enrichment_model: str = "gpt-5-nano"
    enrichment_model_reasoning: str = "medium"

    # Authentication security settings
    max_login_attempts: int = 5  # Maximum failed login attempts before rate limiting
    login_attempt_window: int = 300  # Time window for login attempts (5 minutes)
    enable_rate_limiting: bool = True  # Enable rate limiting for auth endpoints


settings = Settings()
