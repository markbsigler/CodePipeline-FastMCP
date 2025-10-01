#!/usr/bin/env python3
"""
Comprehensive test coverage for openapi_server_simplified.py

This test suite covers all enterprise features implemented in the simplified version:
- Rate limiting with token bucket algorithm
- Caching with LRU/TTL eviction
- Metrics collection and monitoring  
- Error handling and retry logic
- FastMCP patterns and integration
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import httpx
import pytest
from fastmcp.server.elicitation import AcceptedElicitation, DeclinedElicitation


# Import the simplified server components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from openapi_server_simplified import (
    SimpleRateLimiter, 
    SimpleMetrics, 
    SimpleCacheEntry, 
    SimpleCache,
    SimpleErrorHandler,
    with_retry_and_error_handling,
    create_auth_provider
)


class TestSimpleRateLimiter:
    """Test the SimpleRateLimiter token bucket implementation."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization with default values."""
        limiter = SimpleRateLimiter()
        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 10
        assert limiter.tokens == 10  # Should start with full burst capacity
        assert isinstance(limiter.last_refill, datetime)
    
    def test_rate_limiter_custom_values(self):
        """Test rate limiter with custom configuration."""
        limiter = SimpleRateLimiter(requests_per_minute=120, burst_size=20)
        assert limiter.requests_per_minute == 120
        assert limiter.burst_size == 20
        assert limiter.tokens == 20
    
    @pytest.mark.asyncio
    async def test_token_acquisition_success(self):
        """Test successful token acquisition."""
        limiter = SimpleRateLimiter(requests_per_minute=60, burst_size=10)
        
        # Should be able to acquire tokens up to burst size
        for i in range(10):
            result = await limiter.acquire()
            assert result is True
            # Allow for small floating-point precision issues
            expected_tokens = 9 - i
            assert abs(limiter.tokens - expected_tokens) < 0.1
    
    @pytest.mark.asyncio
    async def test_token_acquisition_exhaustion(self):
        """Test token acquisition when exhausted."""
        limiter = SimpleRateLimiter(requests_per_minute=60, burst_size=2)
        
        # Exhaust tokens
        await limiter.acquire()  # tokens = 1
        await limiter.acquire()  # tokens = 0
        
        # Should fail to acquire when exhausted
        result = await limiter.acquire()
        assert result is False
    
    @pytest.mark.asyncio 
    async def test_token_refill(self):
        """Test token refill over time."""
        limiter = SimpleRateLimiter(requests_per_minute=60, burst_size=5)
        
        # Exhaust all tokens
        for _ in range(5):
            await limiter.acquire()
        
        # Allow for small floating-point precision issues
        assert abs(limiter.tokens - 0) < 0.1
        
        # Manually advance time by setting last_refill to past
        limiter.last_refill = datetime.now() - timedelta(minutes=1)
        
        # Calculate refill: 1 minute elapsed * 60 req/min = 60 tokens to add
        # But capped at burst_size: min(5, 0 + 60) = 5 tokens available
        result = await limiter.acquire()
        assert result is True
        # After consuming 1 token: 5 - 1 = 4 tokens remaining
        expected_remaining = 4
        assert abs(limiter.tokens - expected_remaining) < 0.1
    
    @pytest.mark.asyncio
    async def test_wait_for_token(self):
        """Test waiting for token availability."""
        limiter = SimpleRateLimiter(requests_per_minute=3600, burst_size=1)  # Very fast refill for testing
        
        # Exhaust the single token
        await limiter.acquire()
        assert limiter.tokens == 0
        
        # Wait should eventually succeed (with very fast refill rate)
        start_time = datetime.now()
        await limiter.wait_for_token()
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Should have waited some small amount of time
        assert elapsed >= 0
        # Allow for small floating-point precision issues
        assert abs(limiter.tokens - 0) < 0.1  # Token was consumed by wait_for_token


