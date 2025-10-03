#!/usr/bin/env python3
"""
OpenTelemetry Enhanced Metrics for FastMCP Server

This module provides OTEL-compatible metrics while maintaining backward compatibility
with the existing metrics system.
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from opentelemetry import metrics

from ..config.otel_config import get_meter, is_metrics_enabled

logger = logging.getLogger(__name__)


@dataclass
class LegacyMetrics:
    """Legacy metrics structure for backward compatibility."""

    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0

    # Response time metrics
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    avg_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0

    # API endpoint metrics
    endpoint_counts: Dict[str, int] = field(default_factory=dict)
    endpoint_errors: Dict[str, int] = field(default_factory=dict)

    # BMC API metrics
    bmc_api_calls: int = 0
    bmc_api_errors: int = 0
    bmc_api_response_times: deque = field(default_factory=lambda: deque(maxlen=1000))

    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_size: int = 0

    # System metrics
    start_time: datetime = field(default_factory=datetime.now)
    uptime_seconds: float = 0.0

    def update_response_time(self, response_time: float):
        """Update response time metrics."""
        self.response_times.append(response_time)
        if self.response_times:
            self.avg_response_time = sum(self.response_times) / len(self.response_times)
            self.min_response_time = min(self.min_response_time, response_time)
            self.max_response_time = max(self.max_response_time, response_time)

    def update_bmc_response_time(self, response_time: float):
        """Update BMC API response time metrics."""
        self.bmc_api_response_times.append(response_time)

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    def get_success_rate(self) -> float:
        """Calculate request success rate."""
        total = self.successful_requests + self.failed_requests
        return (self.successful_requests / total * 100) if total > 0 else 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        self.uptime_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "rate_limited": self.rate_limited_requests,
                "success_rate": self.get_success_rate(),
            },
            "response_times": {
                "average": round(self.avg_response_time, 3),
                "minimum": (
                    round(self.min_response_time, 3)
                    if self.min_response_time != float("inf")
                    else 0
                ),
                "maximum": round(self.max_response_time, 3),
                "recent_count": len(self.response_times),
            },
            "endpoints": {
                "counts": self.endpoint_counts,
                "errors": self.endpoint_errors,
            },
            "bmc_api": {
                "calls": self.bmc_api_calls,
                "errors": self.bmc_api_errors,
                "avg_response_time": (
                    sum(self.bmc_api_response_times) / len(self.bmc_api_response_times)
                    if self.bmc_api_response_times
                    else 0
                ),
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "size": self.cache_size,
                "hit_rate": self.get_cache_hit_rate(),
            },
            "system": {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "start_time": self.start_time.isoformat(),
            },
        }


class OTELMetrics:
    """OpenTelemetry-enhanced metrics for FastMCP server."""

    def __init__(self, meter: Optional[metrics.Meter] = None):
        """Initialize OTEL metrics."""
        self.meter = meter or get_meter()
        self.enabled = is_metrics_enabled() and self.meter is not None
        self.start_time = time.time()

        if not self.enabled:
            logger.info("OTEL metrics disabled or meter not available")
            return

        # Request metrics
        self.request_counter = self.meter.create_counter(
            name="fastmcp_requests_total",
            description="Total number of requests processed",
            unit="1",
        )

        self.request_duration = self.meter.create_histogram(
            name="fastmcp_request_duration_seconds",
            description="Request duration in seconds",
            unit="s",
            boundaries=[
                0.005,
                0.01,
                0.025,
                0.05,
                0.075,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                2.5,
                5.0,
                7.5,
                10.0,
            ],
        )

        self.active_requests = self.meter.create_up_down_counter(
            name="fastmcp_active_requests",
            description="Number of active requests",
            unit="1",
        )

        # BMC API metrics
        self.bmc_api_calls = self.meter.create_counter(
            name="fastmcp_bmc_api_calls_total",
            description="Total BMC API calls",
            unit="1",
        )

        self.bmc_api_duration = self.meter.create_histogram(
            name="fastmcp_bmc_api_duration_seconds",
            description="BMC API call duration",
            unit="s",
            boundaries=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        )

        # Cache metrics
        self.cache_operations = self.meter.create_counter(
            name="fastmcp_cache_operations_total",
            description="Cache operations (hits/misses)",
            unit="1",
        )

        self.cache_size = self.meter.create_up_down_counter(
            name="fastmcp_cache_size", description="Current cache size", unit="1"
        )

        # Rate limiting metrics
        self.rate_limit_events = self.meter.create_counter(
            name="fastmcp_rate_limit_events_total",
            description="Rate limiting events",
            unit="1",
        )

        # Tool execution metrics
        self.tool_executions = self.meter.create_counter(
            name="fastmcp_tool_executions_total",
            description="MCP tool executions",
            unit="1",
        )

        self.tool_duration = self.meter.create_histogram(
            name="fastmcp_tool_duration_seconds",
            description="Tool execution duration",
            unit="s",
            boundaries=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        # Authentication metrics
        self.auth_attempts = self.meter.create_counter(
            name="fastmcp_auth_attempts_total",
            description="Authentication attempts",
            unit="1",
        )

        # Elicitation metrics
        self.elicitation_workflows = self.meter.create_counter(
            name="fastmcp_elicitation_workflows_total",
            description="User elicitation workflows",
            unit="1",
        )

        self.elicitation_steps = self.meter.create_counter(
            name="fastmcp_elicitation_steps_total",
            description="Individual elicitation steps",
            unit="1",
        )

        # System metrics (observable gauges)
        self.uptime_gauge = self.meter.create_observable_gauge(
            name="fastmcp_uptime_seconds",
            description="Server uptime in seconds",
            unit="s",
            callbacks=[self._get_uptime],
        )

        logger.info("OTEL metrics initialized successfully")

    def _get_uptime(self, options) -> List[metrics.Observation]:
        """Callback for uptime gauge."""
        uptime = time.time() - self.start_time
        return [metrics.Observation(uptime)]

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        user_id: Optional[str] = None,
    ):
        """Record HTTP request metrics."""
        if not self.enabled:
            return

        labels = {
            "method": method,
            "endpoint": endpoint,
            "status_code": str(status_code),
            "status_class": f"{status_code // 100}xx",
        }

        if user_id:
            labels["user_id"] = user_id

        self.request_counter.add(1, labels)
        self.request_duration.record(duration, labels)

    def record_bmc_api_call(
        self,
        operation: str,
        success: bool,
        duration: float,
        status_code: Optional[int] = None,
    ):
        """Record BMC API call metrics."""
        if not self.enabled:
            return

        labels = {"operation": operation, "success": str(success).lower()}

        if status_code:
            labels["status_code"] = str(status_code)

        self.bmc_api_calls.add(1, labels)
        self.bmc_api_duration.record(duration, labels)

    def record_cache_operation(
        self, operation: str, hit: bool, key_type: Optional[str] = None
    ):
        """Record cache operation metrics."""
        if not self.enabled:
            return

        labels = {"operation": operation, "result": "hit" if hit else "miss"}

        if key_type:
            labels["key_type"] = key_type

        self.cache_operations.add(1, labels)

    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error_type: Optional[str] = None,
    ):
        """Record MCP tool execution metrics."""
        if not self.enabled:
            return

        labels = {
            "tool_name": tool_name,
            "success": str(success).lower(),
            "tool_type": self._get_tool_type(tool_name),
        }

        if error_type:
            labels["error_type"] = error_type

        self.tool_executions.add(1, labels)
        self.tool_duration.record(duration, labels)

    def record_auth_attempt(
        self, provider: str, success: bool, method: Optional[str] = None
    ):
        """Record authentication attempt."""
        if not self.enabled:
            return

        labels = {"provider": provider, "success": str(success).lower()}

        if method:
            labels["method"] = method

        self.auth_attempts.add(1, labels)

    def record_rate_limit_event(self, event_type: str, client_id: Optional[str] = None):
        """Record rate limiting event."""
        if not self.enabled:
            return

        labels = {"event_type": event_type}
        if client_id:
            labels["client_id"] = client_id

        self.rate_limit_events.add(1, labels)

    def record_elicitation_workflow(
        self,
        workflow_name: str,
        success: bool,
        steps_completed: int,
        user_cancelled: bool = False,
    ):
        """Record elicitation workflow metrics."""
        if not self.enabled:
            return

        labels = {
            "workflow_name": workflow_name,
            "success": str(success).lower(),
            "user_cancelled": str(user_cancelled).lower(),
        }

        self.elicitation_workflows.add(1, labels)
        self.elicitation_steps.add(steps_completed, {"workflow_name": workflow_name})

    def update_cache_size(self, size: int):
        """Update current cache size."""
        if not self.enabled:
            return

        # This is a bit tricky with UpDownCounter - we need to track the delta
        # For now, we'll use a simple approach
        self.cache_size.add(size, {"operation": "update"})

    def increment_active_requests(self):
        """Increment active request counter."""
        if not self.enabled:
            return
        self.active_requests.add(1)

    def decrement_active_requests(self):
        """Decrement active request counter."""
        if not self.enabled:
            return
        self.active_requests.add(-1)

    def _get_tool_type(self, tool_name: str) -> str:
        """Determine tool type from name."""
        if tool_name.startswith("ispw_"):
            return "openapi"
        elif tool_name.endswith("_interactive"):
            return "elicitation"
        elif tool_name in [
            "get_metrics",
            "get_health_status",
            "get_cache_stats",
            "clear_cache",
        ]:
            return "management"
        else:
            return "custom"


class HybridMetrics:
    """Hybrid metrics supporting both legacy and OTEL formats."""

    def __init__(self, otel_metrics: Optional[OTELMetrics] = None):
        """Initialize hybrid metrics."""
        self.otel = otel_metrics or OTELMetrics()
        self.legacy = LegacyMetrics()

        logger.info("Hybrid metrics initialized with OTEL and legacy support")

    # Backward compatibility properties
    @property
    def failed_requests(self) -> int:
        """Get failed requests count."""
        return self.legacy.failed_requests

    @failed_requests.setter
    def failed_requests(self, value: int):
        """Set failed requests count."""
        self.legacy.failed_requests = value

    @property
    def cache_misses(self) -> int:
        """Get cache misses count."""
        return self.legacy.cache_misses

    @cache_misses.setter
    def cache_misses(self, value: int):
        """Set cache misses count."""
        self.legacy.cache_misses = value

    @property
    def cache_size(self) -> int:
        """Get cache size."""
        return self.legacy.cache_size

    @cache_size.setter
    def cache_size(self, value: int):
        """Set cache size."""
        self.legacy.cache_size = value

    @property
    def total_requests(self) -> int:
        """Get total requests count."""
        return self.legacy.total_requests

    @total_requests.setter
    def total_requests(self, value: int):
        """Set total requests count."""
        self.legacy.total_requests = value

    @property
    def successful_requests(self) -> int:
        """Get successful requests count."""
        return self.legacy.successful_requests

    @successful_requests.setter
    def successful_requests(self, value: int):
        """Set successful requests count."""
        self.legacy.successful_requests = value

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        user_id: Optional[str] = None,
    ):
        """Record request in both systems."""
        # OTEL metrics
        self.otel.record_request(method, endpoint, status_code, duration, user_id)

        # Legacy metrics
        self.legacy.total_requests += 1
        if 200 <= status_code < 300:
            self.legacy.successful_requests += 1
        else:
            self.legacy.failed_requests += 1

        self.legacy.update_response_time(duration)

        # Update endpoint counts
        if endpoint not in self.legacy.endpoint_counts:
            self.legacy.endpoint_counts[endpoint] = 0
        self.legacy.endpoint_counts[endpoint] += 1

        if status_code >= 400:
            if endpoint not in self.legacy.endpoint_errors:
                self.legacy.endpoint_errors[endpoint] = 0
            self.legacy.endpoint_errors[endpoint] += 1

    def record_bmc_api_call(
        self,
        operation: str,
        success: bool,
        duration: float,
        status_code: Optional[int] = None,
    ):
        """Record BMC API call in both systems."""
        # OTEL metrics
        self.otel.record_bmc_api_call(operation, success, duration, status_code)

        # Legacy metrics
        self.legacy.bmc_api_calls += 1
        if not success:
            self.legacy.bmc_api_errors += 1
        self.legacy.update_bmc_response_time(duration)

    def record_cache_operation(
        self, operation: str, hit: bool, key_type: Optional[str] = None
    ):
        """Record cache operation in both systems."""
        # OTEL metrics
        self.otel.record_cache_operation(operation, hit, key_type)

        # Legacy metrics
        if hit:
            self.legacy.cache_hits += 1
        else:
            self.legacy.cache_misses += 1

    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error_type: Optional[str] = None,
    ):
        """Record tool execution in both systems."""
        # OTEL metrics
        self.otel.record_tool_execution(tool_name, success, duration, error_type)

    def record_auth_attempt(
        self, provider: str, success: bool, method: Optional[str] = None
    ):
        """Record authentication attempt in both systems."""
        # OTEL metrics
        self.otel.record_auth_attempt(provider, success, method)

    def record_rate_limit_event(self, event_type: str, client_id: Optional[str] = None):
        """Record rate limiting event in both systems."""
        # OTEL metrics
        self.otel.record_rate_limit_event(event_type, client_id)

        # Legacy metrics
        if event_type == "limited":
            self.legacy.rate_limited_requests += 1

    def record_elicitation_workflow(
        self,
        workflow_name: str,
        success: bool,
        steps_completed: int,
        user_cancelled: bool = False,
    ):
        """Record elicitation workflow in both systems."""
        # OTEL metrics
        self.otel.record_elicitation_workflow(
            workflow_name, success, steps_completed, user_cancelled
        )

    def update_cache_size(self, size: int):
        """Update cache size in both systems."""
        # OTEL metrics
        self.otel.update_cache_size(size)

        # Legacy metrics
        self.legacy.cache_size = size

    @property
    def cache_hits(self) -> int:
        return self.legacy.cache_hits

    @cache_hits.setter
    def cache_hits(self, value: int):
        self.legacy.cache_hits = value

    @property
    def bmc_api_calls(self) -> int:
        return self.legacy.bmc_api_calls

    @bmc_api_calls.setter
    def bmc_api_calls(self, value: int):
        self.legacy.bmc_api_calls = value

    @property
    def bmc_api_errors(self) -> int:
        return self.legacy.bmc_api_errors

    @bmc_api_errors.setter
    def bmc_api_errors(self, value: int):
        self.legacy.bmc_api_errors = value

    @property
    def endpoint_errors(self) -> dict:
        return self.legacy.endpoint_errors

    @endpoint_errors.setter
    def endpoint_errors(self, value: dict):
        self.legacy.endpoint_errors = value

    @property
    def response_times(self):
        return self.legacy.response_times

    @response_times.setter
    def response_times(self, value):
        self.legacy.response_times = value

    @property
    def min_response_time(self) -> float:
        return self.legacy.min_response_time

    @min_response_time.setter
    def min_response_time(self, value: float):
        self.legacy.min_response_time = value

    @property
    def max_response_time(self) -> float:
        return self.legacy.max_response_time

    @max_response_time.setter
    def max_response_time(self, value: float):
        self.legacy.max_response_time = value

    @property
    def avg_response_time(self) -> float:
        return self.legacy.avg_response_time

    @avg_response_time.setter
    def avg_response_time(self, value: float):
        self.legacy.avg_response_time = value

    @property
    def bmc_api_response_times(self):
        return self.legacy.bmc_api_response_times

    @bmc_api_response_times.setter
    def bmc_api_response_times(self, value):
        self.legacy.bmc_api_response_times = value

    @property
    def start_time(self):
        return self.legacy.start_time

    @start_time.setter
    def start_time(self, value):
        self.legacy.start_time = value

    def update_response_time(self, response_time: float):
        self.legacy.update_response_time(response_time)

    def get_cache_hit_rate(self) -> float:
        return self.legacy.get_cache_hit_rate()

    def get_success_rate(self) -> float:
        return self.legacy.get_success_rate()

    def update_bmc_response_time(self, response_time: float):
        """Update BMC API response time."""
        self.legacy.update_bmc_response_time(response_time)

    def increment_active_requests(self):
        """Increment active request counter."""
        self.otel.increment_active_requests()

    def decrement_active_requests(self):
        """Decrement active request counter."""
        self.otel.decrement_active_requests()

    def reset(self):
        """Reset all metrics to initial state."""
        # Reset legacy metrics
        self.legacy.total_requests = 0
        self.legacy.successful_requests = 0
        self.legacy.failed_requests = 0
        self.legacy.cache_hits = 0
        self.legacy.cache_misses = 0
        self.legacy.cache_size = 0
        self.legacy.bmc_api_calls = 0
        self.legacy.bmc_api_errors = 0
        self.legacy.endpoint_errors = {}
        self.legacy.response_times = []
        self.legacy.min_response_time = float("inf")
        self.legacy.max_response_time = 0.0
        self.legacy.avg_response_time = 0.0
        self.legacy.bmc_api_response_times = []
        self.legacy.start_time = datetime.now()

        # Reset OTEL metrics (if available)
        if self.otel:
            # OTEL metrics are cumulative by design, but we can reset our internal state
            # Note: This won't reset the actual OTEL counters/histograms as they're
            # cumulative
            pass

    def to_dict(self) -> Dict[str, Any]:
        """Get legacy metrics as dictionary for JSON serialization."""
        return self.legacy.to_dict()

    def to_json(self, indent: int = 2) -> str:
        """Get legacy metrics as JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# Global metrics instance
_metrics_instance: Optional[HybridMetrics] = None


def get_metrics() -> HybridMetrics:
    """Get global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = HybridMetrics()
    return _metrics_instance


def initialize_metrics() -> HybridMetrics:
    """Initialize global metrics."""
    global _metrics_instance
    _metrics_instance = HybridMetrics()
    logger.info("Global metrics initialized")
    return _metrics_instance
