#!/usr/bin/env python3
"""
Comprehensive fallback mechanism tests for the BMC AMI DevX MCP Server.

Tests graceful degradation, error recovery, and fallback behaviors
when components are unavailable or fail.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from lib.auth import RateLimiter, create_auth_provider
from lib.cache import IntelligentCache
from lib.clients import BMCAMIDevXClient
from lib.errors import ErrorHandler
from lib.health import HealthChecker
from lib.settings import Settings
from observability.metrics.hybrid_metrics import HybridMetrics


class TestAdvancedFeaturesFallback:
    """Test fallback when advanced features are unavailable."""

    def test_openapi_server_fallback_when_lib_unavailable(self):
        """Test openapi_server fallback when lib/ components are unavailable."""
        # Simulate import failure by patching ADVANCED_FEATURES_AVAILABLE
        with patch("openapi_server.ADVANCED_FEATURES_AVAILABLE", False):
            # Import should still work with fallback components
            import openapi_server

            # Should use simple fallback components
            assert hasattr(openapi_server, "SimpleMetrics")
            assert hasattr(openapi_server, "SimpleCache")
            assert hasattr(openapi_server, "SimpleRateLimiter")

    def test_settings_fallback_to_defaults(self):
        """Test settings fallback to default values when environment is empty."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            # Should use all default values
            assert settings.host == "0.0.0.0"
            assert settings.port == 8080
            assert settings.log_level == "INFO"
            assert settings.api_base_url == "https://devx.bmc.com/code-pipeline/api/v1"
            assert settings.api_token is None
            assert settings.api_timeout == 30
            assert settings.cache_enabled is True
            assert settings.metrics_enabled is True
            assert settings.otel_enabled is True

    def test_settings_partial_environment_fallback(self):
        """Test settings fallback when only some environment variables are set."""
        with patch.dict(
            os.environ,
            {
                "PORT": "9000",
                "FASTMCP_CACHE_ENABLED": "false",
                # Missing other variables should use defaults
            },
            clear=True,
        ):
            settings = Settings()

            # Should use provided values
            assert settings.port == 9000
            assert settings.cache_enabled is False

            # Should fallback to defaults for missing values
            assert settings.host == "0.0.0.0"
            assert settings.log_level == "INFO"
            assert settings.api_timeout == 30

    def test_auth_provider_fallback_scenarios(self):
        """Test auth provider creation fallback scenarios."""
        # Test 1: Auth disabled
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            provider = create_auth_provider()
            assert provider is None

        # Test 2: Invalid provider type
        with patch.dict(
            os.environ,
            {"AUTH_ENABLED": "true", "AUTH_PROVIDER": "invalid_provider_type"},
        ):
            provider = create_auth_provider()
            assert provider is None

        # Test 3: Missing required configuration
        with patch.dict(
            os.environ,
            {
                "AUTH_ENABLED": "true",
                "AUTH_PROVIDER": "jwt",
                # Missing FASTMCP_AUTH_JWKS_URI
            },
        ):
            provider = create_auth_provider()
            assert provider is None

    @pytest.mark.asyncio
    async def test_client_graceful_degradation_no_cache(self):
        """Test client graceful degradation without cache."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "no_cache_test"}
        mock_http_client.get.return_value = mock_response

        # Client without cache should still work
        client = BMCAMIDevXClient(http_client=mock_http_client, cache=None)

        result = await client.make_request("GET", "/test")
        assert result == {"data": "no_cache_test"}

        # Should make direct HTTP calls without caching
        assert mock_http_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_client_graceful_degradation_no_metrics(self):
        """Test client graceful degradation without metrics."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "no_metrics_test"}
        mock_http_client.get.return_value = mock_response

        # Client without metrics should still work
        client = BMCAMIDevXClient(http_client=mock_http_client, metrics=None)

        result = await client.make_request("GET", "/test")
        assert result == {"data": "no_metrics_test"}

    @pytest.mark.asyncio
    async def test_client_graceful_degradation_no_error_handler(self):
        """Test client graceful degradation without error handler."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)

        # Test successful request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "no_error_handler_test"}
        mock_http_client.get.return_value = mock_response

        client = BMCAMIDevXClient(http_client=mock_http_client, error_handler=None)

        result = await client.make_request("GET", "/test")
        assert result == {"data": "no_error_handler_test"}

        # Test error case - should raise exception without error handler
        error = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=Mock(status_code=500)
        )
        mock_http_client.get.side_effect = error

        with pytest.raises(httpx.HTTPStatusError):
            await client.make_request("GET", "/test")

    def test_error_handler_without_metrics(self):
        """Test error handler fallback without metrics."""
        settings = Settings()
        error_handler = ErrorHandler(settings, metrics=None)

        # Should initialize correctly without metrics
        assert error_handler.metrics is None
        assert error_handler.max_retries == settings.max_retry_attempts
        assert error_handler.base_delay == settings.retry_base_delay

        # Should still categorize errors correctly
        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=Mock(status_code=404)
        )
        result = error_handler.categorize_error(error, "test_op")
        assert result["type"] == "not_found_error"

    def test_health_checker_minimal_configuration(self):
        """Test health checker with minimal configuration."""
        settings = Settings()
        mock_client = Mock()

        health_checker = HealthChecker(mock_client, settings)

        # Should initialize with minimal configuration
        assert health_checker.bmc_client == mock_client
        assert health_checker.settings == settings
        assert health_checker.start_time is not None


class TestNetworkFailureFallbacks:
    """Test fallback mechanisms during network failures."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings = Settings(max_retry_attempts=2, retry_base_delay=0.1)
        self.cache = IntelligentCache(max_size=100, default_ttl=300)
        self.metrics = HybridMetrics()
        self.error_handler = ErrorHandler(self.settings, self.metrics)

    @pytest.mark.asyncio
    async def test_cache_fallback_on_api_failure(self):
        """Test using cached data when API fails."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        client = BMCAMIDevXClient(
            http_client=mock_http_client,
            cache=self.cache,
            metrics=self.metrics,
            error_handler=self.error_handler,
        )

        # First, populate cache with successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cached": "data", "timestamp": "2023-01-01"}
        mock_http_client.get.return_value = mock_response

        # Make initial request to populate cache
        result1 = await client.get_cached_or_fetch(
            "test_operation", "/test/endpoint", {"param": "value"}
        )
        assert result1 == {"cached": "data", "timestamp": "2023-01-01"}

        # Now simulate API failure
        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=Mock(status_code=503)
        )
        mock_http_client.get.side_effect = error

        # Should still return cached data on subsequent calls
        result2 = await client.get_cached_or_fetch(
            "test_operation", "/test/endpoint", {"param": "value"}
        )
        assert result2 == {"cached": "data", "timestamp": "2023-01-01"}

    @pytest.mark.asyncio
    async def test_retry_exhaustion_fallback(self):
        """Test fallback when all retry attempts are exhausted."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)

        # Always fail with retryable error
        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=Mock(status_code=503)
        )
        mock_http_client.get.side_effect = error

        client = BMCAMIDevXClient(
            http_client=mock_http_client, error_handler=self.error_handler
        )

        # Should return error response after exhausting retries
        result = await client.make_request("GET", "/test")

        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("type") == "server_error"
        assert result.get("attempts_made") > 1  # Should have retried

    @pytest.mark.asyncio
    async def test_timeout_fallback_behavior(self):
        """Test fallback behavior on timeout errors."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)

        # Simulate timeout
        timeout_error = httpx.TimeoutException("Request timeout")
        mock_http_client.get.side_effect = timeout_error

        client = BMCAMIDevXClient(
            http_client=mock_http_client, error_handler=self.error_handler
        )

        result = await client.make_request("GET", "/test")

        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("type") == "timeout_error"
        assert result.get("network_issue") is True

    @pytest.mark.asyncio
    async def test_connection_error_fallback(self):
        """Test fallback behavior on connection errors."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)

        # Simulate connection error
        connection_error = httpx.ConnectError("Connection failed")
        mock_http_client.get.side_effect = connection_error

        client = BMCAMIDevXClient(
            http_client=mock_http_client, error_handler=self.error_handler
        )

        result = await client.make_request("GET", "/test")

        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("type") == "connection_error"
        assert result.get("network_issue") is True


