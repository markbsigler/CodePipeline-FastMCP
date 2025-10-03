#!/usr/bin/env python3
"""
BMC API Client

Provides comprehensive BMC AMI DevX API client with caching, metrics,
error handling, and retry logic for all ISPW operations.
"""

import time
from typing import Any, Dict, Optional

import httpx

from .cache import IntelligentCache
from .errors import (
    BMCAPIAuthenticationError,
    BMCAPINotFoundError,
    BMCAPIValidationError,
    ErrorHandler,
    retry_on_failure,
)


class BMCAMIDevXClient:
    """
    Comprehensive BMC AMI DevX API client.

    Provides methods for all ISPW operations including assignments, releases,
    sets, packages, and deployment operations with built-in caching, metrics,
    and error handling.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        cache: Optional[IntelligentCache] = None,
        metrics: Optional[Any] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        """
        Initialize the BMC API client.

        Args:
            http_client: Configured HTTP client for API requests
            cache: Optional cache instance for response caching
            metrics: Optional metrics collector
            error_handler: Optional error handler for retry logic
        """
        self.http_client = http_client
        self.cache = cache
        self.metrics = metrics
        self.error_handler = error_handler

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        cache_ttl: int = 300,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with caching, metrics, and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request payload for POST/PUT requests
            cache_key: Optional cache key for GET requests
            cache_ttl: Cache TTL in seconds

        Returns:
            API response data
        """
        start_time = time.time()

        try:
            # Check cache for GET requests
            if method == "GET" and cache_key and self.cache:
                cached_response = await self.cache.get(
                    "api_request", endpoint=endpoint, **{cache_key: True}
                )
                if cached_response is not None:
                    # Record cache hit in metrics
                    if self.metrics and hasattr(self.metrics, "record_cache_operation"):
                        self.metrics.record_cache_operation("get", True, cache_key)
                    return cached_response

            # Make the HTTP request
            if method == "GET":
                response = await self.http_client.get(endpoint)
            elif method == "POST":
                response = await self.http_client.post(endpoint, json=data)
            elif method == "PUT":
                response = await self.http_client.put(endpoint, json=data)
            elif method == "DELETE":
                response = await self.http_client.delete(endpoint)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            result = response.json()

            # Cache successful GET responses
            if method == "GET" and cache_key and self.cache:
                await self.cache.set(
                    "api_request",
                    result,
                    ttl=cache_ttl,
                    endpoint=endpoint,
                    **{cache_key: True},
                )
                if self.metrics and hasattr(self.metrics, "record_cache_operation"):
                    self.metrics.record_cache_operation("set", True, cache_key)

            # Record successful request metrics
            duration = time.time() - start_time
            if self.metrics:
                if hasattr(self.metrics, "record_request"):
                    self.metrics.record_request(
                        method, endpoint, response.status_code, duration
                    )
                elif hasattr(self.metrics, "record_bmc_api_call"):
                    self.metrics.record_bmc_api_call(
                        f"{method} {endpoint}", True, duration
                    )

            return result

        except Exception as error:
            duration = time.time() - start_time

            # Record failed request metrics
            if self.metrics:
                # Extract status code from error response
                status_code = 500  # Default
                if hasattr(error, "response") and error.response:
                    if hasattr(error.response, "status_code"):
                        status_code = error.response.status_code
                    elif (
                        isinstance(error.response, dict)
                        and "status_code" in error.response
                    ):
                        status_code = error.response["status_code"]
                if hasattr(self.metrics, "record_request"):
                    self.metrics.record_request(method, endpoint, status_code, duration)
                elif hasattr(self.metrics, "record_bmc_api_call"):
                    self.metrics.record_bmc_api_call(
                        f"{method} {endpoint}", False, duration
                    )

            # Check if this is a non-retryable error before using error handler
            if self.error_handler and isinstance(error, httpx.HTTPStatusError):
                bmc_error = self.error_handler.handle_http_error(
                    error, f"{method} {endpoint}"
                )
                # Don't retry certain error types
                if isinstance(
                    bmc_error,
                    (
                        BMCAPIAuthenticationError,
                        BMCAPINotFoundError,
                        BMCAPIValidationError,
                    ),
                ):
                    return self.error_handler.create_error_response(
                        bmc_error, f"{method} {endpoint}", 1
                    )

                # Use error handler for retryable errors
                return await self.error_handler.execute_with_recovery(
                    f"{method} {endpoint}",
                    self._make_raw_request,
                    method,
                    endpoint,
                    data,
                )
            elif self.error_handler:
                # Non-HTTP errors, use error handler
                return await self.error_handler.execute_with_recovery(
                    f"{method} {endpoint}",
                    self._make_raw_request,
                    method,
                    endpoint,
                    data,
                )

            raise error

    async def _make_raw_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ):
        """Raw HTTP request without caching or metrics (for error handler)."""
        if method == "GET":
            response = await self.http_client.get(endpoint)
        elif method == "POST":
            response = await self.http_client.post(endpoint, json=data)
        elif method == "PUT":
            response = await self.http_client.put(endpoint, json=data)
        elif method == "DELETE":
            response = await self.http_client.delete(endpoint)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()

    async def get_cached_or_fetch(
        self,
        operation: str,
        endpoint: str,
        cache_params: Optional[Dict[str, Any]] = None,
        ttl: int = 300,
    ) -> Dict[str, Any]:
        """
        Get data from cache or fetch from API.

        Args:
            operation: Operation name for cache key generation
            endpoint: API endpoint
            cache_params: Parameters for cache key generation
            ttl: Cache TTL in seconds

        Returns:
            Response data from cache or API
        """
        if self.cache is None:
            return await self.make_request("GET", endpoint)

        cache_params = cache_params or {}
        cached_data = await self.cache.get(operation, **cache_params)

        if cached_data is not None:
            if self.metrics and hasattr(self.metrics, "record_cache_operation"):
                self.metrics.record_cache_operation("get", True, operation)
            return cached_data

        # Cache miss - fetch from API
        data = await self.make_request("GET", endpoint)

        # Check if the response is an error response (from error handler)
        if isinstance(data, dict) and data.get("error") is True:
            # API failed, try to return any available cached data as fallback
            fallback_data = await self.cache.get(operation, **cache_params)
            if fallback_data is not None:
                if self.metrics and hasattr(self.metrics, "record_cache_operation"):
                    self.metrics.record_cache_operation(
                        "get", True, f"{operation}_fallback"
                    )
                return fallback_data
            # No cached data available, return the error response
            return data

        # Success - cache the response
        await self.cache.set(operation, data, ttl=ttl, **cache_params)

        if self.metrics and hasattr(self.metrics, "record_cache_operation"):
            self.metrics.record_cache_operation("get", False, operation)

        return data

    # Assignment Operations
    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def create_assignment(
        self,
        srid: str,
        assignment_id: str,
        stream: str,
        application: str,
        description: Optional[str] = None,
        default_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new assignment."""
        data = {
            "assignmentId": assignment_id,
            "stream": stream,
            "application": application,
        }
        if description:
            data["description"] = description
        if default_path:
            data["defaultPath"] = default_path

        return await self.make_request("POST", f"/ispw/{srid}/assignments", data)

    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_assignments(self, srid: str, **filters) -> Dict[str, Any]:
        """Get assignments with optional filtering."""
        query_params = "&".join(f"{k}={v}" for k, v in filters.items() if v is not None)
        endpoint = f"/ispw/{srid}/assignments"
        if query_params:
            endpoint += f"?{query_params}"

        return await self.get_cached_or_fetch(
            "get_assignments",
            endpoint,
            cache_params={"srid": srid, **filters},
            ttl=180,  # 3 minutes cache
        )

    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_assignment_details(
        self, srid: str, assignment_id: str
    ) -> Dict[str, Any]:
        """Get detailed assignment information."""
        return await self.get_cached_or_fetch(
            "get_assignment_details",
            f"/ispw/{srid}/assignments/{assignment_id}",
            cache_params={"srid": srid, "assignment_id": assignment_id},
            ttl=300,  # 5 minutes cache
        )

    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def generate_assignment(
        self,
        srid: str,
        assignment_id: str,
        generate_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate code for an assignment."""
        return await self.make_request(
            "POST",
            f"/ispw/{srid}/assignments/{assignment_id}/tasks/generate",
            data=generate_data or {},
        )

    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def promote_assignment(
        self,
        srid: str,
        assignment_id: str,
        promote_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Promote an assignment."""
        return await self.make_request(
            "POST",
            f"/ispw/{srid}/assignments/{assignment_id}/tasks/promote",
            data=promote_data or {},
        )

    # Release Operations
    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def create_release(
        self,
        srid: str,
        release_id: str,
        stream: str,
        application: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new release."""
        data = {"releaseId": release_id, "stream": stream, "application": application}
        if description:
            data["description"] = description

        return await self.make_request("POST", f"/ispw/{srid}/releases", data)

    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_releases(self, srid: str, **filters) -> Dict[str, Any]:
        """Get releases with optional filtering."""
        query_params = "&".join(f"{k}={v}" for k, v in filters.items() if v is not None)
        endpoint = f"/ispw/{srid}/releases"
        if query_params:
            endpoint += f"?{query_params}"

        return await self.get_cached_or_fetch(
            "get_releases", endpoint, cache_params={"srid": srid, **filters}, ttl=300
        )

    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_release_details(self, srid: str, release_id: str) -> Dict[str, Any]:
        """Get detailed release information."""
        return await self.get_cached_or_fetch(
            "get_release_details",
            f"/ispw/{srid}/releases/{release_id}",
            cache_params={"srid": srid, "release_id": release_id},
            ttl=300,
        )

    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def deploy_release(
        self, srid: str, release_id: str, deploy_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Deploy a release."""
        return await self.make_request(
            "POST",
            f"/ispw/{srid}/releases/{release_id}/tasks/deploy",
            data=deploy_data or {},
        )

    # Set Operations
    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_sets(
        self, srid: str, set_id: Optional[str] = None, **filters
    ) -> Dict[str, Any]:
        """Get sets with optional filtering."""
        if set_id:
            endpoint = f"/ispw/{srid}/sets/{set_id}"
            return await self.get_cached_or_fetch(
                "get_set_details",
                endpoint,
                cache_params={"srid": srid, "set_id": set_id},
                ttl=300,
            )

        query_params = "&".join(f"{k}={v}" for k, v in filters.items() if v is not None)
        endpoint = f"/ispw/{srid}/sets"
        if query_params:
            endpoint += f"?{query_params}"

        return await self.get_cached_or_fetch(
            "get_sets", endpoint, cache_params={"srid": srid, **filters}, ttl=180
        )

    @retry_on_failure(max_retries=3, base_delay=1.0)
    async def deploy_set(
        self, srid: str, set_id: str, deploy_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Deploy a set."""
        return await self.make_request(
            "POST", f"/ispw/{srid}/sets/{set_id}/tasks/deploy", data=deploy_data or {}
        )

    # Package Operations
    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_packages(
        self, srid: str, package_id: Optional[str] = None, **filters
    ) -> Dict[str, Any]:
        """Get packages with optional filtering."""
        if package_id:
            return await self.get_package_details(srid, package_id)

        query_params = "&".join(f"{k}={v}" for k, v in filters.items() if v is not None)
        endpoint = f"/ispw/{srid}/packages"
        if query_params:
            endpoint += f"?{query_params}"

        return await self.get_cached_or_fetch(
            "get_packages", endpoint, cache_params={"srid": srid, **filters}, ttl=180
        )

    @retry_on_failure(max_retries=2, base_delay=0.5)
    async def get_package_details(self, srid: str, package_id: str) -> Dict[str, Any]:
        """Get detailed package information."""
        return await self.get_cached_or_fetch(
            "get_package_details",
            f"/ispw/{srid}/packages/{package_id}",
            cache_params={"srid": srid, "package_id": package_id},
            ttl=300,
        )
