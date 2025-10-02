#!/usr/bin/env python3
"""
BMC AMI DevX Code Pipeline MCP Server
Real FastMCP 2.x server for BMC AMI DevX Code Pipeline integration.

Enhanced with OpenTelemetry observability for distributed tracing,
metrics collection, and comprehensive monitoring.
"""

import asyncio
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, Field

# OpenTelemetry imports
from otel_config import initialize_otel, get_tracer, get_meter
from otel_metrics import HybridMetrics, get_metrics, initialize_metrics
from otel_tracing import get_fastmcp_tracer, get_elicitation_tracer, trace_tool_execution, trace_bmc_operation


# Custom Exception Classes
class BMCAPIError(Exception):
    """Base exception for BMC API related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class BMCAPITimeoutError(BMCAPIError):
    """Exception raised when BMC API requests timeout."""


class BMCAPIRateLimitError(BMCAPIError):
    """Exception raised when BMC API rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.retry_after = retry_after


class BMCAPIAuthenticationError(BMCAPIError):
    """Exception raised when BMC API authentication fails."""


class BMCAPINotFoundError(BMCAPIError):
    """Exception raised when BMC API resources are not found."""


class BMCAPIValidationError(BMCAPIError):
    """Exception raised when BMC API request validation fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[List[str]] = None,
    ):
        super().__init__(message, status_code, response_data)
        self.validation_errors = validation_errors or []


class MCPValidationError(Exception):
    """Exception raised when MCP tool input validation fails."""

    def __init__(
        self, message: str, field: Optional[str] = None, value: Optional[str] = None
    ):
        super().__init__(message)
        self.field = field
        self.value = value


class MCPServerError(Exception):
    """Exception raised for internal server errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class Settings(BaseModel):
    """Application settings with environment variable support."""

    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    log_level: str = Field(default="INFO")

    # BMC AMI DevX API configuration
    api_base_url: str = Field(default="https://devx.bmc.com/code-pipeline/api/v1")
    api_timeout: int = Field(default=30)
    api_retry_attempts: int = Field(default=3)

    # Rate limiting and connection pooling
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_burst_size: int = Field(default=10)
    connection_pool_size: int = Field(default=20)
    connection_pool_max_keepalive: int = Field(default=30)

    # Authentication configuration (FastMCP native)
    auth_provider: Optional[str] = Field(
        default=None
    )  # e.g., "fastmcp.server.auth.providers.jwt.JWTVerifier"
    auth_jwks_uri: Optional[str] = Field(default=None)
    auth_issuer: Optional[str] = Field(default=None)
    auth_audience: Optional[str] = Field(default=None)
    auth_secret: Optional[str] = Field(default=None)
    auth_enabled: bool = Field(default=False)

    # OpenAPI specification path
    openapi_spec_path: str = Field(default="config/openapi.json")

    # Monitoring and observability
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    health_check_interval: int = Field(default=30)
    log_requests: bool = Field(default=True)
    log_responses: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=False)
    tracing_endpoint: Optional[str] = Field(default=None)

    # Caching configuration
    enable_caching: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=300)  # 5 minutes
    cache_max_size: int = Field(default=1000)
    cache_cleanup_interval: int = Field(default=60)  # 1 minute

    # Error handling configuration
    enable_detailed_errors: bool = Field(default=True)
    log_error_details: bool = Field(default=True)
    max_error_message_length: int = Field(default=1000)
    enable_error_recovery: bool = Field(default=True)
    error_recovery_attempts: int = Field(default=3)

    model_config = ConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def from_env(cls, **kwargs) -> "Settings":
        """Create Settings instance from environment variables with optional overrides."""
        # Get current environment variables
        env_vars = {}
        for field_name, field_info in cls.model_fields.items():
            env_value = os.getenv(field_name.upper())
            if env_value is not None:
                # Handle type conversion
                if field_info.annotation == int:
                    try:
                        env_vars[field_name] = int(env_value)
                    except ValueError:
                        pass  # Keep as string, let Pydantic handle validation
                elif field_info.annotation == bool:
                    env_vars[field_name] = env_value.lower() in (
                        "true",
                        "1",
                        "yes",
                        "on",
                    )
                else:
                    env_vars[field_name] = env_value

        # Merge with any provided kwargs
        env_vars.update(kwargs)
        return cls(**env_vars)


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, requests_per_minute: int, burst_size: int):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a token for making an API request."""
        async with self.lock:
            now = datetime.now()
            time_passed = (now - self.last_refill).total_seconds()

            # Refill tokens based on time passed
            tokens_to_add = (time_passed / 60.0) * self.requests_per_minute
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            else:
                return False

    async def wait_for_token(self) -> None:
        """Wait until a token is available."""
        while not await self.acquire():
            # Calculate wait time based on refill rate
            wait_time = 60.0 / self.requests_per_minute
            await asyncio.sleep(wait_time)


@dataclass
class Metrics:
    """Application metrics for monitoring and observability."""

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
        return {
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "rate_limited": self.rate_limited_requests,
                "success_rate": self.get_success_rate(),
            },
            "response_times": {
                "average": self.avg_response_time,
                "minimum": (
                    self.min_response_time
                    if self.min_response_time != float("inf")
                    else 0
                ),
                "maximum": self.max_response_time,
                "samples": len(self.response_times),
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
                "hit_rate": self.get_cache_hit_rate(),
                "size": self.cache_size,
            },
            "system": {
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "start_time": self.start_time.isoformat(),
            },
        }


class HealthChecker:
    """Health check system for monitoring server status."""

    def __init__(self, bmc_client, settings: Settings):
        self.bmc_client = bmc_client
        self.settings = settings
        self.last_check = None
        self.health_status = "unknown"
        self.health_details = {}

    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        start_time = time.time()
        health_status = "healthy"
        health_details = {}

        try:
            # Check BMC API connectivity
            try:
                # Simple health check - try to get assignments with a minimal request
                await self.bmc_client.get_assignments("HEALTH_CHECK")
                health_details["bmc_api"] = "connected"
            except Exception as e:
                health_status = "degraded"
                health_details["bmc_api"] = f"error: {str(e)}"

            # Check rate limiter status
            if hasattr(self.bmc_client, "rate_limiter"):
                tokens_available = self.bmc_client.rate_limiter.tokens
                health_details["rate_limiter"] = f"tokens_available: {tokens_available}"

            # Check system resources
            import psutil

            health_details["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }

        except ImportError:
            health_details["system"] = "psutil not available"
        except Exception as e:
            health_status = "unhealthy"
            health_details["error"] = str(e)

        check_duration = time.time() - start_time
        health_details["check_duration_ms"] = round(check_duration * 1000, 2)

        self.last_check = datetime.now()
        self.health_status = health_status
        self.health_details = health_details

        return {
            "status": health_status,
            "timestamp": self.last_check.isoformat(),
            "details": health_details,
        }


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""

    data: Any
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return (datetime.now() - self.timestamp).total_seconds() > self.ttl_seconds


class IntelligentCache:
    """Intelligent caching system with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: deque = deque()
        self.lock = asyncio.Lock()

    def _generate_key(self, method: str, **kwargs) -> str:
        """Generate cache key from method and parameters."""
        # Sort kwargs for consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        key_parts = [method] + [f"{k}={v}" for k, v in sorted_kwargs]
        return "|".join(key_parts)

    async def get(self, method: str, **kwargs) -> Optional[Any]:
        """Get cached data if available and not expired."""
        tracer = get_fastmcp_tracer()
        key = self._generate_key(method, **kwargs)
        
        async with tracer.trace_cache_operation("get", key, method):
            async with self.lock:
                if key not in self.cache:
                    # Record cache miss
                    if hasattr(metrics, 'record_cache_operation'):
                        metrics.record_cache_operation("get", False, method)
                    return None

                entry = self.cache[key]
                if entry.is_expired():
                    # Remove expired entry
                    del self.cache[key]
                    if key in self.access_order:
                        self.access_order.remove(key)
                    # Record cache miss (expired)
                    if hasattr(metrics, 'record_cache_operation'):
                        metrics.record_cache_operation("get", False, method)
                    return None

                # Update access order (move to end)
                if key in self.access_order:
                    self.access_order.remove(key)
                self.access_order.append(key)

                # Record cache hit
                if hasattr(metrics, 'record_cache_operation'):
                    metrics.record_cache_operation("get", True, method)
                
                return entry.data

    async def set(
        self, method: str, data: Any, ttl: Optional[int] = None, **kwargs
    ) -> None:
        """Cache data with TTL."""
        tracer = get_fastmcp_tracer()
        key = self._generate_key(method, **kwargs)
        
        async with tracer.trace_cache_operation("set", key, method):
            async with self.lock:
                ttl = ttl or self.default_ttl

                # Remove existing entry if present
                if key in self.cache:
                    if key in self.access_order:
                        self.access_order.remove(key)

                # Add new entry
                self.cache[key] = CacheEntry(
                    data=data, timestamp=datetime.now(), ttl_seconds=ttl
                )
                self.access_order.append(key)

                # Evict if over capacity
                await self._evict_if_needed()
                
                # Update cache size metrics
                if hasattr(metrics, 'update_cache_size'):
                    metrics.update_cache_size(len(self.cache))

    async def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache is over capacity."""
        while len(self.cache) > self.max_size and self.access_order:
            # Remove least recently used entry
            lru_key = self.access_order.popleft()
            if lru_key in self.cache:
                del self.cache[lru_key]

    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed entries."""
        async with self.lock:
            expired_keys = []
            for key, entry in self.cache.items():
                if entry.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "keys": list(self.cache.keys()),
        }


