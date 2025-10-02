#!/usr/bin/env python3
"""
Observability Metrics Module

Provides hybrid metrics collection that supports both legacy metrics
and OpenTelemetry metrics for comprehensive monitoring.
"""

from .hybrid_metrics import (
    HybridMetrics,
    LegacyMetrics,
    get_metrics,
    initialize_metrics
)

__all__ = [
    "HybridMetrics",
    "LegacyMetrics", 
    "get_metrics",
    "initialize_metrics"
]
