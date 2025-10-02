#!/usr/bin/env python3
"""
Observability Configuration Module

Provides OpenTelemetry configuration and initialization utilities
that integrate with the FastMCP server's configuration system.
"""

from .otel_config import (
    OTELConfig,
    initialize_otel,
    get_tracer,
    get_meter,
    is_otel_enabled,
    is_tracing_enabled,
    is_metrics_enabled,
    get_otel_config
)

__all__ = [
    "OTELConfig",
    "initialize_otel", 
    "get_tracer",
    "get_meter",
    "is_otel_enabled",
    "is_tracing_enabled", 
    "is_metrics_enabled",
    "get_otel_config"
]
