#!/usr/bin/env python3
"""
Simplified BMC AMI DevX Code Pipeline MCP Server following FastMCP Best Practices
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
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.workos import WorkOSProvider
from fastmcp.server.elicitation import AcceptedElicitation, DeclinedElicitation
from starlette.requests import Request
from starlette.responses import JSONResponse


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
            
            if self.tokens >= 1:
                self.tokens -= 1
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
        return (self.successful_requests / total * 100) if total > 0 else 100.0
    
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
            "recent_response_count": len(self.response_times)
        }
        
        # Include cache stats if requested (will be set by the metrics tool)
        if include_cache_stats and 'cache' in globals():
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
    
    async def set(self, method: str, data: Any, ttl: Optional[int] = None, **kwargs) -> None:
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
                data=data,
                timestamp=datetime.now(),
                ttl_seconds=ttl
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
            "oldest_entry_age_seconds": self._get_oldest_entry_age(),
            "expired_entries": sum(1 for entry in self.cache.values() if entry.is_expired())
        }
    
    def _get_oldest_entry_age_seconds(self) -> float:
        """Get age of oldest entry in seconds."""
        if not self.cache:
            return 0.0
        oldest_timestamp = min(entry.timestamp for entry in self.cache.values())
        return (datetime.now() - oldest_timestamp).total_seconds()


def create_auth_provider():
    """Create authentication provider following FastMCP patterns."""
    if not os.getenv("AUTH_ENABLED", "false").lower() == "true":
        return None
    
    auth_provider = os.getenv("AUTH_PROVIDER", "").lower()
    
    if auth_provider == "jwt":
        return JWTVerifier(
            jwks_uri=os.getenv("FASTMCP_AUTH_JWKS_URI"),
            issuer=os.getenv("FASTMCP_AUTH_ISSUER"), 
            audience=os.getenv("FASTMCP_AUTH_AUDIENCE")
        )
    elif auth_provider == "github":
        return GitHubProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET")
        )
    elif auth_provider == "google":
        return GoogleProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET")
        )
    elif auth_provider == "workos":
        return WorkOSProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_SECRET"),
            authkit_domain=os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN")
        )
    
    return None


# Load OpenAPI specification
openapi_spec_path = Path("config/openapi.json")
if not openapi_spec_path.exists():
    raise FileNotFoundError(f"OpenAPI specification not found at {openapi_spec_path}")

with open(openapi_spec_path, "r") as f:
    openapi_spec = json.load(f)

# Initialize rate limiting and metrics
rate_limiter = SimpleRateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")),
    burst_size=int(os.getenv("RATE_LIMIT_BURST_SIZE", "10"))
)

metrics = SimpleMetrics()

# Initialize caching system
cache = SimpleCache(
    max_size=int(os.getenv("CACHE_MAX_SIZE", "1000")),
    default_ttl=int(os.getenv("CACHE_TTL_SECONDS", "300"))
)

# Create HTTP client with connection pooling
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
    }
)

# Create main FastMCP server following best practices
mcp = FastMCP(
    name="BMC AMI DevX Code Pipeline MCP Server",
    version="2.2.0",
    instructions="""
    This MCP server provides comprehensive BMC AMI DevX Code Pipeline integration
    with ISPW operations. All tools are automatically generated from the BMC ISPW
    OpenAPI specification, ensuring complete API coverage and maintainability.
    """,
    auth=create_auth_provider(),
    include_tags={"public", "api", "monitoring", "management"},
    exclude_tags={"internal", "deprecated"},
    # Use FastMCP's built-in global settings via environment variables
)

# Create OpenAPI-generated tools server
openapi_server = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=http_client,
    name="BMC ISPW API Tools"
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
            metrics.record_rate_limit()
            bmc_status = "rate_limited"
            response_time = 0.0
        else:
            # Test BMC API connectivity
            response = await http_client.get("/health")
            response_time = (datetime.now() - start_time).total_seconds()
            bmc_status = "healthy" if response.status_code == 200 else "unhealthy"
            metrics.record_request(success=response.status_code == 200, response_time=response_time)
            
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds()
        bmc_status = "unreachable"
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
            "tokens_available": round(rate_limiter.tokens, 2)
        },
        "cache": {
            "size": len(cache.cache),
            "max_size": cache.max_size,
            "hit_rate_percent": round(cache.get_hit_rate(), 2),
            "expired_entries": sum(1 for entry in cache.cache.values() if entry.is_expired())
        }
    }
    
    return json.dumps(health_data, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_server_metrics(ctx: Context = None) -> str:
    """Get server performance metrics."""
    if ctx:
        ctx.info("Retrieving server metrics")
    
    return json.dumps(metrics.to_dict(include_cache_stats=True), indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_rate_limiter_status(ctx: Context = None) -> str:
    """Get current rate limiter status and configuration."""
    if ctx:
        ctx.info("Checking rate limiter status")
    
    status = {
        "configuration": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "burst_size": rate_limiter.burst_size
        },
        "current_state": {
            "tokens_available": round(rate_limiter.tokens, 2),
            "last_refill": rate_limiter.last_refill.isoformat(),
            "time_until_next_token": max(0, 60.0 / rate_limiter.requests_per_minute) if rate_limiter.tokens < 1 else 0
        },
        "metrics": {
            "rate_limited_requests": metrics.rate_limited_requests,
            "rate_limit_percentage": round((metrics.rate_limited_requests / max(1, metrics.total_requests)) * 100, 2)
        }
    }
    
    return json.dumps(status, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_cache_info(ctx: Context = None) -> str:
    """Get comprehensive cache information and statistics."""
    if ctx:
        ctx.info("Retrieving cache information")
    
    cache_stats = cache.get_stats()
    
    # Add additional runtime information
    cache_info = {
        **cache_stats,
        "configuration": {
            "max_size": cache.max_size,
            "default_ttl_seconds": cache.default_ttl
        },
        "performance": {
            "hit_rate_percent": cache_stats["hit_rate_percent"],
            "efficiency": "excellent" if cache_stats["hit_rate_percent"] > 80 else
                         "good" if cache_stats["hit_rate_percent"] > 60 else
                         "needs_improvement"
        }
    }
    
    return json.dumps(cache_info, indent=2)


@mcp.tool(tags={"management", "admin"})
async def clear_cache(ctx: Context = None) -> str:
    """Clear all cache entries."""
    if ctx:
        ctx.info("Clearing cache")
    
    start_time = datetime.now()
    cleared_count = await cache.clear()
    operation_time = (datetime.now() - start_time).total_seconds()
    
    result = {
        "success": True,
        "cleared_entries": cleared_count,
        "operation_time_seconds": round(operation_time, 3),
        "cache_size_after": len(cache.cache),
        "message": f"Successfully cleared {cleared_count} cache entries"
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
        "message": f"Cleaned up {removed_count} expired cache entries"
    }
    
    return json.dumps(result, indent=2)


# Add elicitation tool following FastMCP patterns
@mcp.tool(tags={"elicitation", "workflow"})
async def create_assignment_interactive(ctx: Context) -> str:
    """Interactively create a new BMC ISPW assignment with user elicitation."""
    start_time = datetime.now()
    
    try:
        # Get assignment details through elicitation
        title_result = await ctx.elicit(
            "What is the assignment title?", 
            response_type=str
        )
        
        if isinstance(title_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"
        
        title = title_result.data
        
        description_result = await ctx.elicit(
            "Provide assignment description:", 
            response_type=str
        )
        
        if isinstance(description_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"
        
        description = description_result.data
        
        # Check rate limiter before making API call
        if not await rate_limiter.acquire():
            metrics.record_rate_limit()
            return json.dumps({
                "error": True,
                "message": "Rate limit exceeded. Please try again later.",
                "rate_limit_info": {
                    "requests_per_minute": rate_limiter.requests_per_minute,
                    "retry_after_seconds": 60.0 / rate_limiter.requests_per_minute
                }
            }, indent=2)
        
        # Create assignment via BMC API
        assignment_data = {
            "title": title,
            "description": description,
            "level": "DEV"
        }
        
        response = await http_client.post("/assignments", json=assignment_data)
        response_time = (datetime.now() - start_time).total_seconds()
        response.raise_for_status()
        
        result = response.json()
        metrics.record_request(success=True, response_time=response_time)
        
        return json.dumps({
            "success": True, 
            "assignment": result,
            "message": f"Assignment '{title}' created successfully",
            "response_time_seconds": round(response_time, 3)
        }, indent=2)
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds()
        metrics.record_request(success=False, response_time=response_time)
        
        return json.dumps({
            "error": True,
            "message": f"Failed to create assignment: {str(e)}",
            "response_time_seconds": round(response_time, 3)
        }, indent=2)


# Add custom health check route following FastMCP patterns  
@mcp.custom_route("/health", methods=["GET"])
async def health_check_route(request: Request) -> JSONResponse:
    """Health check endpoint for load balancers."""
    try:
        health_data = await get_server_health()
        return JSONResponse(json.loads(health_data))
    except Exception as e:
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)}, 
            status_code=503
        )


@mcp.custom_route("/metrics", methods=["GET"])  
async def metrics_route(request: Request) -> JSONResponse:
    """Metrics endpoint for monitoring."""
    try:
        metrics_data = await get_server_metrics()
        return JSONResponse(json.loads(metrics_data))
    except Exception as e:
        return JSONResponse(
            {"error": str(e)}, 
            status_code=500
        )


# Add resource template following FastMCP patterns
@mcp.resource("bmc://assignments/{srid}")
async def get_assignment_resource(srid: str) -> dict:
    """Get assignment data as a structured resource with caching."""
    try:
        # Check cache first
        cached_data = await cache.get("get_assignment", srid=srid)
        if cached_data is not None:
            return cached_data
        
        # Use rate limiter
        if not await rate_limiter.acquire():
            return {"error": f"Rate limit exceeded for assignment {srid}"}
        
        start_time = datetime.now()
        response = await http_client.get(f"/assignments/{srid}")
        response_time = (datetime.now() - start_time).total_seconds()
        response.raise_for_status()
        
        data = response.json()
        
        # Cache the successful response
        await cache.set("get_assignment", data, ttl=300, srid=srid)
        metrics.record_request(success=True, response_time=response_time)
        
        return data
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
        metrics.record_request(success=False, response_time=response_time)
        return {"error": f"Failed to get assignment {srid}: {str(e)}"}


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
