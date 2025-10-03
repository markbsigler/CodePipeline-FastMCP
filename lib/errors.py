#!/usr/bin/env python3
"""
Error Handling and Exception Classes

Provides comprehensive error handling for BMC API interactions including
custom exceptions, error categorization, and retry logic.
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional

import httpx

from .settings import Settings


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


class BMCAPIAuthenticationError(BMCAPIError):
    """Exception raised when BMC API authentication fails."""


class BMCAPINotFoundError(BMCAPIError):
    """Exception raised when BMC API resource is not found."""


class BMCAPIValidationError(BMCAPIError):
    """Exception raised when BMC API request validation fails."""


class BMCAPIRateLimitError(BMCAPIError):
    """Exception raised when BMC API rate limit is exceeded."""


class ErrorHandler:
    """Comprehensive error handler with retry logic and categorization."""

    def __init__(self, settings: Settings, metrics: Any):
        self.settings = settings
        self.metrics = metrics
        self.max_retries = settings.max_retry_attempts
        self.base_delay = settings.retry_base_delay
        self.retryable_statuses = {500, 502, 503, 504}
        self.retryable_exceptions = (httpx.TimeoutException, httpx.ConnectError)

    def should_retry(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.retryable_statuses
        return isinstance(error, self.retryable_exceptions)

    def get_retry_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate exponential backoff delay."""
        return base_delay * (2**attempt)

    def categorize_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Categorize error and extract relevant information."""
        error_type = "unknown_error"
        message = str(error)
        status_code = 500

        # Handle BMC API exceptions first
        if isinstance(error, BMCAPIAuthenticationError):
            error_type = "authentication_error"
            status_code = error.status_code or 401
        elif isinstance(error, BMCAPINotFoundError):
            error_type = "not_found_error"
            status_code = error.status_code or 404
        elif isinstance(error, BMCAPIValidationError):
            error_type = "validation_error"
            status_code = error.status_code or 422
        elif isinstance(error, BMCAPIRateLimitError):
            error_type = "rate_limit_error"
            status_code = error.status_code or 429
        elif isinstance(error, BMCAPITimeoutError):
            error_type = "timeout_error"
            status_code = error.status_code or 408
        elif isinstance(error, BMCAPIError):
            error_type = "server_error"
            status_code = error.status_code or 500
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code == 401:
                error_type = "authentication_error"
            elif status_code == 404:
                error_type = "not_found_error"
            elif status_code == 429:
                error_type = "rate_limit_error"
            elif status_code == 422:
                error_type = "validation_error"
            elif status_code >= 500:
                error_type = "server_error"
        elif isinstance(error, httpx.TimeoutException):
            error_type = "timeout_error"
        elif isinstance(error, httpx.ConnectError):
            error_type = "connection_error"

        return {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "operation": operation,
        }

    def handle_http_error(
        self, error: httpx.HTTPStatusError, operation: str
    ) -> BMCAPIError:
        """Convert HTTP errors to appropriate BMC API exceptions."""
        status_code = error.response.status_code
        response_data = {}

        try:
            response_data = error.response.json()
        except Exception:
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
        elif status_code == 422:
            return BMCAPIValidationError(
                f"BMC API validation failed during {operation}",
                status_code=status_code,
                response_data=response_data,
            )
        elif status_code == 429:
            return BMCAPIRateLimitError(
                f"BMC API rate limit exceeded during {operation}",
                status_code=status_code,
                response_data=response_data,
            )
        else:
            return BMCAPIError(
                f"BMC API error during {operation}: {error}",
                status_code=status_code,
                response_data=response_data,
            )

    def create_error_response(
        self, error: Exception, operation: str, attempts_made: int = 1
    ) -> Dict[str, Any]:
        """Create standardized error response."""
        error_info = self.categorize_error(error, operation)

        # Record error metrics if available
        if hasattr(self.metrics, "record_error"):
            self.metrics.record_error(error_info["type"], operation)

        response = {
            "error": True,
            "type": error_info["type"],
            "message": error_info["message"][:500],  # Truncate long messages
            "operation": operation,
            "attempts_made": attempts_made,
            "status_code": error_info.get("status_code"),
            "timestamp": time.time(),
        }

        # Add specific error details based on type
        if error_info["type"] == "rate_limit_error":
            response["retry_after"] = 60  # Suggest retry after 1 minute
        elif error_info["type"] == "validation_error":
            response["validation_details"] = getattr(error, "response_data", {})
        elif error_info["type"] in ["timeout_error", "connection_error"]:
            response["network_issue"] = True

        return response

    async def execute_with_recovery(
        self, operation: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute function with comprehensive error handling and retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                result = await func(*args, **kwargs)

                # Record successful operation
                duration = time.time() - start_time
                if hasattr(self.metrics, "record_request"):
                    # Extract method and endpoint from operation (e.g., "GET /endpoint")
                    parts = operation.split(" ", 1)
                    method = parts[0] if len(parts) > 0 else "GET"
                    endpoint = parts[1] if len(parts) > 1 else operation
                    self.metrics.record_request(method, endpoint, 200, duration)

                return result

            except Exception as error:
                duration = time.time() - start_time
                last_error = error

                # Record failed operation
                if hasattr(self.metrics, "record_request"):
                    # Extract method and endpoint from operation (e.g., "GET /endpoint")
                    parts = operation.split(" ", 1)
                    method = parts[0] if len(parts) > 0 else "GET"
                    endpoint = parts[1] if len(parts) > 1 else operation
                    # Extract status code from error if available
                    status_code = 500
                    if hasattr(error, "response") and hasattr(
                        error.response, "status_code"
                    ):
                        status_code = error.response.status_code
                    self.metrics.record_request(method, endpoint, status_code, duration)

                # Convert HTTP errors to BMC API exceptions
                if isinstance(error, httpx.HTTPStatusError):
                    bmc_error = self.handle_http_error(error, operation)

                    # Don't retry certain error types
                    if isinstance(
                        bmc_error,
                        (
                            BMCAPIAuthenticationError,
                            BMCAPINotFoundError,
                            BMCAPIValidationError,
                        ),
                    ):
                        return self.create_error_response(
                            bmc_error, operation, attempt + 1
                        )

                # Check if we should retry
                if attempt < self.max_retries and self.should_retry(error):
                    delay = self.get_retry_delay(attempt, self.base_delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    # No more retries, return error response
                    break

        # All retries exhausted
        return self.create_error_response(last_error, operation, attempt + 1)


def retry_on_failure(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for adding retry logic to functions."""

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as error:
                    last_error = error

                    # Simple retry logic for decorator
                    retryable_exceptions = (httpx.TimeoutException, httpx.ConnectError)
                    retryable_statuses = {500, 502, 503, 504}

                    should_retry = False
                    if isinstance(error, httpx.HTTPStatusError):
                        should_retry = error.response.status_code in retryable_statuses
                    elif isinstance(error, retryable_exceptions):
                        should_retry = True

                    if attempt < max_retries and should_retry:
                        delay = base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        break

            # All retries exhausted, raise the last error
            raise last_error

        return wrapper

    return decorator
