#!/usr/bin/env python3
"""
BMC AMI DevX Code Pipeline Component Library

This package provides reusable components for the FastMCP server including
clients, caching, metrics, health checking, error handling, and configuration.
"""

# Re-export observability components for convenience
from observability import HybridMetrics, get_metrics, initialize_metrics

from .auth import RateLimiter, create_auth_provider
from .cache import CacheEntry, IntelligentCache
from .clients import BMCAMIDevXClient
from .errors import (
    BMCAPIAuthenticationError,
    BMCAPIError,
    BMCAPINotFoundError,
    BMCAPIRateLimitError,
    BMCAPITimeoutError,
    BMCAPIValidationError,
    ErrorHandler,
)
from .health import HealthChecker
from .settings import Settings

__version__ = "2.2.0"
__all__ = [
    # Core components
    "Settings",
    "BMCAMIDevXClient",
    "IntelligentCache",
    "CacheEntry",
    "HealthChecker",
    "RateLimiter",
    # Error handling
    "BMCAPIError",
    "BMCAPITimeoutError",
    "BMCAPIAuthenticationError",
    "BMCAPINotFoundError",
    "BMCAPIValidationError",
    "BMCAPIRateLimitError",
    "ErrorHandler",
    # Authentication
    "create_auth_provider",
    # Metrics (re-exported from observability)
    "HybridMetrics",
    "get_metrics",
    "initialize_metrics",
]
