#!/usr/bin/env python3
"""
Test script for OpenAPI integration with FastMCP.

This script tests the OpenAPI-generated MCP tools to ensure they work correctly
with the BMC ISPW API specification.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Local imports after path setup
from openapi_server import OpenAPIMCPServer


class TestOpenAPIIntegration:
    """Test OpenAPI integration functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch.dict(
            os.environ,
            {
                "API_BASE_URL": "https://test-api.example.com",
                "API_TOKEN": "test-token",
                "AUTH_ENABLED": "false",
                "RATE_LIMIT_MAX_TOKENS": "10",
                "RATE_LIMIT_REFILL_RATE": "1.0",
                "CACHE_MAX_SIZE": "100",
                "CACHE_DEFAULT_TTL": "300",
                "CONNECTION_POOL_SIZE": "10",
                "MONITORING_ENABLED": "true",
                "ERROR_RECOVERY_ENABLED": "true",
                "LOG_LEVEL": "INFO",
            },
        ):
            yield

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx client for testing."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None
        mock_client.request.return_value = mock_response
        return mock_client

    @pytest.mark.asyncio
    async def test_openapi_server_creation(self, mock_settings):
        """Test OpenAPI server creation."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            assert server.settings.api_base_url == "https://test-api.example.com"
            assert server.settings.auth_enabled is False
            assert server.rate_limiter.requests_per_minute == 60  # Default value
            assert server.cache.max_size == 1000
            assert server.metrics is not None
            assert server.error_handler is not None
            assert server.server is not None

    @pytest.mark.asyncio
    async def test_custom_tools_exist(self, mock_settings):
        """Test that custom tools are properly registered."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Check that custom tools are registered
            tools = await server.server.get_tools()
            tool_names = list(tools.keys())

            expected_tools = [
                "get_server_metrics",
                "get_health_status",
                "get_server_settings",
                "clear_cache",
                "get_cache_info",
            ]

            for tool_name in expected_tools:
                assert (
                    tool_name in tool_names
                ), f"Tool {tool_name} not found in registered tools"

    @pytest.mark.asyncio
    async def test_get_server_metrics_tool(self, mock_settings):
        """Test get_server_metrics tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Find the tool
            tools = await server.server.get_tools()
            metrics_tool = tools.get("get_server_metrics")
            assert metrics_tool is not None

            # Test the tool function
            result = await metrics_tool.fn()
            result_data = json.loads(result)

            assert "requests" in result_data
            assert "cache" in result_data
            assert "rate_limiter" in result_data
            assert result_data["cache"]["size"] == 0
            assert result_data["rate_limiter"]["tokens"] == 10

    @pytest.mark.asyncio
    async def test_get_health_status_tool(self, mock_settings):
        """Test get_health_status tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Find the tool
            tools = await server.server.get_tools()
            health_tool = tools.get("get_health_status")
            assert health_tool is not None

            # Test the tool function
            result = await health_tool.fn()
            result_data = json.loads(result)

            assert "status" in result_data
            assert "timestamp" in result_data

    @pytest.mark.asyncio
    async def test_get_server_settings_tool(self, mock_settings):
        """Test get_server_settings tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Find the tool
            tools = await server.server.get_tools()
            settings_tool = tools.get("get_server_settings")
            assert settings_tool is not None

            # Test the tool function
            result = await settings_tool.fn()
            result_data = json.loads(result)

            assert result_data["api_base_url"] == "https://test-api.example.com"
            assert result_data["auth_enabled"] is False
            assert result_data["rate_limit_requests_per_minute"] == 60
            assert result_data["cache_max_size"] == 100

    @pytest.mark.asyncio
    async def test_clear_cache_tool(self, mock_settings):
        """Test clear_cache tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Add some test data to cache
            await server.cache.set("test_key", {"test": "data"})
            assert len(server.cache.cache) == 1

            # Find the tool
            tools = await server.server.get_tools()
            clear_tool = tools.get("clear_cache")
            assert clear_tool is not None

            # Test the tool function
            result = await clear_tool.fn()
            result_data = json.loads(result)

            assert result_data["success"] is True
            assert "Removed 1 entries" in result_data["message"]
            assert len(server.cache.cache) == 0

    @pytest.mark.asyncio
    async def test_get_cache_info_tool(self, mock_settings):
        """Test get_cache_info tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Add some test data to cache
            await server.cache.set("test_key", {"test": "data"})

            # Find the tool
            tools = await server.server.get_tools()
            cache_info_tool = tools.get("get_cache_info")
            assert cache_info_tool is not None

            # Test the tool function
            result = await cache_info_tool.fn()
            result_data = json.loads(result)

            assert result_data["size"] == 1
            assert result_data["max_size"] == 1000
            assert "test_key" in result_data["keys"]
            assert len(result_data["entries"]) == 1
            assert result_data["entries"][0]["key"] == "test_key"

    @pytest.mark.asyncio
    async def test_openapi_tools_generated(self, mock_settings):
        """Test that OpenAPI tools are generated from the specification."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Check that OpenAPI tools are registered
            tools = await server.server.get_tools()
            tool_names = list(tools.keys())

            # These should be generated from the OpenAPI spec (with ispw_ prefix)
            expected_openapi_tools = [
                "ispw_Get_assignments",
                "ispw_Create_assignment",
                "ispw_Get_assignment_details",
                "ispw_Get_assignment_tasks",
                "ispw_Generate_assignment",
                "ispw_Promote_assignment",
                "ispw_Deploy_assignment",
                "ispw_Get_releases",
                "ispw_Create_release",
                "ispw_Get_release_details",
                "ispw_Deploy_release",
                "ispw_Get_sets",
                "ispw_Deploy_set",
                "ispw_Get_packages",
                "ispw_Get_package_details",
            ]

            # Check that at least some OpenAPI tools are present
            openapi_tools_found = [
                name for name in tool_names if name in expected_openapi_tools
            ]
            assert (
                len(openapi_tools_found) > 0
            ), f"No OpenAPI tools found. Available tools: {tool_names}"

    @pytest.mark.asyncio
    async def test_server_initialization_with_auth(self, mock_settings):
        """Test server initialization with authentication enabled."""
        with patch.dict(
            os.environ,
            {
                "API_BASE_URL": "https://test-api.example.com",
                "API_TOKEN": "test-token",
                "AUTH_ENABLED": "true",
                "AUTH_PROVIDER": "jwt",
                "FASTMCP_AUTH_PROVIDER": "jwt",
                "JWT_SECRET": "test-secret-key",
                "AUTH_JWKS_URI": "https://example.com/.well-known/jwks.json",
                "AUTH_ISSUER": "https://example.com",
                "AUTH_AUDIENCE": "test-audience",
            },
        ):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client_class.return_value = AsyncMock()

                server = OpenAPIMCPServer()

                assert server.settings.auth_enabled is True
                assert server.settings.auth_provider == "jwt"
                assert server.server.auth is not None

    @pytest.mark.asyncio
    async def test_error_handling_in_tools(self, mock_settings):
        """Test error handling in custom tools."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value = AsyncMock()

            server = OpenAPIMCPServer()

            # Find the metrics tool
            tools = await server.server.get_tools()
            metrics_tool = tools.get("get_server_metrics")
            assert metrics_tool is not None

            # Mock an error in metrics
            with patch.object(
                server.metrics, "to_dict", side_effect=Exception("Test error")
            ):
                result = await metrics_tool.fn()
                result_data = json.loads(result)

                assert result_data["error"] is True
                assert "Test error" in result_data["message"]


def run_tests():
    """Run the OpenAPI integration tests."""
    print("Running OpenAPI Integration Tests...")

    # Run pytest
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_openapi_integration.py",
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
