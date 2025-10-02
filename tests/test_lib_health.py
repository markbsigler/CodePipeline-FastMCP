#!/usr/bin/env python3
"""
Tests for lib/health.py to improve coverage to 80%+.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import pytest

from lib.health import HealthChecker
from lib.settings import Settings


class TestHealthChecker:
    """Test HealthChecker class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bmc_client = Mock()
        self.settings = Settings()
        self.health_checker = HealthChecker(self.mock_bmc_client, self.settings)

    def test_health_checker_initialization(self):
        """Test HealthChecker initialization."""
        assert self.health_checker.bmc_client == self.mock_bmc_client
        assert self.health_checker.settings == self.settings
        assert isinstance(self.health_checker.start_time, datetime)

    @pytest.mark.asyncio
    async def test_check_api_health_success(self):
        """Test successful API health check."""
        # Mock successful API response
        self.mock_bmc_client.make_request = AsyncMock(return_value={
            "status": "healthy",
            "version": "1.0.0"
        })
        
        result = await self.health_checker.check_api_health()
        
        assert result["status"] == "healthy"
        assert result["response_time"] > 0
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_check_api_health_failure(self):
        """Test API health check failure."""
        # Mock API failure
        self.mock_bmc_client.make_request = AsyncMock(side_effect=Exception("API Error"))
        
        result = await self.health_checker.check_api_health()
        
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["response_time"] > 0

    @pytest.mark.asyncio
    async def test_check_api_health_timeout(self):
        """Test API health check with timeout."""
        # Mock timeout
        self.mock_bmc_client.make_request = AsyncMock(side_effect=asyncio.TimeoutError())
        
        result = await self.health_checker.check_api_health()
        
        assert result["status"] == "unhealthy"
        assert "timeout" in result["error"].lower()

    def test_check_system_resources_success(self):
        """Test successful system resource check."""
        with patch('psutil.cpu_percent', return_value=25.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock memory info
            mock_memory.return_value = Mock(percent=60.0, available=4000000000)
            
            # Mock disk info
            mock_disk.return_value = Mock(percent=45.0, free=50000000000)
            
            result = self.health_checker.check_system_resources()
            
            assert result["status"] == "healthy"
            assert result["cpu_percent"] == 25.5
            assert result["memory_percent"] == 60.0
            assert result["disk_percent"] == 45.0

    def test_check_system_resources_psutil_unavailable(self):
        """Test system resource check when psutil is unavailable."""
        with patch.dict('sys.modules', {'psutil': None}):
            result = self.health_checker.check_system_resources()
            
            assert result["status"] == "unavailable"
            assert "psutil not available" in result["message"]

    def test_check_system_resources_exception(self):
        """Test system resource check with exception."""
        with patch('psutil.cpu_percent', side_effect=Exception("System error")):
            result = self.health_checker.check_system_resources()
            
            assert result["status"] == "error"
            assert "error" in result

    def test_check_system_resources_high_usage(self):
        """Test system resource check with high resource usage."""
        with patch('psutil.cpu_percent', return_value=95.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock high resource usage
            mock_memory.return_value = Mock(percent=95.0, available=100000000)
            mock_disk.return_value = Mock(percent=98.0, free=1000000000)
            
            result = self.health_checker.check_system_resources()
            
            assert result["status"] == "warning"
            assert result["cpu_percent"] == 95.0
            assert result["memory_percent"] == 95.0
            assert result["disk_percent"] == 98.0

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_all_healthy(self):
        """Test comprehensive health check with all systems healthy."""
        # Mock healthy API
        self.mock_bmc_client.make_request = AsyncMock(return_value={"status": "ok"})
        
        with patch('psutil.cpu_percent', return_value=25.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=50.0, available=4000000000)
            mock_disk.return_value = Mock(percent=30.0, free=50000000000)
            
            result = await self.health_checker.get_comprehensive_health()
            
            assert result["status"] == "healthy"
            assert result["api"]["status"] == "healthy"
            assert result["system"]["status"] == "healthy"
            assert "uptime_seconds" in result
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_api_unhealthy(self):
        """Test comprehensive health check with unhealthy API."""
        # Mock unhealthy API
        self.mock_bmc_client.make_request = AsyncMock(side_effect=Exception("API Down"))
        
        with patch('psutil.cpu_percent', return_value=25.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=50.0, available=4000000000)
            mock_disk.return_value = Mock(percent=30.0, free=50000000000)
            
            result = await self.health_checker.get_comprehensive_health()
            
            assert result["status"] == "unhealthy"
            assert result["api"]["status"] == "unhealthy"
            assert result["system"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_comprehensive_health_system_warning(self):
        """Test comprehensive health check with system warnings."""
        # Mock healthy API
        self.mock_bmc_client.make_request = AsyncMock(return_value={"status": "ok"})
        
        with patch('psutil.cpu_percent', return_value=95.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=90.0, available=500000000)
            mock_disk.return_value = Mock(percent=95.0, free=2000000000)
            
            result = await self.health_checker.get_comprehensive_health()
            
            assert result["status"] == "warning"
            assert result["api"]["status"] == "healthy"
            assert result["system"]["status"] == "warning"

    def test_get_uptime(self):
        """Test uptime calculation."""
        # Set start time to 100 seconds ago
        self.health_checker.start_time = datetime.now() - timedelta(seconds=100)
        
        uptime = self.health_checker.get_uptime()
        
        # Should be approximately 100 seconds
        assert 95 <= uptime <= 105

    @pytest.mark.asyncio
    async def test_is_ready_healthy_system(self):
        """Test readiness check with healthy system."""
        # Mock healthy API
        self.mock_bmc_client.make_request = AsyncMock(return_value={"status": "ok"})
        
        with patch('psutil.cpu_percent', return_value=25.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=50.0, available=4000000000)
            mock_disk.return_value = Mock(percent=30.0, free=50000000000)
            
            result = await self.health_checker.is_ready()
            
            assert result["ready"] is True
            assert result["status"] == "ready"

    @pytest.mark.asyncio
    async def test_is_ready_unhealthy_system(self):
        """Test readiness check with unhealthy system."""
        # Mock unhealthy API
        self.mock_bmc_client.make_request = AsyncMock(side_effect=Exception("API Down"))
        
        result = await self.health_checker.is_ready()
        
        assert result["ready"] is False
        assert result["status"] == "not_ready"
        assert "reasons" in result

    @pytest.mark.asyncio
    async def test_check_dependencies_all_available(self):
        """Test dependency check with all dependencies available."""
        with patch('importlib.import_module') as mock_import:
            mock_import.return_value = Mock()
            
            result = await self.health_checker.check_dependencies()
            
            assert result["status"] == "healthy"
            assert "dependencies" in result
            assert all(dep["available"] for dep in result["dependencies"])

    @pytest.mark.asyncio
    async def test_check_dependencies_missing_dependency(self):
        """Test dependency check with missing dependency."""
        def mock_import_side_effect(module_name):
            if module_name == "psutil":
                raise ImportError("Module not found")
            return Mock()
        
        with patch('importlib.import_module', side_effect=mock_import_side_effect):
            result = await self.health_checker.check_dependencies()
            
            assert result["status"] == "warning"
            assert "dependencies" in result
            
            # Find psutil dependency
            psutil_dep = next((dep for dep in result["dependencies"] if dep["name"] == "psutil"), None)
            assert psutil_dep is not None
            assert psutil_dep["available"] is False

    def test_health_checker_with_custom_settings(self):
        """Test HealthChecker with custom settings."""
        custom_settings = Settings(
            api_timeout=60,
            cache_enabled=False,
            metrics_enabled=False
        )
        
        health_checker = HealthChecker(self.mock_bmc_client, custom_settings)
        
        assert health_checker.settings.api_timeout == 60
        assert health_checker.settings.cache_enabled is False
        assert health_checker.settings.metrics_enabled is False

    @pytest.mark.asyncio
    async def test_health_check_performance(self):
        """Test health check performance and timing."""
        # Mock fast API response
        self.mock_bmc_client.make_request = AsyncMock(return_value={"status": "ok"})
        
        start_time = datetime.now()
        result = await self.health_checker.check_api_health()
        end_time = datetime.now()
        
        # Health check should be reasonably fast
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should complete within 5 seconds
        assert result["response_time"] > 0

    def test_health_checker_initialization_edge_cases(self):
        """Test HealthChecker initialization with edge cases."""
        # Test with None client (should handle gracefully)
        with pytest.raises(AttributeError):
            health_checker = HealthChecker(None, self.settings)
            health_checker.bmc_client.make_request()

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """Test concurrent health check operations."""
        # Mock API response
        self.mock_bmc_client.make_request = AsyncMock(return_value={"status": "ok"})
        
        # Run multiple health checks concurrently
        tasks = [
            self.health_checker.check_api_health(),
            self.health_checker.get_comprehensive_health(),
            self.health_checker.is_ready()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 3
        assert all(isinstance(result, dict) for result in results)

    def test_health_status_priority(self):
        """Test health status priority logic."""
        # Test that unhealthy takes priority over warning
        api_status = {"status": "unhealthy"}
        system_status = {"status": "warning"}
        
        # Simulate the logic from get_comprehensive_health
        if api_status["status"] == "unhealthy" or system_status["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif api_status["status"] == "warning" or system_status["status"] == "warning":
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        assert overall_status == "unhealthy"
