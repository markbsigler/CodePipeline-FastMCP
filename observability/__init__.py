#!/usr/bin/env python3
"""
Observability Package for FastMCP Server

This package provides comprehensive observability features including:
- OpenTelemetry configuration and initialization
- Distributed tracing for FastMCP operations
- Metrics collection and export (legacy + OTEL)
- Prometheus integration and exporters
- Grafana dashboards and alerting rules

## Package Structure
```
observability/
├── config/           # OpenTelemetry configuration and initialization
├── metrics/          # Hybrid metrics (legacy + OTEL) collection
├── tracing/          # Distributed tracing for FastMCP operations
├── exporters/        # Metrics exporters (Prometheus, OTLP, etc.)
├── dashboards/       # Grafana dashboard configurations
├── alerting/         # Prometheus/Grafana alerting rules
└── tests/           # Observability integration tests
```

The observability package follows the project's organizational best practices
and integrates seamlessly with the existing configuration system.
"""

from .config.otel_config import get_meter, get_tracer, initialize_otel, is_otel_enabled
from .metrics.hybrid_metrics import HybridMetrics, get_metrics, initialize_metrics
from .tracing.fastmcp_tracer import (
    get_elicitation_tracer,
    get_fastmcp_tracer,
    trace_bmc_operation,
    trace_tool_execution,
)

__version__ = "1.0.0"
__all__ = [
    # Configuration
    "initialize_otel",
    "get_tracer",
    "get_meter",
    "is_otel_enabled",
    # Metrics
    "HybridMetrics",
    "get_metrics",
    "initialize_metrics",
    # Tracing
    "get_fastmcp_tracer",
    "get_elicitation_tracer",
    "trace_tool_execution",
    "trace_bmc_operation",
]
