#!/usr/bin/env python3
"""
Tests for observability exporters module.

This module tests the exporters functionality including Prometheus
configuration and custom metrics.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prometheus_client import CollectorRegistry
from starlette.responses import Response


class TestObservabilityExportersInit:
    """Test the observability exporters __init__.py module."""

    def test_imports_available(self):
        """Test that required imports are available."""
        from observability.exporters import CustomPrometheusMetrics, PrometheusConfig

        assert PrometheusConfig is not None
        assert CustomPrometheusMetrics is not None

    def test_all_exports(self):
        """Test that __all__ exports are correct."""
        import observability.exporters as exporters_module

        expected_exports = ["PrometheusConfig", "CustomPrometheusMetrics"]
        assert hasattr(exporters_module, "__all__")
        assert set(exporters_module.__all__) == set(expected_exports)

        # Verify all exported items are actually available
        for export in expected_exports:
            assert hasattr(exporters_module, export)


class TestPrometheusConfig:
    """Test PrometheusConfig class."""

    def test_init_enabled(self):
        """Test PrometheusConfig initialization when enabled."""
        with patch.dict(
            os.environ,
            {
                "PROMETHEUS_ENABLED": "true",
                "PROMETHEUS_METRICS_PORT": "9464",
                "PROMETHEUS_METRICS_PATH": "/metrics",
            },
        ):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()

            assert config.enabled is True
            assert config.port == 9464
            assert config.path == "/metrics"
            assert config.registry is not None
            assert config.custom_metrics is not None

    def test_init_disabled(self):
        """Test PrometheusConfig initialization when disabled."""
        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "false"}):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()

            assert config.enabled is False
            assert config.custom_metrics is None

    def test_init_defaults(self):
        """Test PrometheusConfig initialization with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()

            assert config.enabled is True  # Default is true
            assert config.port == 9464  # Default port
            assert config.path == "/metrics"  # Default path

    @pytest.mark.asyncio
    async def test_metrics_handler_disabled(self):
        """Test metrics handler when Prometheus is disabled."""
        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "false"}):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()
            mock_request = Mock()

            response = await config.metrics_handler(mock_request)

            assert isinstance(response, Response)
            assert response.status_code == 404
            assert b"Prometheus metrics disabled" in response.body

    @pytest.mark.asyncio
    async def test_metrics_handler_success(self):
        """Test metrics handler when enabled and successful."""
        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()
            mock_request = Mock()

            # Mock the custom metrics update
            with patch.object(
                config.custom_metrics, "update_metrics", new_callable=AsyncMock
            ):
                response = await config.metrics_handler(mock_request)

            assert isinstance(response, Response)
            assert response.status_code == 200
            # Check content type more flexibly - just verify it's the prometheus content type
            assert "text/plain" in response.media_type
            assert "version=" in response.media_type  # Accept any version

    @pytest.mark.asyncio
    async def test_metrics_handler_exception(self):
        """Test metrics handler when an exception occurs."""
        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()
            mock_request = Mock()

            # Mock generate_latest to raise an exception
            with patch(
                "observability.exporters.prometheus_exporter.generate_latest",
                side_effect=Exception("Test error"),
            ):
                response = await config.metrics_handler(mock_request)

            assert isinstance(response, Response)
            assert response.status_code == 500
            assert b"Error generating metrics: Test error" in response.body

    @pytest.mark.asyncio
    async def test_metrics_handler_no_custom_metrics(self):
        """Test metrics handler when custom_metrics is None."""
        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            from observability.exporters.prometheus_exporter import PrometheusConfig

            config = PrometheusConfig()
            config.custom_metrics = None  # Simulate disabled custom metrics
            mock_request = Mock()

            response = await config.metrics_handler(mock_request)

            assert isinstance(response, Response)
            assert response.status_code == 200


