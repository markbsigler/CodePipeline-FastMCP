#!/usr/bin/env python3
"""
Basic tests for fastmcp_config.py to achieve coverage.
"""

import os
from unittest.mock import patch

import fastmcp_config


class TestFastMCPConfigBasic:
    """Basic test class for fastmcp_config.py coverage."""

    def test_config_exists(self):
        """Test that FASTMCP_CONFIG exists."""
        assert hasattr(fastmcp_config, "FASTMCP_CONFIG")
        assert isinstance(fastmcp_config.FASTMCP_CONFIG, dict)

    def test_get_config_function(self):
        """Test get_fastmcp_config function."""
        config = fastmcp_config.get_fastmcp_config()
        assert isinstance(config, dict)
        assert "log_level" in config

    def test_default_values(self):
        """Test default configuration values."""
        config = fastmcp_config.FASTMCP_CONFIG
        assert config.get("log_level") == "INFO"
        assert config.get("server_name") == "BMC AMI DevX Code Pipeline MCP Server"
        assert config.get("cache_enabled") is True

    @patch.dict(os.environ, {"FASTMCP_LOG_LEVEL": "DEBUG"})
    def test_env_override(self):
        """Test environment variable override."""
        import importlib

        importlib.reload(fastmcp_config)
        config = fastmcp_config.FASTMCP_CONFIG
        assert config["log_level"] == "DEBUG"

    def test_boolean_parsing(self):
        """Test boolean parsing."""
        with patch.dict(os.environ, {"FASTMCP_AUTH_ENABLED": "true"}):
            import importlib

            importlib.reload(fastmcp_config)
            config = fastmcp_config.FASTMCP_CONFIG
            assert config["auth_enabled"] is True

    def test_integer_parsing(self):
        """Test integer parsing."""
        with patch.dict(os.environ, {"FASTMCP_CACHE_MAX_SIZE": "2000"}):
            import importlib

            importlib.reload(fastmcp_config)
            config = fastmcp_config.FASTMCP_CONFIG
            assert config["cache_max_size"] == 2000

    def test_set_parsing(self):
        """Test set parsing."""
        with patch.dict(os.environ, {"FASTMCP_INCLUDE_TAGS": "a,b,c"}):
            import importlib

            importlib.reload(fastmcp_config)
            config = fastmcp_config.FASTMCP_CONFIG
            assert config["include_tags"] == {"a", "b", "c"}

    def test_config_keys(self):
        """Test expected config keys exist."""
        config = fastmcp_config.FASTMCP_CONFIG
        keys = ["log_level", "server_name", "cache_enabled", "auth_enabled"]
        for key in keys:
            assert key in config

    def test_dynamic_config(self):
        """Test dynamic config function."""
        with patch.dict(os.environ, {"FASTMCP_LOG_LEVEL": "ERROR"}):
            config = fastmcp_config.get_fastmcp_config()
            assert config["log_level"] == "ERROR"
