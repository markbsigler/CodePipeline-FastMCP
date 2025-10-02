#!/usr/bin/env python3
"""
Hybrid BMC AMI DevX Code Pipeline MCP Server
Combining FastMCP Best Practices with Enterprise Features
"""

import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastmcp import Context, FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.workos import WorkOSProvider
from fastmcp.server.elicitation import DeclinedElicitation
from starlette.requests import Request
from starlette.responses import JSONResponse

# Import advanced components from main.py and observability
try:
    from main import (
        BMCAMIDevXClient,
        ErrorHandler,
        HealthChecker,
        IntelligentCache,
        RateLimiter,
        Settings,
    )
    from main import create_auth_provider as main_create_auth_provider
    from observability import initialize_metrics, initialize_otel

    ADVANCED_FEATURES_AVAILABLE = True
except ImportError as e:
    print(f"Advanced features not available: {e}")
    ADVANCED_FEATURES_AVAILABLE = False


class SimpleRateLimiter:
    """Simplified token bucket rate limiter following FastMCP patterns."""

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a token for making a request."""
        async with self.lock:
            now = datetime.now()
            time_passed = (now - self.last_refill).total_seconds()

            # Refill tokens based on time passed
            tokens_to_add = (time_passed / 60.0) * self.requests_per_minute
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                # Round to avoid floating-point precision issues
                if abs(self.tokens - round(self.tokens)) < 1e-10:
                    self.tokens = round(self.tokens)
                return True
            return False

    async def wait_for_token(self) -> None:
        """Wait until a token is available."""
        while not await self.acquire():
            wait_time = 60.0 / self.requests_per_minute
            await asyncio.sleep(wait_time)


@dataclass
class SimpleMetrics:
    """Simplified metrics collection for monitoring."""

    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0

    # Response times
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

    # System metrics
    start_time: datetime = field(default_factory=datetime.now)

    def record_request(self, success: bool = True, response_time: float = 0.0):
        """Record a request with timing."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        if response_time > 0:
            self.response_times.append(response_time)

    def record_rate_limit(self):
        """Record a rate limited request."""
        self.rate_limited_requests += 1

    def get_avg_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.successful_requests + self.failed_requests
        if total > 0:
            return round((self.successful_requests / total * 100), 2)
        return 100.0

    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self, include_cache_stats: bool = False) -> Dict:
        """Convert metrics to dictionary."""
        result = {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "success_rate_percent": round(self.get_success_rate(), 2),
            "avg_response_time_seconds": round(self.get_avg_response_time(), 3),
            "uptime_seconds": round(self.get_uptime_seconds(), 2),
            "recent_response_count": len(self.response_times),
        }

        # Include cache stats if requested (will be set by the metrics tool)
        if include_cache_stats and "cache" in globals():
            result["cache_stats"] = cache.get_stats()

        return result


@dataclass
class SimpleCacheEntry:
    """Cache entry with TTL support."""

    data: Any
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return (datetime.now() - self.timestamp).total_seconds() > self.ttl_seconds


