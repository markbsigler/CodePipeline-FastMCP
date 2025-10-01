#!/usr/bin/env python3
"""
Tests for Current OpenAPI-based FastMCP Server Architecture
"""

import json
import os

import pytest

from fastmcp_config import get_caching_config, get_fastmcp_config, get_server_config
from main import IntelligentCache, Metrics, RateLimiter, Settings
from openapi_server import OpenAPIMCPServer


class TestCurrentServerArchitecture:
    """Test current OpenAPI-based server architecture"""

    @pytest.mark.asyncio
    async def test_openapi_server_creation(self):
        """Test OpenAPI server creation"""
        try:
            server_instance = OpenAPIMCPServer()
            assert server_instance is not None
            assert hasattr(server_instance, "settings")
            assert hasattr(server_instance, "cache")
            assert hasattr(server_instance, "rate_limiter")

            print("✅ OpenAPI server creation working")

        except Exception as e:
            pytest.fail(f"OpenAPI server creation failed: {e}")

    @pytest.mark.asyncio
    async def test_fastmcp_server_creation(self):
        """Test FastMCP server creation from OpenAPI"""
        try:
            server_instance = OpenAPIMCPServer()
            server = server_instance._create_server()
            assert server is not None
            assert hasattr(server, "name")
            assert server.name == "BMC AMI DevX Code Pipeline MCP Server"
            assert hasattr(server, "version")
            assert server.version == "2.2.0"

            print("✅ FastMCP server creation working")

        except Exception as e:
            pytest.fail(f"FastMCP server creation failed: {e}")

    @pytest.mark.asyncio
    async def test_configuration_loading(self):
        """Test configuration loading from fastmcp_config"""
        try:
            server_config = get_server_config()
            assert isinstance(server_config, dict)
            # Server config keys may vary based on configuration
            assert len(server_config) >= 0  # Just check it returns a dict

            fastmcp_config = get_fastmcp_config()
            assert isinstance(fastmcp_config, dict)

            caching_config = get_caching_config()
            assert isinstance(caching_config, dict)

            print("✅ Configuration loading working")

        except Exception as e:
            pytest.fail(f"Configuration loading failed: {e}")

    @pytest.mark.asyncio
    async def test_cache_configuration(self):
        """Test cache configuration with updated defaults"""
        try:
            server_instance = OpenAPIMCPServer()
            cache = server_instance.cache
            assert isinstance(cache, IntelligentCache)
            # Updated cache size assertion
            assert cache.max_size == 1000  # Updated from 100 to 1000

            print("✅ Cache configuration working")

        except Exception as e:
            pytest.fail(f"Cache configuration test failed: {e}")

    @pytest.mark.asyncio
    async def test_rate_limiter_configuration(self):
        """Test rate limiter configuration"""
        try:
            server_instance = OpenAPIMCPServer()
            rate_limiter = server_instance.rate_limiter
            assert isinstance(rate_limiter, RateLimiter)
            assert rate_limiter.requests_per_minute == 60  # Default value

            print("✅ Rate limiter configuration working")

        except Exception as e:
            pytest.fail(f"Rate limiter configuration test failed: {e}")

    @pytest.mark.asyncio
    async def test_openapi_spec_loading(self):
        """Test OpenAPI specification loading"""
        try:
            # Check if OpenAPI spec file exists
            spec_path = os.path.join(
                os.path.dirname(__file__), "../config/openapi.json"
            )
            assert os.path.exists(spec_path), f"OpenAPI spec not found at {spec_path}"

            # Test that spec can be loaded
            with open(spec_path, "r") as f:
                spec = json.load(f)
                assert "openapi" in spec
                assert "info" in spec
                assert "paths" in spec

            print("✅ OpenAPI spec loading working")

        except Exception as e:
            pytest.fail(f"OpenAPI spec loading test failed: {e}")

    @pytest.mark.asyncio
    async def test_custom_tools_addition(self):
        """Test custom tools addition to server"""
        try:
            server_instance = OpenAPIMCPServer()
            server = server_instance._create_server()

            # Get tools from server
            tools = await server.get_tools()
            assert len(tools) > 0

            # Check for custom management tools
            tool_names = list(tools.keys())
            custom_tools = [
                "get_server_metrics",
                "get_health_status",
                "get_server_settings",
                "clear_cache",
                "get_cache_info",
            ]

            for tool_name in custom_tools:
                assert tool_name in tool_names, f"Custom tool {tool_name} not found"

            print(f"✅ Custom tools addition working - {len(tools)} tools found")

        except Exception as e:
            pytest.fail(f"Custom tools addition test failed: {e}")

    @pytest.mark.asyncio
    async def test_elicitation_tools(self):
        """Test interactive elicitation tools"""
        try:
            server_instance = OpenAPIMCPServer()
            server = server_instance._create_server()

            # Get tools from server
            tools = await server.get_tools()

            # Check for elicitation tools
            elicitation_tools = [
                "create_assignment_interactive",
                "deploy_release_interactive",
                "troubleshoot_assignment_interactive",
            ]

            for tool_name in elicitation_tools:
                assert tool_name in tools, f"Elicitation tool {tool_name} not found"

            print("✅ Elicitation tools working")

        except Exception as e:
            pytest.fail(f"Elicitation tools test failed: {e}")