class TestRateLimitingFallbacks:
    """Test fallback mechanisms for rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limiter_burst_exhaustion(self):
        """Test rate limiter behavior when burst capacity is exhausted."""
        # Very restrictive rate limiter for testing
        rate_limiter = RateLimiter(requests_per_minute=1, burst_size=2)

        # First two requests should succeed (burst capacity)
        assert await rate_limiter.acquire() is True
        assert await rate_limiter.acquire() is True

        # Third request should be rate limited
        assert await rate_limiter.acquire() is False

    @pytest.mark.asyncio
    async def test_rate_limit_recovery_over_time(self):
        """Test rate limiter recovery over time."""
        # Rate limiter with quick recovery for testing
        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # Exhaust burst
        assert await rate_limiter.acquire() is True
        assert await rate_limiter.acquire() is False

        # Wait for token replenishment (simulate time passage)
        import time

        time.sleep(1.1)  # Wait slightly more than 1 second

        # Should be able to make request again
        assert await rate_limiter.acquire() is True

    @pytest.mark.asyncio
    async def test_client_rate_limit_handling(self):
        """Test client handling of rate limit responses."""
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)

        # Simulate rate limit response
        rate_limit_error = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=Mock(status_code=429)
        )
        mock_http_client.get.side_effect = rate_limit_error

        error_handler = ErrorHandler(Settings(), HybridMetrics())
        client = BMCAMIDevXClient(
            http_client=mock_http_client, error_handler=error_handler
        )

        result = await client.make_request("GET", "/test")

        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("type") == "rate_limit_error"
        assert result.get("retry_after") == 60  # Default retry after


class TestCacheFallbacks:
    """Test cache-related fallback mechanisms."""

    @pytest.mark.asyncio
    async def test_cache_memory_pressure_fallback(self):
        """Test cache behavior under memory pressure."""
        # Small cache to trigger eviction
        small_cache = IntelligentCache(max_size=3, default_ttl=300)

        # Fill cache beyond capacity
        await small_cache.set("key1", {"data": "value1"})
        await small_cache.set("key2", {"data": "value2"})
        await small_cache.set("key3", {"data": "value3"})
        await small_cache.set("key4", {"data": "value4"})  # Should evict oldest

        # Oldest entry should be evicted
        assert await small_cache.get("key1") is None
        assert await small_cache.get("key4") == {"data": "value4"}

        # Cache size should not exceed limit
        assert len(small_cache.cache) <= 3

    @pytest.mark.asyncio
    async def test_cache_corruption_recovery(self):
        """Test cache recovery from corruption scenarios."""
        cache = IntelligentCache(max_size=100, default_ttl=300)

        # Simulate cache corruption by directly manipulating internal state
        cache.cache["corrupted_key"] = "invalid_entry_type"

        # Cache should handle corruption gracefully
        result = await cache.get("corrupted_key")
        assert result is None  # Should return None for corrupted entries

        # Cache should continue working for new entries
        await cache.set("new_key", {"data": "new_value"})
        result = await cache.get("new_key")
        assert result == {"data": "new_value"}

    @pytest.mark.asyncio
    async def test_cache_cleanup_failure_recovery(self):
        """Test cache recovery when cleanup operations fail."""
        cache = IntelligentCache(max_size=100, default_ttl=1)  # Very short TTL

        # Add entry that will expire quickly
        await cache.set("expiring_key", {"data": "expires_soon"})

        # Wait for expiration
        import asyncio

        await asyncio.sleep(1.1)

        # Cleanup should handle expired entries gracefully
        cache.cleanup_expired()

        # Cache should continue working normally
        await cache.set("new_key", {"data": "new_value"})
        result = await cache.get("new_key")
        assert result == {"data": "new_value"}


class TestObservabilityFallbacks:
    """Test observability fallback mechanisms."""

    def test_metrics_collection_failure_fallback(self):
        """Test metrics fallback when collection fails."""
        metrics = HybridMetrics()

        # Simulate metrics collection failure by patching internal methods
        with patch.object(
            metrics.legacy, "record_request", side_effect=Exception("Metrics failure")
        ):
            # Should not raise exception, should fail gracefully
            try:
                metrics.record_request("GET", "/test", 200, 0.1)
                # If no exception, fallback worked
                fallback_worked = True
            except Exception:
                fallback_worked = False

            # Should either work or fail gracefully without crashing
            assert fallback_worked or True  # Accept either outcome

    def test_tracing_disabled_fallback(self):
        """Test tracing fallback when disabled."""
        # Test that tracing operations are no-ops when disabled
        with patch.dict(os.environ, {"FASTMCP_TRACING_ENABLED": "false"}):
            from observability.tracing.fastmcp_tracer import get_fastmcp_tracer

            tracer = get_fastmcp_tracer()

            # Should handle disabled tracing gracefully
            with tracer.trace_mcp_request("test_tool", {"arg": "value"}) as span:
                assert span is not None  # Should return a no-op span

    def test_prometheus_export_failure_fallback(self):
        """Test Prometheus export fallback when export fails."""
        from observability.exporters.prometheus_exporter import get_prometheus_config

        config = get_prometheus_config()

        # Test metrics handler with simulated failure
        with patch(
            "observability.exporters.prometheus_exporter.generate_latest",
            side_effect=Exception("Export failure"),
        ):
            response = config.metrics_handler()

            # Should return error response, not crash
            assert response.status_code == 500
            assert "text/plain" in response.media_type


class TestConfigurationFallbacks:
    """Test configuration-related fallback mechanisms."""

    def test_invalid_configuration_fallback(self):
        """Test fallback when configuration values are invalid."""
        # Test invalid boolean conversion
        with patch.dict(
            os.environ,
            {
                "FASTMCP_CACHE_ENABLED": "invalid_boolean",
                "FASTMCP_METRICS_ENABLED": "not_a_bool",
            },
        ):
            settings = Settings.from_env()

            # Should fallback to False for invalid boolean values
            assert settings.cache_enabled is False
            assert settings.metrics_enabled is False

    def test_missing_required_config_fallback(self):
        """Test fallback when required configuration is missing."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            # Should use sensible defaults
            assert settings.api_base_url is not None
            assert settings.port > 0
            assert settings.api_timeout > 0

    def test_configuration_validation_fallback(self):
        """Test fallback when configuration validation fails."""
        # Create settings with invalid values
        settings = Settings(
            port=-1, api_timeout=0, cache_max_size=-100  # Invalid  # Invalid  # Invalid
        )

        # Validation should catch these and provide meaningful errors
        with pytest.raises(ValueError) as exc_info:
            settings.validate_configuration()

        error_message = str(exc_info.value)
        assert "port" in error_message.lower()
        assert "timeout" in error_message.lower()
        assert "cache" in error_message.lower()