class SimpleCache:
    """Simplified cache with TTL and LRU eviction following FastMCP patterns."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, SimpleCacheEntry] = {}
        self.access_order: deque = deque()
        self.lock = asyncio.Lock()

        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, method: str, **kwargs) -> str:
        """Generate cache key from method and parameters."""
        sorted_kwargs = sorted(kwargs.items())
        key_parts = [method] + [f"{k}={v}" for k, v in sorted_kwargs]
        return "|".join(key_parts)

    async def get(self, method: str, **kwargs) -> Optional[Any]:
        """Get cached data if available and not expired."""
        async with self.lock:
            key = self._generate_key(method, **kwargs)

            if key not in self.cache:
                self.misses += 1
                return None

            entry = self.cache[key]
            if entry.is_expired():
                # Remove expired entry
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                self.misses += 1
                return None

            # Update access order (move to end)
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            self.hits += 1
            return entry.data

    async def set(
        self, method: str, data: Any, ttl: Optional[int] = None, **kwargs
    ) -> None:
        """Store data in cache with TTL."""
        async with self.lock:
            key = self._generate_key(method, **kwargs)
            ttl = ttl or self.default_ttl

            # Remove existing entry if present
            if key in self.cache:
                if key in self.access_order:
                    self.access_order.remove(key)

            # Add new entry
            self.cache[key] = SimpleCacheEntry(
                data=data, timestamp=datetime.now(), ttl_seconds=ttl
            )
            self.access_order.append(key)

            # Evict if over capacity
            await self._evict_if_needed()

    async def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache is over capacity."""
        while len(self.cache) > self.max_size and self.access_order:
            # Remove least recently used entry
            lru_key = self.access_order.popleft()
            if lru_key in self.cache:
                del self.cache[lru_key]
                self.evictions += 1

    async def clear(self) -> int:
        """Clear all cache entries and return count of cleared entries."""
        async with self.lock:
            count = len(self.cache)
            self.cache.clear()
            self.access_order.clear()
            return count

    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
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

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "default_ttl_seconds": self.default_ttl,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate_percent": round(self.get_hit_rate(), 2),
            "oldest_entry_age_seconds": self._get_oldest_entry_age_seconds(),
            "expired_entries": sum(
                1 for entry in self.cache.values() if entry.is_expired()
            ),
        }

    def _get_oldest_entry_age_seconds(self) -> float:
        """Get age of oldest entry in seconds."""
        if not self.cache:
            return 0.0
        oldest_timestamp = min(entry.timestamp for entry in self.cache.values())
        return (datetime.now() - oldest_timestamp).total_seconds()


class SimpleErrorHandler:
    """Simplified error handling and recovery system following FastMCP patterns."""

    def __init__(self, metrics: SimpleMetrics):
        self.metrics = metrics

    def categorize_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Categorize error and create structured response."""
        error_info = {
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
            "error_type": "unknown",
            "retryable": False,
            "message": str(error),
        }

        if isinstance(error, httpx.TimeoutException):
            error_info.update(
                {
                    "error_type": "timeout",
                    "retryable": True,
                    "message": f"Request timed out during {operation}",
                }
            )
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            error_info.update(
                {
                    "error_type": "http_error",
                    "status_code": status_code,
                    "retryable": status_code in [408, 429, 500, 502, 503, 504],
                    "message": f"HTTP {status_code} error during {operation}",
                }
            )

            # Add specific handling for common status codes
            if status_code == 401:
                error_info["error_type"] = "authentication_error"
                error_info["retryable"] = False
            elif status_code == 404:
                error_info["error_type"] = "not_found"
                error_info["retryable"] = False
            elif status_code == 429:
                error_info["error_type"] = "rate_limit_error"
                retry_after = error.response.headers.get("Retry-After", "60")
                error_info["retry_after_seconds"] = int(retry_after)

        elif isinstance(error, httpx.ConnectError):
            error_info.update(
                {
                    "error_type": "connection_error",
                    "retryable": True,
                    "message": f"Failed to connect to API during {operation}",
                }
            )

        return error_info

    def should_retry(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        if isinstance(error, httpx.TimeoutException):
            return True
        elif isinstance(error, httpx.HTTPStatusError):
            # Retry on server errors and rate limiting
            return error.response.status_code in [408, 429, 500, 502, 503, 504]
        elif isinstance(error, httpx.ConnectError):
            return True
        return False

    def get_retry_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay."""
        return base_delay * (2**attempt)