class TestSimpleMetrics:
    """Test the SimpleMetrics monitoring system."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = SimpleMetrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.rate_limited_requests == 0
        assert isinstance(metrics.start_time, datetime)
        assert len(metrics.response_times) == 0
    
    def test_record_request_success(self):
        """Test recording successful requests."""
        metrics = SimpleMetrics()
        metrics.record_request(success=True, response_time=0.5)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert len(metrics.response_times) == 1
        assert metrics.response_times[0] == 0.5
    
    def test_record_request_failure(self):
        """Test recording failed requests."""
        metrics = SimpleMetrics()
        metrics.record_request(success=False, response_time=1.2)
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert len(metrics.response_times) == 1
        assert metrics.response_times[0] == 1.2
    
    def test_record_rate_limit(self):
        """Test recording rate limited requests."""
        metrics = SimpleMetrics()
        metrics.record_rate_limit()
        
        assert metrics.rate_limited_requests == 1
    
    def test_get_avg_response_time(self):
        """Test average response time calculation."""
        metrics = SimpleMetrics()
        metrics.record_request(success=True, response_time=0.5)
        metrics.record_request(success=True, response_time=1.5)
        
        avg_time = metrics.get_avg_response_time()
        assert avg_time == 1.0
    
    def test_get_avg_response_time_empty(self):
        """Test average response time with no data."""
        metrics = SimpleMetrics()
        avg_time = metrics.get_avg_response_time()
        assert avg_time == 0.0
    
    def test_get_success_rate(self):
        """Test success rate calculation."""
        metrics = SimpleMetrics()
        metrics.record_request(success=True)
        metrics.record_request(success=True)
        metrics.record_request(success=False)
        
        success_rate = metrics.get_success_rate()
        assert success_rate == 66.67  # 2/3 rounded to 2 decimals
    
    def test_get_success_rate_no_requests(self):
        """Test success rate with no requests."""
        metrics = SimpleMetrics()
        success_rate = metrics.get_success_rate()
        assert success_rate == 100.0
    
    def test_get_uptime_seconds(self):
        """Test uptime calculation."""
        metrics = SimpleMetrics()
        # Set start time to 10 seconds ago
        metrics.start_time = datetime.now() - timedelta(seconds=10)
        
        uptime = metrics.get_uptime_seconds()
        assert uptime >= 10  # Should be at least 10 seconds
    
    def test_to_dict(self):
        """Test metrics dictionary serialization."""
        metrics = SimpleMetrics()
        metrics.record_request(success=True, response_time=0.5)
        metrics.record_rate_limit()
        
        data = metrics.to_dict()
        
        assert isinstance(data, dict)
        assert data["total_requests"] == 1
        assert data["successful_requests"] == 1
        assert data["failed_requests"] == 0
        assert data["rate_limited_requests"] == 1
        assert "success_rate_percent" in data
        assert "avg_response_time_seconds" in data
        assert "uptime_seconds" in data
        assert "recent_response_count" in data


class TestSimpleCacheEntry:
    """Test the SimpleCacheEntry TTL functionality."""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = SimpleCacheEntry(
            data={"test": "data"},
            timestamp=datetime.now(),
            ttl_seconds=300
        )
        
        assert entry.data == {"test": "data"}
        assert isinstance(entry.timestamp, datetime)
        assert entry.ttl_seconds == 300
    
    def test_cache_entry_not_expired(self):
        """Test cache entry that hasn't expired."""
        entry = SimpleCacheEntry(
            data="test",
            timestamp=datetime.now(),
            ttl_seconds=300
        )
        
        assert not entry.is_expired()
    
    def test_cache_entry_expired(self):
        """Test cache entry that has expired."""
        entry = SimpleCacheEntry(
            data="test",
            timestamp=datetime.now() - timedelta(seconds=400),  # 400 seconds ago
            ttl_seconds=300  # 300 second TTL
        )
        
        assert entry.is_expired()


