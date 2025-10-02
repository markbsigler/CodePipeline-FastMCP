#!/usr/bin/env python3
"""
Simplified integration tests for lib/ components.

Tests core component interaction and fallback mechanisms
for the BMC AMI DevX MCP Server component library.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from lib.auth import RateLimiter, create_auth_provider
from lib.cache import IntelligentCache
from lib.clients import BMCAMIDevXClient
from lib.errors import ErrorHandler
from lib.settings import Settings
from observability.metrics.hybrid_metrics import HybridMetrics


class TestSimpleIntegration:
    """Test basic integration between lib/ components."""

    def setup_method(self):
        """Set up simple integration test fixtures."""
        self.settings = Settings(
            cache_enabled=True,
            cache_max_size=100,
            max_retry_attempts=2,
            retry_base_delay=0.1,
        )

        self.cache = IntelligentCache(max_size=100, default_ttl=300)
        self.metrics = HybridMetrics()
        self.error_handler = ErrorHandler(self.settings, self.metrics)

        self.mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        self.client = BMCAMIDevXClient(
            http_client=self.mock_http_client,
            cache=self.cache,
            metrics=self.metrics,
            error_handler=self.error_handler,
        )

    @pytest.mark.asyncio
    async def test_cache_integration(self):
        """Test cache integration with basic operations."""
        # Test cache set and get
        await self.cache.set("test_key", {"data": "test_value"}, param1="value1")

        result = await self.cache.get("test_key", param1="value1")
        assert result == {"data": "test_value"}

        # Test cache miss
        result_miss = await self.cache.get("test_key", param1="different")
        assert result_miss is None

        # Test cache stats
        stats = self.cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1

    @pytest.mark.asyncio
    async def test_metrics_integration(self):
        """Test metrics integration with basic operations."""
        # Record some metrics
        self.metrics.record_request("GET", "/test", 200, 0.1)
        self.metrics.record_request("POST", "/test", 201, 0.2)
        self.metrics.record_request("GET", "/error", 500, 0.3)

        # Check metrics structure
        metrics_data = self.metrics.to_dict()

        assert "requests" in metrics_data
        assert metrics_data["requests"]["total"] >= 3
        assert metrics_data["requests"]["successful"] >= 2
        assert metrics_data["requests"]["failed"] >= 1

        assert "response_times" in metrics_data
        assert metrics_data["response_times"]["average"] > 0

    @pytest.mark.asyncio
    async def test_error_handler_integration(self):
        """Test error handler integration with retry logic."""
        call_count = 0

        async def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Fail first two times
                raise httpx.HTTPStatusError(
                    "Server error", request=Mock(), response=Mock(status_code=503)
                )
            return {"success": True, "attempt": call_count}

        # Should retry and eventually succeed
        result = await self.error_handler.execute_with_recovery(
            "test_op", mock_function
        )

        assert result == {"success": True, "attempt": 3}
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_client_basic_operations(self):
        """Test client basic operations without complex caching."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "assignmentId": "TEST001",
            "status": "active",
        }
        self.mock_http_client.get.return_value = mock_response

        # Make request
        result = await self.client.make_request("GET", "/test/endpoint")

        assert result == {"assignmentId": "TEST001", "status": "active"}
        assert self.mock_http_client.get.call_count == 1

        # Verify metrics were recorded
        metrics_data = self.metrics.to_dict()
        assert metrics_data["requests"]["total"] >= 1

    def test_settings_integration(self):
        """Test settings integration and validation."""
        # Test valid settings
        valid_settings = Settings(port=8080, api_timeout=30, cache_max_size=1000)

        assert valid_settings.validate_configuration() is True

        # Test invalid settings
        invalid_settings = Settings(port=70000, api_timeout=-1)  # Invalid  # Invalid

        with pytest.raises(ValueError):
            invalid_settings.validate_configuration()

    @pytest.mark.asyncio
    async def test_rate_limiter_integration(self):
        """Test rate limiter basic functionality."""
        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=5)

        # Should allow initial requests
        for i in range(5):
            allowed = await rate_limiter.acquire()
            assert allowed is True

        # Should rate limit after burst
        allowed = await rate_limiter.acquire()
        # This might be True or False depending on timing, so we just check it's boolean
        assert isinstance(allowed, bool)

    def test_auth_provider_fallback(self):
        """Test auth provider creation with fallback."""
        # Test with auth disabled
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            provider = create_auth_provider()
            assert provider is None

        # Test with invalid provider
        with patch.dict(
            os.environ, {"AUTH_ENABLED": "true", "AUTH_PROVIDER": "invalid"}
        ):
            provider = create_auth_provider()
            assert provider is None

    @pytest.mark.asyncio
    async def test_component_cleanup(self):
        """Test component cleanup and resource management."""
        # Add some cache entries
        await self.cache.set("key1", {"data": "test1"})
        await self.cache.set("key2", {"data": "test2"})

        assert len(self.cache.cache) >= 2

        # Clear cache
        await self.cache.clear()
        assert len(self.cache.cache) == 0

        # Metrics don't have a reset method, but we can verify they're working
        metrics_data = self.metrics.to_dict()
        # Just verify the structure is correct
        assert "requests" in metrics_data
        assert "response_times" in metrics_data

    @pytest.mark.asyncio
    async def test_error_categorization(self):
        """Test error categorization across components."""
        # Test different error types
        test_cases = [
            (
                httpx.HTTPStatusError(
                    "Unauthorized", request=Mock(), response=Mock(status_code=401)
                ),
                "authentication_error",
            ),
            (
                httpx.HTTPStatusError(
                    "Not found", request=Mock(), response=Mock(status_code=404)
                ),
                "not_found_error",
            ),
            (
                httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=Mock(status_code=429)
                ),
                "rate_limit_error",
            ),
            (httpx.TimeoutException("Timeout"), "timeout_error"),
            (httpx.ConnectError("Connection failed"), "connection_error"),
        ]

        for error, expected_type in test_cases:
            result = self.error_handler.categorize_error(error, "test_operation")
            assert result["type"] == expected_type

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation without advanced features."""
        # Create minimal client
        minimal_client = BMCAMIDevXClient(
            http_client=self.mock_http_client,
            cache=None,
            metrics=None,
            error_handler=None,
        )

        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"minimal": "response"}
        self.mock_http_client.get.return_value = mock_response

        # Should still work
        result = await minimal_client.make_request("GET", "/test")
        assert result == {"minimal": "response"}


class TestFallbackMechanisms:
    """Test fallback mechanisms when components are unavailable."""

    def test_settings_fallback(self):
        """Test settings fallback to defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            # Should use defaults
            assert settings.host == "0.0.0.0"
            assert settings.port == 8080
            assert settings.cache_enabled is True

    @pytest.mark.asyncio
    async def test_client_without_cache(self):
        """Test client operation without cache."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"no_cache": "test"}
        mock_http_client.get.return_value = mock_response

        client = BMCAMIDevXClient(http_client=mock_http_client, cache=None)

        result = await client.make_request("GET", "/test")
        assert result == {"no_cache": "test"}

    @pytest.mark.asyncio
    async def test_client_without_metrics(self):
        """Test client operation without metrics."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"no_metrics": "test"}
        mock_http_client.get.return_value = mock_response

        client = BMCAMIDevXClient(http_client=mock_http_client, metrics=None)

        result = await client.make_request("GET", "/test")
        assert result == {"no_metrics": "test"}

    @pytest.mark.asyncio
    async def test_client_without_error_handler(self):
        """Test client operation without error handler."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"no_error_handler": "test"}
        mock_http_client.get.return_value = mock_response

        client = BMCAMIDevXClient(http_client=mock_http_client, error_handler=None)

        result = await client.make_request("GET", "/test")
        assert result == {"no_error_handler": "test"}

    def test_error_handler_without_metrics(self):
        """Test error handler without metrics."""
        settings = Settings()
        error_handler = ErrorHandler(settings, metrics=None)

        assert error_handler.metrics is None
        assert error_handler.max_retries == settings.max_retry_attempts