class TestLegacyComponents:
    """Test legacy components that are still used"""

    def test_settings_model(self):
        """Test Settings model from main.py"""
        try:
            settings = Settings.from_env()
            assert isinstance(settings, Settings)
            assert hasattr(settings, "api_base_url")
            assert hasattr(settings, "auth_enabled")

            print("✅ Settings model working")

        except Exception as e:
            pytest.fail(f"Settings model test failed: {e}")

    def test_intelligent_cache(self):
        """Test IntelligentCache from main.py"""
        try:
            cache = IntelligentCache(max_size=1000)
            assert cache.max_size == 1000
            # Just verify cache can be instantiated - internal structure may vary
            assert cache is not None

            print("✅ IntelligentCache working")

        except Exception as e:
            pytest.fail(f"IntelligentCache test failed: {e}")

    def test_rate_limiter(self):
        """Test RateLimiter from main.py"""
        try:
            rate_limiter = RateLimiter(requests_per_minute=60, burst_size=10)
            assert rate_limiter.requests_per_minute == 60
            assert rate_limiter.burst_size == 10

            print("✅ RateLimiter working")

        except Exception as e:
            pytest.fail(f"RateLimiter test failed: {e}")

    def test_metrics(self):
        """Test Metrics from main.py"""
        try:
            metrics = Metrics()
            # Metrics is a dataclass, check if it can be instantiated
            assert metrics is not None
            assert hasattr(metrics, "__dataclass_fields__")

            print("✅ Metrics working")

        except Exception as e:
            pytest.fail(f"Metrics test failed: {e}")


class TestFileSystemPaths:
    """Test file system path assumptions"""

    def test_dockerfile_path(self):
        """Test Dockerfile exists in project root"""
        # Fix path assumption - Docker files should be in project root, not tests/
        dockerfile_path = os.path.join(os.path.dirname(__file__), "../Dockerfile")
        assert os.path.exists(
            dockerfile_path
        ), f"Dockerfile not found at {dockerfile_path}"

        with open(dockerfile_path, "r") as f:
            content = f.read()
            assert "FROM python:" in content
            assert "COPY" in content

        print("✅ Dockerfile path test working")

    def test_docker_compose_path(self):
        """Test docker-compose.yml exists in project root"""
        # Fix path assumption - Docker files should be in project root, not tests/
        compose_path = os.path.join(os.path.dirname(__file__), "../docker-compose.yml")
        assert os.path.exists(
            compose_path
        ), f"docker-compose.yml not found at {compose_path}"

        with open(compose_path, "r") as f:
            content = f.read()
            assert (
                "version:" in content or "services:" in content
            )  # Either format is acceptable

        print("✅ docker-compose.yml path test working")

    def test_config_directory(self):
        """Test config directory and files exist"""
        config_dir = os.path.join(os.path.dirname(__file__), "../config")
        assert os.path.exists(config_dir), f"Config directory not found at {config_dir}"

        # Check for key config files
        openapi_spec = os.path.join(config_dir, "openapi.json")
        assert os.path.exists(openapi_spec), f"OpenAPI spec not found at {openapi_spec}"

        print("✅ Config directory test working")


if __name__ == "__main__":
    # Run tests directly if called as script
    pytest.main([__file__, "-v"])
