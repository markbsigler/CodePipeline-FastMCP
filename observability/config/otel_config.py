#!/usr/bin/env python3
"""
OpenTelemetry Configuration for FastMCP Server

This module provides a simplified, compatible OpenTelemetry configuration
that works with the installed OTEL packages.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Global configuration
_otel_config = None
_tracer = None
_meter = None


class OTELConfig:
    """Simplified OpenTelemetry configuration for FastMCP server."""
    
    def __init__(self):
        """Initialize OTEL configuration with environment variables."""
        # Service identification
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "fastmcp-server")
        self.service_version = os.getenv("OTEL_SERVICE_VERSION", "2.3.1")
        self.environment = os.getenv("OTEL_ENVIRONMENT", "development")
        
        # OTEL configuration
        self.otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
        self.tracing_enabled = os.getenv("OTEL_TRACING_ENABLED", "false").lower() == "true"
        self.metrics_enabled = os.getenv("OTEL_METRICS_ENABLED", "false").lower() == "true"
        
        logger.info(f"OTEL Config: enabled={self.otel_enabled}, tracing={self.tracing_enabled}, metrics={self.metrics_enabled}")
    
    def setup_tracing(self) -> Optional[object]:
        """Configure OpenTelemetry tracing."""
        if not self.otel_enabled or not self.tracing_enabled:
            logger.info("OpenTelemetry tracing is disabled")
            return None
            
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.semconv.resource import ResourceAttributes
            
            # Create resource
            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: self.service_name,
                ResourceAttributes.SERVICE_VERSION: self.service_version,
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            })
            
            # Set up tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)
            
            # Get tracer
            tracer = trace.get_tracer(self.service_name, self.service_version)
            logger.info("OpenTelemetry tracing configured successfully")
            return tracer
            
        except Exception as e:
            logger.error(f"Failed to configure OpenTelemetry tracing: {e}")
            return None
    
    def setup_metrics(self) -> Optional[object]:
        """Configure OpenTelemetry metrics."""
        if not self.otel_enabled or not self.metrics_enabled:
            logger.info("OpenTelemetry metrics is disabled")
            return None
            
        try:
            from opentelemetry import metrics
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.semconv.resource import ResourceAttributes
            
            # Create resource
            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: self.service_name,
                ResourceAttributes.SERVICE_VERSION: self.service_version,
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            })
            
            # Set up meter provider
            meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(meter_provider)
            
            # Get meter
            meter = metrics.get_meter(self.service_name, self.service_version)
            logger.info("OpenTelemetry metrics configured successfully")
            return meter
            
        except Exception as e:
            logger.error(f"Failed to configure OpenTelemetry metrics: {e}")
            return None


def get_otel_config() -> OTELConfig:
    """Get the global OTEL configuration."""
    global _otel_config
    if _otel_config is None:
        _otel_config = OTELConfig()
    return _otel_config


def initialize_otel() -> Tuple[Optional[object], Optional[object]]:
    """Initialize OpenTelemetry tracing and metrics."""
    global _tracer, _meter
    
    config = get_otel_config()
    
    if _tracer is None:
        _tracer = config.setup_tracing()
    
    if _meter is None:
        _meter = config.setup_metrics()
    
    return _tracer, _meter


def get_tracer() -> Optional[object]:
    """Get the global tracer."""
    global _tracer
    if _tracer is None:
        _tracer, _ = initialize_otel()
    return _tracer


def get_meter() -> Optional[object]:
    """Get the global meter."""
    global _meter
    if _meter is None:
        _, _meter = initialize_otel()
    return _meter


def is_otel_enabled() -> bool:
    """Check if OTEL is enabled."""
    return get_otel_config().otel_enabled


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return get_otel_config().tracing_enabled


def is_metrics_enabled() -> bool:
    """Check if metrics is enabled."""
    return get_otel_config().metrics_enabled