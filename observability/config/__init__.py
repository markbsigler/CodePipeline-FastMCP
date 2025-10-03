#!/usr/bin/env python3
"""
Observability Configuration Module

Provides OpenTelemetry configuration and initialization utilities
that integrate with the FastMCP server's configuration system.
"""

from .otel_config import (
    OTELConfig,
    get_meter,
    get_otel_config,
    get_tracer,
    initialize_otel,
    is_metrics_enabled,
    is_otel_enabled,
    is_tracing_enabled,
)

__all__ = [
    "OTELConfig",
    "initialize_otel",
    "get_tracer",
    "get_meter",
    "is_otel_enabled",
    "is_tracing_enabled",
    "is_metrics_enabled",
    "get_otel_config",
]