def with_retry_and_error_handling(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for adding retry logic and error handling to functions."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            error_handler = SimpleErrorHandler(metrics)
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    start_time = datetime.now()
                    result = await func(*args, **kwargs)
                    response_time = (datetime.now() - start_time).total_seconds()

                    # Record successful request
                    if hasattr(metrics, "record_request") and hasattr(
                        metrics, "total_requests"
                    ):
                        # HybridMetrics interface
                        metrics.record_request(
                            method="INTERNAL",
                            endpoint="/retry",
                            status_code=200,
                            duration=response_time,
                        )
                    else:
                        # SimpleMetrics interface
                        metrics.record_request(
                            success=True, response_time=response_time
                        )
                    return result

                except Exception as error:
                    response_time = (datetime.now() - start_time).total_seconds()
                    last_error = error

                    # Record failed request
                    if hasattr(metrics, "record_request") and hasattr(
                        metrics, "total_requests"
                    ):
                        # HybridMetrics interface
                        metrics.record_request(
                            method="INTERNAL",
                            endpoint="/retry",
                            status_code=500,
                            duration=response_time,
                        )
                    else:
                        # SimpleMetrics interface
                        metrics.record_request(
                            success=False, response_time=response_time
                        )

                    # Check if we should retry
                    if attempt < max_retries and error_handler.should_retry(error):
                        delay = error_handler.get_retry_delay(attempt, base_delay)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # No more retries, prepare error response
                        error_handler.categorize_error(error, func.__name__)
                        break

            # All retries exhausted, return structured error
            return {
                "error": True,
                "details": error_handler.categorize_error(last_error, func.__name__),
                "attempts_made": attempt + 1,
                "max_retries": max_retries,
            }

        return wrapper

    return decorator


def create_auth_provider():
    """Create authentication provider with hybrid support for advanced features."""
    if ADVANCED_FEATURES_AVAILABLE:
        return main_create_auth_provider()

    # Fallback to simple auth provider
    if not os.getenv("AUTH_ENABLED", "false").lower() == "true":
        return None

    auth_provider = os.getenv("AUTH_PROVIDER", "").lower()

    if auth_provider == "jwt":
        return JWTVerifier(
            jwks_uri=os.getenv("FASTMCP_AUTH_JWKS_URI"),
            issuer=os.getenv("FASTMCP_AUTH_ISSUER"),
            audience=os.getenv("FASTMCP_AUTH_AUDIENCE"),
        )
    elif auth_provider == "github":
        return GitHubProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET"),
        )
    elif auth_provider == "google":
        return GoogleProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
        )
    elif auth_provider == "workos":
        return WorkOSProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_SECRET"),
            authkit_domain=os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN"),
        )

    return None


# Load OpenAPI specification
openapi_spec_path = Path("config/openapi.json")
if not openapi_spec_path.exists():
    raise FileNotFoundError(f"OpenAPI specification not found at {openapi_spec_path}")

with open(openapi_spec_path, "r") as f:
    openapi_spec = json.load(f)

# Track server start time for uptime calculations
start_time = datetime.now()

# Initialize hybrid components (advanced or simple fallback)
if ADVANCED_FEATURES_AVAILABLE:
    # Initialize OpenTelemetry observability
    tracer, meter = initialize_otel()

    # Use advanced components from main.py
    settings = Settings.from_env()

    # Global hybrid metrics instance (OTEL + legacy)
    metrics = initialize_metrics()

    # Global cache instance with intelligence
    cache = IntelligentCache(
        max_size=settings.cache_max_size, default_ttl=settings.cache_ttl_seconds
    )

    # Advanced rate limiter
    rate_limiter = RateLimiter(
        requests_per_minute=settings.rate_limit_requests_per_minute,
        burst_size=settings.rate_limit_burst_size,
    )

    # Global error handler
    error_handler = ErrorHandler(settings, metrics)

    print("✅ Advanced enterprise features enabled")
else:
    # Fallback to simple components
    settings = None

    # Simple rate limiter
    rate_limiter = SimpleRateLimiter(
        requests_per_minute=int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")),
        burst_size=int(os.getenv("RATE_LIMIT_BURST_SIZE", "10")),
    )

    # Simple metrics
    metrics = SimpleMetrics()

    # Simple caching system
    cache = SimpleCache(
        max_size=int(os.getenv("CACHE_MAX_SIZE", "1000")),
        default_ttl=int(os.getenv("CACHE_TTL_SECONDS", "300")),
    )

    error_handler = None
    print("⚠️  Using simple components - advanced features not available")

# Create HTTP client with connection pooling
if ADVANCED_FEATURES_AVAILABLE and settings:
    http_client = httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=httpx.Timeout(settings.api_timeout),
        limits=httpx.Limits(
            max_keepalive_connections=settings.connection_pool_size,
            max_connections=settings.connection_pool_size * 2,
        ),
        headers={
            "Authorization": f"Bearer {os.getenv('API_TOKEN', '')}",
            "Content-Type": "application/json",
            "User-Agent": "BMC-AMI-DevX-MCP-Server/2.2.0",
        },
    )

    # Initialize advanced BMC client with monitoring, caching, and error handling
    bmc_client = BMCAMIDevXClient(
        http_client, cache=cache, metrics=metrics, error_handler=error_handler
    )

    # Initialize health checker
    health_checker = HealthChecker(bmc_client, settings)

