"""Application configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Spotify API Credentials
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str = "http://localhost:8888/callback"
    default_playlist_id: Optional[str] = None

    # OpenAI Configuration
    openai_api_key: str
    ai_model: str = "gpt-4"

    # Temporal Configuration
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_tls_cert_path: Optional[Path] = None
    temporal_tls_key_path: Optional[Path] = None

    # API Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

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


# Global settings instance
settings = Settings()
