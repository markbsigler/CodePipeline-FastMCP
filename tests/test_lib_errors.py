#!/usr/bin/env python3
"""
Comprehensive tests for lib/errors.py

Tests error handling, categorization, retry logic, and custom exceptions
for the BMC AMI DevX MCP Server.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from lib.errors import (
    BMCAPIAuthenticationError,
    BMCAPIError,
    BMCAPINotFoundError,
    BMCAPIRateLimitError,
    BMCAPITimeoutError,
    BMCAPIValidationError,
    ErrorHandler,
    retry_on_failure,
)
from lib.settings import Settings


class TestBMCAPIExceptions:
    """Test custom BMC API exception classes."""

    def test_bmc_api_error_basic(self):
        """Test basic BMCAPIError creation."""
        error = BMCAPIError("Test error")

        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response_data == {}

    def test_bmc_api_error_with_details(self):
        """Test BMCAPIError with status code and response data."""
        response_data = {"error": "Invalid request", "code": "E001"}
        error = BMCAPIError("Test error", status_code=400, response_data=response_data)

        assert str(error) == "Test error"
        assert error.status_code == 400
        assert error.response_data == response_data

    def test_bmc_api_timeout_error(self):
        """Test BMCAPITimeoutError inheritance."""
        error = BMCAPITimeoutError("Request timeout")

        assert isinstance(error, BMCAPIError)
        assert str(error) == "Request timeout"

    def test_bmc_api_authentication_error(self):
        """Test BMCAPIAuthenticationError inheritance."""
        error = BMCAPIAuthenticationError("Auth failed", status_code=401)

        assert isinstance(error, BMCAPIError)
        assert str(error) == "Auth failed"
        assert error.status_code == 401

    def test_bmc_api_not_found_error(self):
        """Test BMCAPINotFoundError inheritance."""
        error = BMCAPINotFoundError("Resource not found", status_code=404)

        assert isinstance(error, BMCAPIError)
        assert str(error) == "Resource not found"
        assert error.status_code == 404

    def test_bmc_api_validation_error(self):
        """Test BMCAPIValidationError inheritance."""
        error = BMCAPIValidationError("Validation failed", status_code=422)

        assert isinstance(error, BMCAPIError)
        assert str(error) == "Validation failed"
        assert error.status_code == 422

    def test_bmc_api_rate_limit_error(self):
        """Test BMCAPIRateLimitError inheritance."""
        error = BMCAPIRateLimitError("Rate limit exceeded", status_code=429)

        assert isinstance(error, BMCAPIError)
        assert str(error) == "Rate limit exceeded"
        assert error.status_code == 429


class TestErrorHandler:
    """Test ErrorHandler class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.settings = Settings(max_retry_attempts=3, retry_base_delay=1.0)
        self.mock_metrics = Mock()
        self.error_handler = ErrorHandler(self.settings, self.mock_metrics)

    def test_error_handler_initialization(self):
        """Test ErrorHandler initialization."""
        assert self.error_handler.settings == self.settings
        assert self.error_handler.metrics == self.mock_metrics
        assert self.error_handler.max_retries == 3
        assert self.error_handler.base_delay == 1.0
        assert self.error_handler.retryable_statuses == {500, 502, 503, 504}
        assert self.error_handler.retryable_exceptions == (
            httpx.TimeoutException,
            httpx.ConnectError,
        )

    def test_should_retry_http_status_error_retryable(self):
        """Test should_retry with retryable HTTP status error."""
        mock_response = Mock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=mock_response
        )

        assert self.error_handler.should_retry(error) is True

    def test_should_retry_http_status_error_non_retryable(self):
        """Test should_retry with non-retryable HTTP status error."""
        mock_response = Mock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        assert self.error_handler.should_retry(error) is False

    def test_should_retry_timeout_exception(self):
        """Test should_retry with timeout exception."""
        error = httpx.TimeoutException("Request timeout")

        assert self.error_handler.should_retry(error) is True

    def test_should_retry_connect_error(self):
        """Test should_retry with connection error."""
        error = httpx.ConnectError("Connection failed")

        assert self.error_handler.should_retry(error) is True

    def test_should_retry_other_exception(self):
        """Test should_retry with non-retryable exception."""
        error = ValueError("Invalid value")

        assert self.error_handler.should_retry(error) is False

    def test_get_retry_delay(self):
        """Test get_retry_delay exponential backoff calculation."""
        assert self.error_handler.get_retry_delay(0, 1.0) == 1.0
        assert self.error_handler.get_retry_delay(1, 1.0) == 2.0
        assert self.error_handler.get_retry_delay(2, 1.0) == 4.0
        assert self.error_handler.get_retry_delay(3, 2.0) == 16.0

    def test_categorize_error_http_status_401(self):
        """Test categorize_error with 401 HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "authentication_error"
        assert result["status_code"] == 401
        assert result["operation"] == "test_operation"

    def test_categorize_error_http_status_404(self):
        """Test categorize_error with 404 HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "not_found_error"
        assert result["status_code"] == 404

    def test_categorize_error_http_status_429(self):
        """Test categorize_error with 429 HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 429
        error = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "rate_limit_error"
        assert result["status_code"] == 429

    def test_categorize_error_http_status_422(self):
        """Test categorize_error with 422 HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 422
        error = httpx.HTTPStatusError(
            "Validation error", request=Mock(), response=mock_response
        )

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "validation_error"
        assert result["status_code"] == 422

    def test_categorize_error_http_status_500(self):
        """Test categorize_error with 500 HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "server_error"
        assert result["status_code"] == 500

    def test_categorize_error_timeout_exception(self):
        """Test categorize_error with timeout exception."""
        error = httpx.TimeoutException("Request timeout")

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "timeout_error"
        assert result["status_code"] == 500  # Default

    def test_categorize_error_connect_error(self):
        """Test categorize_error with connection error."""
        error = httpx.ConnectError("Connection failed")

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "connection_error"
        assert result["status_code"] == 500  # Default

    def test_categorize_error_unknown_error(self):
        """Test categorize_error with unknown error type."""
        error = ValueError("Unknown error")

        result = self.error_handler.categorize_error(error, "test_operation")

        assert result["type"] == "unknown_error"
        assert result["status_code"] == 500  # Default

    def test_handle_http_error_401(self):
        """Test handle_http_error with 401 status."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        error = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )

        result = self.error_handler.handle_http_error(error, "test_operation")

        assert isinstance(result, BMCAPIAuthenticationError)
        assert result.status_code == 401
        assert result.response_data == {"error": "Unauthorized"}

    def test_handle_http_error_404(self):
        """Test handle_http_error with 404 status."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=mock_response
        )

        result = self.error_handler.handle_http_error(error, "test_operation")

        assert isinstance(result, BMCAPINotFoundError)
        assert result.status_code == 404

    def test_handle_http_error_422(self):
        """Test handle_http_error with 422 status."""
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"error": "Validation failed"}
        error = httpx.HTTPStatusError(
            "Validation failed", request=Mock(), response=mock_response
        )

        result = self.error_handler.handle_http_error(error, "test_operation")

        assert isinstance(result, BMCAPIValidationError)
        assert result.status_code == 422

    def test_handle_http_error_429(self):
        """Test handle_http_error with 429 status."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limited"}
        error = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )

        result = self.error_handler.handle_http_error(error, "test_operation")

        assert isinstance(result, BMCAPIRateLimitError)
        assert result.status_code == 429

    def test_handle_http_error_json_parse_failure(self):
        """Test handle_http_error when JSON parsing fails."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("JSON parse error")
        mock_response.text = "Internal server error"
        error = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )

        result = self.error_handler.handle_http_error(error, "test_operation")

        assert isinstance(result, BMCAPIError)
        assert result.status_code == 500
        assert result.response_data == {"raw_response": "Internal server error"}

    def test_create_error_response_basic(self):
        """Test create_error_response with basic error."""
        error = ValueError("Test error")

        result = self.error_handler.create_error_response(error, "test_operation")

        assert result["error"] is True
        assert result["type"] == "unknown_error"
        assert result["message"] == "Test error"
        assert result["operation"] == "test_operation"
        assert result["attempts_made"] == 1
        assert "timestamp" in result

    def test_create_error_response_with_metrics(self):
        """Test create_error_response with metrics recording."""
        self.mock_metrics.record_error = Mock()
        error = httpx.TimeoutException("Timeout")

        result = self.error_handler.create_error_response(
            error, "test_operation", attempts_made=3
        )

        assert result["type"] == "timeout_error"
        assert result["attempts_made"] == 3
        self.mock_metrics.record_error.assert_called_once_with(
            "timeout_error", "test_operation"
        )

    def test_create_error_response_rate_limit_error(self):
        """Test create_error_response with rate limit error adds retry_after."""
        mock_response = Mock()
        mock_response.status_code = 429
        error = httpx.HTTPStatusError(
            "Rate limited", request=Mock(), response=mock_response
        )

        result = self.error_handler.create_error_response(error, "test_operation")

        assert result["type"] == "rate_limit_error"
        assert result["retry_after"] == 60

    def test_create_error_response_validation_error(self):
        """Test create_error_response with validation error adds validation_details."""
        mock_response = Mock()
        mock_response.status_code = 422
        error = httpx.HTTPStatusError(
            "Validation failed", request=Mock(), response=mock_response
        )
        error.response_data = {"field_errors": ["Invalid field"]}

        result = self.error_handler.create_error_response(error, "test_operation")

        assert result["type"] == "validation_error"
        assert "validation_details" in result

    def test_create_error_response_network_issue(self):
        """Test create_error_response with network issues adds network_issue flag."""
        error = httpx.ConnectError("Connection failed")

        result = self.error_handler.create_error_response(error, "test_operation")

        assert result["type"] == "connection_error"
        assert result["network_issue"] is True

    def test_create_error_response_long_message_truncation(self):
        """Test create_error_response truncates long error messages."""
        long_message = "x" * 600  # Longer than 500 characters
        error = ValueError(long_message)

        result = self.error_handler.create_error_response(error, "test_operation")

        assert len(result["message"]) == 500
        assert result["message"] == "x" * 500

    @pytest.mark.asyncio
    async def test_execute_with_recovery_success(self):
        """Test execute_with_recovery with successful operation."""
        mock_func = AsyncMock(return_value="success")
        self.mock_metrics.record_operation = Mock()

        result = await self.error_handler.execute_with_recovery(
            "test_op", mock_func, "arg1", key="value"
        )

        assert result == "success"
        mock_func.assert_called_once_with("arg1", key="value")
        self.mock_metrics.record_operation.assert_called_once()
        # Check that success was recorded
        call_args = self.mock_metrics.record_operation.call_args
        assert call_args[0][0] == "test_op"  # operation
        assert call_args[0][1] is True  # success

    @pytest.mark.asyncio
    async def test_execute_with_recovery_retry_then_success(self):
        """Test execute_with_recovery with retry then success."""
        mock_func = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "Server error", request=Mock(), response=Mock(status_code=503)
                ),
                "success",
            ]
        )
        self.mock_metrics.record_operation = Mock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.error_handler.execute_with_recovery(
                "test_op", mock_func
            )

        assert result == "success"
        assert mock_func.call_count == 2
        # Should record both failed and successful operations
        assert self.mock_metrics.record_operation.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_recovery_non_retryable_error(self):
        """Test execute_with_recovery with non-retryable error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        error = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )
        mock_func = AsyncMock(side_effect=error)
        self.mock_metrics.record_operation = Mock()

        result = await self.error_handler.execute_with_recovery("test_op", mock_func)

        assert isinstance(result, dict)
        assert result["error"] is True
        # The error gets categorized correctly as authentication_error for 401 status
        assert result["type"] == "authentication_error"
        assert mock_func.call_count == 1  # No retries for auth errors

    @pytest.mark.asyncio
    async def test_execute_with_recovery_max_retries_exceeded(self):
        """Test execute_with_recovery when max retries are exceeded."""
        mock_response = Mock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=mock_response
        )
        mock_func = AsyncMock(side_effect=error)
        self.mock_metrics.record_operation = Mock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.error_handler.execute_with_recovery(
                "test_op", mock_func
            )

        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["type"] == "server_error"
        assert mock_func.call_count == 4  # Initial + 3 retries


