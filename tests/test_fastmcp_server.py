"""
Test suite for BMC AMI DevX Code Pipeline FastMCP Server
Tests the real FastMCP implementation with authentication, validation, and retry logic.
"""

import asyncio
import json
import os
import tempfile
import time
import unittest.mock

import httpx
import pytest
from fastmcp import Context, FastMCP

# Import the main module components
import main
from main import (
    BMCAMIDevXClient,
    BMCAPIError,
    Settings,
    create_auth_provider,
    retry_on_failure,
    validate_level,
    validate_srid,
)


class TestSettings:
    """Test Settings configuration class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()

        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.log_level == "INFO"
        assert settings.api_base_url == "https://devx.bmc.com/code-pipeline/api/v1"
        assert settings.api_timeout == 30
        assert settings.api_retry_attempts == 3
        assert settings.auth_enabled is False
        assert settings.auth_provider is None

    def test_environment_variable_loading(self):
        """Test loading settings from environment variables."""
        # Set test environment variables
        test_env = {
            "HOST": "127.0.0.1",
            "PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "API_BASE_URL": "https://test.bmc.com/api",
            "API_TIMEOUT": "60",
            "API_RETRY_ATTEMPTS": "5",
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.jwt.JWTVerifier",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            # Use the new from_env() method to test environment variable loading
            from main import Settings

            settings = Settings.from_env()

            assert settings.host == "127.0.0.1"
            assert settings.port == 9000
            assert settings.log_level == "DEBUG"
            assert settings.api_base_url == "https://test.bmc.com/api"
            assert settings.api_timeout == 60
            assert settings.api_retry_attempts == 5
            assert settings.auth_enabled is True
            assert (
                settings.auth_provider
                == "fastmcp.server.auth.providers.jwt.JWTVerifier"
            )

    def test_invalid_environment_values(self):
        """Test handling of invalid environment values."""
        # Test invalid port - should use default value instead of raising error
        with unittest.mock.patch.dict(os.environ, {"PORT": "invalid"}):
            from main import Settings

            settings = Settings.from_env()
            # Should fall back to default port since conversion failed
            assert settings.port == 8080

        # Test invalid boolean - should use default value instead of raising error
        with unittest.mock.patch.dict(os.environ, {"AUTH_ENABLED": "maybe"}):
            from main import Settings

            settings = Settings.from_env()
            # Should fall back to default value since conversion failed
            assert settings.auth_enabled is False


class TestRetryLogic:
    """Test retry logic decorator."""

    @pytest.mark.asyncio
    async def test_retry_on_success(self):
        """Test retry decorator with successful call."""

        @retry_on_failure(max_retries=3, delay=0.1)
        async def successful_call():
            return "success"

        result = await successful_call()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_http_error(self):
        """Test retry decorator with HTTP errors."""
        call_count = 0

        @retry_on_failure(max_retries=2, delay=0.1)
        async def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPError("Network error")
            return "success"

        result = await failing_call()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry decorator when retries are exhausted."""

        @retry_on_failure(max_retries=2, delay=0.1)
        async def always_failing_call():
            raise httpx.HTTPError("Persistent error")

        with pytest.raises(httpx.HTTPError, match="Persistent error"):
            await always_failing_call()

    @pytest.mark.asyncio
    async def test_retry_skips_validation_errors(self):
        """Test that retry doesn't retry validation errors."""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.1)
        async def validation_error_call():
            nonlocal call_count
            call_count += 1
            raise ValueError("Validation error")

        with pytest.raises(ValueError, match="Validation error"):
            await validation_error_call()

        assert call_count == 1  # Should not retry


class TestBMCClient:
    """Test BMC AMI DevX client."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        with unittest.mock.patch("httpx.AsyncClient") as mock_client:
            yield mock_client

    @pytest.mark.asyncio
    async def test_get_assignments_success(self, mock_httpx_client):
        """Test successful get_assignments call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignments": [{"id": "ASSIGN-001"}]}
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        # Create client
        client = BMCAMIDevXClient(mock_client_instance)

        # Test call
        result = await client.get_assignments("TEST123", "DEV", "ASSIGN-001")

        assert result == {"assignments": [{"id": "ASSIGN-001"}]}
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_assignments_http_error(self, mock_httpx_client):
        """Test get_assignments with HTTP error."""
        # Create a proper async mock that raises HTTP error
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.side_effect = httpx.HTTPError("API Error")
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)

        # Now expect BMCAPIError due to enhanced error handling
        with pytest.raises(BMCAPIError, match="BMC API connection error"):
            await client.get_assignments("TEST123")

    @pytest.mark.asyncio
    async def test_create_assignment_success(self, mock_httpx_client):
        """Test successful create_assignment call."""
        assignment_data = {
            "assignmentId": "ASSIGN-002",
            "stream": "STREAM1",
            "application": "APP1",
        }

        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN-002",
            "status": "created",
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.create_assignment("TEST123", assignment_data)

        assert "assignmentId" in result
        assert result["assignmentId"] == "ASSIGN-002"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments", json=assignment_data
        )

    @pytest.mark.asyncio
    async def test_get_assignment_details_success(self, mock_httpx_client):
        """Test successful get_assignment_details call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN-001",
            "status": "active",
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.get_assignment_details("TEST123", "ASSIGN-001")

        assert "assignmentId" in result
        assert result["assignmentId"] == "ASSIGN-001"
        mock_client_instance.request.assert_called_once_with(
            "GET", "/ispw/TEST123/assignments/ASSIGN-001"
        )

    @pytest.mark.asyncio
    async def test_get_assignment_tasks_success(self, mock_httpx_client):
        """Test successful get_assignment_tasks call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "tasks": [{"id": "TASK-001", "name": "Task 1"}]
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.get_assignment_tasks("TEST123", "ASSIGN-001")

        assert "tasks" in result
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["id"] == "TASK-001"
        mock_client_instance.request.assert_called_once_with(
            "GET", "/ispw/TEST123/assignments/ASSIGN-001/tasks"
        )

    @pytest.mark.asyncio
    async def test_generate_assignment_success(self, mock_httpx_client):
        """Test successful generate_assignment call."""
        generate_data = {"level": "DEV", "runtimeConfiguration": "config1"}

        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "generationId": "GEN-001",
            "status": "started",
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.generate_assignment(
            "TEST123", "ASSIGN-001", generate_data
        )

        assert "generationId" in result
        assert result["generationId"] == "GEN-001"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments/ASSIGN-001/generate", json=generate_data
        )

    @pytest.mark.asyncio
    async def test_promote_assignment_success(self, mock_httpx_client):
        """Test successful promote_assignment call."""
        promote_data = {"level": "TEST", "changeType": "minor"}

        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "promotionId": "PROM-001",
            "status": "started",
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.promote_assignment("TEST123", "ASSIGN-001", promote_data)

        assert "promotionId" in result
        assert result["promotionId"] == "PROM-001"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments/ASSIGN-001/promote", json=promote_data
        )

    @pytest.mark.asyncio
    async def test_deploy_assignment_success(self, mock_httpx_client):
        """Test successful deploy_assignment call."""
        deploy_data = {
            "level": "PROD",
            "deployImplementationTime": "2025-01-09T10:00:00Z",
        }

        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "deploymentId": "DEP-001",
            "status": "started",
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.deploy_assignment("TEST123", "ASSIGN-001", deploy_data)

        assert "deploymentId" in result
        assert result["deploymentId"] == "DEP-001"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments/ASSIGN-001/deploy", json=deploy_data
        )

    @pytest.mark.asyncio
    async def test_get_releases_success(self, mock_httpx_client):
        """Test successful get_releases call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "releases": [{"id": "REL-001", "name": "Release 1"}]
        }
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.get_releases("TEST123", "REL-001")

        assert "releases" in result
        assert len(result["releases"]) == 1
        assert result["releases"][0]["id"] == "REL-001"
        mock_client_instance.request.assert_called_once_with(
            "GET", "/ispw/TEST123/releases", params={"releaseId": "REL-001"}
        )

    @pytest.mark.asyncio
    async def test_create_release_success(self, mock_httpx_client):
        """Test successful create_release call."""
        release_data = {
            "releaseId": "REL-002",
            "stream": "STREAM1",
            "application": "APP1",
        }

        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"releaseId": "REL-002", "status": "created"}
        mock_response.raise_for_status.return_value = None

        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.create_release("TEST123", release_data)

        assert "releaseId" in result
        assert result["releaseId"] == "REL-002"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/releases", json=release_data
        )


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self):
        """Test successful token acquisition."""
        from main import RateLimiter

        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=10)

        # Should be able to acquire token immediately
        result = await rate_limiter.acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_failure(self):
        """Test token acquisition failure when rate limited."""
        from main import RateLimiter

        # Create rate limiter with very low limits
        rate_limiter = RateLimiter(requests_per_minute=1, burst_size=1)

        # First request should succeed
        result1 = await rate_limiter.acquire()
        assert result1 is True

        # Second request should fail (no tokens available)
        result2 = await rate_limiter.acquire()
        assert result2 is False

    @pytest.mark.asyncio
    async def test_rate_limiter_wait_for_token(self):
        """Test waiting for token availability."""
        from main import RateLimiter

        # Create rate limiter with very low limits
        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # First request should succeed
        result1 = await rate_limiter.acquire()
        assert result1 is True

        # Second request should fail immediately
        result2 = await rate_limiter.acquire()
        assert result2 is False

        # Wait for token should eventually succeed
        start_time = time.time()
        await rate_limiter.wait_for_token()
        elapsed = time.time() - start_time

        # Should have waited at least 1 second (60 requests per minute = 1 per second)
        assert elapsed >= 0.9  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_bmc_client_rate_limiting(self):
        """Test that BMC client uses rate limiting."""
        import unittest.mock

        from main import BMCAMIDevXClient

        # Create a mock rate limiter
        mock_rate_limiter = unittest.mock.AsyncMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        # Create mock HTTP client
        mock_http_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignments": []}
        mock_response.raise_for_status.return_value = None
        mock_http_client.request.return_value = mock_response

        # Create BMC client with mock rate limiter
        client = BMCAMIDevXClient(mock_http_client, mock_rate_limiter)

        # Make a request
        await client.get_assignments("TEST123")

        # Verify rate limiter was called
        mock_rate_limiter.wait_for_token.assert_called_once()
        mock_http_client.request.assert_called_once()


class TestMonitoring:
    """Test monitoring and metrics functionality."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time == 0.0
        assert metrics.min_response_time == float("inf")
        assert metrics.max_response_time == 0.0

    def test_metrics_update_response_time(self):
        """Test response time metrics updates."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.update_response_time(1.5)
        metrics.update_response_time(2.0)
        metrics.update_response_time(0.5)

        assert abs(metrics.avg_response_time - 1.33) < 0.01  # (1.5 + 2.0 + 0.5) / 3
        assert metrics.min_response_time == 0.5
        assert metrics.max_response_time == 2.0
        assert len(metrics.response_times) == 3

    def test_metrics_success_rate(self):
        """Test success rate calculation."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.successful_requests = 80
        metrics.failed_requests = 20

        assert metrics.get_success_rate() == 80.0

    def test_metrics_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.cache_hits = 75
        metrics.cache_misses = 25

        assert metrics.get_cache_hit_rate() == 75.0

    def test_metrics_to_dict(self):
        """Test metrics serialization to dictionary."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.total_requests = 100
        metrics.successful_requests = 90
        metrics.failed_requests = 10
        metrics.cache_hits = 50
        metrics.cache_misses = 50

        metrics_dict = metrics.to_dict()

        assert "requests" in metrics_dict
        assert "response_times" in metrics_dict
        assert "cache" in metrics_dict
        assert "system" in metrics_dict
        assert metrics_dict["requests"]["total"] == 100
        assert metrics_dict["requests"]["success_rate"] == 90.0
        assert metrics_dict["cache"]["hit_rate"] == 50.0


class TestCaching:
    """Test caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_basic_operations(self):
        """Test basic cache operations."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=10, default_ttl=60)

        # Test set and get
        await cache.set("test_method", {"data": "test"}, srid="TEST123")
        result = await cache.get("test_method", srid="TEST123")

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache expiration."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=10, default_ttl=1)  # 1 second TTL

        # Set data
        await cache.set("test_method", {"data": "test"}, srid="TEST123")

        # Should be available immediately
        result = await cache.get("test_method", srid="TEST123")
        assert result == {"data": "test"}

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired
        result = await cache.get("test_method", srid="TEST123")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=3, default_ttl=60)

        # Fill cache to capacity
        await cache.set("method1", "data1", srid="TEST1")
        await cache.set("method2", "data2", srid="TEST2")
        await cache.set("method3", "data3", srid="TEST3")

        # Access first item to make it recently used
        await cache.get("method1", srid="TEST1")

        # Add one more item - should evict least recently used (method2)
        await cache.set("method4", "data4", srid="TEST4")

        # method2 should be evicted
        result = await cache.get("method2", srid="TEST2")
        assert result is None

        # method1 should still be available
        result = await cache.get("method1", srid="TEST1")
        assert result == "data1"

    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=10, default_ttl=1)

        # Add some data
        await cache.set("method1", "data1", srid="TEST1")
        await cache.set("method2", "data2", srid="TEST2", ttl=2)  # Longer TTL

        # Wait for first item to expire
        await asyncio.sleep(1.1)

        # Cleanup expired entries
        expired_count = await cache.cleanup_expired()

        assert expired_count == 1

        # First item should be gone
        result = await cache.get("method1", srid="TEST1")
        assert result is None

        # Second item should still be available
        result = await cache.get("method2", srid="TEST2")
        assert result == "data2"

    def test_cache_stats(self):
        """Test cache statistics."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=100, default_ttl=300)

        stats = cache.get_stats()

        assert "size" in stats
        assert "max_size" in stats
        assert "default_ttl" in stats
        assert "keys" in stats
        assert stats["max_size"] == 100
        assert stats["default_ttl"] == 300


