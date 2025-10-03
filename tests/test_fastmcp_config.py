#!/usr/bin/env python3
"""
Comprehensive test coverage for fastmcp_config.py

This test suite covers all functionality in the FastMCP configuration module including:
- Configuration loading and parsing
- Environment variable handling
- Configuration validation
- Configuration updates and retrieval
- Feature enabling/disabling
- Configuration summary printing
"""

import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

# Import the module under test
import fastmcp_config


class TestFastMCPConfig:
    """Test the FastMCP configuration functionality."""

    def test_global_config_initialization(self):
        """Test that global configuration is properly initialized."""
        assert isinstance(fastmcp_config.FASTMCP_CONFIG, dict)
        assert "log_level" in fastmcp_config.FASTMCP_CONFIG
        assert "server_name" in fastmcp_config.FASTMCP_CONFIG
        assert "auth_enabled" in fastmcp_config.FASTMCP_CONFIG

    def test_get_fastmcp_config(self):
        """Test getting FastMCP configuration."""
        config = fastmcp_config.get_fastmcp_config()

        assert isinstance(config, dict)
        assert "log_level" in config
        assert "server_name" in config
        assert "auth_enabled" in config
        assert "rate_limit_enabled" in config
        assert "cache_enabled" in config

    def test_get_fastmcp_config_with_environment_variables(self):
        """Test configuration with custom environment variables."""
        with patch.dict(
            os.environ,
            {
                "FASTMCP_LOG_LEVEL": "DEBUG",
                "FASTMCP_SERVER_NAME": "Test Server",
                "FASTMCP_AUTH_ENABLED": "true",
                "FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE": "120",
                "FASTMCP_CACHE_MAX_SIZE": "2000",
            },
        ):
            config = fastmcp_config.get_fastmcp_config()

            assert config["log_level"] == "DEBUG"
            assert config["server_name"] == "Test Server"
            assert config["auth_enabled"] is True
            assert config["rate_limit_requests_per_minute"] == 120
            assert config["cache_max_size"] == 2000

    def test_update_fastmcp_config(self):
        """Test updating FastMCP configuration."""
        original_config = fastmcp_config.FASTMCP_CONFIG.copy()

        updates = {
            "log_level": "DEBUG",
            "server_name": "Updated Server",
            "new_setting": "new_value",
        }

        fastmcp_config.update_fastmcp_config(updates)

        assert fastmcp_config.FASTMCP_CONFIG["log_level"] == "DEBUG"
        assert fastmcp_config.FASTMCP_CONFIG["server_name"] == "Updated Server"
        assert fastmcp_config.FASTMCP_CONFIG["new_setting"] == "new_value"

        # Restore original config
        fastmcp_config.FASTMCP_CONFIG.clear()
        fastmcp_config.FASTMCP_CONFIG.update(original_config)

    def test_get_config_value(self):
        """Test getting specific configuration values."""
        # Test existing key
        value = fastmcp_config.get_config_value("log_level")
        assert value is not None

        # Test non-existing key with default
        value = fastmcp_config.get_config_value("non_existing_key", "default_value")
        assert value == "default_value"

        # Test non-existing key without default
        value = fastmcp_config.get_config_value("non_existing_key")
        assert value is None

    def test_is_feature_enabled(self):
        """Test checking if features are enabled."""
        # Test enabled feature
        with patch.dict(os.environ, {"FASTMCP_RATE_LIMIT_ENABLED": "true"}):
            # Update the global config to reflect the environment change
            fastmcp_config.FASTMCP_CONFIG["rate_limit_enabled"] = True
            assert fastmcp_config.is_feature_enabled("rate_limit") is True

        # Test disabled feature
        with patch.dict(os.environ, {"FASTMCP_CACHE_ENABLED": "false"}):
            # Update the global config to reflect the environment change
            fastmcp_config.FASTMCP_CONFIG["cache_enabled"] = False
            assert fastmcp_config.is_feature_enabled("cache") is False

        # Test non-existing feature
        assert fastmcp_config.is_feature_enabled("non_existing") is False

    def test_get_tag_config(self):
        """Test getting tag configuration."""
        tag_config = fastmcp_config.get_tag_config()

        assert isinstance(tag_config, dict)
        assert "include_tags" in tag_config
        assert "exclude_tags" in tag_config
        assert isinstance(tag_config["include_tags"], set)
        assert isinstance(tag_config["exclude_tags"], set)

    def test_get_server_config(self):
        """Test getting server configuration."""
        server_config = fastmcp_config.get_server_config()

        assert isinstance(server_config, dict)
        assert "name" in server_config
        assert "version" in server_config
        assert "auth_enabled" in server_config
        assert "auth_provider" in server_config
        assert "log_level" in server_config

    def test_get_rate_limiting_config(self):
        """Test getting rate limiting configuration."""
        rate_config = fastmcp_config.get_rate_limiting_config()

        assert isinstance(rate_config, dict)
        assert "enabled" in rate_config
        assert "requests_per_minute" in rate_config
        assert "burst_size" in rate_config
        assert isinstance(rate_config["requests_per_minute"], int)
        assert isinstance(rate_config["burst_size"], int)

    def test_get_caching_config(self):
        """Test getting caching configuration."""
        cache_config = fastmcp_config.get_caching_config()

        assert isinstance(cache_config, dict)
        assert "enabled" in cache_config
        assert "max_size" in cache_config
        assert "default_ttl" in cache_config
        assert isinstance(cache_config["max_size"], int)
        assert isinstance(cache_config["default_ttl"], int)

    def test_get_monitoring_config(self):
        """Test getting monitoring configuration."""
        monitoring_config = fastmcp_config.get_monitoring_config()

        assert isinstance(monitoring_config, dict)
        assert "enabled" in monitoring_config
        assert "metrics_enabled" in monitoring_config
        assert isinstance(monitoring_config["enabled"], bool)
        assert isinstance(monitoring_config["metrics_enabled"], bool)

    def test_get_custom_routes_config(self):
        """Test getting custom routes configuration."""
        routes_config = fastmcp_config.get_custom_routes_config()

        assert isinstance(routes_config, dict)
        assert "health_check" in routes_config
        assert "status" in routes_config
        assert "metrics" in routes_config
        assert "ready" in routes_config
        assert all(isinstance(v, str) for v in routes_config.values())

    def test_get_bmc_api_config(self):
        """Test getting BMC API configuration."""
        api_config = fastmcp_config.get_bmc_api_config()

        assert isinstance(api_config, dict)
        assert "base_url" in api_config
        assert "timeout" in api_config
        assert "token" in api_config
        assert isinstance(api_config["timeout"], int)

    def test_validate_config_success(self):
        """Test configuration validation with valid config."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "https://test.example.com/api",
                "FASTMCP_AUTH_ENABLED": "false",
            },
        ):
            with patch("pathlib.Path.exists", return_value=True):
                validation = fastmcp_config.validate_config()

                assert validation["valid"] is True
                assert len(validation["issues"]) == 0

    def test_validate_config_missing_bmc_api_url(self):
        """Test configuration validation with missing BMC API URL."""
        with patch.dict(
            os.environ, {"BMC_API_BASE_URL": "", "FASTMCP_AUTH_ENABLED": "false"}
        ):
            validation = fastmcp_config.validate_config()

            assert validation["valid"] is False
            assert "BMC_API_BASE_URL is required" in validation["issues"]

    def test_validate_config_missing_auth_provider(self):
        """Test configuration validation with missing auth provider."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "https://test.example.com/api",
                "FASTMCP_AUTH_ENABLED": "true",
                "FASTMCP_AUTH_PROVIDER": "",
            },
        ):
            validation = fastmcp_config.validate_config()

            assert validation["valid"] is False
            assert (
                "FASTMCP_AUTH_PROVIDER is required when authentication is enabled"
                in validation["issues"]
            )

    def test_validate_config_invalid_numeric_values(self):
        """Test configuration validation with invalid numeric values."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "https://test.example.com/api",
                "FASTMCP_AUTH_ENABLED": "false",
                "FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE": "invalid",
                "FASTMCP_CACHE_MAX_SIZE": "not_a_number",
            },
        ):
            validation = fastmcp_config.validate_config()

            assert validation["valid"] is False
            assert any(
                "Invalid numeric configuration" in issue
                for issue in validation["issues"]
            )

    def test_validate_config_missing_openapi_file(self):
        """Test configuration validation with missing OpenAPI file."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "https://test.example.com/api",
                "FASTMCP_AUTH_ENABLED": "false",
            },
        ):
            with patch("pathlib.Path.exists", return_value=False):
                validation = fastmcp_config.validate_config()

                assert validation["valid"] is False
                assert any(
                    "OpenAPI specification file not found" in issue
                    for issue in validation["issues"]
                )

    def test_print_config_summary(self):
        """Test printing configuration summary."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            fastmcp_config.print_config_summary()

            output = mock_stdout.getvalue()
            assert "🔧 FastMCP Global Configuration Summary" in output
            assert "=" * 50 in output
            assert "Server:" in output
            assert "Authentication:" in output
            assert "Log Level:" in output
            assert "Features:" in output
            assert "Tag Filtering:" in output

    def test_print_config_summary_with_validation_issues(self):
        """Test printing configuration summary with validation issues."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "",
                "FASTMCP_AUTH_ENABLED": "true",
                "FASTMCP_AUTH_PROVIDER": "",
            },
        ):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                fastmcp_config.print_config_summary()

                output = mock_stdout.getvalue()
                assert "❌ Configuration issues found:" in output
                assert "BMC_API_BASE_URL is required" in output

    def test_print_config_summary_with_valid_config(self):
        """Test printing configuration summary with valid configuration."""
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "https://test.example.com/api",
                "FASTMCP_AUTH_ENABLED": "false",
            },
        ):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    fastmcp_config.print_config_summary()

                    output = mock_stdout.getvalue()
                    assert "✅ Configuration is valid" in output

    def test_boolean_environment_variable_parsing(self):
        """Test parsing of boolean environment variables."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("True", True),
            ("false", False),
            ("FALSE", False),
            ("False", False),
            ("", False),
            ("invalid", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"FASTMCP_AUTH_ENABLED": env_value}):
                config = fastmcp_config.get_fastmcp_config()
                assert (
                    config["auth_enabled"] == expected
                ), f"Failed for value: {env_value}"

    def test_numeric_environment_variable_parsing(self):
        """Test parsing of numeric environment variables."""
        with patch.dict(
            os.environ,
            {
                "FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE": "120",
                "FASTMCP_RATE_LIMIT_BURST_SIZE": "20",
                "FASTMCP_CACHE_MAX_SIZE": "2000",
                "FASTMCP_CACHE_DEFAULT_TTL": "600",
                "BMC_API_TIMEOUT": "60",
            },
        ):
            config = fastmcp_config.get_fastmcp_config()

            assert config["rate_limit_requests_per_minute"] == 120
            assert config["rate_limit_burst_size"] == 20
            assert config["cache_max_size"] == 2000
            assert config["cache_default_ttl"] == 600
            assert config["bmc_api_timeout"] == 60

    def test_set_operations_for_tags(self):
        """Test that tag configuration uses sets properly."""
        # Test the global config directly since get_fastmcp_config doesn't include tags
        tag_config = fastmcp_config.get_tag_config()

        assert isinstance(tag_config["include_tags"], set)
        assert isinstance(tag_config["exclude_tags"], set)
        assert "public" in tag_config["include_tags"]
        assert "internal" in tag_config["exclude_tags"]

    def test_default_values(self):
        """Test that default values are properly set."""
        # Clear environment to test defaults
        with patch.dict(os.environ, {}, clear=True):
            config = fastmcp_config.get_fastmcp_config()

            assert config["log_level"] == "INFO"
            assert config["server_name"] == "BMC AMI DevX Code Pipeline MCP Server"
            assert config["server_version"] == "2.2.0"
            assert config["auth_enabled"] is False
            assert config["rate_limit_enabled"] is True
            assert config["cache_enabled"] is True
            assert config["monitoring_enabled"] is True

    def test_module_execution_as_main(self):
        """Test running the module as main script."""
        import subprocess

        result = subprocess.run(
            [sys.executable, "fastmcp_config.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
        )

        # Should exit with code 0
        assert result.returncode == 0
        assert "🔧 FastMCP Global Configuration Summary" in result.stdout

    def test_configuration_immutability(self):
        """Test that configuration updates don't affect other calls."""
        original_config = fastmcp_config.get_fastmcp_config()

        # Update configuration
        fastmcp_config.update_fastmcp_config({"test_key": "test_value"})

        # Get fresh configuration
        new_config = fastmcp_config.get_fastmcp_config()

        # The fresh config should not include the test key
        assert "test_key" not in new_config

        # Restore original state
        fastmcp_config.FASTMCP_CONFIG.clear()
        fastmcp_config.FASTMCP_CONFIG.update(original_config)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