class TestSimpleCache:
    """Test the SimpleCache LRU/TTL implementation."""
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = SimpleCache(max_size=100, default_ttl=600)
        
        assert cache.max_size == 100
        assert cache.default_ttl == 600
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.evictions == 0
    
    def test_generate_key(self):
        """Test cache key generation."""
        cache = SimpleCache()
        
        key1 = cache._generate_key("method1", param1="value1", param2="value2")
        key2 = cache._generate_key("method1", param2="value2", param1="value1")
        key3 = cache._generate_key("method2", param1="value1", param2="value2")
        
        # Same method and params should generate same key regardless of order
        assert key1 == key2
        # Different method should generate different key
        assert key1 != key3
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = SimpleCache()
        
        # Set a value
        await cache.set("test_method", {"result": "data"}, param1="value1")
        
        # Get the value
        result = await cache.get("test_method", param1="value1")
        
        assert result == {"result": "data"}
        assert cache.hits == 1
        assert cache.misses == 0
        assert len(cache.cache) == 1
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss scenario."""
        cache = SimpleCache()
        
        result = await cache.get("nonexistent", param="value")
        
        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test TTL expiration."""
        cache = SimpleCache(default_ttl=1)  # 1 second TTL
        
        # Set a value
        await cache.set("test_method", "data", param="value")
        
        # Should get the value immediately
        result = await cache.get("test_method", param="value")
        assert result == "data"
        
        # Manually expire the entry
        key = cache._generate_key("test_method", param="value")
        cache.cache[key].timestamp = datetime.now() - timedelta(seconds=2)
        
        # Should miss due to expiration
        result = await cache.get("test_method", param="value")
        assert result is None
        assert len(cache.cache) == 0  # Expired entry should be removed
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SimpleCache(max_size=2)  # Small cache for testing
        
        # Fill cache to capacity
        await cache.set("method", "data1", key="1")
        await cache.set("method", "data2", key="2")
        
        assert len(cache.cache) == 2
        
        # Add one more item, should evict oldest
        await cache.set("method", "data3", key="3")
        
        assert len(cache.cache) == 2
        assert cache.evictions == 1
        
        # First item should be evicted
        result = await cache.get("method", key="1")
        assert result is None
        
        # Second and third items should still be there
        result = await cache.get("method", key="2")
        assert result == "data2"
        result = await cache.get("method", key="3")
        assert result == "data3"
    
    @pytest.mark.asyncio
    async def test_cache_access_order_update(self):
        """Test that cache access updates LRU order."""
        cache = SimpleCache(max_size=2)
        
        # Fill cache
        await cache.set("method", "data1", key="1")
        await cache.set("method", "data2", key="2")
        
        # Access first item (should move it to most recent)
        await cache.get("method", key="1")
        
        # Add third item, should evict second item (least recent)
        await cache.set("method", "data3", key="3")
        
        # First item should still be there (was accessed recently)
        result = await cache.get("method", key="1")
        assert result == "data1"
        
        # Second item should be evicted
        result = await cache.get("method", key="2")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing."""
        cache = SimpleCache()
        
        await cache.set("method", "data1", key="1")
        await cache.set("method", "data2", key="2")
        
        assert len(cache.cache) == 2
        
        cleared_count = await cache.clear()
        
        assert cleared_count == 2
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = SimpleCache(default_ttl=1)
        
        # Add entries
        await cache.set("method", "data1", key="1")
        await cache.set("method", "data2", key="2")
        
        # Manually expire first entry
        key1 = cache._generate_key("method", key="1")
        cache.cache[key1].timestamp = datetime.now() - timedelta(seconds=2)
        
        # Cleanup expired entries
        removed_count = await cache.cleanup_expired()
        
        assert removed_count == 1
        assert len(cache.cache) == 1
        
        # Only second entry should remain
        result = await cache.get("method", key="2")
        assert result == "data2"
    
    def test_cache_get_hit_rate(self):
        """Test hit rate calculation."""
        cache = SimpleCache()
        cache.hits = 8
        cache.misses = 2
        
        hit_rate = cache.get_hit_rate()
        assert hit_rate == 80.0
    
    def test_cache_get_hit_rate_no_data(self):
        """Test hit rate with no data."""
        cache = SimpleCache()
        hit_rate = cache.get_hit_rate()
        assert hit_rate == 0.0
    
    def test_cache_get_stats(self):
        """Test cache statistics."""
        cache = SimpleCache(max_size=100, default_ttl=300)
        cache.hits = 5
        cache.misses = 2
        cache.evictions = 1
        
        stats = cache.get_stats()
        
        assert isinstance(stats, dict)
        assert stats["max_size"] == 100
        assert stats["default_ttl_seconds"] == 300
        assert stats["hits"] == 5
        assert stats["misses"] == 2
        assert stats["evictions"] == 1
        assert stats["hit_rate_percent"] == 71.43  # 5/7 * 100
        assert "oldest_entry_age_seconds" in stats
        assert "expired_entries" in stats


class TestSimpleErrorHandler:
    """Test the SimpleErrorHandler error categorization."""
    
    def test_error_handler_initialization(self):
        """Test error handler initialization."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        assert handler.metrics is metrics
    
    def test_categorize_timeout_error(self):
        """Test categorizing timeout errors."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        error = httpx.TimeoutException("Request timed out")
        error_info = handler.categorize_error(error, "test_operation")
        
        assert error_info["error_type"] == "timeout"
        assert error_info["retryable"] is True
        assert error_info["operation"] == "test_operation"
        assert "timestamp" in error_info
    
    def test_categorize_http_status_error(self):
        """Test categorizing HTTP status errors."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        
        error = httpx.HTTPStatusError("Server error", request=None, response=mock_response)
        error_info = handler.categorize_error(error, "test_operation")
        
        assert error_info["error_type"] == "http_error"
        assert error_info["status_code"] == 500
        assert error_info["retryable"] is True
        assert error_info["operation"] == "test_operation"
    
    def test_categorize_authentication_error(self):
        """Test categorizing authentication errors."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}
        
        error = httpx.HTTPStatusError("Unauthorized", request=None, response=mock_response)
        error_info = handler.categorize_error(error, "test_operation")
        
        assert error_info["error_type"] == "authentication_error"
        assert error_info["retryable"] is False
    
    def test_categorize_rate_limit_error(self):
        """Test categorizing rate limit errors."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}
        
        error = httpx.HTTPStatusError("Rate limited", request=None, response=mock_response)
        error_info = handler.categorize_error(error, "test_operation")
        
        assert error_info["error_type"] == "rate_limit_error"
        assert error_info["retryable"] is True
        assert error_info["retry_after_seconds"] == 120
    
    def test_categorize_connection_error(self):
        """Test categorizing connection errors."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        error = httpx.ConnectError("Connection failed")
        error_info = handler.categorize_error(error, "test_operation")
        
        assert error_info["error_type"] == "connection_error"
        assert error_info["retryable"] is True
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        # Retryable errors
        timeout_error = httpx.TimeoutException("Timeout")
        assert handler.should_retry(timeout_error) is True
        
        connection_error = httpx.ConnectError("Connection failed")
        assert handler.should_retry(connection_error) is True
        
        # HTTP status errors
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        server_error = httpx.HTTPStatusError("Server error", request=None, response=mock_response_500)
        assert handler.should_retry(server_error) is True
        
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        rate_limit_error = httpx.HTTPStatusError("Rate limited", request=None, response=mock_response_429)
        assert handler.should_retry(rate_limit_error) is True
        
        # Non-retryable errors
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        auth_error = httpx.HTTPStatusError("Unauthorized", request=None, response=mock_response_401)
        assert handler.should_retry(auth_error) is False
        
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        not_found_error = httpx.HTTPStatusError("Not found", request=None, response=mock_response_404)
        assert handler.should_retry(not_found_error) is False
    
    def test_get_retry_delay(self):
        """Test exponential backoff delay calculation."""
        metrics = SimpleMetrics()
        handler = SimpleErrorHandler(metrics)
        
        # Test exponential backoff: base_delay * (2 ** attempt)
        assert handler.get_retry_delay(0, 1.0) == 1.0  # 1.0 * 2^0
        assert handler.get_retry_delay(1, 1.0) == 2.0  # 1.0 * 2^1
        assert handler.get_retry_delay(2, 1.0) == 4.0  # 1.0 * 2^2
        assert handler.get_retry_delay(3, 1.0) == 8.0  # 1.0 * 2^3
        
        # Test with different base delay
        assert handler.get_retry_delay(1, 0.5) == 1.0  # 0.5 * 2^1


class TestRetryDecorator:
    """Test the with_retry_and_error_handling decorator."""
    
    @pytest.mark.asyncio
    async def test_successful_function_no_retries(self):
        """Test decorator with successful function (no retries needed)."""
        
        @with_retry_and_error_handling(max_retries=3)
        async def successful_function():
            return {"success": True, "data": "test"}
        
        result = await successful_function()
        
        assert result == {"success": True, "data": "test"}
    
    @pytest.mark.asyncio
    async def test_function_with_retryable_error_then_success(self):
        """Test decorator with retryable error followed by success."""
        call_count = 0
        
        @with_retry_and_error_handling(max_retries=3, base_delay=0.01)  # Very short delay for testing
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:  # Fail first 2 times
                raise httpx.TimeoutException("Timeout")
            return {"success": True, "attempt": call_count}
        
        result = await flaky_function()
        
        assert result == {"success": True, "attempt": 3}
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_function_with_non_retryable_error(self):
        """Test decorator with non-retryable error."""
        
        @with_retry_and_error_handling(max_retries=3, base_delay=0.01)
        async def auth_error_function():
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.headers = {}
            raise httpx.HTTPStatusError("Unauthorized", request=None, response=mock_response)
        
        result = await auth_error_function()
        
        assert result["error"] is True
        assert result["attempts_made"] == 1  # Should not retry
        assert result["details"]["error_type"] == "authentication_error"
    
    @pytest.mark.asyncio
    async def test_function_exceeds_max_retries(self):
        """Test decorator when function exceeds max retries."""
        
        @with_retry_and_error_handling(max_retries=2, base_delay=0.01)
        async def always_fails_function():
            raise httpx.TimeoutException("Always timeout")
        
        result = await always_fails_function()
        
        assert result["error"] is True
        assert result["attempts_made"] == 3  # Initial + 2 retries
        assert result["max_retries"] == 2
        assert result["details"]["error_type"] == "timeout"


class TestAuthProvider:
    """Test authentication provider creation."""
    
    def test_auth_provider_disabled(self):
        """Test auth provider when authentication is disabled."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            provider = create_auth_provider()
            assert provider is None
    
    def test_auth_provider_jwt(self):
        """Test JWT auth provider creation."""
        with patch.dict(os.environ, {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "jwt",
            "FASTMCP_AUTH_JWT_SECRET": "test-secret",
            "FASTMCP_AUTH_ISSUER": "test-issuer",
            "FASTMCP_AUTH_AUDIENCE": "test-audience"
        }):
            with patch('openapi_server_simplified.JWTVerifier') as mock_jwt:
                provider = create_auth_provider()
                mock_jwt.assert_called_once()
    
    def test_auth_provider_github(self):
        """Test GitHub auth provider creation."""
        with patch.dict(os.environ, {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "github",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID": "test-client-id",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET": "test-secret"
        }):
            with patch('openapi_server_simplified.GitHubProvider') as mock_github:
                provider = create_auth_provider()
                mock_github.assert_called_once()


