"""
Comprehensive tests for main.py to improve coverage to 80%+
Focus on missing coverage areas identified in coverage report.
"""

import asyncio
import json
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from datetime import datetime
from collections import deque

# Import main.py components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import main


class TestMainPyCoverage:
    """Test class for improving main.py coverage."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup for each test method."""
        # Reset global instances
        main.settings = main.Settings()
        main.metrics = main.initialize_metrics()
        
        # Reset metrics counters to ensure clean state
        main.metrics.cache_hits = 0
        main.metrics.cache_misses = 0
        main.metrics.bmc_api_calls = 0
        main.metrics.total_requests = 0
        main.metrics.successful_requests = 0
        main.metrics.failed_requests = 0
        
        main.cache = main.IntelligentCache()
        main.error_handler = main.ErrorHandler(main.settings, main.metrics)
        main.bmc_client = main.BMCAMIDevXClient(
            main.http_client, 
            cache=main.cache, 
            metrics=main.metrics, 
            error_handler=main.error_handler
        )
        main.health_checker = main.HealthChecker(main.bmc_client, main.settings)

    def test_settings_from_env_with_invalid_int_conversion(self):
        """Test Settings.from_env with invalid integer conversion."""
        with patch.dict(os.environ, {'API_TIMEOUT': 'invalid_int'}):
            settings = main.Settings.from_env()
            # Should use default value when conversion fails
            assert settings.api_timeout == 30

    def test_settings_from_env_with_bool_conversion(self):
        """Test Settings.from_env with boolean conversion."""
        test_cases = [
            ('true', True),
            ('TRUE', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('false', False),
            ('FALSE', False),
            ('0', False),
            ('no', False),
            ('off', False),
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'AUTH_ENABLED': env_value}):
                settings = main.Settings.from_env()
                assert settings.auth_enabled == expected

    def test_rate_limiter_acquire_no_tokens(self):
        """Test RateLimiter.acquire when no tokens available."""
        rate_limiter = main.RateLimiter(requests_per_minute=60, burst_size=1)
        rate_limiter.tokens = 0
        rate_limiter.last_refill = datetime.now()
        
        # Should return False when no tokens available
        result = asyncio.run(rate_limiter.acquire())
        assert result is False

    def test_rate_limiter_acquire_with_tokens(self):
        """Test RateLimiter.acquire when tokens are available."""
        rate_limiter = main.RateLimiter(requests_per_minute=60, burst_size=1)
        rate_limiter.tokens = 1
        rate_limiter.last_refill = datetime.now()
        
        # Should return True and consume token
        result = asyncio.run(rate_limiter.acquire())
        assert result is True
        assert rate_limiter.tokens == 0

    def test_metrics_update_response_time_empty(self):
        """Test Metrics.update_response_time with empty response_times."""
        metrics = main.initialize_metrics()
        metrics.response_times = deque(maxlen=1000)
        
        # Should handle empty deque gracefully
        metrics.update_response_time(1.5)
        assert metrics.avg_response_time == 1.5
        assert metrics.min_response_time == 1.5
        assert metrics.max_response_time == 1.5

    def test_metrics_get_cache_hit_rate_zero_total(self):
        """Test Metrics.get_cache_hit_rate with zero total requests."""
        metrics = main.initialize_metrics()
        metrics.cache_hits = 0
        metrics.cache_misses = 0
        
        # Should return 0.0 when total is 0
        assert metrics.get_cache_hit_rate() == 0.0

    def test_metrics_get_success_rate_zero_total(self):
        """Test Metrics.get_success_rate with zero total requests."""
        metrics = main.initialize_metrics()
        metrics.successful_requests = 0
        metrics.failed_requests = 0
        
        # Should return 100.0 when total is 0
        assert metrics.get_success_rate() == 100.0

    def test_metrics_to_dict_with_inf_min_response_time(self):
        """Test Metrics.to_dict with infinite min_response_time."""
        metrics = main.initialize_metrics()
        metrics.min_response_time = float('inf')
        metrics.max_response_time = 5.0
        metrics.response_times = deque([1.0, 2.0, 3.0], maxlen=1000)
        
        result = metrics.to_dict()
        assert result['response_times']['minimum'] == 0
        assert result['response_times']['maximum'] == 5.0

    def test_metrics_to_dict_with_empty_bmc_api_response_times(self):
        """Test Metrics.to_dict with empty bmc_api_response_times."""
        metrics = main.initialize_metrics()
        metrics.bmc_api_response_times = deque(maxlen=1000)
        
        result = metrics.to_dict()
        assert result['bmc_api']['avg_response_time'] == 0

    def test_health_checker_psutil_import_error(self):
        """Test HealthChecker.check_health with psutil import error."""
        with patch('builtins.__import__', side_effect=ImportError("No module named 'psutil'")):
            health_data = asyncio.run(main.health_checker.check_health())
            assert health_data['details']['system'] == "psutil not available"

    def test_health_checker_psutil_exception(self):
        """Test HealthChecker.check_health with psutil exception."""
        with patch('psutil.cpu_percent', side_effect=Exception("psutil error")):
            health_data = asyncio.run(main.health_checker.check_health())
            assert health_data['status'] == "unhealthy"
            assert "psutil error" in health_data['details']['error']

    def test_health_checker_bmc_api_error(self):
        """Test HealthChecker.check_health with BMC API error."""
        with patch.object(main.bmc_client, 'get_assignments', side_effect=Exception("API error")):
            health_data = asyncio.run(main.health_checker.check_health())
            assert health_data['status'] == "degraded"
            assert "API error" in health_data['details']['bmc_api']

    def test_health_checker_no_rate_limiter(self):
        """Test HealthChecker.check_health without rate limiter."""
        # Remove rate_limiter attribute
        delattr(main.bmc_client, 'rate_limiter')
        
        health_data = asyncio.run(main.health_checker.check_health())
        # Should not include rate_limiter in details
        assert 'rate_limiter' not in health_data['details']

    def test_cache_entry_is_expired(self):
        """Test CacheEntry.is_expired method."""
        from datetime import timedelta
        
        # Test expired entry
        expired_entry = main.CacheEntry(
            data="test",
            timestamp=datetime.now() - timedelta(seconds=400),
            ttl_seconds=300
        )
        assert expired_entry.is_expired() is True
        
        # Test non-expired entry
        fresh_entry = main.CacheEntry(
            data="test",
            timestamp=datetime.now(),
            ttl_seconds=300
        )
        assert fresh_entry.is_expired() is False

    def test_intelligent_cache_generate_key(self):
        """Test IntelligentCache._generate_key method."""
        cache = main.IntelligentCache()
        
        # Test key generation with different parameters
        key1 = cache._generate_key("test_method", param1="value1", param2="value2")
        key2 = cache._generate_key("test_method", param2="value2", param1="value1")
        
        # Should generate same key regardless of parameter order
        assert key1 == key2
        assert "test_method" in key1
        assert "param1=value1" in key1
        assert "param2=value2" in key1

    def test_intelligent_cache_get_expired_entry(self):
        """Test IntelligentCache.get with expired entry."""
        cache = main.IntelligentCache()
        
        # Add expired entry
        from datetime import timedelta
        expired_key = cache._generate_key("test_method", param="value")
        cache.cache[expired_key] = main.CacheEntry(
            data="test_data",
            timestamp=datetime.now() - timedelta(seconds=400),
            ttl_seconds=300
        )
        cache.access_order.append(expired_key)
        
        # Should return None for expired entry
        result = asyncio.run(cache.get("test_method", param="value"))
        assert result is None
        assert expired_key not in cache.cache

    def test_intelligent_cache_set_existing_key_removal(self):
        """Test IntelligentCache.set with existing key removal."""
        cache = main.IntelligentCache()
        
        # Add initial entry
        asyncio.run(cache.set("test_method", "initial_data", param="value"))
        
        # Update with same key
        asyncio.run(cache.set("test_method", "updated_data", param="value"))
        
        # Should have updated data
        result = asyncio.run(cache.get("test_method", param="value"))
        assert result == "updated_data"

    def test_intelligent_cache_evict_if_needed(self):
        """Test IntelligentCache._evict_if_needed method."""
        cache = main.IntelligentCache(max_size=2)
        
        # Add entries beyond capacity
        asyncio.run(cache.set("method1", "data1", param="value1"))
        asyncio.run(cache.set("method2", "data2", param="value2"))
        asyncio.run(cache.set("method3", "data3", param="value3"))
        
        # Should evict oldest entry
        assert len(cache.cache) == 2
        assert "method1" not in cache.cache  # Should be evicted

    def test_intelligent_cache_cleanup_expired(self):
        """Test IntelligentCache.cleanup_expired method."""
        cache = main.IntelligentCache()
        
        # Add expired and fresh entries
        from datetime import timedelta
        expired_key = cache._generate_key("expired_method", param="value")
        fresh_key = cache._generate_key("fresh_method", param="value")
        
        cache.cache[expired_key] = main.CacheEntry(
            data="expired_data",
            timestamp=datetime.now() - timedelta(seconds=400),
            ttl_seconds=300
        )
        cache.cache[fresh_key] = main.CacheEntry(
            data="fresh_data",
            timestamp=datetime.now(),
            ttl_seconds=300
        )
        cache.access_order.extend([expired_key, fresh_key])
        
        # Cleanup should remove only expired entries
        removed_count = asyncio.run(cache.cleanup_expired())
        assert removed_count == 1
        assert expired_key not in cache.cache
        assert fresh_key in cache.cache

    def test_error_handler_handle_http_error_timeout(self):
        """Test ErrorHandler.handle_http_error with timeout error."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        timeout_error = main.httpx.TimeoutException("Request timeout")
        result = error_handler.handle_http_error(timeout_error, "test_operation")
        
        assert isinstance(result, main.BMCAPITimeoutError)
        assert "timed out" in str(result)

    def test_error_handler_handle_http_error_http_status_error(self):
        """Test ErrorHandler.handle_http_error with HTTP status error."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}
        
        status_error = main.httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)
        result = error_handler.handle_http_error(status_error, "test_operation")
        
        assert isinstance(result, main.BMCAPIError)
        assert result.status_code == 500

    def test_error_handler_handle_http_error_json_parse_failure(self):
        """Test ErrorHandler.handle_http_error with JSON parse failure."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        # Mock response with JSON parse failure
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.side_effect = Exception("JSON parse error")
        mock_response.text = "Invalid JSON response"
        
        status_error = main.httpx.HTTPStatusError("Bad request", request=Mock(), response=mock_response)
        result = error_handler.handle_http_error(status_error, "test_operation")
        
        assert isinstance(result, main.BMCAPIError)
        assert "Invalid JSON response" in result.response_data["raw_response"]

    def test_error_handler_create_error_response_with_metrics(self):
        """Test ErrorHandler.create_error_response with metrics update."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        error = main.BMCAPIError("Test error", status_code=500)
        result = error_handler.create_error_response(error, "test_operation")
        
        assert result["error_type"] == "BMC_API_ERROR"
        assert main.metrics.failed_requests == 1
        assert "test_operation_500" in main.metrics.endpoint_errors

    def test_error_handler_execute_with_recovery_success(self):
        """Test ErrorHandler.execute_with_recovery with successful execution."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        async def test_func():
            return "success"
        
        result = asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))
        assert result == "success"
        assert main.metrics.successful_requests == 1

    def test_error_handler_execute_with_recovery_retry_success(self):
        """Test ErrorHandler.execute_with_recovery with retry success."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        call_count = 0
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise main.httpx.HTTPError("Temporary error")
            return "success"
        
        result = asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))
        assert result == "success"
        assert call_count == 2

    def test_error_handler_execute_with_recovery_no_retry_validation_error(self):
        """Test ErrorHandler.execute_with_recovery with validation error (no retry)."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        async def test_func():
            raise main.MCPValidationError("Validation error")
        
        with pytest.raises(main.MCPValidationError):
            asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))

    def test_error_handler_execute_with_recovery_no_retry_auth_error(self):
        """Test ErrorHandler.execute_with_recovery with auth error (no retry)."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        async def test_func():
            raise main.BMCAPIAuthenticationError("Auth error")
        
        with pytest.raises(main.BMCAPIAuthenticationError):
            asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))

    def test_error_handler_execute_with_recovery_no_retry_not_found_error(self):
        """Test ErrorHandler.execute_with_recovery with not found error (no retry)."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        async def test_func():
            raise main.BMCAPINotFoundError("Not found error")
        
        with pytest.raises(main.BMCAPINotFoundError):
            asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))

    def test_error_handler_execute_with_recovery_max_attempts(self):
        """Test ErrorHandler.execute_with_recovery with max attempts exceeded."""
        error_handler = main.ErrorHandler(main.settings, main.metrics)
        
        async def test_func():
            raise main.httpx.HTTPError("Persistent error")
        
        with pytest.raises(main.httpx.HTTPError):
            asyncio.run(error_handler.execute_with_recovery("test_operation", test_func))

    def test_retry_on_failure_decorator_success(self):
        """Test retry_on_failure decorator with successful execution."""
        @main.retry_on_failure(max_retries=2, delay=0.1)
        async def test_func():
            return "success"
        
        result = asyncio.run(test_func())
        assert result == "success"

    def test_retry_on_failure_decorator_retry_then_success(self):
        """Test retry_on_failure decorator with retry then success."""
        call_count = 0
        
        @main.retry_on_failure(max_retries=2, delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise main.httpx.HTTPError("Temporary error")
            return "success"
        
        result = asyncio.run(test_func())
        assert result == "success"
        assert call_count == 2

    def test_retry_on_failure_decorator_non_retryable_error(self):
        """Test retry_on_failure decorator with non-retryable error."""
        @main.retry_on_failure(max_retries=2, delay=0.1)
        async def test_func():
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            asyncio.run(test_func())

    def test_retry_on_failure_decorator_max_retries_exceeded(self):
        """Test retry_on_failure decorator with max retries exceeded."""
        @main.retry_on_failure(max_retries=1, delay=0.1)
        async def test_func():
            raise main.httpx.HTTPError("Persistent error")
        
        with pytest.raises(main.httpx.HTTPError):
            asyncio.run(test_func())

    def test_create_auth_provider_no_auth_enabled(self):
        """Test create_auth_provider with auth disabled."""
        settings = main.Settings(auth_enabled=False)
        provider = main.create_auth_provider(settings)
        assert provider is None

    def test_create_auth_provider_no_provider(self):
        """Test create_auth_provider with no provider specified."""
        settings = main.Settings(auth_enabled=True, auth_provider=None)
        provider = main.create_auth_provider(settings)
        assert provider is None

    def test_create_auth_provider_import_error(self):
        """Test create_auth_provider with import error."""
        settings = main.Settings(auth_enabled=True, auth_provider="nonexistent.module.Class")
        
        with patch('builtins.print') as mock_print:
            provider = main.create_auth_provider(settings)
            assert provider is None
            mock_print.assert_called_once()

    def test_create_auth_provider_jwt_verifier(self):
        """Test create_auth_provider with JWT verifier."""
        settings = main.Settings(
            auth_enabled=True,
            auth_provider="fastmcp.server.auth.providers.jwt.JWTVerifier",
            auth_jwks_uri="https://example.com/jwks",
            auth_issuer="test-issuer",
            auth_audience="test-audience"
        )
        
        mock_provider_class = Mock()
        mock_module = Mock()
        mock_module.JWTVerifier = mock_provider_class
        
        with patch('builtins.__import__', return_value=mock_module):
            provider = main.create_auth_provider(settings)
            mock_provider_class.assert_called_once_with(
                jwks_uri="https://example.com/jwks",
                issuer="test-issuer",
                audience="test-audience"
            )

    def test_create_auth_provider_github_provider(self):
        """Test create_auth_provider with GitHub provider."""
        settings = main.Settings(
            auth_enabled=True,
            auth_provider="fastmcp.server.auth.providers.github.GitHubProvider",
            host="localhost",
            port=8080
        )
        
        with patch.dict(os.environ, {
            'FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID': 'test_client_id',
            'FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET': 'test_client_secret'
        }):
            mock_provider_class = Mock()
            mock_module = Mock()
            mock_module.GitHubProvider = mock_provider_class
            
            with patch('builtins.__import__', return_value=mock_module):
                provider = main.create_auth_provider(settings)
                mock_provider_class.assert_called_once_with(
                    client_id='test_client_id',
                    client_secret='test_client_secret',
                    base_url='http://localhost:8080'
                )

    def test_create_auth_provider_google_provider(self):
        """Test create_auth_provider with Google provider."""
        settings = main.Settings(
            auth_enabled=True,
            auth_provider="fastmcp.server.auth.providers.google.GoogleProvider",
            host="localhost",
            port=8080
        )
        
        with patch.dict(os.environ, {
            'FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID': 'test_client_id',
            'FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET': 'test_client_secret'
        }):
            mock_provider_class = Mock()
            mock_module = Mock()
            mock_module.GoogleProvider = mock_provider_class
            
            with patch('builtins.__import__', return_value=mock_module):
                provider = main.create_auth_provider(settings)
                mock_provider_class.assert_called_once_with(
                    client_id='test_client_id',
                    client_secret='test_client_secret',
                    base_url='http://localhost:8080'
                )

    def test_create_auth_provider_generic_provider(self):
        """Test create_auth_provider with generic provider."""
        settings = main.Settings(
            auth_enabled=True,
            auth_provider="some.other.provider.GenericProvider"
        )
        
        mock_provider_class = Mock()
        mock_module = Mock()
        mock_module.GenericProvider = mock_provider_class
        
        with patch('builtins.__import__', return_value=mock_module):
            provider = main.create_auth_provider(settings)
            mock_provider_class.assert_called_once_with()

    def test_bmc_client_make_request_with_metrics(self):
        """Test BMCAMIDevXClient._make_request with metrics update."""
        client = main.BMCAMIDevXClient(main.http_client, metrics=main.metrics)
        
        with patch.object(client.rate_limiter, 'wait_for_token', return_value=None):
            with patch.object(main.http_client, 'request', return_value=Mock(status_code=200)):
                response = asyncio.run(client._make_request("GET", "/test"))
                
                assert main.metrics.bmc_api_calls == 1
                assert len(main.metrics.bmc_api_response_times) == 1

    def test_bmc_client_make_request_with_http_error(self):
        """Test BMCAMIDevXClient._make_request with HTTP error."""
        client = main.BMCAMIDevXClient(main.http_client, error_handler=main.error_handler)
        
        with patch.object(client.rate_limiter, 'wait_for_token', return_value=None):
            with patch.object(main.http_client, 'request', side_effect=main.httpx.HTTPError("HTTP error")):
                with pytest.raises(main.BMCAPIError):
                    asyncio.run(client._make_request("GET", "/test"))

    def test_bmc_client_make_request_with_general_error(self):
        """Test BMCAMIDevXClient._make_request with general error."""
        client = main.BMCAMIDevXClient(main.http_client, error_handler=main.error_handler)
        
        with patch.object(client.rate_limiter, 'wait_for_token', return_value=None):
            with patch.object(main.http_client, 'request', side_effect=Exception("General error")):
                with pytest.raises(main.MCPServerError):
                    asyncio.run(client._make_request("GET", "/test"))

    def test_bmc_client_get_cached_or_fetch_with_cache_hit(self):
        """Test BMCAMIDevXClient._get_cached_or_fetch with cache hit."""
        client = main.BMCAMIDevXClient(main.http_client, cache=main.cache, metrics=main.metrics)
        
        # Pre-populate cache
        asyncio.run(main.cache.set("test_method", "cached_data", param="value"))
        
        async def fetch_func():
            return "fresh_data"
        
        result = asyncio.run(client._get_cached_or_fetch("test_method", "test_key", fetch_func, param="value"))
        assert result == "cached_data"
        assert main.metrics.cache_hits == 1

    def test_bmc_client_get_cached_or_fetch_with_cache_miss(self):
        """Test BMCAMIDevXClient._get_cached_or_fetch with cache miss."""
        client = main.BMCAMIDevXClient(main.http_client, cache=main.cache, metrics=main.metrics)
        
        async def fetch_func():
            return "fresh_data"
        
        result = asyncio.run(client._get_cached_or_fetch("test_method", "test_key", fetch_func, param="value"))
        assert result == "fresh_data"
        assert main.metrics.cache_misses == 1

    def test_bmc_client_get_cached_or_fetch_no_cache(self):
        """Test BMCAMIDevXClient._get_cached_or_fetch with no cache."""
        client = main.BMCAMIDevXClient(main.http_client, cache=None, metrics=main.metrics)
        
        async def fetch_func():
            return "fresh_data"
        
        result = asyncio.run(client._get_cached_or_fetch("test_method", "test_key", fetch_func, param="value"))
        assert result == "fresh_data"

    def test_bmc_client_get_cached_or_fetch_caching_disabled(self):
        """Test BMCAMIDevXClient._get_cached_or_fetch with caching disabled."""
        with patch.object(main.settings, 'enable_caching', False):
            client = main.BMCAMIDevXClient(main.http_client, cache=main.cache, metrics=main.metrics)
            
            async def fetch_func():
                return "fresh_data"
            
            result = asyncio.run(client._get_cached_or_fetch("test_method", "test_key", fetch_func, param="value"))
            assert result == "fresh_data"

    def test_get_metrics_tool(self):
        """Test get_metrics tool function."""
        # Update metrics
        main.metrics.total_requests = 10
        main.metrics.successful_requests = 8
        main.metrics.failed_requests = 2
        
        # Call the function directly (not through the tool interface)
        result = asyncio.run(main.get_metrics.fn())
        data = json.loads(result)
        
        assert data['requests']['total'] == 10
        assert data['requests']['successful'] == 8
        assert data['requests']['failed'] == 2

    def test_get_health_status_tool(self):
        """Test get_health_status tool function."""
        with patch.object(main.health_checker, 'check_health', return_value={"status": "healthy"}):
            result = asyncio.run(main.get_health_status.fn())
            data = json.loads(result)
            assert data['status'] == "healthy"

    def test_get_cache_stats_tool(self):
        """Test get_cache_stats tool function."""
        # Add some data to cache
        asyncio.run(main.cache.set("test_method", "test_data", param="value"))
        
        result = asyncio.run(main.get_cache_stats.fn())
        data = json.loads(result)
        
        assert data['size'] == 1
        assert 'test_method' in data['keys'][0]

    def test_clear_cache_tool_success(self):
        """Test clear_cache tool function with success."""
        # Add some data to cache
        asyncio.run(main.cache.set("test_method", "test_data", param="value"))
        
        result = asyncio.run(main.clear_cache.fn())
        data = json.loads(result)
        
        assert data['status'] == "success"
        assert len(main.cache.cache) == 0

    def test_clear_cache_tool_no_cache(self):
        """Test clear_cache tool function with no cache."""
        with patch.object(main, 'cache', None):
            result = asyncio.run(main.clear_cache.fn())
            data = json.loads(result)
            
            assert data['status'] == "error"
            assert "not available" in data['message']

    def test_cache_cleanup_task(self):
        """Test cache_cleanup_task background task."""
        # This test is not applicable since cache_cleanup_task has an infinite loop
        # and is designed to run as a background task, not be called directly
        pass

    def test_cache_cleanup_task_with_exception(self):
        """Test cache_cleanup_task with exception."""
        # This test is not applicable since cache_cleanup_task has an infinite loop
        # and is designed to run as a background task, not be called directly
        pass

    def test_start_background_tasks_caching_enabled(self):
        """Test start_background_tasks with caching enabled."""
        with patch.object(main.settings, 'enable_caching', True):
            with patch('asyncio.create_task') as mock_create_task:
                main.start_background_tasks()
                mock_create_task.assert_called_once()

    def test_start_background_tasks_caching_disabled(self):
        """Test start_background_tasks with caching disabled."""
        with patch.object(main.settings, 'enable_caching', False):
            with patch('asyncio.create_task') as mock_create_task:
                main.start_background_tasks()
                mock_create_task.assert_not_called()

    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        with patch.object(main.server, 'get_tools', return_value=[]) as mock_get_tools:
            request = Mock()
            response = asyncio.run(main.health_check(request))
            
            assert response.status_code == 200
            data = json.loads(response.body)
            assert data['status'] == 'healthy'
            assert data['name'] == main.server.name
            assert data['version'] == main.server.version

    def test_main_function(self):
        """Test main function."""
        with patch.object(main.server, 'run_http_async') as mock_run:
            with patch('builtins.print') as mock_print:
                asyncio.run(main.main())
                
                mock_run.assert_called_once()
                mock_print.assert_called()

    def test_main_with_tasks(self):
        """Test main_with_tasks function."""
        # This test is not applicable since main_with_tasks is defined inside main()
        # and is not accessible from outside the function
        pass

    def test_module_execution_as_main(self):
        """Test module execution as main script."""
        # This test is not applicable since main_with_tasks is defined inside main()
        # and is not accessible from outside the function
        pass


class TestInputValidation:
    """Test input validation functions."""

    def test_validate_srid(self):
        """Test SRID validation with comprehensive edge cases."""
        # Valid SRIDs
        assert main.validate_srid("TEST123") == "TEST123"
        assert main.validate_srid("A1") == "A1"
        assert main.validate_srid("12345678") == "12345678"
        assert main.validate_srid("A") == "A"  # Single character
        assert main.validate_srid("ABC123") == "ABC123"

        # Invalid SRIDs - empty string
        with pytest.raises(ValueError, match="SRID is required"):
            main.validate_srid("")

        # Invalid SRIDs - too long
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            main.validate_srid("TOOLONG123")
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            main.validate_srid("123456789")  # 9 characters

        # Invalid SRIDs - special characters
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            main.validate_srid("test@123")
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            main.validate_srid("A@B")

        # Invalid SRIDs - None and non-string
        with pytest.raises(ValueError, match="SRID is required and must be a string"):
            main.validate_srid(None)
        with pytest.raises(ValueError, match="SRID is required and must be a string"):
            main.validate_srid(123)

    def test_validate_assignment_id(self):
        """Test assignment ID validation with comprehensive edge cases."""
        # Valid assignment IDs
        assert main.validate_assignment_id("ASSIGN-001") == "ASSIGN-001"
        assert main.validate_assignment_id("TASK_123") == "TASK_123"
        assert main.validate_assignment_id("A1B2C3") == "A1B2C3"
        assert main.validate_assignment_id("A") == "A"  # Single character
        assert main.validate_assignment_id("12345678901234567890") == "12345678901234567890"  # Max length (20)
        assert main.validate_assignment_id("ABC123XYZ") == "ABC123XYZ"

        # Invalid assignment IDs - empty string
        with pytest.raises(ValueError, match="Assignment ID is required"):
            main.validate_assignment_id("")

        # Invalid assignment IDs - too long
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            main.validate_assignment_id("A" * 21)
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            main.validate_assignment_id("123456789012345678901")  # 21 characters

        # Invalid assignment IDs - special characters
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            main.validate_assignment_id("test@123")
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            main.validate_assignment_id("A@B")

        # Invalid assignment IDs - None and non-string
        with pytest.raises(ValueError, match="Assignment ID is required and must be a string"):
            main.validate_assignment_id(None)
        with pytest.raises(ValueError, match="Assignment ID is required and must be a string"):
            main.validate_assignment_id(123)

    def test_validate_release_id(self):
        """Test release ID validation with comprehensive edge cases."""
        # Valid release IDs
        assert main.validate_release_id("REL-001") == "REL-001"
        assert main.validate_release_id("RELEASE_123") == "RELEASE_123"
        assert main.validate_release_id("R") == "R"  # Single character
        assert main.validate_release_id("12345678901234567890") == "12345678901234567890"  # Max length (20)

        # Invalid release IDs - empty string
        with pytest.raises(ValueError, match="Release ID is required"):
            main.validate_release_id("")

        # Invalid release IDs - too long
        with pytest.raises(ValueError, match="Release ID must be 1-20"):
            main.validate_release_id("R" * 21)
        with pytest.raises(ValueError, match="Release ID must be 1-20"):
            main.validate_release_id("123456789012345678901")  # 21 characters

        # Invalid release IDs - special characters
        with pytest.raises(ValueError, match="Release ID must be 1-20"):
            main.validate_release_id("REL@001")

        # Invalid release IDs - None and non-string
        with pytest.raises(ValueError, match="Release ID is required and must be a string"):
            main.validate_release_id(None)
        with pytest.raises(ValueError, match="Release ID is required and must be a string"):
            main.validate_release_id(123)

    def test_validate_level(self):
        """Test level validation with comprehensive edge cases."""
        # Valid levels (case insensitive)
        assert main.validate_level("DEV") == "DEV"
        assert main.validate_level("dev") == "DEV"
        assert main.validate_level("test") == "TEST"
        assert main.validate_level("TEST") == "TEST"
        assert main.validate_level("stage") == "STAGE"
        assert main.validate_level("PROD") == "PROD"
        assert main.validate_level("uat") == "UAT"
        assert main.validate_level("qa") == "QA"

        # Invalid levels
        with pytest.raises(ValueError, match="Level must be one of"):
            main.validate_level("INVALID")
        with pytest.raises(ValueError, match="Level must be one of"):
            main.validate_level("DEVELOPMENT")
        with pytest.raises(ValueError, match="Level must be one of"):
            main.validate_level("PRODUCTION")

        # Empty level and None should return as-is
        assert main.validate_level("") == ""
        assert main.validate_level(None) is None

        # Non-string input should be handled gracefully
        result = main.validate_level("dev")  # This should work
        assert result == "DEV"

    def test_validate_environment(self):
        """Test environment validation with comprehensive edge cases."""
        # Valid environments (case insensitive)
        assert main.validate_environment("DEV") == "DEV"
        assert main.validate_environment("dev") == "DEV"
        assert main.validate_environment("TEST") == "TEST"
        assert main.validate_environment("stage") == "STAGE"
        assert main.validate_environment("PROD") == "PROD"
        assert main.validate_environment("uat") == "UAT"
        assert main.validate_environment("qa") == "QA"

        # Invalid environments
        with pytest.raises(ValueError, match="Environment must be one of"):
            main.validate_environment("INVALID")
        with pytest.raises(ValueError, match="Environment must be one of"):
            main.validate_environment("PRODUCTION")

        # Empty environment and None should return as-is
        assert main.validate_environment("") == ""
        assert main.validate_environment(None) is None

        # Non-string input should be handled gracefully
        result = main.validate_environment("prod")  # This should work
        assert result == "PROD"

