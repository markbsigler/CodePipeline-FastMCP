#!/usr/bin/env python3
"""
Test script for advanced FastMCP features.

This script tests tag-based filtering, custom routes, global configuration,
resource templates, and prompts functionality.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Local imports after path setup
from fastmcp_config import (
    get_bmc_api_config,
    get_caching_config,
    get_custom_routes_config,
    get_fastmcp_config,
    get_monitoring_config,
    get_rate_limiting_config,
    get_server_config,
    get_tag_config,
    print_config_summary,
    validate_config,
)
from openapi_server import OpenAPIMCPServer


class TestAdvancedFeatures:
    """Test advanced FastMCP features."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch.dict(
            os.environ,
            {
                "API_BASE_URL": "https://test-api.example.com",
                "API_TOKEN": "test-token",
                "FASTMCP_AUTH_ENABLED": "false",
                "FASTMCP_LOG_LEVEL": "DEBUG",
                "FASTMCP_RATE_LIMIT_ENABLED": "true",
                "FASTMCP_CACHE_ENABLED": "true",
                "FASTMCP_MONITORING_ENABLED": "true",
                "FASTMCP_CUSTOM_ROUTES_ENABLED": "true",
                "FASTMCP_RESOURCE_TEMPLATES_ENABLED": "true",
                "FASTMCP_PROMPTS_ENABLED": "true",
            },
        ):
            yield

    @pytest.mark.asyncio
    async def test_global_configuration(self, mock_settings):
        """Test global configuration management."""
        config = get_fastmcp_config()
        assert config["log_level"] == "DEBUG"
        assert config["rate_limit_enabled"] is True
        assert config["cache_enabled"] is True
        assert config["monitoring_enabled"] is True

        # Test configuration validation
        validation = validate_config()
        assert validation["valid"] is True

        # Test specific configuration getters
        server_config = get_server_config()
        assert "name" in server_config
        assert "version" in server_config

        rate_config = get_rate_limiting_config()
        assert rate_config["enabled"] is True

        cache_config = get_caching_config()
        assert cache_config["enabled"] is True

        monitoring_config = get_monitoring_config()
        assert monitoring_config["enabled"] is True

    @pytest.mark.asyncio
    async def test_tag_based_filtering(self, mock_settings):
        """Test tag-based filtering functionality."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Test that tools are properly tagged
            tools = await server.server.get_tools()

            # Check that custom tools have proper tags
            custom_tools = [
                name for name in tools.keys() if not name.startswith("ispw_")
            ]
            for tool_name in custom_tools:
                tool = tools[tool_name]
                # Tools should have tags like 'public', 'admin', 'monitoring', 'management'
                assert hasattr(tool, "tags") or "tags" in str(tool)

    @pytest.mark.asyncio
    async def test_custom_routes(self, mock_settings):
        """Test custom HTTP routes."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Test that custom routes are registered
            # Note: We can't easily test the actual HTTP endpoints without starting the server
            # But we can verify the server was created successfully
            assert server.server is not None

            # Test configuration
            routes_config = get_custom_routes_config()
            assert "health_check" in routes_config
            assert "status" in routes_config
            assert "metrics" in routes_config
            assert "ready" in routes_config

    @pytest.mark.asyncio
    async def test_resource_templates(self, mock_settings):
        """Test resource templates functionality."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Test that resource templates are registered
            # Note: Resource templates are registered during server creation
            # We can verify the server was created successfully
            assert server.server is not None

    @pytest.mark.asyncio
    async def test_prompts(self, mock_settings):
        """Test prompts functionality."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Test that prompts are registered
            # Note: Prompts are registered during server creation
            # We can verify the server was created successfully
            assert server.server is not None

    @pytest.mark.asyncio
    async def test_server_with_global_config(self, mock_settings):
        """Test server initialization with global configuration."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Test that server uses global configuration
            assert server.config is not None
            assert server.config["log_level"] == "DEBUG"
            assert server.config["rate_limit_enabled"] is True
            assert server.config["cache_enabled"] is True
            assert server.config["monitoring_enabled"] is True

            # Test that components are initialized based on configuration
            if server.config["rate_limit_enabled"]:
                assert server.rate_limiter is not None
            else:
                assert server.rate_limiter is None

            if server.config["cache_enabled"]:
                assert server.cache is not None
            else:
                assert server.cache is None

            if server.config["monitoring_enabled"]:
                assert server.metrics is not None
            else:
                assert server.metrics is None

    @pytest.mark.asyncio
    async def test_configuration_validation(self, mock_settings):
        """Test configuration validation."""
        # Test with valid configuration
        validation = validate_config()
        assert validation["valid"] is True
        assert len(validation["issues"]) == 0

        # Test with invalid configuration
        with patch.dict(
            os.environ,
            {
                "BMC_API_BASE_URL": "",  # Invalid: empty URL
                "FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE": "invalid",  # Invalid: not a number
            },
        ):
            validation = validate_config()
            assert validation["valid"] is False
            assert len(validation["issues"]) > 0

    @pytest.mark.asyncio
    async def test_configuration_getters(self, mock_settings):
        """Test configuration getter functions."""
        # Test server configuration
        server_config = get_server_config()
        assert "name" in server_config
        assert "version" in server_config
        assert "auth_enabled" in server_config
        assert "log_level" in server_config

        # Test rate limiting configuration
        rate_config = get_rate_limiting_config()
        assert "enabled" in rate_config
        assert "requests_per_minute" in rate_config
        assert "burst_size" in rate_config

        # Test caching configuration
        cache_config = get_caching_config()
        assert "enabled" in cache_config
        assert "max_size" in cache_config
        assert "default_ttl" in cache_config

        # Test monitoring configuration
        monitoring_config = get_monitoring_config()
        assert "enabled" in monitoring_config
        assert "metrics_enabled" in monitoring_config

        # Test tag configuration
        tag_config = get_tag_config()
        assert "include_tags" in tag_config
        assert "exclude_tags" in tag_config
        assert isinstance(tag_config["include_tags"], set)
        assert isinstance(tag_config["exclude_tags"], set)

        # Test BMC API configuration
        bmc_config = get_bmc_api_config()
        assert "base_url" in bmc_config
        assert "timeout" in bmc_config
        assert "token" in bmc_config

    def test_configuration_summary(self, mock_settings):
        """Test configuration summary printing."""
        # This test just ensures the function doesn't crash
        print_config_summary()
        assert True  # If we get here, the function executed successfully

    @pytest.mark.asyncio
    async def test_feature_toggles(self, mock_settings):
        """Test feature toggle functionality."""
        # Test with all features enabled
        with patch.dict(
            os.environ,
            {
                "FASTMCP_RATE_LIMIT_ENABLED": "true",
                "FASTMCP_CACHE_ENABLED": "true",
                "FASTMCP_MONITORING_ENABLED": "true",
                "FASTMCP_CUSTOM_ROUTES_ENABLED": "true",
                "FASTMCP_RESOURCE_TEMPLATES_ENABLED": "true",
                "FASTMCP_PROMPTS_ENABLED": "true",
            },
        ):
            server = OpenAPIMCPServer()
            assert server.rate_limiter is not None
            assert server.cache is not None
            assert server.metrics is not None

        # Test with all features disabled
        with patch.dict(
            os.environ,
            {
                "FASTMCP_RATE_LIMIT_ENABLED": "false",
                "FASTMCP_CACHE_ENABLED": "false",
                "FASTMCP_MONITORING_ENABLED": "false",
                "FASTMCP_CUSTOM_ROUTES_ENABLED": "false",
                "FASTMCP_RESOURCE_TEMPLATES_ENABLED": "false",
                "FASTMCP_PROMPTS_ENABLED": "false",
            },
        ):
            server = OpenAPIMCPServer()
            assert server.rate_limiter is None
            assert server.cache is None
            assert server.metrics is None


def run_tests():
    """Run the advanced features tests."""
    print("Running Advanced FastMCP Features Tests...")

    # Run pytest
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_advanced_features.py",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