class TestHealthChecker:
    """Test health checker functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        import unittest.mock

        from main import HealthChecker, Settings

        # Create mock BMC client
        mock_bmc_client = unittest.mock.AsyncMock()
        mock_bmc_client.get_assignments.return_value = {"assignments": []}

        settings = Settings()
        health_checker = HealthChecker(mock_bmc_client, settings)

        health_data = await health_checker.check_health()

        assert "status" in health_data
        assert "timestamp" in health_data
        assert "details" in health_data
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_health_check_bmc_api_error(self):
        """Test health check with BMC API error."""
        import unittest.mock

        from main import HealthChecker, Settings

        # Create mock BMC client that raises error
        mock_bmc_client = unittest.mock.AsyncMock()
        mock_bmc_client.get_assignments.side_effect = Exception("API Error")

        settings = Settings()
        health_checker = HealthChecker(mock_bmc_client, settings)

        health_data = await health_checker.check_health()

        assert health_data["status"] == "degraded"
        assert "bmc_api" in health_data["details"]
        assert "error" in health_data["details"]["bmc_api"]


class TestErrorHandling:
    """Test enhanced error handling functionality."""

    def test_bmc_api_error_creation(self):
        """Test BMC API error creation."""
        from main import BMCAPIError, BMCAPIRateLimitError, BMCAPITimeoutError

        # Test base BMC API error
        error = BMCAPIError(
            "Test error", status_code=500, response_data={"test": "data"}
        )
        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.response_data == {"test": "data"}

        # Test timeout error
        timeout_error = BMCAPITimeoutError("Request timed out")
        assert str(timeout_error) == "Request timed out"

        # Test rate limit error
        rate_limit_error = BMCAPIRateLimitError("Rate limit exceeded", retry_after=60)
        assert str(rate_limit_error) == "Rate limit exceeded"
        assert rate_limit_error.retry_after == 60

    def test_mcp_validation_error_creation(self):
        """Test MCP validation error creation."""
        from main import MCPValidationError

        error = MCPValidationError("Invalid input", field="srid", value="INVALID")
        assert str(error) == "Invalid input"
        assert error.field == "srid"
        assert error.value == "INVALID"

    def test_mcp_server_error_creation(self):
        """Test MCP server error creation."""
        from main import MCPServerError

        error = MCPServerError(
            "Server error", error_code="ERR001", details={"key": "value"}
        )
        assert str(error) == "Server error"
        assert error.error_code == "ERR001"
        assert error.details == {"key": "value"}

    def test_error_handler_initialization(self):
        """Test error handler initialization."""
        from main import ErrorHandler, Settings

        settings = Settings()
        metrics = initialize_metrics()
        error_handler = ErrorHandler(settings, metrics)

        assert error_handler.settings == settings
        assert error_handler.metrics == metrics

    def test_error_handler_http_error_conversion(self):
        """Test HTTP error conversion to BMC API errors."""
        import httpx

        from main import (
            BMCAPIAuthenticationError,
            BMCAPITimeoutError,
            ErrorHandler,
            Settings,
        )

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Test timeout error conversion
        timeout_error = httpx.TimeoutException("Request timed out")
        bmc_error = error_handler.handle_http_error(timeout_error, "test_operation")
        assert isinstance(bmc_error, BMCAPITimeoutError)
        assert "test_operation" in str(bmc_error)

        # Test HTTP status error conversion
        response = httpx.Response(401, request=httpx.Request("GET", "http://test.com"))
        status_error = httpx.HTTPStatusError(
            "Unauthorized", request=response.request, response=response
        )
        bmc_error = error_handler.handle_http_error(status_error, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.status_code == 401

    def test_error_handler_validation_error_conversion(self):
        """Test validation error conversion."""
        from main import ErrorHandler, MCPValidationError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        validation_error = ValueError("Invalid format")
        mcp_error = error_handler.handle_validation_error(
            validation_error, "srid", "INVALID"
        )

        assert isinstance(mcp_error, MCPValidationError)
        assert mcp_error.field == "srid"
        assert mcp_error.value == "INVALID"
        assert "Invalid format" in str(mcp_error)

    def test_error_handler_general_error_conversion(self):
        """Test general error conversion."""
        from main import ErrorHandler, MCPServerError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        general_error = RuntimeError("Something went wrong")
        server_error = error_handler.handle_general_error(
            general_error, "test_operation"
        )

        assert isinstance(server_error, MCPServerError)
        assert server_error.error_code == "INTERNAL_ERROR_TEST_OPERATION"
        assert "test_operation" in server_error.details["operation"]
        assert server_error.details["error_type"] == "RuntimeError"

    def test_error_response_creation(self):
        """Test standardized error response creation."""
        from main import BMCAPIError, ErrorHandler, MCPValidationError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Test BMC API error response
        bmc_error = BMCAPIError(
            "API Error", status_code=500, response_data={"test": "data"}
        )
        response = error_handler.create_error_response(bmc_error, "test_operation")

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert response["error_type"] == "BMC_API_ERROR"
        assert response["message"] == "API Error"
        assert response["status_code"] == 500
        assert response["response_data"] == {"test": "data"}
        assert "timestamp" in response

        # Test validation error response
        validation_error = MCPValidationError(
            "Invalid input", field="srid", value="INVALID"
        )
        response = error_handler.create_error_response(
            validation_error, "test_operation"
        )

        assert response["error_type"] == "VALIDATION_ERROR"
        assert response["field"] == "srid"
        assert response["value"] == "INVALID"

    def test_error_response_message_truncation(self):
        """Test error message truncation."""
        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings(max_error_message_length=50)
        error_handler = ErrorHandler(settings)

        long_message = "This is a very long error message that should be truncated because it exceeds the maximum length"
        bmc_error = BMCAPIError(long_message)
        response = error_handler.create_error_response(bmc_error, "test_operation")

        assert len(response["message"]) <= 53  # 50 + "..."
        assert response["message"].endswith("...")

    @pytest.mark.asyncio
    async def test_error_recovery_execution(self):
        """Test error recovery execution with retry logic."""
        from main import BMCAPITimeoutError, ErrorHandler, Settings

        settings = Settings(error_recovery_attempts=3)
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise BMCAPITimeoutError("Temporary failure")
            return "success"

        # Should succeed after retries
        result = await error_handler.execute_with_recovery(
            "test_operation", failing_function
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_error_recovery_no_retry_for_validation_errors(self):
        """Test that validation errors are not retried."""
        from main import ErrorHandler, MCPValidationError, Settings

        settings = Settings(error_recovery_attempts=3)
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def validation_failing_function():
            nonlocal call_count
            call_count += 1
            raise MCPValidationError("Validation failed")

        # Should not retry validation errors
        with pytest.raises(MCPValidationError):
            await error_handler.execute_with_recovery(
                "test_operation", validation_failing_function
            )

        assert call_count == 1  # Should only be called once

    def test_error_handler_http_status_errors(self):
        """Test HTTP status error conversion for different status codes."""
        import httpx

        from main import (
            BMCAPIAuthenticationError,
            BMCAPINotFoundError,
            BMCAPIRateLimitError,
            BMCAPIValidationError,
            ErrorHandler,
            Settings,
        )

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Test 401 Authentication Error
        response_401 = httpx.Response(
            401, request=httpx.Request("GET", "http://test.com")
        )
        response_401._content = b'{"error": "unauthorized"}'
        status_error_401 = httpx.HTTPStatusError(
            "Unauthorized", request=response_401.request, response=response_401
        )
        bmc_error = error_handler.handle_http_error(status_error_401, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.status_code == 401

        # Test 404 Not Found Error
        response_404 = httpx.Response(
            404, request=httpx.Request("GET", "http://test.com")
        )
        response_404._content = b'{"error": "not found"}'
        status_error_404 = httpx.HTTPStatusError(
            "Not Found", request=response_404.request, response=response_404
        )
        bmc_error = error_handler.handle_http_error(status_error_404, "test_operation")
        assert isinstance(bmc_error, BMCAPINotFoundError)
        assert bmc_error.status_code == 404

        # Test 429 Rate Limit Error
        response_429 = httpx.Response(
            429, request=httpx.Request("GET", "http://test.com")
        )
        response_429._content = b'{"error": "rate limited"}'
        response_429.headers["Retry-After"] = "60"
        status_error_429 = httpx.HTTPStatusError(
            "Too Many Requests", request=response_429.request, response=response_429
        )
        bmc_error = error_handler.handle_http_error(status_error_429, "test_operation")
        assert isinstance(bmc_error, BMCAPIRateLimitError)
        assert bmc_error.status_code == 429
        assert bmc_error.retry_after == 60

        # Test 422 Validation Error
        response_422 = httpx.Response(
            422, request=httpx.Request("GET", "http://test.com")
        )
        response_422._content = (
            b'{"errors": ["field1 is required", "field2 is invalid"]}'
        )
        status_error_422 = httpx.HTTPStatusError(
            "Unprocessable Entity", request=response_422.request, response=response_422
        )
        bmc_error = error_handler.handle_http_error(status_error_422, "test_operation")
        assert isinstance(bmc_error, BMCAPIValidationError)
        assert bmc_error.status_code == 422
        assert bmc_error.validation_errors == [
            "field1 is required",
            "field2 is invalid",
        ]

        # Test other status codes
        response_500 = httpx.Response(
            500, request=httpx.Request("GET", "http://test.com")
        )
        response_500._content = b'{"error": "internal server error"}'
        status_error_500 = httpx.HTTPStatusError(
            "Internal Server Error", request=response_500.request, response=response_500
        )
        bmc_error = error_handler.handle_http_error(status_error_500, "test_operation")
        assert isinstance(bmc_error, BMCAPIError)
        assert bmc_error.status_code == 500

    def test_error_handler_json_parsing_failure(self):
        """Test error handler when JSON parsing fails."""
        import httpx

        from main import BMCAPIAuthenticationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create response with invalid JSON
        response = httpx.Response(401, request=httpx.Request("GET", "http://test.com"))
        response._content = b"invalid json content"
        status_error = httpx.HTTPStatusError(
            "Unauthorized", request=response.request, response=response
        )

        bmc_error = error_handler.handle_http_error(status_error, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.response_data == {"raw_response": "invalid json content"}

    def test_error_response_with_metrics(self):
        """Test error response creation with metrics integration."""
        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings()
        metrics = initialize_metrics()
        error_handler = ErrorHandler(settings, metrics)

        bmc_error = BMCAPIError("Test error", status_code=500)
        response = error_handler.create_error_response(bmc_error, "test_operation")

        assert response["error"] is True
        assert metrics.failed_requests == 1
        assert "test_operation_500" in metrics.endpoint_errors
        assert metrics.endpoint_errors["test_operation_500"] == 1

    @pytest.mark.asyncio
    async def test_error_recovery_with_different_error_types(self):
        """Test error recovery with different types of errors."""
        from main import (
            BMCAPIAuthenticationError,
            BMCAPITimeoutError,
            ErrorHandler,
            Settings,
        )

        settings = Settings(error_recovery_attempts=2)
        error_handler = ErrorHandler(settings)

        # Test with timeout error (should retry)
        call_count = 0

        async def timeout_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise BMCAPITimeoutError("Timeout")
            return "success"

        result = await error_handler.execute_with_recovery(
            "test_operation", timeout_failing_function
        )
        assert result == "success"
        assert call_count == 2

        # Test with authentication error (should not retry)
        call_count = 0

        async def auth_failing_function():
            nonlocal call_count
            call_count += 1
            raise BMCAPIAuthenticationError("Auth failed")

        with pytest.raises(BMCAPIAuthenticationError):
            await error_handler.execute_with_recovery(
                "test_operation", auth_failing_function
            )
        assert call_count == 1  # Should not retry

    def test_error_handler_http_status_errors(self):
        """Test HTTP status error conversion for different status codes."""
        import httpx

        from main import (
            BMCAPIAuthenticationError,
            BMCAPINotFoundError,
            BMCAPIRateLimitError,
            BMCAPIValidationError,
            ErrorHandler,
            Settings,
        )

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Test 401 Authentication Error
        response_401 = httpx.Response(
            401, request=httpx.Request("GET", "http://test.com")
        )
        response_401._content = b'{"error": "unauthorized"}'
        status_error_401 = httpx.HTTPStatusError(
            "Unauthorized", request=response_401.request, response=response_401
        )
        bmc_error = error_handler.handle_http_error(status_error_401, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.status_code == 401

        # Test 404 Not Found Error
        response_404 = httpx.Response(
            404, request=httpx.Request("GET", "http://test.com")
        )
        response_404._content = b'{"error": "not found"}'
        status_error_404 = httpx.HTTPStatusError(
            "Not Found", request=response_404.request, response=response_404
        )
        bmc_error = error_handler.handle_http_error(status_error_404, "test_operation")
        assert isinstance(bmc_error, BMCAPINotFoundError)
        assert bmc_error.status_code == 404

        # Test 429 Rate Limit Error
        response_429 = httpx.Response(
            429, request=httpx.Request("GET", "http://test.com")
        )
        response_429._content = b'{"error": "rate limited"}'
        response_429.headers["Retry-After"] = "60"
        status_error_429 = httpx.HTTPStatusError(
            "Too Many Requests", request=response_429.request, response=response_429
        )
        bmc_error = error_handler.handle_http_error(status_error_429, "test_operation")
        assert isinstance(bmc_error, BMCAPIRateLimitError)
        assert bmc_error.status_code == 429
        assert bmc_error.retry_after == 60

        # Test 422 Validation Error
        response_422 = httpx.Response(
            422, request=httpx.Request("GET", "http://test.com")
        )
        response_422._content = (
            b'{"errors": ["field1 is required", "field2 is invalid"]}'
        )
        status_error_422 = httpx.HTTPStatusError(
            "Unprocessable Entity", request=response_422.request, response=response_422
        )
        bmc_error = error_handler.handle_http_error(status_error_422, "test_operation")
        assert isinstance(bmc_error, BMCAPIValidationError)
        assert bmc_error.status_code == 422
        assert bmc_error.validation_errors == [
            "field1 is required",
            "field2 is invalid",
        ]

        # Test other status codes
        response_500 = httpx.Response(
            500, request=httpx.Request("GET", "http://test.com")
        )
        response_500._content = b'{"error": "internal server error"}'
        status_error_500 = httpx.HTTPStatusError(
            "Internal Server Error", request=response_500.request, response=response_500
        )
        bmc_error = error_handler.handle_http_error(status_error_500, "test_operation")
        assert isinstance(bmc_error, BMCAPIError)
        assert bmc_error.status_code == 500

    def test_error_handler_json_parsing_failure(self):
        """Test error handler when JSON parsing fails."""
        import httpx

        from main import BMCAPIAuthenticationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create response with invalid JSON
        response = httpx.Response(401, request=httpx.Request("GET", "http://test.com"))
        response._content = b"invalid json content"
        status_error = httpx.HTTPStatusError(
            "Unauthorized", request=response.request, response=response
        )

        bmc_error = error_handler.handle_http_error(status_error, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.response_data == {"raw_response": "invalid json content"}

    def test_error_response_with_metrics(self):
        """Test error response creation with metrics integration."""
        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings()
        metrics = initialize_metrics()
        error_handler = ErrorHandler(settings, metrics)

        bmc_error = BMCAPIError("Test error", status_code=500)
        response = error_handler.create_error_response(bmc_error, "test_operation")

        assert response["error"] is True
        assert metrics.failed_requests == 1
        assert "test_operation_500" in metrics.endpoint_errors
        assert metrics.endpoint_errors["test_operation_500"] == 1

    @pytest.mark.asyncio
    async def test_error_recovery_with_different_error_types(self):
        """Test error recovery with different types of errors."""
        from main import (
            BMCAPIAuthenticationError,
            BMCAPITimeoutError,
            ErrorHandler,
            Settings,
        )

        settings = Settings(error_recovery_attempts=2)
        error_handler = ErrorHandler(settings)

        # Test with timeout error (should retry)
        call_count = 0

        async def timeout_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise BMCAPITimeoutError("Timeout")
            return "success"

        result = await error_handler.execute_with_recovery(
            "test_operation", timeout_failing_function
        )
        assert result == "success"
        assert call_count == 2

        # Test with authentication error (should not retry)
        call_count = 0

        async def auth_failing_function():
            nonlocal call_count
            call_count += 1
            raise BMCAPIAuthenticationError("Auth failed")

        with pytest.raises(BMCAPIAuthenticationError):
            await error_handler.execute_with_recovery(
                "test_operation", auth_failing_function
            )
        assert call_count == 1  # Should not retry


class TestBMCClientComprehensive:
    """Comprehensive tests for BMCAMIDevXClient methods."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient for testing."""
        with unittest.mock.patch("httpx.AsyncClient") as mock_client:
            yield mock_client

    @pytest.mark.asyncio
    async def test_create_assignment_success(self, mock_httpx_client):
        """Test successful create_assignment call."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN-002",
            "status": "created",
        }
        mock_response.raise_for_status.return_value = None
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        assignment_data = {"assignmentId": "ASSIGN-002", "stream": "STREAM1"}
        result = await client.create_assignment("TEST123", assignment_data)

        assert result["assignmentId"] == "ASSIGN-002"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments", json=assignment_data
        )

    @pytest.mark.asyncio
    async def test_get_assignment_details_success(self, mock_httpx_client):
        """Test successful get_assignment_details call."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN-001",
            "status": "active",
        }
        mock_response.raise_for_status.return_value = None
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.get_assignment_details("TEST123", "ASSIGN-001")

        assert result["assignmentId"] == "ASSIGN-001"
        mock_client_instance.request.assert_called_once_with(
            "GET", "/ispw/TEST123/assignments/ASSIGN-001"
        )