class ErrorHandler:
    """Comprehensive error handling and recovery system."""

    def __init__(self, settings: Settings, metrics: Optional[Metrics] = None):
        self.settings = settings
        self.metrics = metrics

    def handle_http_error(self, error: httpx.HTTPError, operation: str) -> BMCAPIError:
        """Convert HTTP errors to specific BMC API errors."""
        if isinstance(error, httpx.TimeoutException):
            return BMCAPITimeoutError(
                f"BMC API request timed out during {operation}",
                response_data={"operation": operation, "error_type": "timeout"},
            )
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            response_data = {}

            try:
                response_data = error.response.json()
            except:
                response_data = {"raw_response": str(error.response.text)}

            if status_code == 401:
                return BMCAPIAuthenticationError(
                    f"BMC API authentication failed during {operation}",
                    status_code=status_code,
                    response_data=response_data,
                )
            elif status_code == 404:
                return BMCAPINotFoundError(
                    f"BMC API resource not found during {operation}",
                    status_code=status_code,
                    response_data=response_data,
                )
            elif status_code == 429:
                retry_after = error.response.headers.get("Retry-After")
                return BMCAPIRateLimitError(
                    f"BMC API rate limit exceeded during {operation}",
                    status_code=status_code,
                    response_data=response_data,
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif status_code == 422:
                validation_errors = response_data.get("errors", [])
                return BMCAPIValidationError(
                    f"BMC API validation failed during {operation}",
                    status_code=status_code,
                    response_data=response_data,
                    validation_errors=validation_errors,
                )
            else:
                return BMCAPIError(
                    f"BMC API error during {operation}: {error.response.status_code}",
                    status_code=status_code,
                    response_data=response_data,
                )
        else:
            return BMCAPIError(
                f"BMC API connection error during {operation}: {str(error)}",
                response_data={"operation": operation, "error_type": "connection"},
            )

    def handle_validation_error(
        self, error: ValueError, field: str, value: str
    ) -> MCPValidationError:
        """Convert validation errors to MCP validation errors."""
        return MCPValidationError(
            f"Validation failed for {field}: {str(error)}", field=field, value=value
        )

    def handle_general_error(self, error: Exception, operation: str) -> MCPServerError:
        """Convert general errors to MCP server errors."""
        error_code = f"INTERNAL_ERROR_{operation.upper()}"
        details = {
            "operation": operation,
            "error_type": type(error).__name__,
            "timestamp": datetime.now().isoformat(),
        }

        if self.settings.log_error_details:
            details["error_message"] = str(error)

        return MCPServerError(
            f"Internal server error during {operation}",
            error_code=error_code,
            details=details,
        )

    def create_error_response(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Create standardized error response."""
        response = {
            "error": True,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
        }

        if isinstance(error, BMCAPIError):
            response.update(
                {
                    "error_type": "BMC_API_ERROR",
                    "message": str(error),
                    "status_code": getattr(error, "status_code", None),
                    "response_data": getattr(error, "response_data", {}),
                }
            )

            if isinstance(error, BMCAPIRateLimitError):
                response["retry_after"] = getattr(error, "retry_after", None)
            elif isinstance(error, BMCAPIValidationError):
                response["validation_errors"] = getattr(error, "validation_errors", [])

        elif isinstance(error, MCPValidationError):
            response.update(
                {
                    "error_type": "VALIDATION_ERROR",
                    "message": str(error),
                    "field": getattr(error, "field", None),
                    "value": getattr(error, "value", None),
                }
            )

        elif isinstance(error, MCPServerError):
            response.update(
                {
                    "error_type": "SERVER_ERROR",
                    "message": str(error),
                    "error_code": getattr(error, "error_code", None),
                    "details": getattr(error, "details", {}),
                }
            )

        else:
            response.update(
                {
                    "error_type": "UNKNOWN_ERROR",
                    "message": (
                        str(error)
                        if self.settings.enable_detailed_errors
                        else "An unexpected error occurred"
                    ),
                }
            )

        # Truncate message if too long
        if len(response.get("message", "")) > self.settings.max_error_message_length:
            response["message"] = (
                response["message"][: self.settings.max_error_message_length] + "..."
            )

        # Update metrics
        if self.metrics:
            self.metrics.failed_requests += 1
            if hasattr(error, "status_code") and error.status_code:
                endpoint_key = f"{operation}_{error.status_code}"
                self.metrics.endpoint_errors[endpoint_key] = (
                    self.metrics.endpoint_errors.get(endpoint_key, 0) + 1
                )

        return response

    async def execute_with_recovery(self, operation: str, func, *args, **kwargs):
        """Execute function with error recovery and retry logic."""
        last_error = None

        for attempt in range(self.settings.error_recovery_attempts):
            try:
                result = await func(*args, **kwargs)

                # Update metrics on success
                if self.metrics:
                    self.metrics.successful_requests += 1

                return result

            except Exception as error:
                last_error = error

                # Don't retry certain types of errors
                if isinstance(
                    error,
                    (
                        MCPValidationError,
                        BMCAPIAuthenticationError,
                        BMCAPINotFoundError,
                    ),
                ):
                    break

                # Don't retry on last attempt
                if attempt == self.settings.error_recovery_attempts - 1:
                    break

                # Wait before retry (exponential backoff)
                wait_time = (2**attempt) * 0.5
                await asyncio.sleep(wait_time)

        # All retries failed, raise the last error
        raise last_error


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance, reloading from environment if needed."""
    # Create a new Settings instance which will pick up current environment variables
    return Settings.from_env()


# Input validation functions
def validate_srid(srid: str) -> str:
    """Validate SRID format."""
    if not srid or not isinstance(srid, str):
        raise ValueError("SRID is required and must be a string")

    # SRID should be alphanumeric, typically 1-8 characters
    if not re.match(r"^[A-Z0-9]{1,8}$", srid.upper()):
        raise ValueError("SRID must be 1-8 alphanumeric characters")

    return srid.upper()


def validate_assignment_id(assignment_id: str) -> str:
    """Validate assignment ID format."""
    if not assignment_id or not isinstance(assignment_id, str):
        raise ValueError("Assignment ID is required and must be a string")

    # Assignment ID should be alphanumeric with possible hyphens/underscores
    if not re.match(r"^[A-Z0-9_-]{1,20}$", assignment_id.upper()):
        raise ValueError(
            "Assignment ID must be 1-20 alphanumeric characters with optional hyphens/underscores"
        )

    return assignment_id.upper()


def validate_release_id(release_id: str) -> str:
    """Validate release ID format."""
    if not release_id or not isinstance(release_id, str):
        raise ValueError("Release ID is required and must be a string")

    # Release ID should be alphanumeric with possible hyphens/underscores
    if not re.match(r"^[A-Z0-9_-]{1,20}$", release_id.upper()):
        raise ValueError(
            "Release ID must be 1-20 alphanumeric characters with optional hyphens/underscores"
        )

    return release_id.upper()


def validate_level(level: str) -> str:
    """Validate level parameter."""
    if not level:
        return level

    valid_levels = ["DEV", "TEST", "STAGE", "PROD", "UAT", "QA"]
    if level.upper() not in valid_levels:
        raise ValueError(f"Level must be one of: {', '.join(valid_levels)}")

    return level.upper()


def validate_environment(env: str) -> str:
    """Validate environment parameter."""
    if not env:
        return env

    valid_envs = ["DEV", "TEST", "STAGE", "PROD", "UAT", "QA"]
    if env.upper() not in valid_envs:
        raise ValueError(f"Environment must be one of: {', '.join(valid_envs)}")

    return env.upper()


# Retry logic decorator
def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry API calls on failure."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (2**attempt))  # Exponential backoff
                        continue
                    else:
                        raise last_exception
                except Exception as e:
                    # Don't retry on validation errors or other non-retryable errors
                    raise e

            raise last_exception

        return wrapper

    return decorator


def create_auth_provider(
    settings_instance: Optional[Settings] = None, import_func=None
):
    """Create FastMCP authentication provider based on settings."""
    if settings_instance is None:
        settings_instance = settings

    if not settings_instance.auth_enabled or not settings_instance.auth_provider:
        return None

    try:
        # Import the authentication provider dynamically
        module_path, class_name = settings_instance.auth_provider.rsplit(".", 1)
        import_func = import_func or __import__
        module = import_func(module_path, fromlist=[class_name])
        provider_class = getattr(module, class_name)

        # Configure provider based on type
        if "JWTVerifier" in settings_instance.auth_provider:
            return provider_class(
                jwks_uri=settings_instance.auth_jwks_uri,
                issuer=settings_instance.auth_issuer,
                audience=settings_instance.auth_audience,
            )
        elif "GitHubProvider" in settings_instance.auth_provider:
            return provider_class(
                client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
                client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET"),
                base_url=f"http://{settings_instance.host}:{settings_instance.port}",
            )
        elif "GoogleProvider" in settings_instance.auth_provider:
            return provider_class(
                client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
                base_url=f"http://{settings_instance.host}:{settings_instance.port}",
            )
        else:
            # Generic provider - pass common settings
            return provider_class()

    except Exception as e:
        print(f"Warning: Failed to create auth provider: {e}")
        return None


# HTTP client for BMC AMI DevX API
# HTTP client with connection pooling
limits = httpx.Limits(
    max_keepalive_connections=settings.connection_pool_size,
    max_connections=settings.connection_pool_size * 2,
    keepalive_expiry=settings.connection_pool_max_keepalive,
)

http_client = httpx.AsyncClient(
    base_url=settings.api_base_url,
    timeout=settings.api_timeout,
    limits=limits,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
)


class BMCAMIDevXClient:
    """Client for BMC AMI DevX Code Pipeline API operations with retry logic, rate limiting, connection pooling, monitoring, caching, and enhanced error handling."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: Optional[RateLimiter] = None,
        cache: Optional[IntelligentCache] = None,
        metrics: Optional[Metrics] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        self.client = client
        self.max_retries = settings.api_retry_attempts
        self.retry_delay = 1.0  # seconds
        self.rate_limiter = rate_limiter or RateLimiter(
            settings.rate_limit_requests_per_minute, settings.rate_limit_burst_size
        )
        self.cache = cache
        self.metrics = metrics
        self.error_handler = error_handler or ErrorHandler(settings, metrics)

    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with rate limiting, monitoring, caching, and enhanced error handling."""
        start_time = time.time()
        operation = f"{method} {url}"
        
        # Get tracer for BMC API calls
        tracer = get_fastmcp_tracer()

        async with tracer.trace_bmc_api_call(operation, url, method) as span:
            try:
                # Wait for rate limit token
                await self.rate_limiter.wait_for_token()

                # Make the request
                response = await self.client.request(method, url, **kwargs)
                
                # Add response details to span
                if span:
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("http.response_size", len(response.content) if response.content else 0)

                # Update metrics (both legacy and OTEL)
                if self.metrics:
                    response_time = time.time() - start_time
                    success = response.status_code < 400
                    
                    # Record in hybrid metrics (handles both OTEL and legacy)
                    self.metrics.record_bmc_api_call(operation, success, response_time, response.status_code)

                return response

            except httpx.HTTPError as error:
                # Convert HTTP errors to specific BMC API errors
                bmc_error = self.error_handler.handle_http_error(error, operation)
                raise bmc_error
            except Exception as error:
                # Handle other types of errors
                server_error = self.error_handler.handle_general_error(error, operation)
                raise server_error

    async def _get_cached_or_fetch(
        self, method: str, cache_key: str, fetch_func, **kwargs
    ) -> Any:
        """Get data from cache or fetch from API with caching."""
        if not self.cache or not settings.enable_caching:
            return await fetch_func()

        # Try to get from cache
        cached_data = await self.cache.get(method, **kwargs)
        if cached_data is not None:
            if self.metrics:
                self.metrics.cache_hits += 1
            return cached_data

        # Cache miss - fetch from API
        if self.metrics:
            self.metrics.cache_misses += 1

        data = await fetch_func()

        # Cache the result
        await self.cache.set(method, data, **kwargs)

        return data

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_assignments(
        self,
        srid: str,
        level: Optional[str] = None,
        assignment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get assignments for a specific SRID with caching."""

        async def fetch_assignments():
            params = {}
            if level:
                params["level"] = level
            if assignment_id:
                params["assignmentId"] = assignment_id

            response = await self._make_request(
                "GET", f"/ispw/{srid}/assignments", params=params
            )
            response.raise_for_status()
            return response.json()

        return await self._get_cached_or_fetch(
            "get_assignments",
            f"assignments_{srid}_{level}_{assignment_id}",
            fetch_assignments,
            srid=srid,
            level=level,
            assignment_id=assignment_id,
        )

    @retry_on_failure(max_retries=3, delay=1.0)
    async def create_assignment(
        self, srid: str, assignment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new assignment."""
        response = await self._make_request(
            "POST", f"/ispw/{srid}/assignments", json=assignment_data
        )
        response.raise_for_status()
        return response.json()

    async def get_assignment_details(
        self, srid: str, assignment_id: str
    ) -> Dict[str, Any]:
        """Get details for a specific assignment."""
        response = await self._make_request(
            "GET", f"/ispw/{srid}/assignments/{assignment_id}"
        )
        response.raise_for_status()
        return response.json()

    async def get_assignment_tasks(
        self, srid: str, assignment_id: str
    ) -> Dict[str, Any]:
        """Get tasks for a specific assignment."""
        response = await self._make_request(
            "GET", f"/ispw/{srid}/assignments/{assignment_id}/tasks"
        )
        response.raise_for_status()
        return response.json()

    async def generate_assignment(
        self, srid: str, assignment_id: str, generate_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate code for an assignment."""
        response = await self._make_request(
            "POST",
            f"/ispw/{srid}/assignments/{assignment_id}/generate",
            json=generate_data,
        )
        response.raise_for_status()
        return response.json()

    async def promote_assignment(
        self, srid: str, assignment_id: str, promote_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Promote assignment to next level."""
        response = await self._make_request(
            "POST",
            f"/ispw/{srid}/assignments/{assignment_id}/promote",
            json=promote_data,
        )
        response.raise_for_status()
        return response.json()

    async def deploy_assignment(
        self, srid: str, assignment_id: str, deploy_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy assignment to target environment."""
        response = await self._make_request(
            "POST", f"/ispw/{srid}/assignments/{assignment_id}/deploy", json=deploy_data
        )
        response.raise_for_status()
        return response.json()

    async def get_releases(
        self, srid: str, release_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get releases for a specific SRID."""
        params = {}
        if release_id:
            params["releaseId"] = release_id

        response = await self._make_request(
            "GET", f"/ispw/{srid}/releases", params=params
        )
        response.raise_for_status()
        return response.json()

    async def create_release(
        self, srid: str, release_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new release."""
        response = await self._make_request(
            "POST", f"/ispw/{srid}/releases", json=release_data
        )
        response.raise_for_status()
        return response.json()

    async def get_release_details(self, srid: str, release_id: str) -> Dict[str, Any]:
        """Get details for a specific release."""
        response = await self._make_request(
            "GET", f"/ispw/{srid}/releases/{release_id}"
        )
        response.raise_for_status()
        return response.json()

    async def deploy_release(
        self, srid: str, release_id: str, deploy_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy a release."""
        response = await self._make_request(
            "POST", f"/ispw/{srid}/releases/{release_id}/deploy", json=deploy_data
        )
        response.raise_for_status()
        return response.json()

    async def get_sets(self, srid: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        """Get sets for a specific SRID."""
        params = {}
        if set_id:
            params["setId"] = set_id

        response = await self._make_request("GET", f"/ispw/{srid}/sets", params=params)
        response.raise_for_status()
        return response.json()

    async def deploy_set(
        self, srid: str, set_id: str, deploy_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy a set."""
        response = await self._make_request(
            "POST", f"/ispw/{srid}/sets/{set_id}/deploy", json=deploy_data
        )
        response.raise_for_status()
        return response.json()

    async def get_packages(
        self, srid: str, package_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get packages for a specific SRID."""
        params = {}
        if package_id:
            params["packageId"] = package_id

        response = await self._make_request(
            "GET", f"/ispw/{srid}/packages", params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_package_details(self, srid: str, package_id: str) -> Dict[str, Any]:
        """Get details for a specific package."""
        response = await self._make_request(
            "GET", f"/ispw/{srid}/packages/{package_id}"
        )
        response.raise_for_status()
        return response.json()


# Initialize OpenTelemetry observability
tracer, meter = initialize_otel()

# Initialize global instances
# Global hybrid metrics instance (OTEL + legacy)
metrics = initialize_metrics()

# Global cache instance
cache = IntelligentCache(
    max_size=settings.cache_max_size, default_ttl=settings.cache_ttl_seconds
)

# Global error handler
error_handler = ErrorHandler(settings, metrics)

# Initialize BMC AMI DevX client with monitoring, caching, and error handling
bmc_client = BMCAMIDevXClient(
    http_client, cache=cache, metrics=metrics, error_handler=error_handler
)

# Initialize health checker
health_checker = HealthChecker(bmc_client, settings)

# Create FastMCP server with authentication
auth_provider = create_auth_provider()
server = FastMCP(
    name="BMC AMI DevX Code Pipeline MCP Server",
    version="2.2.0",
    instructions="MCP server for BMC AMI DevX Code Pipeline integration with comprehensive ISPW operations",
    auth=auth_provider,
)


# Add monitoring and health check endpoints
@server.tool
async def get_metrics(ctx: Context = None) -> str:
    """Get server metrics and performance statistics."""
    return await trace_tool_execution(
        "get_metrics", {}, _get_metrics_impl, ctx
    )

async def _get_metrics_impl(ctx: Context = None) -> str:
    """Implementation of get_metrics with tracing."""
    if ctx:
        ctx.info("Retrieving server metrics")

    # Update cache size in metrics
    if metrics and cache:
        metrics.update_cache_size(len(cache.cache))

    # Get metrics data (hybrid metrics handles both OTEL and legacy)
    metrics_data = metrics.to_dict() if metrics else {}
    return json.dumps(metrics_data, indent=2)


@server.tool
async def get_health_status(ctx: Context = None) -> str:
    """Get server health status and system information."""
    return await trace_tool_execution(
        "get_health_status", {}, _get_health_status_impl, ctx
    )

async def _get_health_status_impl(ctx: Context = None) -> str:
    """Implementation of get_health_status with tracing."""
    if ctx:
        ctx.info("Performing health check")

    health_data = await health_checker.check_health()
    return json.dumps(health_data, indent=2)


@server.tool
async def get_cache_stats(ctx: Context = None) -> str:
    """Get cache statistics and performance metrics."""
    if ctx:
        ctx.info("Retrieving cache statistics")

    cache_stats = cache.get_stats() if cache else {}
    return json.dumps(cache_stats, indent=2)


@server.tool
async def clear_cache(ctx: Context = None) -> str:
    """Clear all cached data."""
    if ctx:
        ctx.info("Clearing cache")

    if cache:
        cache.cache.clear()
        cache.access_order.clear()
        return json.dumps({"status": "success", "message": "Cache cleared"})
    else:
        return json.dumps({"status": "error", "message": "Cache not available"})


# Background tasks
async def cache_cleanup_task():
    """Background task to clean up expired cache entries."""
    while True:
        try:
            if cache:
                expired_count = await cache.cleanup_expired()
                if expired_count > 0:
                    print(f"Cleaned up {expired_count} expired cache entries")
        except Exception as e:
            print(f"Cache cleanup error: {e}")

        await asyncio.sleep(settings.cache_cleanup_interval)


def start_background_tasks():
    """Start background tasks for the server."""
    if settings.enable_caching:
        asyncio.create_task(cache_cleanup_task())


# Assignment Management Tools - Core Functions (for testing)
async def _get_assignments_core(
    srid: str,
    level: Optional[str] = None,
    assignment_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Get assignments for a specific SRID (System Resource Identifier).

    Args:
        srid: System/Resource ID (1-8 alphanumeric characters)
        level: Environment level (DEV, TEST, STAGE, PROD, UAT, QA)
        assignment_id: Specific assignment ID to retrieve
        ctx: FastMCP context for logging and progress

    Returns:
        JSON string containing assignments data
    """
    try:
        # Input validation
        srid = validate_srid(srid)
        if level:
            level = validate_level(level)
        if assignment_id:
            assignment_id = validate_assignment_id(assignment_id)

        if ctx:
            await ctx.info(f"Retrieving assignments for SRID: {srid}")
            if level:
                await ctx.info(f"Filtering by level: {level}")
            if assignment_id:
                await ctx.info(f"Filtering by assignment ID: {assignment_id}")

        result = await bmc_client.get_assignments(srid, level, assignment_id)

        if ctx:
            await ctx.info(
                f"Successfully retrieved {len(result.get('assignments', []))} assignments"
            )

        return json.dumps(result, indent=2)

    except ValueError as e:
        # Handle validation errors with enhanced error handling
        validation_error = error_handler.handle_validation_error(
            e, "input_validation", str(e)
        )
        error_response = error_handler.create_error_response(
            validation_error, "get_assignments"
        )
        if ctx:
            await ctx.error(f"Validation error: {validation_error}")
        return json.dumps(error_response, indent=2)

    except (BMCAPIError, MCPServerError) as e:
        # Handle BMC API and server errors with enhanced error handling
        error_response = error_handler.create_error_response(e, "get_assignments")
        if ctx:
            await ctx.error(f"API error: {e}")
        return json.dumps(error_response, indent=2)

    except Exception as e:
        # Handle unexpected errors with enhanced error handling
        server_error = error_handler.handle_general_error(e, "get_assignments")
        error_response = error_handler.create_error_response(
            server_error, "get_assignments"
        )
        if ctx:
            await ctx.error(f"Unexpected error: {e}")
        return json.dumps(error_response, indent=2)


# MCP Tool Wrapper
@server.tool
async def get_assignments(
    srid: str,
    level: Optional[str] = None,
    assignment_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Get assignments for a specific SRID (System Resource Identifier)."""
    return await _get_assignments_core(srid, level, assignment_id, ctx)


async def _create_assignment_core(
    srid: str,
    assignment_id: str,
    stream: str,
    application: str,
    description: Optional[str] = None,
    default_path: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Create a new assignment in BMC AMI DevX."""
    try:
        if ctx:
            await ctx.info(f"Creating assignment {assignment_id} for SRID: {srid}")

        assignment_data = {
            "assignmentId": assignment_id,
            "stream": stream,
            "application": application,
        }

        if description:
            assignment_data["description"] = description
        if default_path:
            assignment_data["defaultPath"] = default_path

        result = await bmc_client.create_assignment(srid, assignment_data)

        if ctx:
            await ctx.info(f"Successfully created assignment: {assignment_id}")

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error creating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error creating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# MCP Tool Wrapper
@server.tool
async def create_assignment(
    srid: str,
    assignment_id: str,
    stream: str,
    application: str,
    description: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Create a new mainframe development assignment."""
    return await _create_assignment_core(
        srid, assignment_id, stream, application, description, ctx
    )


async def _get_assignment_details_core(
    srid: str, assignment_id: str, ctx: Context = None
) -> str:
    """Get detailed information for a specific assignment."""
    try:
        if ctx:
            await ctx.info(f"Retrieving details for assignment {assignment_id}")

        result = await bmc_client.get_assignment_details(srid, assignment_id)

        if ctx:
            await ctx.info(f"Successfully retrieved assignment details")

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving assignment details: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving assignment details: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# MCP Tool Wrapper
@server.tool
async def get_assignment_details(
    srid: str, assignment_id: str, ctx: Context = None
) -> str:
    """Get detailed information for a specific assignment."""
    return await _get_assignment_details_core(srid, assignment_id, ctx)


async def _get_assignment_tasks_core(
    srid: str, assignment_id: str, ctx: Context = None
) -> str:
    """Get tasks for a specific assignment."""
    try:
        if ctx:
            await ctx.info(f"Retrieving tasks for assignment {assignment_id}")

        result = await bmc_client.get_assignment_tasks(srid, assignment_id)

        if ctx:
            await ctx.info(
                f"Successfully retrieved {len(result.get('tasks', []))} tasks"
            )

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving assignment tasks: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving assignment tasks: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# MCP Tool Wrapper
@server.tool
async def get_assignment_tasks(
    srid: str, assignment_id: str, ctx: Context = None
) -> str:
    """Get tasks for a specific assignment."""
    return await _get_assignment_tasks_core(srid, assignment_id, ctx)


# Release Management Tools
@server.tool
async def get_releases(
    srid: str, release_id: Optional[str] = None, ctx: Context = None
) -> str:
    """Get releases for a specific SRID."""
    try:
        if ctx:
            await ctx.info(f"Retrieving releases for SRID: {srid}")

        result = await bmc_client.get_releases(srid, release_id)

        if ctx:
            await ctx.info(
                f"Successfully retrieved {len(result.get('releases', []))} releases"
            )

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving releases: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving releases: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def create_release(
    srid: str,
    release_id: str,
    stream: str,
    application: str,
    description: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Create a new release in BMC AMI DevX."""
    try:
        if ctx:
            await ctx.info(f"Creating release {release_id} for SRID: {srid}")

        release_data = {
            "releaseId": release_id,
            "stream": stream,
            "application": application,
        }

        if description:
            release_data["description"] = description

        result = await bmc_client.create_release(srid, release_data)

        if ctx:
            await ctx.info(f"Successfully created release: {release_id}")

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error creating release: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error creating release: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# Operation Tools
@server.tool
async def generate_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    runtime_configuration: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Generate code for an assignment."""
    try:
        if ctx:
            await ctx.info(f"Generating code for assignment {assignment_id}")
            await ctx.report_progress(0, 100, "Starting generation")

        generate_data = {}
        if level:
            generate_data["level"] = level
        if runtime_configuration:
            generate_data["runtimeConfiguration"] = runtime_configuration

        result = await bmc_client.generate_assignment(
            srid, assignment_id, generate_data
        )

        if ctx:
            await ctx.report_progress(100, 100, "Generation completed")
            await ctx.info(
                f"Successfully initiated generation for assignment: {assignment_id}"
            )

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error generating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error generating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def promote_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    change_type: Optional[str] = None,
    execution_status: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Promote assignment to next level."""
    try:
        if ctx:
            await ctx.info(
                f"Promoting assignment {assignment_id} to level: {level or 'next'}"
            )
            await ctx.report_progress(0, 100, "Starting promotion")

        promote_data = {}
        if level:
            promote_data["level"] = level
        if change_type:
            promote_data["changeType"] = change_type
        if execution_status:
            promote_data["executionStatus"] = execution_status

        result = await bmc_client.promote_assignment(srid, assignment_id, promote_data)

        if ctx:
            await ctx.report_progress(100, 100, "Promotion completed")
            await ctx.info(
                f"Successfully initiated promotion for assignment: {assignment_id}"
            )

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error promoting assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error promoting assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def deploy_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    deploy_implementation_time: Optional[str] = None,
    deploy_active: Optional[bool] = None,
    ctx: Context = None,
) -> str:
    """Deploy assignment to target environment."""
    try:
        if ctx:
            await ctx.info(
                f"Deploying assignment {assignment_id} to level: {level or 'default'}"
            )
            await ctx.report_progress(0, 100, "Starting deployment")

        deploy_data = {}
        if level:
            deploy_data["level"] = level
        if deploy_implementation_time:
            deploy_data["deployImplementationTime"] = deploy_implementation_time
        if deploy_active is not None:
            deploy_data["deployActive"] = deploy_active

        result = await bmc_client.deploy_assignment(srid, assignment_id, deploy_data)

        if ctx:
            await ctx.report_progress(100, 100, "Deployment completed")
            await ctx.info(
                f"Successfully initiated deployment for assignment: {assignment_id}"
            )

        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error deploying assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error deploying assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# Health check endpoint
@server.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "healthy",
            "name": server.name,
            "version": server.version,
            "tools_count": len(await server.get_tools()),
            "api_base_url": settings.api_base_url,
        }
    )


async def main():
    """Main entry point."""
    print("Starting BMC AMI DevX Code Pipeline MCP Server...")
    print(f"Server: {server.name} v{server.version}")
    print(f"Host: {settings.host}:{settings.port}")
    print(f"API Base URL: {settings.api_base_url}")
    print(f"Health check: http://{settings.host}:{settings.port}/health")

    # Run the server
    await server.run_http_async(
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        transport="streamable-http",
    )


if __name__ == "__main__":
    import asyncio

    async def main_with_tasks():
        # Start background tasks
        start_background_tasks()
        # Run the main server
        await main()

    asyncio.run(main_with_tasks())
