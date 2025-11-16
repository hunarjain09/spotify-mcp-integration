"""Unit tests for configuration settings."""

import pytest
from pathlib import Path
from pydantic import ValidationError
from config.settings import Settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_with_all_required_fields(self, temp_env):
        """Test creating settings with all required fields."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_client_id",
            SPOTIFY_CLIENT_SECRET="test_client_secret",
            OPENAI_API_KEY="test_openai_key",
        )

        settings = Settings()

        assert settings.spotify_client_id == "test_client_id"
        assert settings.spotify_client_secret == "test_client_secret"
        assert settings.openai_api_key == "test_openai_key"

    def test_default_values(self, temp_env):
        """Test default configuration values."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_client_id",
            SPOTIFY_CLIENT_SECRET="test_client_secret",
            OPENAI_API_KEY="test_openai_key",
        )

        settings = Settings()

        assert settings.spotify_redirect_uri == "http://localhost:8888/callback"
        assert settings.ai_model == "gpt-4"
        assert settings.temporal_host == "localhost:7233"
        assert settings.temporal_namespace == "default"
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.api_workers == 4
        assert settings.fuzzy_match_threshold == 0.85
        assert settings.use_ai_disambiguation is True
        assert settings.max_concurrent_activities == 100
        assert settings.max_concurrent_workflows == 50
        assert settings.max_activities_per_second == 10.0
        assert settings.log_level == "INFO"
        assert settings.task_queue_name == "music-sync-queue"

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                _env_file=None,  # Don't load from .env
                spotify_client_id="test",
                # Missing spotify_client_secret and openai_api_key
            )

        errors = exc_info.value.errors()
        error_fields = {err["loc"][0] for err in errors}
        assert "spotify_client_secret" in error_fields
        assert "openai_api_key" in error_fields

    def test_custom_values(self, temp_env):
        """Test setting custom configuration values."""
        temp_env(
            SPOTIFY_CLIENT_ID="custom_client_id",
            SPOTIFY_CLIENT_SECRET="custom_secret",
            OPENAI_API_KEY="custom_openai_key",
            AI_MODEL="gpt-3.5-turbo",
            TEMPORAL_HOST="custom.temporal.host:7233",
            API_PORT="9000",
            FUZZY_MATCH_THRESHOLD="0.90",
            USE_AI_DISAMBIGUATION="false",
        )

        settings = Settings()

        assert settings.spotify_client_id == "custom_client_id"
        assert settings.ai_model == "gpt-3.5-turbo"
        assert settings.temporal_host == "custom.temporal.host:7233"
        assert settings.api_port == 9000
        assert settings.fuzzy_match_threshold == 0.90
        assert settings.use_ai_disambiguation is False

    def test_case_insensitive_env_vars(self, temp_env):
        """Test that environment variables are case insensitive."""
        temp_env(
            spotify_client_id="test_id",  # lowercase
            SPOTIFY_CLIENT_SECRET="test_secret",  # uppercase
            OpenAI_API_Key="test_key",  # mixed case
        )

        settings = Settings()

        assert settings.spotify_client_id == "test_id"
        assert settings.spotify_client_secret == "test_secret"
        assert settings.openai_api_key == "test_key"

    def test_is_temporal_cloud_property_false(self, temp_env):
        """Test is_temporal_cloud property for local Temporal."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_HOST="localhost:7233",
        )

        settings = Settings()

        assert settings.is_temporal_cloud is False

    def test_is_temporal_cloud_property_true(self, temp_env):
        """Test is_temporal_cloud property for Temporal Cloud."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_HOST="namespace.account.tmprl.cloud:7233",
        )

        settings = Settings()

        assert settings.is_temporal_cloud is True

    def test_temporal_tls_config_none_for_local(self, temp_env):
        """Test that TLS config is None for local Temporal."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_HOST="localhost:7233",
        )

        settings = Settings()

        assert settings.temporal_tls_config is None

    def test_temporal_tls_config_none_without_certs(self, temp_env):
        """Test that TLS config is None without cert paths."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_HOST="namespace.account.tmprl.cloud:7233",
        )

        settings = Settings()

        assert settings.temporal_tls_config is None

    def test_temporal_tls_config_with_certs(self, temp_env, tmp_path):
        """Test TLS config with certificate files."""
        # Create temporary cert and key files
        cert_file = tmp_path / "client.pem"
        key_file = tmp_path / "client.key"
        cert_file.write_text("fake cert content")
        key_file.write_text("fake key content")

        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_HOST="namespace.account.tmprl.cloud:7233",
            TEMPORAL_TLS_CERT_PATH=str(cert_file),
            TEMPORAL_TLS_KEY_PATH=str(key_file),
        )

        settings = Settings()

        tls_config = settings.temporal_tls_config
        assert tls_config is not None
        assert "client_cert" in tls_config
        assert "client_private_key" in tls_config
        assert tls_config["client_cert"] == b"fake cert content"
        assert tls_config["client_private_key"] == b"fake key content"

    def test_optional_playlist_id(self, temp_env):
        """Test optional default_playlist_id."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            DEFAULT_PLAYLIST_ID="37i9dQZF1DXcBWIGoYBM5M",
        )

        settings = Settings()

        assert settings.default_playlist_id == "37i9dQZF1DXcBWIGoYBM5M"

    def test_numeric_string_conversion(self, temp_env):
        """Test that numeric strings are properly converted."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            API_PORT="9999",
            API_WORKERS="8",
            MAX_CONCURRENT_ACTIVITIES="200",
            MAX_ACTIVITIES_PER_SECOND="25.5",
            FUZZY_MATCH_THRESHOLD="0.92",
        )

        settings = Settings()

        assert settings.api_port == 9999
        assert settings.api_workers == 8
        assert settings.max_concurrent_activities == 200
        assert settings.max_activities_per_second == 25.5
        assert settings.fuzzy_match_threshold == 0.92

    def test_boolean_string_conversion(self, temp_env):
        """Test that boolean strings are properly converted."""
        # Test "false" string
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            USE_AI_DISAMBIGUATION="false",
        )

        settings = Settings()
        assert settings.use_ai_disambiguation is False

        # Test "true" string
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            USE_AI_DISAMBIGUATION="true",
        )

        settings = Settings()
        assert settings.use_ai_disambiguation is True

        # Test "0" and "1"
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            USE_AI_DISAMBIGUATION="0",
        )

        settings = Settings()
        assert settings.use_ai_disambiguation is False

    def test_extra_fields_ignored(self, temp_env):
        """Test that extra environment variables are ignored."""
        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            UNKNOWN_FIELD="should_be_ignored",
            ANOTHER_UNKNOWN="also_ignored",
        )

        # Should not raise validation error
        settings = Settings()

        assert settings.spotify_client_id == "test_id"
        # Unknown fields should not be set
        assert not hasattr(settings, "unknown_field")
        assert not hasattr(settings, "another_unknown")

    def test_log_levels(self, temp_env):
        """Test different log level values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            temp_env(
                SPOTIFY_CLIENT_ID="test_id",
                SPOTIFY_CLIENT_SECRET="test_secret",
                OPENAI_API_KEY="test_key",
                LOG_LEVEL=level,
            )

            settings = Settings()
            assert settings.log_level == level

    def test_path_conversion(self, temp_env, tmp_path):
        """Test that string paths are converted to Path objects."""
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        cert_file.touch()
        key_file.touch()

        temp_env(
            SPOTIFY_CLIENT_ID="test_id",
            SPOTIFY_CLIENT_SECRET="test_secret",
            OPENAI_API_KEY="test_key",
            TEMPORAL_TLS_CERT_PATH=str(cert_file),
            TEMPORAL_TLS_KEY_PATH=str(key_file),
        )

        settings = Settings()

        assert isinstance(settings.temporal_tls_cert_path, Path)
        assert isinstance(settings.temporal_tls_key_path, Path)
        assert settings.temporal_tls_cert_path == cert_file
        assert settings.temporal_tls_key_path == key_file