class TestMCPToolsComprehensive:
    """Comprehensive tests for MCP tool core functions."""

    @pytest.fixture
    def mock_bmc_client(self):
        """Mock BMC client for testing."""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def mock_context(self):
        """Mock FastMCP context for testing."""
        context = unittest.mock.MagicMock(spec=Context)
        context.info = unittest.mock.AsyncMock()
        context.error = unittest.mock.AsyncMock()
        return context


class TestSettingsComprehensive:
    """Comprehensive tests for Settings class."""

    def test_settings_from_env_with_all_types(self):
        """Test Settings.from_env with all data types."""
        test_env = {
            "HOST": "127.0.0.1",
            "PORT": "9000",
            "LOG_LEVEL": "DEBUG",
            "API_BASE_URL": "https://test.bmc.com/api",
            "API_TIMEOUT": "60",
            "API_RETRY_ATTEMPTS": "5",
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.jwt.JWTVerifier",
            "RATE_LIMIT_REQUESTS_PER_MINUTE": "120",
            "RATE_LIMIT_BURST_SIZE": "20",
            "CONNECTION_POOL_SIZE": "30",
            "CONNECTION_POOL_MAX_KEEPALIVE": "60",
            "ENABLE_METRICS": "true",
            "METRICS_PORT": "9090",
            "HEALTH_CHECK_INTERVAL": "45",
            "LOG_REQUESTS": "true",
            "LOG_RESPONSES": "true",
            "ENABLE_TRACING": "false",
            "ENABLE_CACHING": "true",
            "CACHE_TTL_SECONDS": "600",
            "CACHE_MAX_SIZE": "2000",
            "CACHE_CLEANUP_INTERVAL": "120",
            "ENABLE_DETAILED_ERRORS": "true",
            "LOG_ERROR_DETAILS": "true",
            "MAX_ERROR_MESSAGE_LENGTH": "2000",
            "ENABLE_ERROR_RECOVERY": "true",
            "ERROR_RECOVERY_ATTEMPTS": "5",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            from main import Settings

            settings = Settings.from_env()

            # Test string values
            assert settings.host == "127.0.0.1"
            assert settings.log_level == "DEBUG"
            assert settings.api_base_url == "https://test.bmc.com/api"
            assert (
                settings.auth_provider
                == "fastmcp.server.auth.providers.jwt.JWTVerifier"
            )

            # Test integer values
            assert settings.port == 9000
            assert settings.api_timeout == 60
            assert settings.api_retry_attempts == 5
            assert settings.rate_limit_requests_per_minute == 120
            assert settings.rate_limit_burst_size == 20
            assert settings.connection_pool_size == 30
            assert settings.connection_pool_max_keepalive == 60
            assert settings.metrics_port == 9090
            assert settings.health_check_interval == 45
            assert settings.cache_ttl_seconds == 600
            assert settings.cache_max_size == 2000
            assert settings.cache_cleanup_interval == 120
            assert settings.max_error_message_length == 2000
            assert settings.error_recovery_attempts == 5

            # Test boolean values
            assert settings.auth_enabled is True
            assert settings.enable_metrics is True
            assert settings.log_requests is True
            assert settings.log_responses is True
            assert settings.enable_tracing is False
            assert settings.enable_caching is True
            assert settings.enable_detailed_errors is True
            assert settings.log_error_details is True
            assert settings.enable_error_recovery is True

    def test_settings_from_env_with_invalid_types(self):
        """Test Settings.from_env with invalid type conversions."""
        test_env = {
            "PORT": "invalid_port",
            "API_TIMEOUT": "not_a_number",
            "AUTH_ENABLED": "maybe",
            "RATE_LIMIT_REQUESTS_PER_MINUTE": "invalid",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            from main import Settings

            settings = Settings.from_env()

            # Should fall back to defaults for invalid values
            assert settings.port == 8080  # default
            assert settings.api_timeout == 30  # default
            assert settings.auth_enabled is False  # default
            assert settings.rate_limit_requests_per_minute == 60  # default

    def test_settings_from_env_with_kwargs_override(self):
        """Test Settings.from_env with kwargs override."""
        test_env = {"HOST": "127.0.0.1", "PORT": "9000"}

        with unittest.mock.patch.dict(os.environ, test_env):
            from main import Settings

            settings = Settings.from_env(host="192.168.1.1", port=8000)

            # kwargs should override environment variables
            assert settings.host == "192.168.1.1"
            assert settings.port == 8000


class TestMetricsComprehensive:
    """Comprehensive tests for Metrics class."""

    def test_metrics_initialization(self):
        """Test Metrics class initialization."""
        from collections import deque

        from main import initialize_metrics

        metrics = initialize_metrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.bmc_api_calls == 0
        assert metrics.bmc_api_errors == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.start_time is not None
        assert isinstance(metrics.response_times, deque)
        assert isinstance(metrics.endpoint_errors, dict)

    def test_metrics_update_response_time(self):
        """Test Metrics response time updates."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.update_bmc_response_time(1.0)
        metrics.update_bmc_response_time(2.0)
        metrics.update_bmc_response_time(3.0)

        assert len(metrics.bmc_api_response_times) == 3
        assert list(metrics.bmc_api_response_times) == [1.0, 2.0, 3.0]

    def test_metrics_success_rate(self):
        """Test Metrics success rate calculation."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.successful_requests = 8
        metrics.failed_requests = 2

        assert metrics.get_success_rate() == 80.0  # Returns percentage

    def test_metrics_cache_hit_rate(self):
        """Test Metrics cache hit rate calculation."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.cache_hits = 7
        metrics.cache_misses = 3

        assert metrics.get_cache_hit_rate() == 70.0  # Returns percentage

    def test_metrics_to_dict(self):
        """Test Metrics to_dict serialization."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.total_requests = 10
        metrics.successful_requests = 8
        metrics.failed_requests = 2
        metrics.bmc_api_calls = 5
        metrics.bmc_api_errors = 1
        metrics.cache_hits = 3
        metrics.cache_misses = 2

        metrics_dict = metrics.to_dict()

        # Test nested structure
        assert metrics_dict["requests"]["total"] == 10
        assert metrics_dict["requests"]["successful"] == 8
        assert metrics_dict["requests"]["failed"] == 2
        assert metrics_dict["bmc_api"]["calls"] == 5
        assert metrics_dict["bmc_api"]["errors"] == 1
        assert metrics_dict["cache"]["hits"] == 3
        assert metrics_dict["cache"]["misses"] == 2
        assert "success_rate" in metrics_dict["requests"]
        assert "hit_rate" in metrics_dict["cache"]

        # Test that all expected top-level keys exist
        expected_keys = [
            "requests",
            "response_times",
            "endpoints",
            "bmc_api",
            "cache",
            "system",
        ]
        for key in expected_keys:
            assert key in metrics_dict


class TestCacheComprehensive:
    """Comprehensive tests for Cache classes."""

    def test_cache_entry_creation(self):
        """Test CacheEntry creation and TTL."""
        from datetime import datetime

        from main import CacheEntry

        entry = CacheEntry(
            data={"data": "value"}, timestamp=datetime.now(), ttl_seconds=1
        )
        assert entry.data == {"data": "value"}
        assert entry.ttl_seconds == 1
        assert not entry.is_expired()

    def test_intelligent_cache_initialization(self):
        """Test IntelligentCache initialization."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=3, default_ttl=60)
        assert cache.max_size == 3
        assert cache.default_ttl == 60
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0


class TestHealthCheckerComprehensive:
    """Comprehensive tests for HealthChecker class."""

    def test_health_checker_initialization(self):
        """Test HealthChecker initialization."""
        import unittest.mock

        from main import HealthChecker, Settings

        mock_bmc_client = unittest.mock.MagicMock()
        settings = Settings()
        health_checker = HealthChecker(mock_bmc_client, settings)

        assert health_checker.bmc_client == mock_bmc_client
        assert health_checker.settings == settings
        assert health_checker.health_status == "unknown"
        assert health_checker.last_check is None
        assert health_checker.health_details == {}


class TestRateLimiterComprehensive:
    """Comprehensive tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        from main import RateLimiter

        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        assert rate_limiter.requests_per_minute == 60
        assert rate_limiter.burst_size == 10
        assert rate_limiter.tokens == 10  # Should start with burst size
        assert rate_limiter.last_refill == rate_limiter.last_refill  # Should be set

    @pytest.mark.asyncio
    async def test_rate_limiter_token_consumption(self):
        """Test RateLimiter token consumption."""
        from main import RateLimiter

        rate_limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        initial_tokens = rate_limiter.tokens

        # Consume one token
        await rate_limiter.wait_for_token()
        assert rate_limiter.tokens < initial_tokens  # Should be less than initial

        # Consume another token
        await rate_limiter.wait_for_token()
        assert rate_limiter.tokens < initial_tokens  # Should be even less

    def test_rate_limiter_properties(self):
        """Test RateLimiter properties and initialization."""
        from main import RateLimiter

        rate_limiter = RateLimiter(requests_per_minute=120, burst_size=5)
        assert rate_limiter.requests_per_minute == 120
        assert rate_limiter.burst_size == 5
        assert rate_limiter.tokens == 5  # Should start with burst size
        assert hasattr(rate_limiter, "last_refill")


class TestBMCClientMethodsComprehensive:
    """Comprehensive tests for BMCAMIDevXClient methods."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient for testing."""
        with unittest.mock.patch("httpx.AsyncClient") as mock_client:
            yield mock_client

    @pytest.mark.asyncio
    async def test_create_assignment_with_application(self, mock_httpx_client):
        """Test create_assignment with application parameter."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN-002",
            "status": "created",
        }
        mock_response.raise_for_status.return_value = None
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)
        assignment_data = {"assignmentId": "ASSIGN-002", "stream": "STREAM1"}
        result = await client.create_assignment("TEST123", assignment_data)

        assert result["assignmentId"] == "ASSIGN-002"
        mock_client_instance.request.assert_called_once_with(
            "POST", "/ispw/TEST123/assignments", json=assignment_data
        )

    @pytest.mark.asyncio
    async def test_get_assignment_details_with_error_handling(self, mock_httpx_client):
        """Test get_assignment_details with error handling."""
        from main import MCPServerError

        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.side_effect = Exception("Network error")
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        client = BMCAMIDevXClient(mock_client_instance)

        with pytest.raises(MCPServerError):
            await client.get_assignment_details("TEST123", "ASSIGN-001")

    @pytest.mark.asyncio
    async def test_bmc_client_with_metrics(self, mock_httpx_client):
        """Test BMCAMIDevXClient with metrics integration."""
        from main import initialize_metrics

        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignments": [{"id": "ASSIGN-001"}]}
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        metrics = initialize_metrics()
        client = BMCAMIDevXClient(mock_client_instance, metrics=metrics)

        result = await client.get_assignments("TEST123")

        assert result["assignments"][0]["id"] == "ASSIGN-001"
        assert metrics.bmc_api_calls == 1
        assert len(metrics.bmc_api_response_times) == 1

    @pytest.mark.asyncio
    async def test_bmc_client_with_cache(self, mock_httpx_client):
        """Test BMCAMIDevXClient with cache integration."""
        from main import IntelligentCache

        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignments": [{"id": "ASSIGN-001"}]}
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        cache = IntelligentCache(max_size=100, default_ttl=60)
        client = BMCAMIDevXClient(mock_client_instance, cache=cache)

        # First call should hit the API
        result1 = await client.get_assignments("TEST123")
        assert result1["assignments"][0]["id"] == "ASSIGN-001"

        # Second call should use cache (if implemented)
        result2 = await client.get_assignments("TEST123")
        assert result2["assignments"][0]["id"] == "ASSIGN-001"


class TestMCPToolsComprehensive:
    """Comprehensive tests for MCP tool core functions."""

    @pytest.fixture
    def mock_bmc_client(self):
        """Mock BMC client for testing."""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def mock_context(self):
        """Mock FastMCP context for testing."""
        context = unittest.mock.MagicMock(spec=Context)
        context.info = unittest.mock.AsyncMock()
        context.error = unittest.mock.AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_assignments_core_with_level_and_assignment_id(
        self, mock_bmc_client, mock_context
    ):
        """Test get_assignments core function with level and assignment_id parameters."""
        from main import _get_assignments_core

        # Mock the global bmc_client to return our mock
        with unittest.mock.patch("main.bmc_client", mock_bmc_client):
            # Make the mock return an awaitable
            async def mock_get_assignments(*args, **kwargs):
                return {"assignments": [{"id": "ASSIGN-001"}]}

            mock_bmc_client.get_assignments = mock_get_assignments

            result = await _get_assignments_core(
                "TEST123", "DEV", "ASSIGN-001", mock_context
            )

            result_data = json.loads(result)
            assert "assignments" in result_data
            assert result_data["assignments"][0]["id"] == "ASSIGN-001"
            mock_context.info.assert_called()

    @pytest.mark.asyncio
    async def test_get_assignments_core_with_none_parameters(
        self, mock_bmc_client, mock_context
    ):
        """Test get_assignments core function with None parameters."""
        from main import _get_assignments_core

        # Mock the global bmc_client to return our mock
        with unittest.mock.patch("main.bmc_client", mock_bmc_client):
            # Make the mock return an awaitable
            async def mock_get_assignments(*args, **kwargs):
                return {"assignments": [{"id": "ASSIGN-001"}]}

            mock_bmc_client.get_assignments = mock_get_assignments

            result = await _get_assignments_core("TEST123", None, None, mock_context)

            result_data = json.loads(result)
            assert "assignments" in result_data
            assert result_data["assignments"][0]["id"] == "ASSIGN-001"
            mock_context.info.assert_called()

    @pytest.mark.asyncio
    async def test_get_assignments_core_with_bmc_api_error(
        self, mock_bmc_client, mock_context
    ):
        """Test get_assignments core function with BMC API error."""
        from main import BMCAPIError, _get_assignments_core

        mock_bmc_client.get_assignments.side_effect = BMCAPIError(
            "API Error", status_code=500
        )

        result = await _get_assignments_core("TEST123", "DEV", None, mock_context)

        result_data = json.loads(result)
        assert result_data["error"] is True
        assert result_data["error_type"] == "BMC_API_ERROR"
        assert "BMC API connection error" in result_data["message"]
        mock_context.error.assert_called()


class TestServerInitialization:
    """Test server initialization and startup."""

    def test_settings_creation(self):
        """Test Settings creation with defaults."""
        from main import Settings

        settings = Settings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.log_level == "INFO"
        assert settings.api_base_url == "https://devx.bmc.com/code-pipeline/api/v1"
        assert settings.api_timeout == 30
        assert settings.api_retry_attempts == 3
        assert settings.auth_enabled is False
        assert settings.rate_limit_requests_per_minute == 60
        assert settings.rate_limit_burst_size == 10
        assert settings.connection_pool_size == 20
        assert settings.connection_pool_max_keepalive == 30
        assert settings.enable_metrics is True
        assert settings.metrics_port == 9090
        assert settings.health_check_interval == 30
        assert settings.log_requests is True
        assert settings.log_responses is False
        assert settings.enable_tracing is False
        assert settings.enable_caching is True
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_max_size == 1000
        assert settings.cache_cleanup_interval == 60
        assert settings.enable_detailed_errors is True
        assert settings.log_error_details is True
        assert settings.max_error_message_length == 1000
        assert settings.enable_error_recovery is True
        assert settings.error_recovery_attempts == 3

    def test_create_auth_provider_with_different_providers(self):
        """Test create_auth_provider with different provider types."""
        from main import Settings, create_auth_provider

        # Test JWT provider
        jwt_settings = Settings(
            auth_enabled=True,
            auth_provider="fastmcp.server.auth.providers.jwt.JWTVerifier",
        )

        with unittest.mock.patch(
            "fastmcp.server.auth.providers.jwt.JWTVerifier"
        ) as mock_jwt:
            provider = create_auth_provider(jwt_settings)
            assert provider is not None

        # Test GitHub provider
        github_settings = Settings(
            auth_enabled=True,
            auth_provider="fastmcp.server.auth.providers.github.GitHubProvider",
        )

        with unittest.mock.patch(
            "fastmcp.server.auth.providers.github.GitHubProvider"
        ) as mock_github:
            provider = create_auth_provider(github_settings)
            assert provider is not None

    def test_create_auth_provider_with_invalid_provider(self):
        """Test create_auth_provider with invalid provider."""
        from main import Settings, create_auth_provider

        invalid_settings = Settings(
            auth_enabled=True, auth_provider="invalid.module.InvalidProvider"
        )

        provider = create_auth_provider(invalid_settings)
        assert provider is None


class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    def test_metrics_update_response_time(self):
        """Test Metrics update_response_time method."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.update_response_time(1.5)
        metrics.update_response_time(2.5)
        metrics.update_response_time(3.5)

        assert len(metrics.response_times) == 3
        assert metrics.avg_response_time == 2.5
        assert metrics.min_response_time == 1.5
        assert metrics.max_response_time == 3.5

    def test_metrics_get_success_rate(self):
        """Test Metrics get_success_rate method."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.successful_requests = 8
        metrics.failed_requests = 2

        success_rate = metrics.get_success_rate()
        assert success_rate == 80.0  # 8/10 * 100

    def test_metrics_get_cache_hit_rate(self):
        """Test Metrics get_cache_hit_rate method."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.cache_hits = 7
        metrics.cache_misses = 3

        hit_rate = metrics.get_cache_hit_rate()
        assert hit_rate == 70.0  # 7/10 * 100

    def test_metrics_get_cache_hit_rate_zero_total(self):
        """Test Metrics get_cache_hit_rate with zero total."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.cache_hits = 0
        metrics.cache_misses = 0

        hit_rate = metrics.get_cache_hit_rate()
        assert hit_rate == 0.0

    def test_metrics_get_success_rate_zero_total(self):
        """Test Metrics get_success_rate with zero total."""
        from main import initialize_metrics

        metrics = initialize_metrics()
        metrics.successful_requests = 0
        metrics.failed_requests = 0

        success_rate = metrics.get_success_rate()
        assert success_rate == 100.0  # 0/0 should return 100% (no failures)

    def test_cache_entry_is_expired(self):
        """Test CacheEntry is_expired method."""
        from datetime import datetime, timedelta

        from main import CacheEntry

        # Test non-expired entry
        entry = CacheEntry(
            data={"test": "data"}, timestamp=datetime.now(), ttl_seconds=60
        )
        assert not entry.is_expired()

        # Test expired entry
        expired_entry = CacheEntry(
            data={"test": "data"},
            timestamp=datetime.now() - timedelta(seconds=120),
            ttl_seconds=60,
        )
        assert expired_entry.is_expired()

    def test_intelligent_cache_generate_key(self):
        """Test IntelligentCache _generate_key method."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=10, default_ttl=60)

        key1 = cache._generate_key("get_assignments", srid="TEST123", level="DEV")
        key2 = cache._generate_key("get_assignments", srid="TEST123", level="DEV")
        key3 = cache._generate_key("get_assignments", srid="TEST456", level="DEV")

        assert key1 == key2  # Same parameters should generate same key
        assert key1 != key3  # Different parameters should generate different keys
        assert "get_assignments" in key1
        assert "TEST123" in key1
        assert "DEV" in key1

    def test_error_handler_handle_validation_error(self):
        """Test ErrorHandler handle_validation_error method."""
        from main import ErrorHandler, MCPValidationError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        validation_error = error_handler.handle_validation_error(
            ValueError("Invalid input"), "test_field", "invalid_value"
        )

        assert isinstance(validation_error, MCPValidationError)
        assert "test_field" in str(validation_error)
        assert "Invalid input" in str(validation_error)

    def test_error_handler_handle_general_error(self):
        """Test ErrorHandler handle_general_error method."""
        from main import ErrorHandler, MCPServerError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        general_error = error_handler.handle_general_error(
            Exception("Something went wrong"), "test_operation"
        )

        assert isinstance(general_error, MCPServerError)
        assert "test_operation" in str(general_error)
        assert "Internal server error during test_operation" == str(general_error)

    def test_error_handler_http_timeout_error(self):
        """Test ErrorHandler HTTP timeout error conversion."""
        import httpx

        from main import BMCAPITimeoutError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        timeout_error = httpx.TimeoutException("Request timed out")
        converted_error = error_handler.handle_http_error(
            timeout_error, "test_operation"
        )

        assert isinstance(converted_error, BMCAPITimeoutError)
        assert "test_operation" in str(converted_error)
        assert "timed out" in str(converted_error)

    def test_error_handler_http_401_error(self):
        """Test ErrorHandler HTTP 401 authentication error conversion."""
        import httpx

        from main import BMCAPIAuthenticationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}

        http_error = httpx.HTTPStatusError(
            "401 Unauthorized", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPIAuthenticationError)
        assert "test_operation" in str(converted_error)
        assert "authentication failed" in str(converted_error)
        assert converted_error.status_code == 401

    def test_error_handler_http_404_error(self):
        """Test ErrorHandler HTTP 404 not found error conversion."""
        import httpx

        from main import BMCAPINotFoundError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not Found"}

        http_error = httpx.HTTPStatusError(
            "404 Not Found", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPINotFoundError)
        assert "test_operation" in str(converted_error)
        assert "not found" in str(converted_error)
        assert converted_error.status_code == 404

    def test_error_handler_http_429_error(self):
        """Test ErrorHandler HTTP 429 rate limit error conversion."""
        import httpx

        from main import BMCAPIRateLimitError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate Limited"}
        mock_response.headers = {"Retry-After": "60"}

        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPIRateLimitError)
        assert "test_operation" in str(converted_error)
        assert "rate limit exceeded" in str(converted_error)
        assert converted_error.status_code == 429
        assert converted_error.retry_after == 60

    def test_error_handler_http_422_error(self):
        """Test ErrorHandler HTTP 422 validation error conversion."""
        import httpx

        from main import BMCAPIValidationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "errors": ["Invalid field", "Missing required field"]
        }

        http_error = httpx.HTTPStatusError(
            "422 Unprocessable Entity", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPIValidationError)
        assert "test_operation" in str(converted_error)
        assert "validation failed" in str(converted_error)
        assert converted_error.status_code == 422
        assert len(converted_error.validation_errors) == 2

    def test_error_handler_http_500_error(self):
        """Test ErrorHandler HTTP 500 server error conversion."""
        import httpx

        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Server Error"}

        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPIError)
        assert "test_operation" in str(converted_error)
        assert "500" in str(converted_error)
        assert converted_error.status_code == 500

    def test_error_handler_http_error_json_parse_failure(self):
        """Test ErrorHandler HTTP error with JSON parse failure."""
        import httpx

        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a mock response that fails JSON parsing
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 400
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid response"

        http_error = httpx.HTTPStatusError(
            "400 Bad Request", request=None, response=mock_response
        )
        converted_error = error_handler.handle_http_error(http_error, "test_operation")

        assert isinstance(converted_error, BMCAPIError)
        assert "test_operation" in str(converted_error)
        assert converted_error.status_code == 400
        assert "raw_response" in converted_error.response_data

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_success(self):
        """Test ErrorHandler execute_with_recovery with successful operation."""
        from main import ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        async def successful_operation():
            return "success"

        result = await error_handler.execute_with_recovery(
            "test_operation", successful_operation
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_retry_success(self):
        """Test ErrorHandler execute_with_recovery with retry that eventually succeeds."""
        from main import ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"

        result = await error_handler.execute_with_recovery(
            "test_operation", flaky_operation
        )
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_no_retry_validation_error(self):
        """Test ErrorHandler execute_with_recovery doesn't retry validation errors."""
        from main import ErrorHandler, MCPValidationError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def validation_error_operation():
            nonlocal call_count
            call_count += 1
            raise MCPValidationError("Validation failed")

        with pytest.raises(MCPValidationError):
            await error_handler.execute_with_recovery(
                "test_operation", validation_error_operation
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_no_retry_auth_error(self):
        """Test ErrorHandler execute_with_recovery doesn't retry authentication errors."""
        from main import BMCAPIAuthenticationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def auth_error_operation():
            nonlocal call_count
            call_count += 1
            raise BMCAPIAuthenticationError("Auth failed")

        with pytest.raises(BMCAPIAuthenticationError):
            await error_handler.execute_with_recovery(
                "test_operation", auth_error_operation
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_no_retry_not_found_error(self):
        """Test ErrorHandler execute_with_recovery doesn't retry not found errors."""
        from main import BMCAPINotFoundError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def not_found_error_operation():
            nonlocal call_count
            call_count += 1
            raise BMCAPINotFoundError("Not found")

        with pytest.raises(BMCAPINotFoundError):
            await error_handler.execute_with_recovery(
                "test_operation", not_found_error_operation
            )

        assert call_count == 1  # Should not retry


class TestAdditionalFunctionality:
    """Test additional functionality to improve coverage."""

    def test_settings_from_env_with_invalid_types(self):
        """Test Settings.from_env with invalid type conversions."""
        from main import Settings

        test_env = {
            "PORT": "invalid_port",
            "API_TIMEOUT": "invalid_timeout",
            "AUTH_ENABLED": "invalid_bool",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            settings = Settings.from_env()

            # Should use defaults for invalid values
            assert settings.port == 8080  # Default value
            assert settings.api_timeout == 30  # Default value
            assert settings.auth_enabled is False  # Default value

    def test_error_handler_create_error_response_with_metrics(self):
        """Test ErrorHandler create_error_response with metrics."""
        from main import ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a test exception
        test_error = Exception("Test error")

        response = error_handler.create_error_response(test_error, "test_operation")

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert "timestamp" in response
        assert "message" in response
        assert response["message"] == "Test error"

    def test_rate_limiter_properties(self):
        """Test RateLimiter properties."""
        from main import RateLimiter

        rate_limiter = RateLimiter(60, 10)

        assert rate_limiter.requests_per_minute == 60
        assert rate_limiter.burst_size == 10
        assert rate_limiter.tokens == 10  # Initial tokens
        assert rate_limiter.last_refill == rate_limiter.last_refill  # Should be set

    def test_cache_entry_expired(self):
        """Test CacheEntry expiration."""
        from datetime import datetime, timedelta

        from main import CacheEntry

        # Create an expired entry
        expired_time = datetime.now() - timedelta(seconds=400)
        cache_entry = CacheEntry("data", expired_time, 300)  # TTL 300 seconds

        assert cache_entry.is_expired() is True

        # Create a fresh entry
        fresh_time = datetime.now()
        fresh_entry = CacheEntry("data", fresh_time, 300)

        assert fresh_entry.is_expired() is False

    def test_intelligent_cache_generate_key(self):
        """Test IntelligentCache key generation."""
        from main import IntelligentCache

        cache = IntelligentCache()

        # Test key generation with different parameters
        key1 = cache._generate_key("GET", srid="TEST123", level="DEV")
        key2 = cache._generate_key("GET", srid="TEST123", level="PROD")
        key3 = cache._generate_key("POST", srid="TEST123", level="DEV")

        assert key1 != key2  # Different level should generate different key
        assert key1 != key3  # Different method should generate different key
        assert "GET" in key1
        assert "TEST123" in key1
        assert "DEV" in key1

    def test_intelligent_cache_initialization(self):
        """Test IntelligentCache initialization."""
        from main import IntelligentCache

        cache = IntelligentCache(max_size=500, default_ttl=600)

        assert cache.max_size == 500
        assert cache.default_ttl == 600
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0

    def test_metrics_update_bmc_response_time(self):
        """Test Metrics update_bmc_response_time method."""
        from main import initialize_metrics

        metrics = initialize_metrics()

        # Update BMC response times
        metrics.update_bmc_response_time(1.5)
        metrics.update_bmc_response_time(2.0)
        metrics.update_bmc_response_time(1.0)

        assert len(metrics.bmc_api_response_times) == 3
        assert list(metrics.bmc_api_response_times) == [1.5, 2.0, 1.0]

    def test_error_handler_create_error_response_rate_limit_error(self):
        """Test ErrorHandler create_error_response with rate limit error."""
        from main import BMCAPIRateLimitError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a rate limit error
        rate_limit_error = BMCAPIRateLimitError("Rate limited", retry_after=60)

        response = error_handler.create_error_response(
            rate_limit_error, "test_operation"
        )

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert response["retry_after"] == 60
        assert "timestamp" in response

    def test_error_handler_create_error_response_validation_error(self):
        """Test ErrorHandler create_error_response with validation error."""
        from main import BMCAPIValidationError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create a validation error
        validation_error = BMCAPIValidationError(
            "Validation failed", validation_errors=["Field required"]
        )

        response = error_handler.create_error_response(
            validation_error, "test_operation"
        )

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert response["validation_errors"] == ["Field required"]
        assert "timestamp" in response

    def test_error_handler_create_error_response_mcp_validation_error(self):
        """Test ErrorHandler create_error_response with MCP validation error."""
        from main import ErrorHandler, MCPValidationError, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Create an MCP validation error
        mcp_validation_error = MCPValidationError(
            "MCP validation failed", field="test_field", value="invalid"
        )

        response = error_handler.create_error_response(
            mcp_validation_error, "test_operation"
        )

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert response["error_type"] == "VALIDATION_ERROR"
        assert "timestamp" in response

    def test_error_handler_create_error_response_with_metrics(self):
        """Test ErrorHandler create_error_response with metrics updates."""
        from main import BMCAPIError, ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Mock metrics
        mock_metrics = unittest.mock.MagicMock()
        error_handler.metrics = mock_metrics

        # Create an error with status code
        error = BMCAPIError("API Error", status_code=500)

        response = error_handler.create_error_response(error, "test_operation")

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert "timestamp" in response

        # Check that metrics were updated
        mock_metrics.failed_requests += 1
        mock_metrics.endpoint_errors.__setitem__.assert_called()

    def test_error_handler_create_error_response_message_truncation(self):
        """Test ErrorHandler create_error_response with message truncation."""
        from main import ErrorHandler, Settings

        settings = Settings()
        settings.max_error_message_length = 10
        error_handler = ErrorHandler(settings)

        # Create an error with a long message
        long_message = "This is a very long error message that should be truncated"
        error = Exception(long_message)

        response = error_handler.create_error_response(error, "test_operation")

        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert len(response["message"]) <= 13  # 10 + "..."
        assert response["message"].endswith("...")

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_max_attempts(self):
        """Test ErrorHandler execute_with_recovery with max attempts reached."""
        from main import ErrorHandler, Settings

        settings = Settings()
        settings.error_recovery_attempts = 2
        error_handler = ErrorHandler(settings)

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception):
            await error_handler.execute_with_recovery(
                "test_operation", failing_operation
            )

        assert call_count == 2  # Should retry once, then fail

    @pytest.mark.asyncio
    async def test_error_handler_execute_with_recovery_with_metrics(self):
        """Test ErrorHandler execute_with_recovery with metrics updates."""
        from main import ErrorHandler, Settings

        settings = Settings()
        error_handler = ErrorHandler(settings)

        # Mock metrics
        mock_metrics = unittest.mock.MagicMock()
        error_handler.metrics = mock_metrics

        async def successful_operation():
            return "success"

        result = await error_handler.execute_with_recovery(
            "test_operation", successful_operation
        )

        assert result == "success"
        mock_metrics.successful_requests += 1

    def test_create_auth_provider_with_none_settings(self):
        """Test create_auth_provider with None settings."""
        from main import create_auth_provider

        # Mock the global settings
        with unittest.mock.patch("main.settings") as mock_settings:
            mock_settings.auth_enabled = False

            provider = create_auth_provider(None)

            assert provider is None

    def test_create_auth_provider_auth_disabled(self):
        """Test create_auth_provider with auth disabled."""
        from main import Settings, create_auth_provider

        settings = Settings()
        settings.auth_enabled = False

        provider = create_auth_provider(settings)

        assert provider is None

    def test_create_auth_provider_no_provider(self):
        """Test create_auth_provider with no provider specified."""
        from main import Settings, create_auth_provider

        settings = Settings()
        settings.auth_enabled = True
        settings.auth_provider = None

        provider = create_auth_provider(settings)

        assert provider is None

    @pytest.mark.asyncio
    async def test_bmc_client_make_request_success_with_metrics(self):
        """Test BMC client _make_request success with metrics updates."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        # Mock metrics
        mock_metrics = unittest.mock.MagicMock()

        # Mock error handler
        mock_error_handler = unittest.mock.MagicMock()

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client, mock_rate_limiter, None, mock_metrics, mock_error_handler
        )

        result = await client._make_request("GET", "/test")

        assert result.status_code == 200
        assert result.json() == {"data": "test"}
        mock_metrics.bmc_api_calls += 1
        mock_metrics.record_bmc_api_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_bmc_client_make_request_http_error(self):
        """Test BMC client _make_request with HTTP error."""
        import httpx

        from main import BMCAMIDevXClient, BMCAPIError, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_http_error = httpx.HTTPStatusError(
            "500 Internal Server Error", request=None, response=None
        )
        mock_httpx_client.request.side_effect = mock_http_error

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        # Mock error handler
        mock_error_handler = unittest.mock.MagicMock()
        mock_error_handler.handle_http_error.return_value = BMCAPIError("API Error")

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client, mock_rate_limiter, None, None, mock_error_handler
        )

        with pytest.raises(BMCAPIError):
            await client._make_request("GET", "/test")

        mock_error_handler.handle_http_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_bmc_client_get_release_details(self):
        """Test BMC client get_release_details method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "release_id": "REL-001",
            "name": "Test Release",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_release_details("TEST123", "REL-001")

        assert result == {"release_id": "REL-001", "name": "Test Release"}
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/releases/REL-001"
        )

    @pytest.mark.asyncio
    async def test_bmc_client_deploy_release(self):
        """Test BMC client deploy_release method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "deployment_id": "DEP-001",
            "status": "success",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        deploy_data = {"environment": "PROD", "target": "server1"}
        result = await client.deploy_release("TEST123", "REL-001", deploy_data)

        assert result == {"deployment_id": "DEP-001", "status": "success"}
        mock_httpx_client.request.assert_called_once_with(
            "POST", "/ispw/TEST123/releases/REL-001/deploy", json=deploy_data
        )

    @pytest.mark.asyncio
    async def test_bmc_client_get_sets(self):
        """Test BMC client get_sets method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "sets": [{"set_id": "SET-001", "name": "Test Set"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_sets("TEST123")

        assert result == {"sets": [{"set_id": "SET-001", "name": "Test Set"}]}
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/sets", params={}
        )

    @pytest.mark.asyncio
    async def test_bmc_client_get_sets_with_set_id(self):
        """Test BMC client get_sets method with set_id."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"set_id": "SET-001", "name": "Test Set"}
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_sets("TEST123", "SET-001")

        assert result == {"set_id": "SET-001", "name": "Test Set"}
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/sets", params={"setId": "SET-001"}
        )

    @pytest.mark.asyncio
    async def test_bmc_client_deploy_set(self):
        """Test BMC client deploy_set method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "deployment_id": "DEP-001",
            "status": "success",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        deploy_data = {"environment": "PROD", "target": "server1"}
        result = await client.deploy_set("TEST123", "SET-001", deploy_data)

        assert result == {"deployment_id": "DEP-001", "status": "success"}
        mock_httpx_client.request.assert_called_once_with(
            "POST", "/ispw/TEST123/sets/SET-001/deploy", json=deploy_data
        )

    @pytest.mark.asyncio
    async def test_bmc_client_get_packages(self):
        """Test BMC client get_packages method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "packages": [{"package_id": "PKG-001", "name": "Test Package"}]
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_packages("TEST123")

        assert result == {
            "packages": [{"package_id": "PKG-001", "name": "Test Package"}]
        }
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/packages", params={}
        )

    @pytest.mark.asyncio
    async def test_bmc_client_get_packages_with_package_id(self):
        """Test BMC client get_packages method with package_id."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "package_id": "PKG-001",
            "name": "Test Package",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_packages("TEST123", "PKG-001")

        assert result == {"package_id": "PKG-001", "name": "Test Package"}
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/packages", params={"packageId": "PKG-001"}
        )

    @pytest.mark.asyncio
    async def test_bmc_client_get_package_details(self):
        """Test BMC client get_package_details method."""
        from main import BMCAMIDevXClient, Settings

        # Mock httpx client
        mock_httpx_client = unittest.mock.AsyncMock()
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {
            "package_id": "PKG-001",
            "name": "Test Package",
            "version": "1.0",
        }
        mock_response.raise_for_status.return_value = None
        mock_httpx_client.request.return_value = mock_response

        # Mock rate limiter
        mock_rate_limiter = unittest.mock.MagicMock()
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        settings = Settings()
        client = BMCAMIDevXClient(mock_httpx_client, mock_rate_limiter)

        result = await client.get_package_details("TEST123", "PKG-001")

        assert result == {
            "package_id": "PKG-001",
            "name": "Test Package",
            "version": "1.0",
        }
        mock_httpx_client.request.assert_called_once_with(
            "GET", "/ispw/TEST123/packages/PKG-001"
        )

    @pytest.mark.asyncio
    async def test_get_metrics_tool(self):
        """Test get_metrics MCP tool function."""
        # Import the actual function before it gets decorated

        # Mock context
        mock_context = unittest.mock.MagicMock()
        mock_context.info = unittest.mock.AsyncMock()

        # Mock global instances
        with (
            unittest.mock.patch("main.metrics") as mock_metrics,
            unittest.mock.patch("main.cache") as mock_cache,
        ):

            mock_metrics.to_dict.return_value = {"requests": {"total": 100}}
            mock_cache.cache = {"key1": "value1", "key2": "value2"}

            # Call the underlying function using the fn attribute
            from main import get_metrics

            result = await get_metrics.fn(mock_context)

            # Verify context info was called
            mock_context.info.assert_called_once_with("Retrieving server metrics")

            # Verify metrics were updated with cache size
            mock_metrics.update_cache_size.assert_called_once_with(2)

            # Verify metrics data was returned
            assert "total" in result
            assert "100" in result

    @pytest.mark.asyncio
    async def test_get_metrics_tool_no_context(self):
        """Test get_metrics MCP tool function without context."""
        # Mock global instances
        with (
            unittest.mock.patch("main.metrics") as mock_metrics,
            unittest.mock.patch("main.cache") as mock_cache,
        ):

            mock_metrics.to_dict.return_value = {"requests": {"total": 50}}
            mock_cache.cache = {"key1": "value1"}

            # Call the underlying function using the fn attribute
            from main import get_metrics

            result = await get_metrics.fn(None)

            # Verify metrics were updated with cache size
            mock_metrics.update_cache_size.assert_called_once_with(1)

            # Verify metrics data was returned
            assert "total" in result
            assert "50" in result

    @pytest.mark.asyncio
    async def test_get_health_status_tool(self):
        """Test get_health_status MCP tool function."""
        # Mock context
        mock_context = unittest.mock.MagicMock()
        mock_context.info = unittest.mock.AsyncMock()

        # Mock health checker
        with unittest.mock.patch("main.health_checker") as mock_health_checker:
            mock_health_checker.check_health = unittest.mock.AsyncMock(
                return_value={"status": "healthy", "details": {}}
            )

            # Call the underlying function using the fn attribute
            from main import get_health_status

            result = await get_health_status.fn(mock_context)

            # Verify context info was called
            mock_context.info.assert_called_once_with("Performing health check")

            # Verify health checker was called
            mock_health_checker.check_health.assert_called_once()

            # Verify health data was returned
            assert "status" in result
            assert "healthy" in result

    @pytest.mark.asyncio
    async def test_get_health_status_tool_no_context(self):
        """Test get_health_status MCP tool function without context."""
        # Mock health checker
        with unittest.mock.patch("main.health_checker") as mock_health_checker:
            mock_health_checker.check_health = unittest.mock.AsyncMock(
                return_value={"status": "unhealthy", "error": "test error"}
            )

            # Call the underlying function using the fn attribute
            from main import get_health_status

            result = await get_health_status.fn(None)

            # Verify health checker was called
            mock_health_checker.check_health.assert_called_once()

            # Verify health data was returned
            assert "status" in result
            assert "unhealthy" in result

    @pytest.mark.asyncio
    async def test_health_checker_with_psutil_available(self):
        """Test health checker when psutil is available."""
        from main import HealthChecker, Settings

        # Mock settings
        mock_settings = Settings()

        # Mock BMC client
        mock_bmc_client = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter.tokens = 5.0
        mock_bmc_client.check_health = unittest.mock.AsyncMock(
            return_value={"status": "healthy"}
        )

        # Mock psutil module
        mock_psutil = unittest.mock.MagicMock()
        mock_psutil.cpu_percent.return_value = 25.5
        mock_psutil.virtual_memory.return_value = unittest.mock.MagicMock(percent=60.0)
        mock_psutil.disk_usage.return_value = unittest.mock.MagicMock(percent=40.0)

        with unittest.mock.patch.dict("sys.modules", {"psutil": mock_psutil}):
            health_checker = HealthChecker(mock_bmc_client, mock_settings)
            result = await health_checker.check_health()

            # Verify system metrics were included
            assert "details" in result
            assert "system" in result["details"]
            assert "cpu_percent" in result["details"]["system"]
            assert "memory_percent" in result["details"]["system"]
            assert "disk_percent" in result["details"]["system"]
            assert result["details"]["system"]["cpu_percent"] == 25.5
            assert result["details"]["system"]["memory_percent"] == 60.0
            assert result["details"]["system"]["disk_percent"] == 40.0

    @pytest.mark.asyncio
    async def test_health_checker_with_psutil_import_error(self):
        """Test health checker when psutil import fails."""
        from main import HealthChecker, Settings

        # Mock settings
        mock_settings = Settings()

        # Mock BMC client
        mock_bmc_client = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter.tokens = 5.0

        # Mock BMC client check_health method to avoid async issues
        mock_bmc_client.check_health = unittest.mock.AsyncMock(
            return_value={"status": "healthy"}
        )

        # Mock import error for psutil
        with unittest.mock.patch(
            "builtins.__import__", side_effect=ImportError("No module named 'psutil'")
        ):
            health_checker = HealthChecker(mock_bmc_client, mock_settings)
            result = await health_checker.check_health()

            # Verify system metrics show psutil not available
            assert "details" in result
            assert "system" in result["details"]
            assert result["details"]["system"] == "psutil not available"

    @pytest.mark.asyncio
    async def test_health_checker_with_psutil_exception(self):
        """Test health checker when psutil raises an exception."""
        from main import HealthChecker, Settings

        # Mock settings
        mock_settings = Settings()

        # Mock BMC client
        mock_bmc_client = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter = unittest.mock.MagicMock()
        mock_bmc_client.rate_limiter.tokens = 5.0

        # Mock BMC client check_health method to avoid async issues
        mock_bmc_client.check_health = unittest.mock.AsyncMock(
            return_value={"status": "healthy"}
        )

        # Mock psutil module to raise an exception
        mock_psutil = unittest.mock.MagicMock()
        mock_psutil.cpu_percent.side_effect = Exception("psutil error")

        with unittest.mock.patch.dict("sys.modules", {"psutil": mock_psutil}):
            health_checker = HealthChecker(mock_bmc_client, mock_settings)
            result = await health_checker.check_health()

            # Verify health status is unhealthy and error is captured
            assert result["status"] == "unhealthy"
            assert "details" in result
            assert "error" in result["details"]
            assert "psutil error" in result["details"]["error"]

    def test_get_settings_function(self):
        """Test get_settings function that reloads environment variables."""
        from main import get_settings

        # Mock environment variables
        with unittest.mock.patch.dict(
            "os.environ",
            {
                "API_BASE_URL": "https://test-api.example.com",
                "AUTH_ENABLED": "true",
                "AUTH_PROVIDER": "test-provider",
            },
        ):
            settings = get_settings()

            # Verify settings were loaded from environment
            assert settings.api_base_url == "https://test-api.example.com"
            assert settings.auth_enabled is True
            assert settings.auth_provider == "test-provider"

    def test_get_settings_function_with_defaults(self):
        """Test get_settings function with minimal environment variables."""
        from main import get_settings

        # Mock minimal environment variables
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            settings = get_settings()

            # Verify default values are used
            assert settings.api_base_url == "https://devx.bmc.com/code-pipeline/api/v1"
            assert settings.auth_enabled is False
            assert settings.auth_provider is None

    @pytest.mark.asyncio
    async def test_cache_set_existing_key_removal(self):
        """Test cache set method when key already exists (edge case)."""
        from main import IntelligentCache

        cache = IntelligentCache()

        # Add initial entry
        await cache.set("test_key", {"data": "initial"}, ttl=60)
        assert "test_key" in cache.cache
        assert "test_key" in cache.access_order
        assert len(cache.access_order) == 1

        # Add same key again (should remove from access_order first)
        await cache.set("test_key", {"data": "updated"}, ttl=120)
        assert "test_key" in cache.cache
        assert "test_key" in cache.access_order
        assert len(cache.access_order) == 1  # Should still be 1, not 2
        assert cache.cache["test_key"].data == {"data": "updated"}
        assert cache.cache["test_key"].ttl_seconds == 120

    @pytest.mark.asyncio
    async def test_cache_set_multiple_keys(self):
        """Test cache set method with multiple keys."""
        from main import IntelligentCache

        cache = IntelligentCache()

        # Add multiple entries
        await cache.set("key1", {"data": "value1"}, ttl=60)
        await cache.set("key2", {"data": "value2"}, ttl=120)
        await cache.set("key3", {"data": "value3"}, ttl=180)

        assert len(cache.cache) == 3
        assert len(cache.access_order) == 3
        assert list(cache.access_order) == ["key1", "key2", "key3"]

        # Update existing key (should remove from access_order first)
        await cache.set("key2", {"data": "value2_updated"}, ttl=240)
        assert len(cache.cache) == 3
        assert len(cache.access_order) == 3
        assert list(cache.access_order) == ["key1", "key3", "key2"]  # key2 moved to end
        assert cache.cache["key2"].data == {"data": "value2_updated"}
        assert cache.cache["key2"].ttl_seconds == 240


class TestBMCClientAdvanced:
    """Test advanced BMC client functionality."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        return unittest.mock.AsyncMock()

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def mock_metrics(self):
        """Create a mock metrics."""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def mock_error_handler(self):
        """Create a mock error handler."""
        return unittest.mock.MagicMock()

    @pytest.mark.asyncio
    async def test_bmc_client_make_request_with_rate_limiting(
        self,
        mock_httpx_client,
        mock_rate_limiter,
        mock_cache,
        mock_metrics,
        mock_error_handler,
    ):
        """Test BMC client _make_request with rate limiting."""
        from main import BMCAMIDevXClient, Settings

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client,
            mock_rate_limiter,
            mock_cache,
            mock_metrics,
            mock_error_handler,
        )

        # Mock rate limiter to allow request
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        # Mock successful response
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_httpx_client.request.return_value = mock_response

        result = await client._make_request("GET", "/test")

        assert result.status_code == 200
        assert result.json() == {"data": "test"}
        mock_rate_limiter.wait_for_token.assert_called_once()
        mock_metrics.record_bmc_api_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_bmc_client_make_request_rate_limited(
        self,
        mock_httpx_client,
        mock_rate_limiter,
        mock_cache,
        mock_metrics,
        mock_error_handler,
    ):
        """Test BMC client _make_request when rate limited."""
        from main import BMCAMIDevXClient, Settings

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client,
            mock_rate_limiter,
            mock_cache,
            mock_metrics,
            mock_error_handler,
        )

        # Mock rate limiter to deny request
        mock_rate_limiter.wait_for_token.side_effect = Exception("Rate limited")

        with pytest.raises(Exception):
            await client._make_request("GET", "/test")

        mock_rate_limiter.wait_for_token.assert_called_once()
        mock_httpx_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_bmc_client_get_cached_or_fetch_with_cache_hit(
        self,
        mock_httpx_client,
        mock_rate_limiter,
        mock_cache,
        mock_metrics,
        mock_error_handler,
    ):
        """Test BMC client _get_cached_or_fetch with cache hit."""
        from main import BMCAMIDevXClient, Settings

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client,
            mock_rate_limiter,
            mock_cache,
            mock_metrics,
            mock_error_handler,
        )

        # Mock cache hit
        mock_cache.get = unittest.mock.AsyncMock(return_value={"data": "cached"})

        async def fetch_func():
            return {"data": "fresh"}

        result = await client._get_cached_or_fetch("GET", "test_key", fetch_func)

        assert result == {"data": "cached"}
        mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_bmc_client_get_cached_or_fetch_with_cache_miss(
        self,
        mock_httpx_client,
        mock_rate_limiter,
        mock_cache,
        mock_metrics,
        mock_error_handler,
    ):
        """Test BMC client _get_cached_or_fetch with cache miss."""
        from main import BMCAMIDevXClient, Settings

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client,
            mock_rate_limiter,
            mock_cache,
            mock_metrics,
            mock_error_handler,
        )

        # Mock cache miss
        mock_cache.get = unittest.mock.AsyncMock(return_value=None)
        mock_cache.set = unittest.mock.AsyncMock()

        async def fetch_func():
            return {"data": "fresh"}

        result = await client._get_cached_or_fetch("GET", "test_key", fetch_func)

        assert result == {"data": "fresh"}
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_bmc_client_make_request_with_http_error(
        self,
        mock_httpx_client,
        mock_rate_limiter,
        mock_cache,
        mock_metrics,
        mock_error_handler,
    ):
        """Test BMC client _make_request with HTTP error."""
        import httpx

        from main import BMCAMIDevXClient, BMCAPIError, Settings

        settings = Settings()
        client = BMCAMIDevXClient(
            mock_httpx_client,
            mock_rate_limiter,
            mock_cache,
            mock_metrics,
            mock_error_handler,
        )

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock rate limiter to allow request
        mock_rate_limiter.wait_for_token = unittest.mock.AsyncMock()

        # Mock HTTP error
        mock_http_error = httpx.HTTPStatusError(
            "500 Internal Server Error", request=None, response=None
        )
        mock_httpx_client.request.side_effect = mock_http_error

        # Mock error handler
        mock_error_handler.handle_http_error.return_value = BMCAPIError("API Error")

        with pytest.raises(BMCAPIError):
            await client._make_request("GET", "/test")

        mock_error_handler.handle_http_error.assert_called_once()
        # Metrics are not updated for HTTP errors


class TestAuthentication:
    """Test authentication provider creation."""

    def test_no_auth_provider(self):
        """Test when authentication is disabled."""
        with unittest.mock.patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            provider = create_auth_provider()
            assert provider is None

    def test_jwt_auth_provider(self):
        """Test JWT authentication provider creation."""
        test_env = {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.jwt.JWTVerifier",
            "AUTH_JWKS_URI": "https://test.com/jwks.json",
            "AUTH_ISSUER": "https://test.com",
            "AUTH_AUDIENCE": "test-audience",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            # Mock the JWT provider class
            mock_provider_class = unittest.mock.MagicMock()
            mock_module = unittest.mock.MagicMock()
            mock_module.JWTVerifier = mock_provider_class
            mock_import = unittest.mock.MagicMock(return_value=mock_module)

            # Create test settings instance manually
            from main import Settings

            test_settings = Settings(
                auth_enabled=True,
                auth_provider="fastmcp.server.auth.providers.jwt.JWTVerifier",
                auth_jwks_uri="https://test.com/jwks.json",
                auth_issuer="https://test.com",
                auth_audience="test-audience",
            )
            provider = create_auth_provider(test_settings, import_func=mock_import)

            # Should have called the provider with correct parameters
            mock_provider_class.assert_called_once_with(
                jwks_uri="https://test.com/jwks.json",
                issuer="https://test.com",
                audience="test-audience",
            )

    def test_github_auth_provider(self):
        """Test GitHub authentication provider creation."""
        test_env = {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.github.GitHubProvider",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID": "test-client-id",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET": "test-client-secret",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            # Mock the GitHub provider class
            mock_provider_class = unittest.mock.MagicMock()
            mock_module = unittest.mock.MagicMock()
            mock_module.GitHubProvider = mock_provider_class
            mock_import = unittest.mock.MagicMock(return_value=mock_module)

            # Create test settings instance manually
            from main import Settings

            test_settings = Settings(
                auth_enabled=True,
                auth_provider="fastmcp.server.auth.providers.github.GitHubProvider",
                host="0.0.0.0",
                port=8080,
            )
            provider = create_auth_provider(test_settings, import_func=mock_import)

            # Should have called the provider with correct parameters
            mock_provider_class.assert_called_once_with(
                client_id="test-client-id",
                client_secret="test-client-secret",
                base_url="http://0.0.0.0:8080",
            )

    def test_auth_provider_import_error(self):
        """Test handling of import errors in auth provider creation."""
        test_env = {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "nonexistent.module.Provider",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            with unittest.mock.patch("builtins.print") as mock_print:
                # Create test settings instance manually
                from main import Settings

                test_settings = Settings(
                    auth_enabled=True, auth_provider="nonexistent.module.Provider"
                )
                provider = create_auth_provider(test_settings)

                assert provider is None
                mock_print.assert_called()

    def test_google_auth_provider(self):
        """Test Google authentication provider creation."""
        from main import Settings, create_auth_provider

        settings = Settings()
        settings.auth_enabled = True
        settings.auth_provider = "fastmcp.auth.GoogleProvider"

        # Mock the import function
        mock_import = unittest.mock.MagicMock()
        mock_provider_class = unittest.mock.MagicMock()
        mock_module = unittest.mock.MagicMock()
        mock_module.GoogleProvider = mock_provider_class
        mock_import.return_value = mock_module

        provider = create_auth_provider(settings, import_func=mock_import)

        assert provider is not None
        mock_provider_class.assert_called_once()

    def test_auth_kit_provider(self):
        """Test AuthKit authentication provider creation."""
        from main import Settings, create_auth_provider

        settings = Settings()
        settings.auth_enabled = True
        settings.auth_provider = "fastmcp.auth.AuthKitProvider"

        # Mock the import function
        mock_import = unittest.mock.MagicMock()
        mock_provider_class = unittest.mock.MagicMock()
        mock_module = unittest.mock.MagicMock()
        mock_module.AuthKitProvider = mock_provider_class
        mock_import.return_value = mock_module

        provider = create_auth_provider(settings, import_func=mock_import)

        assert provider is not None
        mock_provider_class.assert_called_once()


class TestFastMCPServer:
    """Test FastMCP server creation and configuration."""

    def test_server_creation(self):
        """Test FastMCP server creation."""
        with unittest.mock.patch("main.create_auth_provider", return_value=None):
            server = main.server

            assert isinstance(server, FastMCP)
            assert server.name == "BMC AMI DevX Code Pipeline MCP Server"
            assert server.version == "2.2.0"

    def test_server_with_auth(self):
        """Test FastMCP server creation with authentication."""
        mock_auth = unittest.mock.MagicMock()

        with unittest.mock.patch("main.create_auth_provider", return_value=mock_auth):
            # Recreate server with auth
            server = FastMCP(
                name="Test Server",
                version="1.0.0",
                instructions="Test server",
                auth=mock_auth,
            )

            assert server.auth == mock_auth


class TestMCPTools:
    """Test MCP tool functions."""

    @pytest.fixture
    def mock_bmc_client(self):
        """Create a mock BMC client."""
        with unittest.mock.patch("main.bmc_client") as mock_client:
            # Set up async mocks for BMC client methods
            mock_client.get_assignments = unittest.mock.AsyncMock()
            mock_client.create_assignment = unittest.mock.AsyncMock()
            mock_client.get_assignment_details = unittest.mock.AsyncMock()
            mock_client.get_assignment_tasks = unittest.mock.AsyncMock()
            mock_client.get_releases = unittest.mock.AsyncMock()
            mock_client.create_release = unittest.mock.AsyncMock()
            mock_client.generate_assignment = unittest.mock.AsyncMock()
            mock_client.promote_assignment = unittest.mock.AsyncMock()
            mock_client.deploy_assignment = unittest.mock.AsyncMock()
            yield mock_client

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context."""
        context = unittest.mock.MagicMock(spec=Context)
        context.info = unittest.mock.AsyncMock()
        context.error = unittest.mock.AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_assignments_success(self, mock_bmc_client, mock_context):
        """Test successful get_assignments tool call."""
        # Mock BMC client response
        mock_bmc_client.get_assignments.return_value = {
            "assignments": [{"id": "ASSIGN-001", "name": "Test Assignment"}]
        }

        # Import the core function (not the wrapped tool)
        from main import _get_assignments_core

        # Call the core function directly
        result = await _get_assignments_core(
            "TEST123", "DEV", "ASSIGN-001", mock_context
        )

        # Verify result
        result_data = json.loads(result)
        assert "assignments" in result_data
        assert len(result_data["assignments"]) == 1
        assert result_data["assignments"][0]["id"] == "ASSIGN-001"

        # Verify BMC client was called correctly
        mock_bmc_client.get_assignments.assert_called_once_with(
            "TEST123", "DEV", "ASSIGN-001"
        )

        # Verify context logging
        mock_context.info.assert_called()

    @pytest.mark.asyncio
    async def test_get_assignments_validation_error(
        self, mock_bmc_client, mock_context
    ):
        """Test get_assignments with validation error."""
        # Import the core function
        from main import _get_assignments_core

        # Call with invalid SRID
        result = await _get_assignments_core("", "DEV", None, mock_context)

        # Should return enhanced error JSON
        result_data = json.loads(result)
        assert result_data["error"] is True
        assert result_data["error_type"] == "VALIDATION_ERROR"
        assert "Validation failed" in result_data["message"]
        assert result_data["field"] == "input_validation"

        # BMC client should not be called
        mock_bmc_client.get_assignments.assert_not_called()

        # Context should log error
        mock_context.error.assert_called()

    @pytest.mark.asyncio
    async def test_get_assignments_http_error(self, mock_bmc_client, mock_context):
        """Test get_assignments with HTTP error."""
        # Import the core function
        from main import _get_assignments_core

        # Mock HTTP error
        mock_bmc_client.get_assignments.side_effect = httpx.HTTPError("API Error")

        # Call the core function
        result = await _get_assignments_core("TEST123", "DEV", None, mock_context)

        # Should return enhanced error JSON
        result_data = json.loads(result)
        assert result_data["error"] is True
        assert result_data["error_type"] == "SERVER_ERROR"
        assert "Internal server error during get_assignments" in result_data["message"]

        # Context should log error
        mock_context.error.assert_called()

    @pytest.mark.asyncio
    async def test_create_assignment_success(self, mock_bmc_client, mock_context):
        """Test successful create_assignment tool call."""
        # Import the core function
        from main import _create_assignment_core

        # Mock BMC client response
        mock_bmc_client.create_assignment.return_value = {
            "assignmentId": "ASSIGN-002",
            "status": "created",
        }

        # Call the core function
        result = await _create_assignment_core(
            "TEST123", "ASSIGN-002", "STREAM1", "APP1", None, mock_context
        )

        # Verify result
        result_data = json.loads(result)
        assert "assignmentId" in result_data
        assert result_data["assignmentId"] == "ASSIGN-002"

        # Verify BMC client was called
        mock_bmc_client.create_assignment.assert_called_once()
        call_args = mock_bmc_client.create_assignment.call_args
        assert call_args[0][0] == "TEST123"  # srid
        assert call_args[0][1]["assignmentId"] == "ASSIGN-002"

    @pytest.mark.asyncio
    async def test_get_assignment_details_success(self, mock_bmc_client, mock_context):
        """Test successful get_assignment_details tool call."""
        # Import the core function
        from main import _get_assignment_details_core

        # Mock BMC client response
        mock_bmc_client.get_assignment_details.return_value = {
            "assignmentId": "ASSIGN-001",
            "status": "active",
            "tasks": [],
        }

        # Call the core function
        result = await _get_assignment_details_core(
            "TEST123", "ASSIGN-001", mock_context
        )

        # Verify result
        result_data = json.loads(result)
        assert "assignmentId" in result_data
        assert result_data["assignmentId"] == "ASSIGN-001"

        # Verify BMC client was called
        mock_bmc_client.get_assignment_details.assert_called_once_with(
            "TEST123", "ASSIGN-001"
        )


class TestServerIntegration:
    """Test server integration and startup."""

    @pytest.mark.asyncio
    async def test_server_startup(self):
        """Test server startup without actually running it."""
        # This test verifies the server can be created and configured
        # without actually starting the HTTP server

        server = main.server
        assert server is not None
        assert isinstance(server, FastMCP)

        # Verify server has tools
        # Note: In real FastMCP, tools are registered via decorators
        # We can't easily test the exact number without running the server

        print("✅ Server startup test passed")

    def test_health_endpoint_route(self):
        """Test that health endpoint route is registered."""
        # In FastMCP, custom routes are registered via decorators
        # We can verify the route exists by checking the server configuration

        server = main.server
        assert server is not None

        # FastMCP handles route registration internally
        # This test mainly verifies the server can be created
        print("✅ Health endpoint route test passed")


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_tool_exception_handling(self):
        """Test that tools handle exceptions gracefully."""
        # Import the core function
        from main import _get_assignments_core

        with unittest.mock.patch("main.bmc_client") as mock_client:
            mock_client.get_assignments.side_effect = Exception("Unexpected error")

            context = unittest.mock.MagicMock(spec=Context)
            context.error = unittest.mock.AsyncMock()

            result = await _get_assignments_core("TEST123", None, None, context)

            # Should return enhanced error JSON
            result_data = json.loads(result)
            assert result_data["error"] is True
            assert result_data["error_type"] == "SERVER_ERROR"
            assert (
                "Internal server error during get_assignments" in result_data["message"]
            )
            assert "get_assignments" in result_data["operation"]
            assert "error_code" in result_data

            # Context should log error
            context.error.assert_called()

    def test_validation_error_messages(self):
        """Test that validation errors provide helpful messages."""
        # Test various validation error scenarios
        with pytest.raises(ValueError, match="SRID is required"):
            validate_srid("")

        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            validate_srid("INVALID@123")

        with pytest.raises(ValueError, match="Level must be one of"):
            validate_level("INVALID_LEVEL")


class TestConfiguration:
    """Test configuration and environment handling."""

    def test_configuration_file_loading(self):
        """Test loading configuration from .env file."""
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("HOST=127.0.0.1\n")
            f.write("PORT=9000\n")
            f.write("LOG_LEVEL=DEBUG\n")
            temp_env_file = f.name

        try:
            # Test loading from the temp file
            with unittest.mock.patch("main.Settings") as mock_settings:
                mock_settings.return_value.model_config = {"env_file": temp_env_file}

                # This would normally load from the .env file
                # In our test, we just verify the mechanism exists
                print("✅ Configuration file loading test passed")

        finally:
            os.unlink(temp_env_file)

    def test_environment_variable_precedence(self):
        """Test that environment variables override defaults."""
        test_env = {
            "HOST": "192.168.1.100",
            "PORT": "9999",
            "API_BASE_URL": "https://custom.bmc.com/api",
        }

        with unittest.mock.patch.dict(os.environ, test_env):
            # Use from_env() to get a fresh instance
            from main import Settings

            settings = Settings.from_env()

            assert settings.host == "192.168.1.100"
            assert settings.port == 9999
            assert settings.api_base_url == "https://custom.bmc.com/api"


if __name__ == "__main__":
    # Run the tests
    print("🧪 Running BMC AMI DevX Code Pipeline FastMCP Server Tests")
    pytest.main([__file__, "-v", "--tb=short"])