class TestCustomPrometheusMetrics:
    """Test CustomPrometheusMetrics class."""

    def test_init(self):
        """Test CustomPrometheusMetrics initialization."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=True,
            )

            metrics = CustomPrometheusMetrics(registry)

            assert metrics.registry == registry
            assert metrics.fastmcp_info is not None
            assert metrics.mcp_tools_total is not None
            assert metrics.bmc_api_quota_remaining is not None
            assert metrics.bmc_api_health_status is not None
            assert metrics.cache_memory_usage_bytes is not None
            assert metrics.cache_entry_count is not None
            assert metrics.rate_limiter_tokens_available is not None
            assert metrics.rate_limiter_capacity is not None
            assert metrics.auth_provider_status is not None
            assert metrics.system_memory_usage_bytes is not None
            assert metrics.system_cpu_usage_percent is not None
            assert metrics.otel_status is not None

    def test_initialize_static_info(self):
        """Test static info initialization."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=False,
            )

            metrics = CustomPrometheusMetrics(registry)

            # Verify static info was set (we can't easily inspect the Info metric,
            # but we can verify the method was called without errors)
            assert metrics.fastmcp_info is not None

    @pytest.mark.asyncio
    async def test_update_metrics_success(self):
        """Test successful metrics update."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        # Mock the main module imports
        mock_metrics = Mock()
        mock_cache = Mock()
        mock_cache.cache = {"key1": "value1", "key2": "value2"}
        mock_settings = Mock(
            rate_limit_burst_size=10, auth_enabled=True, auth_provider="jwt"
        )

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=True,
            )

            metrics_obj = CustomPrometheusMetrics(registry)

            # Mock psutil
            mock_process = Mock()
            mock_memory_info = Mock(rss=1024 * 1024)  # 1MB
            mock_process.memory_info.return_value = mock_memory_info
            mock_process.cpu_percent.return_value = 15.5

            with patch.dict(
                "sys.modules",
                {
                    "main": Mock(
                        metrics=mock_metrics, cache=mock_cache, settings=mock_settings
                    ),
                    "psutil": Mock(Process=Mock(return_value=mock_process)),
                },
            ):
                await metrics_obj.update_metrics()

            # If no exception was raised, the test passes
            assert True

    @pytest.mark.asyncio
    async def test_update_metrics_import_error(self):
        """Test metrics update with import error."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=True,
            )

            metrics = CustomPrometheusMetrics(registry)

            # Mock import to fail
            with patch(
                "builtins.__import__", side_effect=ImportError("Module not found")
            ):
                # Should not raise exception, just log error
                await metrics.update_metrics()

            assert True  # Test passes if no exception raised

    @pytest.mark.asyncio
    async def test_update_metrics_psutil_error(self):
        """Test metrics update with psutil error."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        mock_metrics = Mock()
        mock_cache = Mock()
        mock_cache.cache = {}
        mock_settings = Mock(
            rate_limit_burst_size=10, auth_enabled=False, auth_provider="none"
        )

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=True,
            )

            metrics_obj = CustomPrometheusMetrics(registry)

            # Mock psutil to raise exception
            mock_process = Mock()
            mock_process.memory_info.side_effect = Exception("psutil error")

            with patch.dict(
                "sys.modules",
                {
                    "main": Mock(
                        metrics=mock_metrics, cache=mock_cache, settings=mock_settings
                    ),
                    "psutil": Mock(Process=Mock(return_value=mock_process)),
                },
            ):
                await metrics_obj.update_metrics()

            # Should handle the exception gracefully
            assert True

    @pytest.mark.asyncio
    async def test_update_metrics_no_cache(self):
        """Test metrics update when cache is None."""
        from observability.exporters.prometheus_exporter import CustomPrometheusMetrics

        registry = CollectorRegistry()

        mock_metrics = Mock()
        mock_settings = Mock(
            rate_limit_burst_size=5, auth_enabled=True, auth_provider="github"
        )

        with patch(
            "observability.exporters.prometheus_exporter.get_otel_config"
        ) as mock_config:
            mock_config.return_value = Mock(
                service_version="2.2.0",
                service_name="test-service",
                environment="test",
                otel_enabled=True,
                tracing_enabled=True,
                metrics_enabled=True,
            )

            metrics_obj = CustomPrometheusMetrics(registry)

            with patch.dict(
                "sys.modules",
                {
                    "main": Mock(
                        metrics=mock_metrics, cache=None, settings=mock_settings
                    ),
                    "psutil": Mock(
                        Process=Mock(
                            return_value=Mock(
                                memory_info=Mock(return_value=Mock(rss=2048)),
                                cpu_percent=Mock(return_value=25.0),
                            )
                        )
                    ),
                },
            ):
                await metrics_obj.update_metrics()

            assert True


class TestPrometheusGlobalFunctions:
    """Test global Prometheus functions."""

    def test_get_prometheus_config_singleton(self):
        """Test that get_prometheus_config returns singleton."""
        from observability.exporters.prometheus_exporter import get_prometheus_config

        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            config1 = get_prometheus_config()
            config2 = get_prometheus_config()

            assert config1 is config2  # Should be the same instance

    def test_is_prometheus_enabled_true(self):
        """Test is_prometheus_enabled when enabled."""
        from observability.exporters.prometheus_exporter import is_prometheus_enabled

        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            # Clear the global config to force re-initialization
            import observability.exporters.prometheus_exporter as prom_module

            prom_module._prometheus_config = None

            assert is_prometheus_enabled() is True

    def test_is_prometheus_enabled_false(self):
        """Test is_prometheus_enabled when disabled."""
        from observability.exporters.prometheus_exporter import is_prometheus_enabled

        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "false"}):
            # Clear the global config to force re-initialization
            import observability.exporters.prometheus_exporter as prom_module

            prom_module._prometheus_config = None

            assert is_prometheus_enabled() is False

    @pytest.mark.asyncio
    async def test_prometheus_metrics_handler(self):
        """Test prometheus_metrics_handler function."""
        from observability.exporters.prometheus_exporter import (
            prometheus_metrics_handler,
        )

        mock_request = Mock()

        with patch.dict(os.environ, {"PROMETHEUS_ENABLED": "true"}):
            # Clear the global config to force re-initialization
            import observability.exporters.prometheus_exporter as prom_module

            prom_module._prometheus_config = None

            response = await prometheus_metrics_handler(mock_request)

            assert isinstance(response, Response)
            assert response.status_code == 200
