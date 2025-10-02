#!/usr/bin/env python3
"""
Prometheus Configuration for FastMCP Server

This module provides Prometheus-specific metrics configuration and
custom metrics for the FastMCP server.
"""

import os
import logging
from typing import Dict, Any, Optional
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST, Info, Gauge, Counter
from starlette.responses import Response
from otel_config import get_otel_config

logger = logging.getLogger(__name__)


class PrometheusConfig:
    """Prometheus metrics configuration for FastMCP server."""
    
    def __init__(self):
        """Initialize Prometheus configuration."""
        self.enabled = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
        self.port = int(os.getenv("PROMETHEUS_METRICS_PORT", "9464"))
        self.path = os.getenv("PROMETHEUS_METRICS_PATH", "/metrics")
        self.registry = CollectorRegistry()
        
        # Custom metrics
        self.custom_metrics = None
        if self.enabled:
            self.custom_metrics = CustomPrometheusMetrics(self.registry)
            logger.info(f"Prometheus metrics configured on port {self.port}")
    
    async def metrics_handler(self, request) -> Response:
        """Handle Prometheus metrics scraping."""
        if not self.enabled:
            return Response(
                content="Prometheus metrics disabled",
                status_code=404
            )
        
        try:
            # Update custom metrics before generating output
            if self.custom_metrics:
                await self.custom_metrics.update_metrics()
            
            metrics_data = generate_latest(self.registry)
            return Response(
                content=metrics_data,
                media_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return Response(
                content=f"Error generating metrics: {str(e)}",
                status_code=500
            )


class CustomPrometheusMetrics:
    """Custom Prometheus metrics for FastMCP server."""
    
    def __init__(self, registry: CollectorRegistry):
        """Initialize custom Prometheus metrics."""
        self.registry = registry
        
        # Server information
        self.fastmcp_info = Info(
            'fastmcp_server_info',
            'FastMCP server information',
            registry=registry
        )
        
        # Tool metrics
        self.mcp_tools_total = Gauge(
            'fastmcp_mcp_tools_total',
            'Total number of MCP tools available',
            ['tool_type'],
            registry=registry
        )
        
        # BMC API quota and health
        self.bmc_api_quota_remaining = Gauge(
            'fastmcp_bmc_api_quota_remaining',
            'Remaining BMC API quota',
            registry=registry
        )
        
        self.bmc_api_health_status = Gauge(
            'fastmcp_bmc_api_health_status',
            'BMC API health status (1=healthy, 0=unhealthy)',
            registry=registry
        )
        
        # Cache metrics
        self.cache_memory_usage_bytes = Gauge(
            'fastmcp_cache_memory_usage_bytes',
            'Cache memory usage in bytes',
            registry=registry
        )
        
        self.cache_entry_count = Gauge(
            'fastmcp_cache_entry_count',
            'Number of entries in cache',
            registry=registry
        )
        
        # Rate limiter metrics
        self.rate_limiter_tokens_available = Gauge(
            'fastmcp_rate_limiter_tokens_available',
            'Available rate limiter tokens',
            ['client_id'],
            registry=registry
        )
        
        self.rate_limiter_capacity = Gauge(
            'fastmcp_rate_limiter_capacity',
            'Rate limiter total capacity',
            registry=registry
        )
        
        # Authentication metrics
        self.auth_provider_status = Gauge(
            'fastmcp_auth_provider_status',
            'Authentication provider status (1=enabled, 0=disabled)',
            ['provider'],
            registry=registry
        )
        
        # System resource metrics
        self.system_memory_usage_bytes = Gauge(
            'fastmcp_system_memory_usage_bytes',
            'System memory usage in bytes',
            registry=registry
        )
        
        self.system_cpu_usage_percent = Gauge(
            'fastmcp_system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=registry
        )
        
        # OpenTelemetry integration status
        self.otel_status = Gauge(
            'fastmcp_otel_status',
            'OpenTelemetry integration status (1=enabled, 0=disabled)',
            ['component'],
            registry=registry
        )
        
        # Initialize static information
        self._initialize_static_info()
        
        logger.info("Custom Prometheus metrics initialized")
    
    def _initialize_static_info(self):
        """Initialize static server information."""
        config = get_otel_config()
        
        self.fastmcp_info.info({
            'version': config.service_version,
            'service_name': config.service_name,
            'environment': config.environment,
            'framework': 'FastMCP',
            'python_version': os.sys.version.split()[0],
            'otel_enabled': str(config.otel_enabled).lower()
        })
        
        # Set OTEL component status
        self.otel_status.labels(component='tracing').set(1 if config.tracing_enabled else 0)
        self.otel_status.labels(component='metrics').set(1 if config.metrics_enabled else 0)
    
    async def update_metrics(self):
        """Update dynamic metrics."""
        try:
            # Import here to avoid circular imports
            from main import metrics, cache, settings
            import psutil
            
            # Update tool counts (mock data for now - would be populated by actual server)
            self.mcp_tools_total.labels(tool_type='openapi').set(15)
            self.mcp_tools_total.labels(tool_type='custom').set(8)
            self.mcp_tools_total.labels(tool_type='elicitation').set(3)
            self.mcp_tools_total.labels(tool_type='management').set(5)
            
            # Update cache metrics
            if cache:
                self.cache_entry_count.set(len(cache.cache))
                # Estimate memory usage (rough calculation)
                estimated_memory = len(cache.cache) * 1024  # 1KB per entry estimate
                self.cache_memory_usage_bytes.set(estimated_memory)
            
            # Update rate limiter metrics
            self.rate_limiter_capacity.set(settings.rate_limit_burst_size)
            # Default client tokens (would be updated by actual rate limiter)
            self.rate_limiter_tokens_available.labels(client_id='default').set(
                settings.rate_limit_burst_size
            )
            
            # Update authentication provider status
            auth_enabled = settings.auth_enabled
            self.auth_provider_status.labels(provider='jwt').set(
                1 if auth_enabled and settings.auth_provider == 'jwt' else 0
            )
            self.auth_provider_status.labels(provider='github').set(
                1 if auth_enabled and settings.auth_provider == 'github' else 0
            )
            self.auth_provider_status.labels(provider='google').set(
                1 if auth_enabled and settings.auth_provider == 'google' else 0
            )
            
            # Update system metrics
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                self.system_memory_usage_bytes.set(memory_info.rss)
                
                cpu_percent = process.cpu_percent()
                self.system_cpu_usage_percent.set(cpu_percent)
            except Exception as e:
                logger.warning(f"Failed to update system metrics: {e}")
            
            # Mock BMC API health (would be updated by actual health checker)
            self.bmc_api_health_status.set(1)  # Assume healthy
            self.bmc_api_quota_remaining.set(1000)  # Mock quota
            
        except Exception as e:
            logger.error(f"Error updating custom Prometheus metrics: {e}")


# Global Prometheus configuration
_prometheus_config: Optional[PrometheusConfig] = None


def get_prometheus_config() -> PrometheusConfig:
    """Get global Prometheus configuration."""
    global _prometheus_config
    if _prometheus_config is None:
        _prometheus_config = PrometheusConfig()
    return _prometheus_config


def is_prometheus_enabled() -> bool:
    """Check if Prometheus metrics are enabled."""
    config = get_prometheus_config()
    return config.enabled


async def prometheus_metrics_handler(request) -> Response:
    """Handle Prometheus metrics endpoint."""
    config = get_prometheus_config()
    return await config.metrics_handler(request)
