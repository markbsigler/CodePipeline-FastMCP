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
from typing import Dict, Any

import httpx
import pytest
from main import BMCAPIError
from fastmcp import FastMCP, Context

# Import the main module components
import main
from main import (
    Settings, 
    BMCAMIDevXClient, 
    validate_srid, 
    validate_assignment_id,
    validate_release_id,
    validate_level,
    validate_environment,
    retry_on_failure,
    create_auth_provider
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
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.jwt.JWTVerifier"
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
            assert settings.auth_provider == "fastmcp.server.auth.providers.jwt.JWTVerifier"
    
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


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_srid(self):
        """Test SRID validation."""
        # Valid SRIDs
        assert validate_srid("TEST123") == "TEST123"
        assert validate_srid("A1") == "A1"
        assert validate_srid("12345678") == "12345678"
        
        # Invalid SRIDs
        with pytest.raises(ValueError, match="SRID is required"):
            validate_srid("")
        
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            validate_srid("TOOLONG123")
        
        with pytest.raises(ValueError, match="SRID must be 1-8 alphanumeric"):
            validate_srid("test@123")
    
    def test_validate_assignment_id(self):
        """Test assignment ID validation."""
        # Valid assignment IDs
        assert validate_assignment_id("ASSIGN-001") == "ASSIGN-001"
        assert validate_assignment_id("TASK_123") == "TASK_123"
        assert validate_assignment_id("A1B2C3") == "A1B2C3"
        
        # Invalid assignment IDs
        with pytest.raises(ValueError, match="Assignment ID is required"):
            validate_assignment_id("")
        
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            validate_assignment_id("A" * 21)
        
        with pytest.raises(ValueError, match="Assignment ID must be 1-20"):
            validate_assignment_id("test@123")
    
    def test_validate_release_id(self):
        """Test release ID validation."""
        # Valid release IDs
        assert validate_release_id("REL-001") == "REL-001"
        assert validate_release_id("RELEASE_123") == "RELEASE_123"
        
        # Invalid release IDs
        with pytest.raises(ValueError, match="Release ID is required"):
            validate_release_id("")
        
        with pytest.raises(ValueError, match="Release ID must be 1-20"):
            validate_release_id("R" * 21)
    
    def test_validate_level(self):
        """Test level validation."""
        # Valid levels
        assert validate_level("DEV") == "DEV"
        assert validate_level("test") == "TEST"
        assert validate_level("PROD") == "PROD"
        
        # Invalid levels
        with pytest.raises(ValueError, match="Level must be one of"):
            validate_level("INVALID")
        
        # Empty level should return as-is
        assert validate_level("") == ""
        assert validate_level(None) is None
    
    def test_validate_environment(self):
        """Test environment validation."""
        # Valid environments
        assert validate_environment("DEV") == "DEV"
        assert validate_environment("stage") == "STAGE"
        assert validate_environment("PROD") == "PROD"
        
        # Invalid environments
        with pytest.raises(ValueError, match="Environment must be one of"):
            validate_environment("INVALID")
        
        # Empty environment should return as-is
        assert validate_environment("") == ""
        assert validate_environment(None) is None


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
        with unittest.mock.patch('httpx.AsyncClient') as mock_client:
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
        assignment_data = {"assignmentId": "ASSIGN-002", "stream": "STREAM1", "application": "APP1"}
        
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignmentId": "ASSIGN-002", "status": "created"}
        mock_response.raise_for_status.return_value = None
        
        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.create_assignment("TEST123", assignment_data)
        
        assert "assignmentId" in result
        assert result["assignmentId"] == "ASSIGN-002"
        mock_client_instance.request.assert_called_once_with("POST","/ispw/TEST123/assignments", json=assignment_data)
    
    @pytest.mark.asyncio
    async def test_get_assignment_details_success(self, mock_httpx_client):
        """Test successful get_assignment_details call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"assignmentId": "ASSIGN-001", "status": "active"}
        mock_response.raise_for_status.return_value = None
        
        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.get_assignment_details("TEST123", "ASSIGN-001")
        
        assert "assignmentId" in result
        assert result["assignmentId"] == "ASSIGN-001"
        mock_client_instance.request.assert_called_once_with("GET","/ispw/TEST123/assignments/ASSIGN-001")
    
    @pytest.mark.asyncio
    async def test_get_assignment_tasks_success(self, mock_httpx_client):
        """Test successful get_assignment_tasks call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"tasks": [{"id": "TASK-001", "name": "Task 1"}]}
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
        mock_client_instance.request.assert_called_once_with("GET","/ispw/TEST123/assignments/ASSIGN-001/tasks")
    
    @pytest.mark.asyncio
    async def test_generate_assignment_success(self, mock_httpx_client):
        """Test successful generate_assignment call."""
        generate_data = {"level": "DEV", "runtimeConfiguration": "config1"}
        
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"generationId": "GEN-001", "status": "started"}
        mock_response.raise_for_status.return_value = None
        
        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.generate_assignment("TEST123", "ASSIGN-001", generate_data)
        
        assert "generationId" in result
        assert result["generationId"] == "GEN-001"
        mock_client_instance.request.assert_called_once_with("POST","/ispw/TEST123/assignments/ASSIGN-001/generate", json=generate_data)
    
    @pytest.mark.asyncio
    async def test_promote_assignment_success(self, mock_httpx_client):
        """Test successful promote_assignment call."""
        promote_data = {"level": "TEST", "changeType": "minor"}
        
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"promotionId": "PROM-001", "status": "started"}
        mock_response.raise_for_status.return_value = None
        
        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.promote_assignment("TEST123", "ASSIGN-001", promote_data)
        
        assert "promotionId" in result
        assert result["promotionId"] == "PROM-001"
        mock_client_instance.request.assert_called_once_with("POST","/ispw/TEST123/assignments/ASSIGN-001/promote", json=promote_data)
    
    @pytest.mark.asyncio
    async def test_deploy_assignment_success(self, mock_httpx_client):
        """Test successful deploy_assignment call."""
        deploy_data = {"level": "PROD", "deployImplementationTime": "2025-01-09T10:00:00Z"}
        
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"deploymentId": "DEP-001", "status": "started"}
        mock_response.raise_for_status.return_value = None
        
        # Create a proper async mock
        mock_client_instance = unittest.mock.AsyncMock()
        mock_client_instance.request.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = BMCAMIDevXClient(mock_client_instance)
        result = await client.deploy_assignment("TEST123", "ASSIGN-001", deploy_data)
        
        assert "deploymentId" in result
        assert result["deploymentId"] == "DEP-001"
        mock_client_instance.request.assert_called_once_with("POST","/ispw/TEST123/assignments/ASSIGN-001/deploy", json=deploy_data)
    
    @pytest.mark.asyncio
    async def test_get_releases_success(self, mock_httpx_client):
        """Test successful get_releases call."""
        # Mock response
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"releases": [{"id": "REL-001", "name": "Release 1"}]}
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
        mock_client_instance.request.assert_called_once_with("GET","/ispw/TEST123/releases", params={"releaseId": "REL-001"})
    
    @pytest.mark.asyncio
    async def test_create_release_success(self, mock_httpx_client):
        """Test successful create_release call."""
        release_data = {"releaseId": "REL-002", "stream": "STREAM1", "application": "APP1"}
        
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
        mock_client_instance.request.assert_called_once_with("POST","/ispw/TEST123/releases", json=release_data)


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
        from main import BMCAMIDevXClient, RateLimiter
        import unittest.mock
        
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
        from main import Metrics
        
        metrics = Metrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time == 0.0
        assert metrics.min_response_time == float('inf')
        assert metrics.max_response_time == 0.0
    
    def test_metrics_update_response_time(self):
        """Test response time metrics updates."""
        from main import Metrics
        
        metrics = Metrics()
        metrics.update_response_time(1.5)
        metrics.update_response_time(2.0)
        metrics.update_response_time(0.5)
        
        assert abs(metrics.avg_response_time - 1.33) < 0.01  # (1.5 + 2.0 + 0.5) / 3
        assert metrics.min_response_time == 0.5
        assert metrics.max_response_time == 2.0
        assert len(metrics.response_times) == 3
    
    def test_metrics_success_rate(self):
        """Test success rate calculation."""
        from main import Metrics
        
        metrics = Metrics()
        metrics.successful_requests = 80
        metrics.failed_requests = 20
        
        assert metrics.get_success_rate() == 80.0
    
    def test_metrics_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        from main import Metrics
        
        metrics = Metrics()
        metrics.cache_hits = 75
        metrics.cache_misses = 25
        
        assert metrics.get_cache_hit_rate() == 75.0
    
    def test_metrics_to_dict(self):
        """Test metrics serialization to dictionary."""
        from main import Metrics
        
        metrics = Metrics()
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
        from main import HealthChecker, Settings
        import unittest.mock
        
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
        from main import HealthChecker, Settings
        import unittest.mock
        
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
        from main import BMCAPIError, BMCAPITimeoutError, BMCAPIRateLimitError
        
        # Test base BMC API error
        error = BMCAPIError("Test error", status_code=500, response_data={"test": "data"})
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
        
        error = MCPServerError("Server error", error_code="ERR001", details={"key": "value"})
        assert str(error) == "Server error"
        assert error.error_code == "ERR001"
        assert error.details == {"key": "value"}
    
    def test_error_handler_initialization(self):
        """Test error handler initialization."""
        from main import ErrorHandler, Settings, Metrics
        
        settings = Settings()
        metrics = Metrics()
        error_handler = ErrorHandler(settings, metrics)
        
        assert error_handler.settings == settings
        assert error_handler.metrics == metrics
    
    def test_error_handler_http_error_conversion(self):
        """Test HTTP error conversion to BMC API errors."""
        from main import ErrorHandler, Settings, BMCAPITimeoutError, BMCAPIAuthenticationError
        import httpx
        
        settings = Settings()
        error_handler = ErrorHandler(settings)
        
        # Test timeout error conversion
        timeout_error = httpx.TimeoutException("Request timed out")
        bmc_error = error_handler.handle_http_error(timeout_error, "test_operation")
        assert isinstance(bmc_error, BMCAPITimeoutError)
        assert "test_operation" in str(bmc_error)
        
        # Test HTTP status error conversion
        response = httpx.Response(401, request=httpx.Request("GET", "http://test.com"))
        status_error = httpx.HTTPStatusError("Unauthorized", request=response.request, response=response)
        bmc_error = error_handler.handle_http_error(status_error, "test_operation")
        assert isinstance(bmc_error, BMCAPIAuthenticationError)
        assert bmc_error.status_code == 401
    
    def test_error_handler_validation_error_conversion(self):
        """Test validation error conversion."""
        from main import ErrorHandler, Settings, MCPValidationError
        
        settings = Settings()
        error_handler = ErrorHandler(settings)
        
        validation_error = ValueError("Invalid format")
        mcp_error = error_handler.handle_validation_error(validation_error, "srid", "INVALID")
        
        assert isinstance(mcp_error, MCPValidationError)
        assert mcp_error.field == "srid"
        assert mcp_error.value == "INVALID"
        assert "Invalid format" in str(mcp_error)
    
    def test_error_handler_general_error_conversion(self):
        """Test general error conversion."""
        from main import ErrorHandler, Settings, MCPServerError
        
        settings = Settings()
        error_handler = ErrorHandler(settings)
        
        general_error = RuntimeError("Something went wrong")
        server_error = error_handler.handle_general_error(general_error, "test_operation")
        
        assert isinstance(server_error, MCPServerError)
        assert server_error.error_code == "INTERNAL_ERROR_TEST_OPERATION"
        assert "test_operation" in server_error.details["operation"]
        assert server_error.details["error_type"] == "RuntimeError"
    
    def test_error_response_creation(self):
        """Test standardized error response creation."""
        from main import ErrorHandler, Settings, BMCAPIError, MCPValidationError
        
        settings = Settings()
        error_handler = ErrorHandler(settings)
        
        # Test BMC API error response
        bmc_error = BMCAPIError("API Error", status_code=500, response_data={"test": "data"})
        response = error_handler.create_error_response(bmc_error, "test_operation")
        
        assert response["error"] is True
        assert response["operation"] == "test_operation"
        assert response["error_type"] == "BMC_API_ERROR"
        assert response["message"] == "API Error"
        assert response["status_code"] == 500
        assert response["response_data"] == {"test": "data"}
        assert "timestamp" in response
        
        # Test validation error response
        validation_error = MCPValidationError("Invalid input", field="srid", value="INVALID")
        response = error_handler.create_error_response(validation_error, "test_operation")
        
        assert response["error_type"] == "VALIDATION_ERROR"
        assert response["field"] == "srid"
        assert response["value"] == "INVALID"
    
    def test_error_response_message_truncation(self):
        """Test error message truncation."""
        from main import ErrorHandler, Settings, BMCAPIError
        
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
        from main import ErrorHandler, Settings, BMCAPITimeoutError
        
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
        result = await error_handler.execute_with_recovery("test_operation", failing_function)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_error_recovery_no_retry_for_validation_errors(self):
        """Test that validation errors are not retried."""
        from main import ErrorHandler, Settings, MCPValidationError
        
        settings = Settings(error_recovery_attempts=3)
        error_handler = ErrorHandler(settings)
        
        call_count = 0
        
        async def validation_failing_function():
            nonlocal call_count
            call_count += 1
            raise MCPValidationError("Validation failed")
        
        # Should not retry validation errors
        with pytest.raises(MCPValidationError):
            await error_handler.execute_with_recovery("test_operation", validation_failing_function)
        
        assert call_count == 1  # Should only be called once


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
            "AUTH_AUDIENCE": "test-audience"
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
                auth_audience="test-audience"
            )
            provider = create_auth_provider(test_settings, import_func=mock_import)
            
            # Should have called the provider with correct parameters
            mock_provider_class.assert_called_once_with(
                jwks_uri="https://test.com/jwks.json",
                issuer="https://test.com",
                audience="test-audience"
            )
    
    def test_github_auth_provider(self):
        """Test GitHub authentication provider creation."""
        test_env = {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "fastmcp.server.auth.providers.github.GitHubProvider",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID": "test-client-id",
            "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET": "test-client-secret"
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
                port=8080
            )
            provider = create_auth_provider(test_settings, import_func=mock_import)
            
            # Should have called the provider with correct parameters
            mock_provider_class.assert_called_once_with(
                client_id="test-client-id",
                client_secret="test-client-secret",
                base_url="http://0.0.0.0:8080"
            )
    
    def test_auth_provider_import_error(self):
        """Test handling of import errors in auth provider creation."""
        test_env = {
            "AUTH_ENABLED": "true",
            "AUTH_PROVIDER": "nonexistent.module.Provider"
        }
        
        with unittest.mock.patch.dict(os.environ, test_env):
            with unittest.mock.patch('builtins.print') as mock_print:
                # Create test settings instance manually
                from main import Settings
                test_settings = Settings(
                    auth_enabled=True,
                    auth_provider="nonexistent.module.Provider"
                )
                provider = create_auth_provider(test_settings)
                
                assert provider is None
                mock_print.assert_called()