class TestRetryOnFailureDecorator:
    """Test retry_on_failure decorator functionality."""

    @pytest.mark.asyncio
    async def test_retry_on_failure_success(self):
        """Test retry_on_failure decorator with successful function."""

        @retry_on_failure(max_retries=3, base_delay=0.1)
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_failure_retry_then_success(self):
        """Test retry_on_failure decorator with retry then success."""
        call_count = 0

        @retry_on_failure(max_retries=3, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("Timeout")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await test_func()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure_non_retryable_error(self):
        """Test retry_on_failure decorator with non-retryable error."""

        @retry_on_failure(max_retries=3, base_delay=0.1)
        async def test_func():
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError, match="Non-retryable error"):
            await test_func()

    @pytest.mark.asyncio
    async def test_retry_on_failure_max_retries_exceeded(self):
        """Test retry_on_failure decorator when max retries are exceeded."""

        @retry_on_failure(max_retries=2, base_delay=0.1)
        async def test_func():
            raise httpx.TimeoutException("Always fails")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.TimeoutException, match="Always fails"):
                await test_func()

    @pytest.mark.asyncio
    async def test_retry_on_failure_http_status_retryable(self):
        """Test retry_on_failure decorator with retryable HTTP status."""
        call_count = 0

        @retry_on_failure(max_retries=2, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_response = Mock()
                mock_response.status_code = 502
                raise httpx.HTTPStatusError(
                    "Bad gateway", request=Mock(), response=mock_response
                )
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await test_func()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure_http_status_non_retryable(self):
        """Test retry_on_failure decorator with non-retryable HTTP status."""

        @retry_on_failure(max_retries=3, base_delay=0.1)
        async def test_func():
            mock_response = Mock()
            mock_response.status_code = 404
            raise httpx.HTTPStatusError(
                "Not found", request=Mock(), response=mock_response
            )

        with pytest.raises(httpx.HTTPStatusError, match="Not found"):
            await test_func()