class TestIntegration:
    """Integration tests for the simplified server."""
    
    @pytest.fixture
    def mock_openapi_spec(self):
        """Mock OpenAPI specification."""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "test_operation",
                        "summary": "Test operation",
                    }
                }
            }
        }
    
    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables."""
        return {
            "API_BASE_URL": "https://test-api.example.com",
            "API_TOKEN": "test-token",
            "AUTH_ENABLED": "false",
            "RATE_LIMIT_REQUESTS_PER_MINUTE": "60",
            "RATE_LIMIT_BURST_SIZE": "10",
            "CACHE_MAX_SIZE": "1000",
            "CACHE_TTL_SECONDS": "300",
            "CONNECTION_POOL_SIZE": "20",
            "API_TIMEOUT": "30"
        }
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(self, mock_openapi_spec, mock_environment):
        """Test full integration flow with all components."""
        with patch.dict(os.environ, mock_environment):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_openapi_spec)
                
                # Import the simplified server module
                import openapi_server_simplified
                
                # Test that components are initialized
                assert hasattr(openapi_server_simplified, 'rate_limiter')
                assert hasattr(openapi_server_simplified, 'metrics')
                assert hasattr(openapi_server_simplified, 'cache')
                assert hasattr(openapi_server_simplified, 'http_client')
                assert hasattr(openapi_server_simplified, 'mcp')


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