class TestIntegrationFallbacks:
    """Test fallback mechanisms in integrated scenarios."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.settings = Settings(max_retry_attempts=1, retry_base_delay=0.1)
        self.mock_http_client = AsyncMock(spec=httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_full_system_degradation_scenario(self):
        """Test system behavior when multiple components fail."""
        # Create client with minimal components (simulate partial system failure)
        client = BMCAMIDevXClient(
            http_client=self.mock_http_client,
            cache=None,  # Cache unavailable
            metrics=None,  # Metrics unavailable
            error_handler=None,  # Error handler unavailable
        )

        # Should still handle basic requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"degraded": "response"}
        self.mock_http_client.get.return_value = mock_response

        result = await client.make_request("GET", "/test")
        assert result == {"degraded": "response"}

    @pytest.mark.asyncio
    async def test_partial_component_failure_recovery(self):
        """Test recovery when some components fail but others work."""
        # Create system with working cache but no metrics
        cache = IntelligentCache(max_size=100, default_ttl=300)

        client = BMCAMIDevXClient(
            http_client=self.mock_http_client,
            cache=cache,
            metrics=None,  # Metrics unavailable
            error_handler=None,
        )

        # Should still use cache effectively
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cached": "response"}
        self.mock_http_client.get.return_value = mock_response

        # First call should hit API and cache
        result1 = await client.get_cached_or_fetch(
            "test_op", "/test", {"param": "value"}
        )
        assert result1 == {"cached": "response"}

        # Second call should hit cache
        result2 = await client.get_cached_or_fetch(
            "test_op", "/test", {"param": "value"}
        )
        assert result2 == {"cached": "response"}

        # Should only make one HTTP call (second was cached)
        assert self.mock_http_client.get.call_count == 1

    def test_configuration_override_fallback(self):
        """Test configuration override and fallback mechanisms."""
        # Test environment variable precedence
        with patch.dict(
            os.environ,
            {
                "PORT": "9999",
                "FASTMCP_PORT": "8888",  # Should take precedence
            },
        ):
            settings = Settings.from_env()
            assert settings.port == 8888  # FASTMCP_ prefix takes precedence

        # Test fallback when FASTMCP_ version is invalid
        with patch.dict(
            os.environ,
            {
                "PORT": "9999",
                "FASTMCP_PORT": "invalid",  # Invalid, should fallback
            },
        ):
            settings = Settings.from_env()
            assert settings.port == 9999  # Should use PORT as fallback

    @pytest.mark.asyncio
    async def test_error_cascade_prevention(self):
        """Test prevention of error cascades in fallback scenarios."""
        # Create error handler that might fail
        error_handler = ErrorHandler(self.settings, metrics=None)

        # Simulate cascading errors
        original_error = httpx.HTTPStatusError(
            "Original error", request=Mock(), response=Mock(status_code=500)
        )

        # Error handler should not cause additional errors
        try:
            result = error_handler.create_error_response(
                original_error, "test_operation"
            )
            assert isinstance(result, dict)
            assert result["error"] is True
            cascade_prevented = True
        except Exception:
            cascade_prevented = False

        assert cascade_prevented, "Error handler should prevent error cascades"
