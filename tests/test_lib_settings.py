#!/usr/bin/env python3
"""
Comprehensive tests for lib/settings.py

Tests configuration management, environment variable integration,
and validation for the BMC AMI DevX MCP Server settings.
"""

import os
from unittest.mock import patch

import pytest

from lib.settings import Settings


class TestSettings:
    """Test Settings class functionality."""

    def test_settings_default_values(self):
        """Test Settings with default values."""
        settings = Settings()

        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.log_level == "INFO"
        assert settings.api_base_url == "https://devx.bmc.com/code-pipeline/api/v1"
        assert settings.api_token is None
        assert settings.api_timeout == 30
        assert settings.connection_pool_size == 20
        assert settings.rate_limit_requests_per_minute == 60
        assert settings.rate_limit_burst_size == 10
        assert settings.cache_enabled is True
        assert settings.cache_max_size == 1000
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_cleanup_interval == 60
        assert settings.auth_enabled is False
        assert settings.auth_provider == ""
        assert settings.max_retry_attempts == 3
        assert settings.retry_base_delay == 1.0
        assert settings.otel_enabled is True
        assert settings.metrics_enabled is True
        assert settings.tracing_enabled is True

    def test_settings_with_custom_values(self):
        """Test Settings with custom values."""
        settings = Settings(
            host="127.0.0.1",
            port=9000,
            log_level="DEBUG",
            api_base_url="https://custom.api.com",
            api_token="test-token",
            api_timeout=60,
            connection_pool_size=50,
            rate_limit_requests_per_minute=120,
            rate_limit_burst_size=20,
            cache_enabled=False,
            cache_max_size=2000,
            cache_ttl_seconds=600,
            cache_cleanup_interval=120,
            auth_enabled=True,
            auth_provider="jwt",
            max_retry_attempts=5,
            retry_base_delay=2.0,
            otel_enabled=False,
            metrics_enabled=False,
            tracing_enabled=False,
        )

        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.log_level == "DEBUG"
        assert settings.api_base_url == "https://custom.api.com"
        assert settings.api_token == "test-token"
        assert settings.api_timeout == 60
        assert settings.connection_pool_size == 50
        assert settings.rate_limit_requests_per_minute == 120
        assert settings.rate_limit_burst_size == 20
        assert settings.cache_enabled is False
        assert settings.cache_max_size == 2000
        assert settings.cache_ttl_seconds == 600
        assert settings.cache_cleanup_interval == 120
        assert settings.auth_enabled is True
        assert settings.auth_provider == "jwt"
        assert settings.max_retry_attempts == 5
        assert settings.retry_base_delay == 2.0
        assert settings.otel_enabled is False
        assert settings.metrics_enabled is False
        assert settings.tracing_enabled is False

    def test_from_env_with_standard_env_vars(self):
        """Test Settings.from_env() with standard environment variables."""
        with patch.dict(
            os.environ,
            {
                "HOST": "192.168.1.1",
                "PORT": "3000",
                "API_BASE_URL": "https://test.api.com",
                "API_TOKEN": "env-token",
                "LOG_LEVEL": "ERROR",
            },
        ):
            settings = Settings.from_env()

            assert settings.host == "192.168.1.1"
            assert settings.port == 3000
            assert settings.api_base_url == "https://test.api.com"
            assert settings.api_token == "env-token"
            assert settings.log_level == "ERROR"

    def test_from_env_with_fastmcp_prefix(self):
        """Test Settings.from_env() with FASTMCP_ prefixed environment variables."""
        with patch.dict(
            os.environ,
            {
                "FASTMCP_CACHE_ENABLED": "false",
                "FASTMCP_CACHE_MAX_SIZE": "5000",
                "FASTMCP_CACHE_TTL_SECONDS": "1200",
                "FASTMCP_AUTH_ENABLED": "true",
                "FASTMCP_OTEL_ENABLED": "false",
                "FASTMCP_METRICS_ENABLED": "false",
                "FASTMCP_TRACING_ENABLED": "false",
            },
        ):
            settings = Settings.from_env()

            assert settings.cache_enabled is False
            assert settings.cache_max_size == 5000
            assert settings.cache_ttl_seconds == 1200
            assert settings.auth_enabled is True
            assert settings.otel_enabled is False
            assert settings.metrics_enabled is False
            assert settings.tracing_enabled is False

    def test_from_env_with_bool_variations(self):
        """Test Settings.from_env() with various boolean string formats."""
        test_cases = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("invalid", False),  # Invalid values default to False
        ]

        for bool_str, expected in test_cases:
            with patch.dict(os.environ, {"FASTMCP_CACHE_ENABLED": bool_str}):
                settings = Settings.from_env()
                assert settings.cache_enabled == expected, f"Failed for '{bool_str}'"

    def test_from_env_with_invalid_int_conversion(self):
        """Test Settings.from_env() with invalid integer values."""
        with patch.dict(
            os.environ,
            {
                "PORT": "invalid",
                "FASTMCP_CACHE_MAX_SIZE": "not_a_number",
                "FASTMCP_API_TIMEOUT": "abc",
            },
        ):
            settings = Settings.from_env()

            # Should use defaults when conversion fails
            assert settings.port == 8080  # Default
            assert settings.cache_max_size == 1000  # Default
            assert settings.api_timeout == 30  # Default

    def test_from_env_with_invalid_float_conversion(self):
        """Test Settings.from_env() with invalid float values."""
        with patch.dict(os.environ, {"FASTMCP_RETRY_BASE_DELAY": "not_a_float"}):
            settings = Settings.from_env()

            # Should use default when conversion fails
            assert settings.retry_base_delay == 1.0  # Default

    def test_validate_configuration_success(self):
        """Test validate_configuration with valid settings."""
        settings = Settings(
            port=8080,
            api_timeout=30,
            cache_max_size=1000,
            cache_ttl_seconds=300,
            rate_limit_requests_per_minute=60,
            rate_limit_burst_size=10,
            max_retry_attempts=3,
            retry_base_delay=1.0,
        )

        # Should not raise any exception
        assert settings.validate_configuration() is True

    def test_validate_configuration_invalid_port(self):
        """Test validate_configuration with invalid port."""
        settings = Settings(port=70000)  # Invalid port

        with pytest.raises(ValueError, match="Invalid port: 70000"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_port_zero(self):
        """Test validate_configuration with port zero."""
        settings = Settings(port=0)  # Invalid port

        with pytest.raises(ValueError, match="Invalid port: 0"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_api_timeout(self):
        """Test validate_configuration with invalid API timeout."""
        settings = Settings(api_timeout=-1)  # Invalid timeout

        with pytest.raises(ValueError, match="Invalid API timeout: -1"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_cache_max_size(self):
        """Test validate_configuration with invalid cache max size."""
        settings = Settings(cache_max_size=0)  # Invalid size

        with pytest.raises(ValueError, match="Invalid cache max size: 0"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_cache_ttl(self):
        """Test validate_configuration with invalid cache TTL."""
        settings = Settings(cache_ttl_seconds=-1)  # Invalid TTL

        with pytest.raises(ValueError, match="Invalid cache TTL: -1"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_rate_limit(self):
        """Test validate_configuration with invalid rate limit."""
        settings = Settings(rate_limit_requests_per_minute=0)  # Invalid rate limit

        with pytest.raises(ValueError, match="Invalid rate limit: 0"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_burst_size(self):
        """Test validate_configuration with invalid burst size."""
        settings = Settings(rate_limit_burst_size=-1)  # Invalid burst size

        with pytest.raises(ValueError, match="Invalid burst size: -1"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_max_retry_attempts(self):
        """Test validate_configuration with invalid max retry attempts."""
        settings = Settings(max_retry_attempts=-1)  # Invalid retry attempts

        with pytest.raises(ValueError, match="Invalid max retry attempts: -1"):
            settings.validate_configuration()

    def test_validate_configuration_invalid_retry_base_delay(self):
        """Test validate_configuration with invalid retry base delay."""
        settings = Settings(retry_base_delay=0)  # Invalid delay

        with pytest.raises(ValueError, match="Invalid retry base delay: 0"):
            settings.validate_configuration()

    def test_validate_configuration_multiple_errors(self):
        """Test validate_configuration with multiple validation errors."""
        settings = Settings(port=70000, api_timeout=-1, cache_max_size=0)

        with pytest.raises(ValueError) as exc_info:
            settings.validate_configuration()

        error_message = str(exc_info.value)
        assert "Invalid port: 70000" in error_message
        assert "Invalid API timeout: -1" in error_message
        assert "Invalid cache max size: 0" in error_message

    def test_global_settings_instance(self):
        """Test that the global settings instance is created correctly."""
        from lib.settings import settings

        assert isinstance(settings, Settings)
        assert settings.host == "0.0.0.0"  # Default value
        assert settings.port == 8080  # Default value

    def test_pydantic_model_config(self):
        """Test Pydantic model configuration."""
        settings = Settings()

        # Test that the model config is set correctly
        assert settings.model_config["env_prefix"] == "FASTMCP_"
        assert settings.model_config["case_sensitive"] is False
        assert settings.model_config["validate_assignment"] is True
        assert settings.model_config["extra"] == "ignore"

    def test_field_descriptions(self):
        """Test that fields have proper descriptions."""
        # This tests that the Field descriptions are set
        settings = Settings()

        # Get field info from the model
        fields = settings.model_fields

        assert "Server host" in str(fields["host"].description)
        assert "Server port" in str(fields["port"].description)
        assert "BMC API base URL" in str(fields["api_base_url"].description)
        assert "Enable caching" in str(fields["cache_enabled"].description)

    def test_settings_immutability_with_validation(self):
        """Test that settings validation works with assignment."""
        settings = Settings()

        # This should work (valid port)
        settings.port = 9000
        assert settings.port == 9000

        # Test that validation occurs on assignment due to validate_assignment=True
        # Note: Pydantic will validate the type but our custom validation is separate