else:
    # Fallback HTTP client
    http_client = httpx.AsyncClient(
        base_url=os.getenv("API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1"),
        timeout=httpx.Timeout(int(os.getenv("API_TIMEOUT", "30"))),
        limits=httpx.Limits(
            max_keepalive_connections=int(os.getenv("CONNECTION_POOL_SIZE", "20")),
            max_connections=int(os.getenv("CONNECTION_POOL_SIZE", "20")) * 2,
        ),
        headers={
            "Authorization": f"Bearer {os.getenv('API_TOKEN', '')}",
            "Content-Type": "application/json",
            "User-Agent": "BMC-AMI-DevX-MCP-Server/2.2.0",
        },
    )

    bmc_client = None
    health_checker = None

# Create main FastMCP server following best practices
mcp = FastMCP(
    name="BMC AMI DevX Code Pipeline MCP Server",
    version="2.2.0",
    instructions="""
    This MCP server provides comprehensive BMC AMI DevX Code Pipeline integration
    with ISPW operations. All tools are automatically generated from the BMC ISPW
    OpenAPI specification, ensuring complete API coverage and maintainability.

    Features:
    - Enterprise-grade observability with OpenTelemetry
    - Intelligent caching and rate limiting
    - Comprehensive error handling and recovery
    - Interactive user elicitation workflows
    - Production-ready monitoring endpoints
    """,
    auth=create_auth_provider(),
    include_tags={"public", "api", "monitoring", "management"},
    exclude_tags={"internal", "deprecated"},
    # Use FastMCP's built-in global settings via environment variables
)

# Create OpenAPI-generated tools server
openapi_server = FastMCP.from_openapi(
    openapi_spec=openapi_spec, client=http_client, name="BMC ISPW API Tools"
)

# Mount OpenAPI server following FastMCP composition pattern
mcp.mount(openapi_server, prefix="ispw")


