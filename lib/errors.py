#!/usr/bin/env python3
"""
Error Handling and Exception Classes

Provides comprehensive error handling for BMC API interactions including
custom exceptions, error categorization, and retry logic.
"""

import asyncio
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union

import httpx

from .settings import Settings


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker implementation for enhanced resilience.

    Prevents cascading failures by temporarily stopping requests
    to failing services and allowing them time to recover.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    async def acall(self, func: Callable, *args, **kwargs):
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None
            and time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""


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

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        response_data: dict = None,
        validation_errors: list = None,
    ):
        super().__init__(message, status_code, response_data)
        self.validation_errors = validation_errors or []


class BMCAPIRateLimitError(BMCAPIError):
    """Exception raised when BMC API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        status_code: int = 429,
        response_data: dict = None,
        retry_after: int = None,
    ):
        super().__init__(message, status_code, response_data)
        self.retry_after = retry_after


class MCPValidationError(Exception):
    """Exception raised for MCP validation errors."""

    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message)
        self.field = field
        self.value = value


class MCPServerError(Exception):
    """Exception raised for general MCP server errors."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ErrorHandler:
    """Comprehensive error handler with retry logic and categorization."""

    def __init__(self, settings: Settings, metrics: Any):
        self.settings = settings
        self.metrics = metrics
        self.max_retries = settings.max_retry_attempts
        self.base_delay = settings.retry_base_delay
        self.retryable_statuses = {500, 502, 503, 504}
        self.retryable_exceptions = (httpx.TimeoutException, httpx.ConnectError)

        # Initialize circuit breaker for enhanced resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(settings, "circuit_breaker_failure_threshold", 5),
            recovery_timeout=getattr(settings, "circuit_breaker_recovery_timeout", 60),
            expected_exception=(BMCAPIError, httpx.HTTPError),
        )

    def should_retry(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.retryable_statuses

        # Don't retry validation or authentication errors
        if isinstance(
            error,
            (
                MCPValidationError,
                BMCAPIAuthenticationError,
                BMCAPINotFoundError,
                BMCAPIValidationError,
            ),
        ):
            return False

        # Retry network-related exceptions
        if isinstance(error, self.retryable_exceptions):
            return True

        # Don't retry other exceptions by default
        return False

    def get_retry_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate exponential backoff delay with jitter."""
        # Exponential backoff: base_delay * 2^attempt
        delay = base_delay * (2**attempt)

        # Add jitter to prevent thundering herd problem
        # Jitter is ±25% of the calculated delay
        jitter = delay * 0.25 * (2 * random.random() - 1)

        # Ensure minimum delay and cap maximum delay
        final_delay = max(0.1, delay + jitter)
        return min(final_delay, 60.0)  # Cap at 60 seconds

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
        self,
        error: Union[httpx.HTTPStatusError, httpx.TimeoutException],
        operation: str,
    ) -> BMCAPIError:
        """Convert HTTP errors to appropriate BMC API exceptions."""
        # Handle timeout errors
        if isinstance(error, httpx.TimeoutException):
            return BMCAPITimeoutError(
                f"BMC API request timed out during {operation}: {str(error)}"
            )

        # Handle HTTP status errors
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
            validation_errors = []
            if isinstance(response_data, dict):
                if "errors" in response_data:
                    validation_errors = response_data["errors"]
                elif "error" in response_data:
                    validation_errors = [response_data["error"]]
            return BMCAPIValidationError(
                f"BMC API validation failed during {operation}",
                status_code=status_code,
                response_data=response_data,
                validation_errors=validation_errors,
            )
        elif status_code == 429:
            retry_after = None
            if (
                hasattr(error.response, "headers")
                and error.response.headers is not None
                and hasattr(error.response.headers, "__contains__")
                and "Retry-After" in error.response.headers
            ):
                try:
                    retry_after = int(error.response.headers["Retry-After"])
                except (ValueError, TypeError):
                    pass
            return BMCAPIRateLimitError(
                f"BMC API rate limit exceeded during {operation}",
                status_code=status_code,
                response_data=response_data,
                retry_after=retry_after,
            )
        else:
            return BMCAPIError(
                f"BMC API error during {operation}: {error}",
                status_code=status_code,
                response_data=response_data,
            )

    def handle_validation_error(
        self, error: Exception, field: str, value: str
    ) -> MCPValidationError:
        """Convert validation errors to MCP validation exceptions."""
        return MCPValidationError(
            f"Validation failed for field '{field}' with value '{value}': {str(error)}",
            field=field,
            value=value,
        )

    def handle_general_error(self, error: Exception, operation: str) -> MCPServerError:
        """Convert general errors to MCP server exceptions."""
        return MCPServerError(
            f"Server error during {operation}: {str(error)}",
            error_code="GENERAL_ERROR",
            details={"operation": operation, "error_type": type(error).__name__},
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

                # Use circuit breaker for enhanced resilience
                try:
                    result = await self.circuit_breaker.acall(func, *args, **kwargs)
                except CircuitBreakerOpenError as cb_error:
                    # Circuit breaker is open, return error response immediately
                    return self.create_error_response(
                        BMCAPIError(f"Service temporarily unavailable: {cb_error}"),
                        operation,
                        attempt + 1,
                    )

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