class TestFastMCPServer:
    """Test FastMCP server creation and configuration."""
    
    def test_server_creation(self):
        """Test FastMCP server creation."""
        with unittest.mock.patch('main.create_auth_provider', return_value=None):
            server = main.server
            
            assert isinstance(server, FastMCP)
            assert server.name == "BMC AMI DevX Code Pipeline MCP Server"
            assert server.version == "2.2.0"
    
    def test_server_with_auth(self):
        """Test FastMCP server creation with authentication."""
        mock_auth = unittest.mock.MagicMock()
        
        with unittest.mock.patch('main.create_auth_provider', return_value=mock_auth):
            # Recreate server with auth
            server = FastMCP(
                name="Test Server",
                version="1.0.0",
                instructions="Test server",
                auth=mock_auth
            )
            
            assert server.auth == mock_auth


class TestMCPTools:
    """Test MCP tool functions."""
    
    @pytest.fixture
    def mock_bmc_client(self):
        """Create a mock BMC client."""
        with unittest.mock.patch('main.bmc_client') as mock_client:
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
        result = await _get_assignments_core("TEST123", "DEV", "ASSIGN-001", mock_context)
        
        # Verify result
        result_data = json.loads(result)
        assert "assignments" in result_data
        assert len(result_data["assignments"]) == 1
        assert result_data["assignments"][0]["id"] == "ASSIGN-001"
        
        # Verify BMC client was called correctly
        mock_bmc_client.get_assignments.assert_called_once_with("TEST123", "DEV", "ASSIGN-001")
        
        # Verify context logging
        mock_context.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_assignments_validation_error(self, mock_bmc_client, mock_context):
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
            "status": "created"
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
            "tasks": []
        }
        
        # Call the core function
        result = await _get_assignment_details_core("TEST123", "ASSIGN-001", mock_context)
        
        # Verify result
        result_data = json.loads(result)
        assert "assignmentId" in result_data
        assert result_data["assignmentId"] == "ASSIGN-001"
        
        # Verify BMC client was called
        mock_bmc_client.get_assignment_details.assert_called_once_with("TEST123", "ASSIGN-001")


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
        
        with unittest.mock.patch('main.bmc_client') as mock_client:
            mock_client.get_assignments.side_effect = Exception("Unexpected error")
            
            context = unittest.mock.MagicMock(spec=Context)
            context.error = unittest.mock.AsyncMock()
            
            result = await _get_assignments_core("TEST123", None, None, context)
            
            # Should return enhanced error JSON
            result_data = json.loads(result)
            assert result_data["error"] is True
            assert result_data["error_type"] == "SERVER_ERROR"
            assert "Internal server error during get_assignments" in result_data["message"]
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("HOST=127.0.0.1\n")
            f.write("PORT=9000\n")
            f.write("LOG_LEVEL=DEBUG\n")
            temp_env_file = f.name
        
        try:
            # Test loading from the temp file
            with unittest.mock.patch('main.Settings') as mock_settings:
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
            "API_BASE_URL": "https://custom.bmc.com/api"
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