# Add custom monitoring tools following FastMCP patterns
@mcp.tool(tags={"monitoring", "public"})
async def get_server_health(ctx: Context = None) -> str:
    """Get comprehensive server health status."""
    if ctx:
        ctx.info("Checking server health status")

    start_time = datetime.now()

    try:
        # Use rate limiter for health check
        if not await rate_limiter.acquire():
            if hasattr(metrics, "record_rate_limit_event"):
                # HybridMetrics interface
                metrics.record_rate_limit_event("limit_exceeded")
            else:
                # SimpleMetrics interface
                metrics.record_rate_limit()
            bmc_status = "rate_limited"
            response_time = 0.0
        else:
            # Test BMC API connectivity
            response = await http_client.get("/health")
            response_time = (datetime.now() - start_time).total_seconds()
            bmc_status = "healthy" if response.status_code == 200 else "unhealthy"
            if hasattr(metrics, "record_request") and hasattr(
                metrics, "total_requests"
            ):
                # HybridMetrics interface
                metrics.record_request(
                    method="GET",
                    endpoint="/health",
                    status_code=response.status_code,
                    duration=response_time,
                )
            else:
                # SimpleMetrics interface
                metrics.record_request(
                    success=response.status_code == 200, response_time=response_time
                )

    except Exception:
        response_time = (datetime.now() - start_time).total_seconds()
        bmc_status = "unreachable"
        if hasattr(metrics, "record_request") and hasattr(metrics, "total_requests"):
            # HybridMetrics interface
            metrics.record_request(
                method="GET",
                endpoint="/health",
                status_code=500,
                duration=response_time,
            )
        else:
            # SimpleMetrics interface
            metrics.record_request(success=False, response_time=response_time)

    health_data = {
        "status": "healthy",
        "name": mcp.name,
        "version": "2.2.0",
        "bmc_api_status": bmc_status,
        "response_time_seconds": round(response_time, 3),
        "tools_count": len(await mcp.get_tools()),
        "rate_limiter": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "burst_size": rate_limiter.burst_size,
            "tokens_available": round(rate_limiter.tokens, 2),
        },
        "cache": {
            "size": len(cache.cache),
            "max_size": cache.max_size,
            "hit_rate_percent": round(getattr(cache, "get_hit_rate", lambda: 0.0)(), 2),
            "expired_entries": sum(
                1 for entry in cache.cache.values() if entry.is_expired()
            ),
        },
    }

    return json.dumps(health_data, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_server_metrics(ctx: Context = None) -> str:
    """Get server performance metrics."""
    if ctx:
        ctx.info("Retrieving server metrics")

    return json.dumps(metrics.to_dict(), indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_rate_limiter_status(ctx: Context = None) -> str:
    """Get current rate limiter status and configuration."""
    if ctx:
        ctx.info("Checking rate limiter status")

    status = {
        "configuration": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "burst_size": rate_limiter.burst_size,
        },
        "current_state": {
            "tokens_available": round(rate_limiter.tokens, 2),
            "last_refill": rate_limiter.last_refill.isoformat(),
            "time_until_next_token": (
                max(0, 60.0 / rate_limiter.requests_per_minute)
                if rate_limiter.tokens < 1
                else 0
            ),
        },
        "metrics": {
            "rate_limited_requests": getattr(metrics, "rate_limited_requests", 0),
            "rate_limit_percentage": round(
                (
                    getattr(metrics, "rate_limited_requests", 0)
                    / max(1, getattr(metrics, "total_requests", 1))
                )
                * 100,
                2,
            ),
        },
    }

    return json.dumps(status, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_cache_info(ctx: Context = None) -> str:
    """Get comprehensive cache information and statistics."""
    if ctx:
        ctx.info("Retrieving cache information")

    # Handle different cache types
    if hasattr(cache, "get_stats"):
        # IntelligentCache
        cache_stats = cache.get_stats()

        # Calculate hit rate from metrics if available
        hit_rate_percent = 0.0
        if hasattr(metrics, "get_cache_hit_rate"):
            hit_rate_percent = metrics.get_cache_hit_rate()
        elif hasattr(cache, "get_hit_rate"):
            hit_rate_percent = cache.get_hit_rate()

        cache_info = {
            **cache_stats,
            "configuration": {
                "max_size": cache.max_size,
                "default_ttl_seconds": cache.default_ttl,
            },
            "performance": {
                "hit_rate_percent": hit_rate_percent,
                "efficiency": (
                    "excellent"
                    if hit_rate_percent > 80
                    else ("good" if hit_rate_percent > 60 else "needs_improvement")
                ),
            },
        }
    else:
        # SimpleCache
        cache_info = {
            "size": len(cache.cache),
            "max_size": cache.max_size,
            "default_ttl_seconds": cache.default_ttl,
            "hit_rate_percent": round(cache.get_hit_rate(), 2),
            "expired_entries": sum(
                1 for entry in cache.cache.values() if entry.is_expired()
            ),
            "configuration": {
                "max_size": cache.max_size,
                "default_ttl_seconds": cache.default_ttl,
            },
            "performance": {
                "hit_rate_percent": round(cache.get_hit_rate(), 2),
                "efficiency": (
                    "excellent"
                    if cache.get_hit_rate() > 80
                    else ("good" if cache.get_hit_rate() > 60 else "needs_improvement")
                ),
            },
        }

    return json.dumps(cache_info, indent=2)


@mcp.tool(tags={"management", "admin"})
async def clear_cache(ctx: Context = None) -> str:
    """Clear all cache entries."""
    if ctx:
        ctx.info("Clearing cache")

    start_time = datetime.now()

    # Handle different cache types
    if hasattr(cache, "lock") and hasattr(cache, "access_order"):
        # IntelligentCache
        async with cache.lock:
            cleared_count = len(cache.cache)
            cache.cache.clear()
            cache.access_order.clear()
    else:
        # SimpleCache
        cleared_count = len(cache.cache)
        cache.clear()

    operation_time = (datetime.now() - start_time).total_seconds()

    result = {
        "success": True,
        "cleared_entries": cleared_count,
        "operation_time_seconds": round(operation_time, 3),
        "cache_size_after": len(cache.cache),
        "message": f"Successfully cleared {cleared_count} cache entries",
    }

    return json.dumps(result, indent=2)


@mcp.tool(tags={"management", "admin"})
async def cleanup_expired_cache(ctx: Context = None) -> str:
    """Remove expired cache entries."""
    if ctx:
        ctx.info("Cleaning up expired cache entries")

    start_time = datetime.now()
    removed_count = await cache.cleanup_expired()
    operation_time = (datetime.now() - start_time).total_seconds()

    result = {
        "success": True,
        "removed_entries": removed_count,
        "operation_time_seconds": round(operation_time, 3),
        "cache_size_after": len(cache.cache),
        "message": f"Cleaned up {removed_count} expired cache entries",
    }

    return json.dumps(result, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_error_recovery_status(ctx: Context = None) -> str:
    """Get error recovery and retry configuration status."""
    if ctx:
        ctx.info("Retrieving error recovery status")

    SimpleErrorHandler(metrics)

    status = {
        "configuration": {
            "max_retries": int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            "base_delay_seconds": float(os.getenv("RETRY_BASE_DELAY", "1.0")),
            "retry_enabled": True,
        },
        "error_statistics": {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "error_rate_percent": round(
                (metrics.failed_requests / max(1, metrics.total_requests)) * 100, 2
            ),
        },
        "retryable_error_types": [
            "timeout",
            "connection_error",
            "http_500",
            "http_502",
            "http_503",
            "http_504",
            "rate_limit_error",
        ],
        "non_retryable_error_types": [
            "authentication_error",
            "not_found",
            "validation_error",
        ],
    }

    return json.dumps(status, indent=2)


# Add elicitation tool following FastMCP patterns
@mcp.tool(tags={"elicitation", "workflow"})
async def create_assignment_interactive(ctx: Context) -> str:
    """Interactively create a new BMC ISPW assignment with user elicitation."""
    start_time = datetime.now()

    try:
        # Get assignment details through elicitation
        title_result = await ctx.elicit(
            "What is the assignment title?", response_type=str
        )

        if isinstance(title_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"

        title = title_result.data

        description_result = await ctx.elicit(
            "Provide assignment description:", response_type=str
        )

        if isinstance(description_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"

        description = description_result.data

        # Check rate limiter before making API call
        if not await rate_limiter.acquire():
            if hasattr(metrics, "record_rate_limit_event"):
                # HybridMetrics interface
                metrics.record_rate_limit_event("limit_exceeded")
            else:
                # SimpleMetrics interface
                metrics.record_rate_limit()
            return json.dumps(
                {
                    "error": True,
                    "message": "Rate limit exceeded. Please try again later.",
                    "rate_limit_info": {
                        "requests_per_minute": rate_limiter.requests_per_minute,
                        "retry_after_seconds": 60.0 / rate_limiter.requests_per_minute,
                    },
                },
                indent=2,
            )

        # Create assignment via BMC API
        assignment_data = {"title": title, "description": description, "level": "DEV"}

        response = await http_client.post("/assignments", json=assignment_data)
        response_time = (datetime.now() - start_time).total_seconds()
        response.raise_for_status()

        result = response.json()
        if hasattr(metrics, "record_request") and hasattr(metrics, "total_requests"):
            # HybridMetrics interface
            metrics.record_request(
                method="POST",
                endpoint="/assignments",
                status_code=response.status_code,
                duration=response_time,
            )
        else:
            # SimpleMetrics interface
            metrics.record_request(success=True, response_time=response_time)

        return json.dumps(
            {
                "success": True,
                "assignment": result,
                "message": f"Assignment '{title}' created successfully",
                "response_time_seconds": round(response_time, 3),
            },
            indent=2,
        )

    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds()
        if hasattr(metrics, "record_request") and hasattr(metrics, "total_requests"):
            # HybridMetrics interface
            metrics.record_request(
                method="POST",
                endpoint="/assignments",
                status_code=500,
                duration=response_time,
            )
        else:
            # SimpleMetrics interface
            metrics.record_request(success=False, response_time=response_time)

        return json.dumps(
            {
                "error": True,
                "message": f"Failed to create assignment: {str(e)}",
                "response_time_seconds": round(response_time, 3),
            },
            indent=2,
        )


# Simple health check function for routes
async def _simple_health_check():
    """Simple health check implementation for routes."""
    try:
        start_check = datetime.now()

        # Use rate limiter for health check
        if not await rate_limiter.acquire():
            if hasattr(metrics, "record_rate_limit"):
                metrics.record_rate_limit()
            elif hasattr(metrics, "rate_limited_requests"):
                metrics.rate_limited_requests += 1
            bmc_status = "rate_limited"
            response_time = 0.0
        else:
            # Test BMC API connectivity
            try:
                response = await http_client.get("/health")
                response_time = (datetime.now() - start_check).total_seconds()
                bmc_status = "healthy" if response.status_code == 200 else "unhealthy"

                if hasattr(metrics, "record_request"):
                    metrics.record_request(
                        success=response.status_code == 200, response_time=response_time
                    )
                elif hasattr(metrics, "total_requests"):
                    metrics.total_requests += 1
                    if response.status_code == 200:
                        metrics.successful_requests += 1
                    else:
                        metrics.failed_requests += 1

            except Exception:
                response_time = (datetime.now() - start_check).total_seconds()
                bmc_status = "unreachable"
                if hasattr(metrics, "record_request"):
                    metrics.record_request(success=False, response_time=response_time)
                elif hasattr(metrics, "total_requests"):
                    metrics.total_requests += 1
                    metrics.failed_requests += 1

        health_data = {
            "status": (
                "healthy" if bmc_status in ["healthy", "rate_limited"] else "unhealthy"
            ),
            "name": mcp.name,
            "version": mcp.version,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - start_time).total_seconds(),
            "bmc_api_status": bmc_status,
            "rate_limiter_status": (
                "active" if hasattr(rate_limiter, "tokens") else "inactive"
            ),
            "cache_status": "active" if cache else "inactive",
            "advanced_features": ADVANCED_FEATURES_AVAILABLE,
            "observability": ADVANCED_FEATURES_AVAILABLE,
            "response_time_seconds": round(response_time, 3),
        }

        return health_data

    except Exception as e:
        return {
            "status": "unhealthy",
            "name": mcp.name,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# Add custom health check route following FastMCP patterns
@mcp.custom_route("/health", methods=["GET"])
async def health_check_route(request: Request) -> JSONResponse:
    """Health check endpoint for load balancers."""
    try:
        if ADVANCED_FEATURES_AVAILABLE and health_checker:
            # Use advanced health checker
            health_data = await health_checker.get_health()
            status_code = 200 if health_data.get("status") == "healthy" else 503
        else:
            # Use simple health check
            health_data = await _simple_health_check()
            status_code = 200 if health_data.get("status") == "healthy" else 503

        return JSONResponse(health_data, status_code=status_code)
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)


@mcp.custom_route("/status", methods=["GET"])
async def status_route(request: Request) -> JSONResponse:
    """Detailed server status endpoint."""
    try:
        uptime = (datetime.now() - start_time).total_seconds()

        status_data = {
            "server": {
                "name": mcp.name,
                "version": mcp.version,
                "uptime_seconds": round(uptime, 1),
                "start_time": start_time.isoformat(),
            },
            "features": {
                "advanced_features": ADVANCED_FEATURES_AVAILABLE,
                "rate_limiting": True,
                "caching": True,
                "metrics": True,
                "observability": ADVANCED_FEATURES_AVAILABLE,
                "error_handling": ADVANCED_FEATURES_AVAILABLE,
            },
            "configuration": {
                "api_base_url": (
                    settings.api_base_url
                    if ADVANCED_FEATURES_AVAILABLE and settings
                    else os.getenv("API_BASE_URL")
                ),
                "rate_limit_rpm": (
                    settings.rate_limit_requests_per_minute
                    if ADVANCED_FEATURES_AVAILABLE and settings
                    else int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
                ),
                "cache_max_size": (
                    settings.cache_max_size
                    if ADVANCED_FEATURES_AVAILABLE and settings
                    else int(os.getenv("CACHE_MAX_SIZE", "1000"))
                ),
                "cache_ttl": (
                    settings.cache_ttl_seconds
                    if ADVANCED_FEATURES_AVAILABLE and settings
                    else int(os.getenv("CACHE_TTL_SECONDS", "300"))
                ),
            },
        }

        return JSONResponse(status_data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_route(request: Request) -> JSONResponse:
    """Readiness probe endpoint for load balancers."""
    try:
        # Check if server is ready to accept traffic
        ready = True

        # Check rate limiter
        if not hasattr(rate_limiter, "tokens"):
            ready = False

        # Check if OpenAPI spec is loaded
        if not openapi_spec:
            ready = False

        if ready:
            return JSONResponse(
                {"status": "ready", "timestamp": datetime.now().isoformat()},
                status_code=200,
            )
        else:
            return JSONResponse(
                {"status": "not_ready", "timestamp": datetime.now().isoformat()},
                status_code=503,
            )
    except Exception as e:
        return JSONResponse({"status": "not_ready", "error": str(e)}, status_code=503)


@mcp.custom_route("/openapi.json", methods=["GET"])
async def openapi_spec_route(request: Request) -> JSONResponse:
    """OpenAPI specification endpoint."""
    try:
        return JSONResponse(openapi_spec)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics_route(request: Request) -> JSONResponse:
    """Metrics endpoint for monitoring."""
    try:
        if ADVANCED_FEATURES_AVAILABLE and hasattr(metrics, "to_dict"):
            # Use advanced metrics
            metrics_data = metrics.to_dict()
        else:
            # Use simple metrics directly
            metrics_data = (
                metrics.to_dict()
                if hasattr(metrics, "to_dict")
                else {
                    "total_requests": getattr(metrics, "total_requests", 0),
                    "successful_requests": getattr(metrics, "successful_requests", 0),
                    "failed_requests": getattr(metrics, "failed_requests", 0),
                    "rate_limited_requests": getattr(
                        metrics, "rate_limited_requests", 0
                    ),
                    "avg_response_time": getattr(metrics, "avg_response_time", 0.0),
                    "cache_hits": getattr(metrics, "cache_hits", 0),
                    "cache_misses": getattr(metrics, "cache_misses", 0),
                }
            )

        return JSONResponse(metrics_data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Add resource template following FastMCP patterns with retry logic
@mcp.resource("bmc://assignments/{srid}")
async def get_assignment_resource(srid: str) -> dict:
    """Get assignment data as a structured resource with caching and retry logic."""
    # Check cache first
    cached_data = await cache.get("get_assignment", srid=srid)
    if cached_data is not None:
        return cached_data

    # Use rate limiter
    if not await rate_limiter.acquire():
        return {"error": f"Rate limit exceeded for assignment {srid}"}

    # Define the API call function for retry logic
    @with_retry_and_error_handling(
        max_retries=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
        base_delay=float(os.getenv("RETRY_BASE_DELAY", "1.0")),
    )
    async def fetch_assignment():
        response = await http_client.get(f"/assignments/{srid}")
        response.raise_for_status()
        return response.json()

    # Execute with retry logic
    result = await fetch_assignment()

    # Handle successful response
    if isinstance(result, dict) and not result.get("error"):
        # Cache the successful response
        await cache.set("get_assignment", result, ttl=300, srid=srid)
        return result

    # Return error result (already structured by retry decorator)
    return result


# Add prompt following FastMCP patterns
@mcp.prompt
def analyze_assignment_status(assignment_data: dict) -> str:
    """Generate analysis prompt for assignment status."""
    assignment_id = assignment_data.get("assignmentId", "Unknown")
    status = assignment_data.get("status", "Unknown")
    level = assignment_data.get("level", "Unknown")

    return f"""
    Analyze the following BMC ISPW assignment status:

    Assignment ID: {assignment_id}
    Status: {status}
    Level: {level}

    Please provide:
    1. Status interpretation and implications
    2. Recommended next actions
    3. Potential issues or risks
    4. Timeline considerations
    5. Dependencies to check
    """


if __name__ == "__main__":
    # Follow FastMCP standard server running pattern
    mcp.run(
        transport="http",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        # FastMCP automatically uses FASTMCP_LOG_LEVEL environment variable
    )
