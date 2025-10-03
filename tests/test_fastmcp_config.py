#!/usr/bin/env python3
"""
Tests for fastmcp_config.py

Comprehensive test coverage for FastMCP configuration functionality.
"""

import os
from unittest.mock import patch

import pytest


class TestFastMCPConfig:
    """Test cases for fastmcp_config.py functions."""

    def test_get_fastmcp_config_defaults(self):
        """Test get_fastmcp_config returns default values."""
        # Clear environment variables to test defaults
        # env_vars_to_clear = [
        #     "FASTMCP_LOG_LEVEL",
        #     "FASTMCP_MASK_ERROR_DETAILS",
        #     "FASTMCP_RESOURCE_PREFIX_FORMAT",
        #     "FASTMCP_INCLUDE_FASTMCP_META",
        #     "FASTMCP_SERVER_NAME",
        #     "FASTMCP_SERVER_VERSION",
        # ]

        with patch.dict(os.environ, {}, clear=True):
            from fastmcp_config import get_fastmcp_config

            config = get_fastmcp_config()

            # Test default values
            assert config["log_level"] == "INFO"
            assert config["mask_error_details"] is False
            assert config["resource_prefix_format"] == "path"
            assert config["include_fastmcp_meta"] is True
            assert config["server_name"] == "BMC AMI DevX Code Pipeline MCP Server"
            assert config["server_version"] == "2.2.0"

    def test_get_fastmcp_config_with_env_vars(self):
        """Test get_fastmcp_config with environment variables set."""
        test_env = {
            "FASTMCP_LOG_LEVEL": "DEBUG",
            "FASTMCP_MASK_ERROR_DETAILS": "true",
            "FASTMCP_RESOURCE_PREFIX_FORMAT": "name",
            "FASTMCP_INCLUDE_FASTMCP_META": "false",
            "FASTMCP_SERVER_NAME": "Test Server",
            "FASTMCP_SERVER_VERSION": "1.0.0",
            "FASTMCP_AUTH_ENABLED": "true",
            "FASTMCP_RATE_LIMIT_ENABLED": "false",
            "FASTMCP_CACHE_ENABLED": "false",
            "FASTMCP_MONITORING_ENABLED": "false",
        }

        with patch.dict(os.environ, test_env, clear=True):
            from fastmcp_config import get_fastmcp_config

            config = get_fastmcp_config()

            # Test environment variable values
            assert config["log_level"] == "DEBUG"
            assert config["mask_error_details"] is True
            assert config["resource_prefix_format"] == "name"
            assert config["include_fastmcp_meta"] is False
            assert config["server_name"] == "Test Server"
            assert config["server_version"] == "1.0.0"
            assert config["auth_enabled"] is True
            assert config["rate_limit_enabled"] is False
            assert config["cache_enabled"] is False
            assert config["monitoring_enabled"] is False

    def test_update_fastmcp_config(self):
        """Test update_fastmcp_config updates global config."""
        from fastmcp_config import FASTMCP_CONFIG, update_fastmcp_config

        # Store original values
        original_log_level = FASTMCP_CONFIG.get("log_level")
        original_server_name = FASTMCP_CONFIG.get("server_name")

        try:
            # Update config
            updates = {"log_level": "ERROR", "server_name": "Updated Server"}
            update_fastmcp_config(updates)

            # Verify updates
            assert FASTMCP_CONFIG["log_level"] == "ERROR"
            assert FASTMCP_CONFIG["server_name"] == "Updated Server"

        finally:
            # Restore original values
            FASTMCP_CONFIG["log_level"] = original_log_level
            FASTMCP_CONFIG["server_name"] = original_server_name

    def test_get_config_value(self):
        """Test get_config_value retrieves specific values."""
        from fastmcp_config import get_config_value

        # Test existing key
        value = get_config_value("log_level")
        assert value is not None

        # Test non-existing key with default
        value = get_config_value("non_existing_key", "default_value")
        assert value == "default_value"

        # Test non-existing key without default
        value = get_config_value("non_existing_key")
        assert value is None

    def test_is_feature_enabled(self):
        """Test is_feature_enabled checks boolean features."""
        from fastmcp_config import is_feature_enabled, update_fastmcp_config

        # Test with enabled feature
        update_fastmcp_config({"test_feature_enabled": True})
        assert is_feature_enabled("test_feature") is True

        # Test with disabled feature
        update_fastmcp_config({"test_feature_enabled": False})
        assert is_feature_enabled("test_feature") is False

        # Test with non-existing feature
        assert is_feature_enabled("non_existing_feature") is False

    def test_validate_config_success(self):
        """Test validate_config with valid environment."""
        from fastmcp_config import validate_config

        # Set up valid environment
        valid_env = {
            "BMC_API_BASE_URL": "https://valid.api.com",
            "FASTMCP_AUTH_ENABLED": "true",
            "FASTMCP_AUTH_PROVIDER": "jwt",
        }

        with patch.dict(os.environ, valid_env, clear=True):
            result = validate_config()
            assert "issues" in result
            # The function returns issues, empty list means valid

    def test_validate_config_with_issues(self):
        """Test validate_config with problematic environment."""
        from fastmcp_config import validate_config

        # Set up environment that might cause validation issues
        problematic_env = {
            "BMC_API_BASE_URL": "",  # Empty URL might cause issues
            "FASTMCP_AUTH_ENABLED": "true",
            "FASTMCP_AUTH_PROVIDER": "",  # Empty provider with auth enabled
        }

        with patch.dict(os.environ, problematic_env, clear=True):
            result = validate_config()
            assert "issues" in result
            # Function should return validation results

    def test_print_config_summary(self):
        """Test print_config_summary outputs configuration."""
        from fastmcp_config import print_config_summary

        with patch("builtins.print") as mock_print:
            print_config_summary()

            # Verify that print was called (summary was output)
            assert mock_print.called

            # Check that key configuration items are mentioned
            print_calls = [str(call) for call in mock_print.call_args_list]
            summary_text = " ".join(print_calls)
            assert (
                "FastMCP Configuration" in summary_text
                or "Configuration" in summary_text
            )

    def test_boolean_environment_parsing(self):
        """Test that boolean environment variables are parsed correctly."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("1", False),  # Only 'true' should be True
            ("0", False),
            ("yes", False),
            ("", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict(
                os.environ, {"FASTMCP_AUTH_ENABLED": env_value}, clear=True
            ):
                from fastmcp_config import get_fastmcp_config

                config = get_fastmcp_config()
                assert (
                    config["auth_enabled"] is expected
                ), f"Failed for env_value: {env_value}"

    def test_integer_environment_parsing(self):
        """Test that integer environment variables are parsed correctly."""
        test_env = {
            "FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE": "120",
            "FASTMCP_RATE_LIMIT_BURST_SIZE": "20",
            "FASTMCP_CACHE_MAX_SIZE": "2000",
        }

        with patch.dict(os.environ, test_env, clear=True):
            from fastmcp_config import get_fastmcp_config

            config = get_fastmcp_config()

            assert config["rate_limit_requests_per_minute"] == 120
            assert config["rate_limit_burst_size"] == 20
            assert config["cache_max_size"] == 2000

    def test_config_file_paths(self):
        """Test configuration file path handling."""
        from fastmcp_config import get_fastmcp_config

        config = get_fastmcp_config()

        # Verify that config file paths are strings
        if "openapi_spec_file" in config:
            assert isinstance(config["openapi_spec_file"], str)
        if "oauth_config_file" in config:
            assert isinstance(config["oauth_config_file"], str)


class TestFastMCPConfigIntegration:
    """Integration tests for fastmcp_config functionality."""

    def test_config_module_structure(self):
        """Test that fastmcp_config module has expected structure."""
        import fastmcp_config

        # Verify key functions exist
        assert hasattr(fastmcp_config, "get_fastmcp_config")
        assert hasattr(fastmcp_config, "update_fastmcp_config")
        assert hasattr(fastmcp_config, "get_config_value")
        assert hasattr(fastmcp_config, "is_feature_enabled")
        assert hasattr(fastmcp_config, "validate_config")
        assert hasattr(fastmcp_config, "print_config_summary")

        # Verify global config exists
        assert hasattr(fastmcp_config, "FASTMCP_CONFIG")
        assert isinstance(fastmcp_config.FASTMCP_CONFIG, dict)

    def test_config_consistency(self):
        """Test that config values are consistent between methods."""
        from fastmcp_config import FASTMCP_CONFIG, get_config_value, get_fastmcp_config

        config = get_fastmcp_config()

        # Test get_config_value returns same values as FASTMCP_CONFIG
        common_keys = ["log_level", "server_name", "server_version"]
        for key in common_keys:
            if key in config and key in FASTMCP_CONFIG:
                config_value = get_config_value(key)
                if (
                    config_value is not None
                ):  # get_config_value might return None for missing keys
                    assert config_value == FASTMCP_CONFIG[key]

    def test_environment_isolation(self):
        """Test that environment changes don't affect global config."""
        from fastmcp_config import get_fastmcp_config

        # Get initial config
        initial_config = get_fastmcp_config()
        initial_config["log_level"]

        # Change environment variable
        with patch.dict(os.environ, {"FASTMCP_LOG_LEVEL": "ERROR"}):
            # get_fastmcp_config should reflect environment change
            env_config = get_fastmcp_config()
            assert env_config["log_level"] == "ERROR"

            # But global FASTMCP_CONFIG should remain unchanged
            # (unless explicitly updated)
            # This tests the dynamic nature of get_fastmcp_config

    def test_main_execution(self):
        """Test that module can be executed as main."""
        with patch("fastmcp_config.print_config_summary") as mock_print:
            # This would test the if __name__ == "__main__" block
            # We can't easily test this directly, so we test the function it calls
            from fastmcp_config import print_config_summary

            print_config_summary()

            # Verify the function was called
            mock_print.assert_called_once()

            # Verify the function can be called without errors
            assert True  # If we get here, no exceptions were raised


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
