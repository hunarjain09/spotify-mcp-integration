"""Application configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Spotify API Credentials
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str = "http://localhost:8888/callback"
    default_playlist_id: Optional[str] = None

    # AI Configuration
    ai_provider: Literal["langchain", "claude"] = "langchain"  # Choose between Langchain (OpenAI) or Claude SDK

    # OpenAI Configuration (used when ai_provider="langchain")
    openai_api_key: Optional[str] = None
    ai_model: str = "gpt-4"  # Used for Langchain provider

    # Anthropic Configuration (used when ai_provider="claude")
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20241022"  # Used for Claude provider

    # Temporal Configuration
    # USE_TEMPORAL: Feature flag to enable/disable Temporal orchestration
    # - When True: Uses Temporal for durable workflow execution with retry policies,
    #   state persistence, and distributed execution. Requires Temporal server running.
    # - When False: Uses direct synchronous execution without Temporal dependency.
    #   Simpler deployment with just FastAPI + Spotify, but loses durability and
    #   advanced retry mechanisms. Ideal for lightweight deployments or development.
    # Reasoning: Some deployments don't need the complexity of Temporal infrastructure.
    # For simple use cases (single server, fire-and-forget), direct execution is sufficient.
    use_temporal: bool = True

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_tls_cert_path: Optional[Path] = None
    temporal_tls_key_path: Optional[Path] = None

    # API Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # CORS Configuration
    # For development: Use "*" to allow all origins (default)
    # For production: Specify comma-separated list of allowed origins
    # Example: "https://yourdomain.com,https://app.yourdomain.com"
    # Security: Restricting origins prevents CSRF attacks
    cors_allowed_origins: str = "*"

    # Matching Configuration
    fuzzy_match_threshold: float = 0.85
    use_ai_disambiguation: bool = True

    # Worker Configuration
    max_concurrent_activities: int = 100
    max_concurrent_workflows: int = 50
    max_activities_per_second: float = 10.0

    # Logging
    log_level: str = "INFO"

    # Task Queue Configuration
    task_queue_name: str = "music-sync-queue"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS allowed origins into a list.

        Returns:
            List of allowed origin strings. If "*" is present, returns ["*"].
        """
        if self.cors_allowed_origins == "*":
            return ["*"]
        # Split by comma and strip whitespace
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_temporal_cloud(self) -> bool:
        """Check if using Temporal Cloud."""
        return "tmprl.cloud" in self.temporal_host

    @property
    def temporal_tls_config(self) -> Optional[dict]:
        """Get TLS config for Temporal Cloud."""
        if self.is_temporal_cloud and self.temporal_tls_cert_path and self.temporal_tls_key_path:
            return {
                "client_cert": self.temporal_tls_cert_path.read_bytes(),
                "client_private_key": self.temporal_tls_key_path.read_bytes(),
            }
        return None

    def validate_ai_config(self) -> None:
        """Validate that required AI API keys are present based on provider.

        Note: This should be called at application startup, not at module import time,
        to allow importing settings for tests, CLI tools, and other non-AI use cases.
        """
        if self.use_ai_disambiguation:
            if self.ai_provider == "langchain" and not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when AI_PROVIDER=langchain and USE_AI_DISAMBIGUATION=true"
                )
            elif self.ai_provider == "claude" and not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when AI_PROVIDER=claude and USE_AI_DISAMBIGUATION=true"
                )


# Global settings instance
settings = Settings()

# NOTE: AI config validation is now done at startup time, not module import time.
# This prevents crashes when importing settings for non-AI use cases (e.g., tests, CLI tools).
# Applications should call settings.validate_ai_config() during initialization if AI is needed.
