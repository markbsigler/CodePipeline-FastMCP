#!/usr/bin/env python3
"""
Tests for lib/security_middleware.py

Comprehensive test coverage for security middleware functionality.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestSecurityMiddleware:
    """Test cases for SecurityMiddleware."""

    @pytest.fixture
    def mock_settings(self):
        """Create a mock Settings object."""
        settings = Mock()
        settings.security_enabled = True
        settings.security_rate_limit_enabled = True
        settings.security_rate_limit_per_user_rpm = 30
        settings.security_rate_limit_per_api_key_rpm = 100
        settings.security_input_validation_enabled = True
        settings.security_max_request_size = 1024 * 1024
        settings.security_max_string_length = 1000
        settings.security_headers_enabled = True
        settings.security_cors_enabled = True
        settings.security_cors_allowed_origins = "https://example.com,https://test.com"
        settings.security_audit_logging_enabled = True
        settings.security_audit_log_sensitive_data = False
        return settings

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP Context."""
        context = Mock()
        context.metadata = {
            "x-api-key": "test-api-key-123",
            "user-agent": "test-client/1.0",
        }
        return context

    @pytest.fixture
    def security_middleware(self, mock_settings):
        """Create a SecurityMiddleware instance."""
        from lib.security_middleware import SecurityMiddleware

        return SecurityMiddleware(mock_settings)

    def test_security_middleware_initialization(self, security_middleware):
        """Test security middleware initialization."""
        assert security_middleware.settings is not None
        assert security_middleware.security_config is not None
        assert security_middleware.security_manager is not None
        assert security_middleware.enabled is True

    def test_security_middleware_disabled(self):
        """Test security middleware when disabled."""
        from lib.security_middleware import SecurityMiddleware

        settings = Mock()
        settings.security_enabled = False
        settings.security_rate_limit_enabled = False
        settings.security_rate_limit_per_user_rpm = 30
        settings.security_rate_limit_per_api_key_rpm = 100
        settings.security_input_validation_enabled = False
        settings.security_max_request_size = 1024
        settings.security_max_string_length = 100
        settings.security_headers_enabled = False
        settings.security_cors_enabled = False
        settings.security_cors_allowed_origins = ""
        settings.security_audit_logging_enabled = False
        settings.security_audit_log_sensitive_data = False

        middleware = SecurityMiddleware(settings)
        assert middleware.enabled is False

    @pytest.mark.asyncio
    async def test_process_request_disabled(self, mock_settings, mock_context):
        """Test process_request when security is disabled."""
        from lib.security_middleware import SecurityMiddleware

        mock_settings.security_enabled = False
        middleware = SecurityMiddleware(mock_settings)

        result = await middleware.process_request(
            context=mock_context,
            request_data={"test": "data"},
            endpoint="/api/test",
            method="POST",
        )

        assert result["security_enabled"] is False

    @pytest.mark.asyncio
    async def test_process_request_success(self, security_middleware, mock_context):
        """Test successful request processing."""
        # Mock the security manager's check_request_security method
        with patch.object(
            security_middleware.security_manager, "check_request_security"
        ) as mock_check:
            mock_check.return_value = {
                "rate_limit_passed": True,
                "validation_passed": True,
                "security_headers": {"X-Frame-Options": "DENY"},
                "audit_logged": True,
            }

            result = await security_middleware.process_request(
                context=mock_context,
                request_data={"test": "data"},
                endpoint="/api/test",
                method="POST",
            )

            assert result["security_enabled"] is True
            assert result["security_passed"] is True
            assert result["rate_limit_passed"] is True
            assert result["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_process_request_rate_limit_exceeded(
        self, security_middleware, mock_context
    ):
        """Test request processing when rate limit is exceeded."""
        from lib.security import RateLimitExceeded

        # Mock the security manager to raise RateLimitExceeded
        with patch.object(
            security_middleware.security_manager, "check_request_security"
        ) as mock_check:
            mock_check.side_effect = RateLimitExceeded(
                "Rate limit exceeded", retry_after=60
            )

            # Mock the audit logger
            with patch.object(
                security_middleware.security_manager.audit_logger,
                "log_rate_limit_exceeded",
            ) as mock_log:
                mock_log.return_value = None

                result = await security_middleware.process_request(
                    context=mock_context,
                    request_data={"test": "data"},
                    endpoint="/api/test",
                    method="POST",
                )

                assert result["security_enabled"] is True
                assert result["security_passed"] is False
                assert result["error"] == "rate_limit_exceeded"
                assert result["retry_after"] == 60
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_validation_error(
        self, security_middleware, mock_context
    ):
        """Test request processing when validation fails."""
        from lib.security import ValidationError

        # Mock the security manager to raise ValidationError
        with patch.object(
            security_middleware.security_manager, "check_request_security"
        ) as mock_check:
            validation_error = ValidationError("Invalid input")
            validation_error.field = "email"
            mock_check.side_effect = validation_error

            # Mock the audit logger
            with patch.object(
                security_middleware.security_manager.audit_logger,
                "log_validation_error",
            ) as mock_log:
                mock_log.return_value = None

                result = await security_middleware.process_request(
                    context=mock_context,
                    request_data={"test": "data"},
                    endpoint="/api/test",
                    method="POST",
                )

                assert result["security_enabled"] is True
                assert result["security_passed"] is False
                assert result["error"] == "validation_error"
                assert result["field"] == "email"
                mock_log.assert_called_once()

    def test_extract_client_info_basic(self, security_middleware):
        """Test basic client info extraction."""
        mock_context = Mock()
        mock_context.metadata = None

        client_info = security_middleware._extract_client_info(mock_context)

        assert client_info["identifier"] == "unknown_client"
        assert client_info["identifier_type"] == "client_id"
        assert client_info["ip_address"] == "127.0.0.1"
        assert client_info["user_agent"] == "FastMCP-Client/1.0"

    def test_extract_client_info_with_api_key(self, security_middleware):
        """Test client info extraction with API key."""
        mock_context = Mock()
        mock_context.metadata = {"x-api-key": "test-api-key-123456789"}

        client_info = security_middleware._extract_client_info(mock_context)

        assert client_info["api_key"] == "test-api-key-123456789"
        assert client_info["identifier"] == "test-api-key-123"  # First 16 chars
        assert client_info["identifier_type"] == "api_key"

    def test_extract_client_info_with_authorization(self, security_middleware):
        """Test client info extraction with authorization header."""
        mock_context = Mock()
        mock_context.metadata = {"authorization": "Bearer token123456789"}

        client_info = security_middleware._extract_client_info(mock_context)

        assert client_info["api_key"] == "Bearer token123456789"
        assert client_info["identifier"] == "Bearer token1234"  # First 16 chars
        assert client_info["identifier_type"] == "api_key"

    def test_get_security_headers_enabled(self, security_middleware):
        """Test getting security headers when enabled."""
        # Mock the security headers get_security_headers method
        with patch.object(
            security_middleware.security_manager.security_headers,
            "get_security_headers",
        ) as mock_headers:
            mock_headers.return_value = {
                "X-Frame-Options": "DENY",
                "X-Content-Type-Options": "nosniff",
            }

            headers = security_middleware.get_security_headers()

            assert headers["X-Frame-Options"] == "DENY"
            assert headers["X-Content-Type-Options"] == "nosniff"

    def test_get_security_headers_disabled(self, mock_settings):
        """Test getting security headers when disabled."""
        from lib.security_middleware import SecurityMiddleware

        mock_settings.security_enabled = False
        middleware = SecurityMiddleware(mock_settings)

        headers = middleware.get_security_headers()
        assert headers == {}

    def test_get_security_stats_enabled(self, security_middleware):
        """Test getting security stats when enabled."""
        # Mock the security manager get_security_stats method
        with patch.object(
            security_middleware.security_manager, "get_security_stats"
        ) as mock_stats:
            mock_stats.return_value = {
                "total_requests": 100,
                "blocked_requests": 5,
                "rate_limit_hits": 3,
            }

            stats = security_middleware.get_security_stats()

            assert stats["security_enabled"] is True
            assert stats["total_requests"] == 100
            assert stats["blocked_requests"] == 5

    def test_get_security_stats_disabled(self, mock_settings):
        """Test getting security stats when disabled."""
        from lib.security_middleware import SecurityMiddleware

        mock_settings.security_enabled = False
        middleware = SecurityMiddleware(mock_settings)

        stats = middleware.get_security_stats()
        assert stats["security_enabled"] is False


class TestSecurityDecorator:
    """Test cases for security decorator functionality."""

    @pytest.fixture
    def mock_security_middleware(self):
        """Create a mock SecurityMiddleware."""
        middleware = Mock()
        middleware.process_request = AsyncMock()
        return middleware

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP Context."""
        from fastmcp import Context

        context = Mock(spec=Context)
        context.metadata = {"x-api-key": "test-key"}
        return context

    def test_create_security_decorator(self, mock_security_middleware):
        """Test creating a security decorator."""
        from lib.security_middleware import create_security_decorator

        decorator_factory = create_security_decorator(mock_security_middleware)
        assert callable(decorator_factory)

        decorator = decorator_factory(endpoint="/api/test", method="POST")
        assert callable(decorator)

    @pytest.mark.asyncio
    async def test_security_decorator_success(
        self, mock_security_middleware, mock_context
    ):
        """Test security decorator with successful security check."""
        from lib.security_middleware import create_security_decorator

        # Mock successful security check
        mock_security_middleware.process_request.return_value = {
            "security_passed": True,
            "rate_limit_passed": True,
        }

        decorator_factory = create_security_decorator(mock_security_middleware)
        decorator = decorator_factory(endpoint="/api/test", method="POST")

        # Create a test function
        @decorator
        async def test_function(context, data):
            return {"result": "success", "data": data}

        # Call the decorated function
        result = await test_function(mock_context, data={"test": "value"})

        assert result["result"] == "success"
        assert result["data"]["test"] == "value"
        mock_security_middleware.process_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_security_decorator_failure(
        self, mock_security_middleware, mock_context
    ):
        """Test security decorator with failed security check."""
        from lib.security_middleware import create_security_decorator

        # Mock failed security check
        mock_security_middleware.process_request.return_value = {
            "security_passed": False,
            "error": "rate_limit_exceeded",
            "message": "Too many requests",
            "retry_after": 60,
        }

        decorator_factory = create_security_decorator(mock_security_middleware)
        decorator = decorator_factory(endpoint="/api/test", method="POST")

        # Create a test function
        @decorator
        async def test_function(context, data):
            return {"result": "success"}

        # Call the decorated function
        result = await test_function(mock_context, data={"test": "value"})

        # Should return JSON error response
        error_response = json.loads(result)
        assert error_response["error"] is True
        assert error_response["error_type"] == "rate_limit_exceeded"
        assert error_response["message"] == "Too many requests"
        assert error_response["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_security_decorator_no_context(self, mock_security_middleware):
        """Test security decorator when no context is provided."""
        from lib.security_middleware import create_security_decorator

        decorator_factory = create_security_decorator(mock_security_middleware)
        decorator = decorator_factory(endpoint="/api/test", method="POST")

        # Create a test function
        @decorator
        async def test_function(data):
            return {"result": "success", "data": data}

        # Call the decorated function without context
        result = await test_function(data={"test": "value"})

        # Should proceed without security checks
        assert result["result"] == "success"
        mock_security_middleware.process_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_security_decorator_exception_handling(
        self, mock_security_middleware, mock_context
    ):
        """Test security decorator exception handling."""
        from lib.security_middleware import create_security_decorator

        # Mock security processing to raise an exception
        mock_security_middleware.process_request.side_effect = Exception(
            "Security error"
        )

        # Mock audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_security_event = AsyncMock()
        mock_security_middleware.security_manager.audit_logger = mock_audit_logger

        decorator_factory = create_security_decorator(mock_security_middleware)
        decorator = decorator_factory(endpoint="/api/test", method="POST")

        # Create a test function
        @decorator
        async def test_function(context, data):
            return {"result": "success"}

        # Call the decorated function
        result = await test_function(mock_context, data={"test": "value"})

        # Should proceed with original function despite security error
        assert result["result"] == "success"
        mock_audit_logger.log_security_event.assert_called_once()


class TestSecurityHealthCheck:
    """Test cases for SecurityHealthCheck."""

    @pytest.fixture
    def mock_security_middleware(self):
        """Create a mock SecurityMiddleware."""
        middleware = Mock()
        middleware.enabled = True
        middleware.security_config = Mock()
        middleware.security_config.input_validation_enabled = True
        middleware.security_config.audit_logging_enabled = True

        # Mock security manager components
        middleware.security_manager = Mock()
        middleware.security_manager.rate_limiter = Mock()
        middleware.security_manager.rate_limiter.get_stats.return_value = {
            "total_buckets": 10,
            "global_tokens": 50,
        }

        middleware.get_security_headers.return_value = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        }

        return middleware

    @pytest.fixture
    def health_check(self, mock_security_middleware):
        """Create a SecurityHealthCheck instance."""
        from lib.security_middleware import SecurityHealthCheck

        return SecurityHealthCheck(mock_security_middleware)

    @pytest.mark.asyncio
    async def test_security_health_check_healthy(self, health_check):
        """Test security health check when all components are healthy."""
        result = await health_check.check_security_health()

        assert result["security_enabled"] is True
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "checks" in result

        # Check individual component health
        assert result["checks"]["rate_limiter"]["status"] == "healthy"
        assert result["checks"]["input_validator"]["status"] == "healthy"
        assert result["checks"]["audit_logger"]["status"] == "healthy"
        assert result["checks"]["security_headers"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_security_health_check_disabled(self):
        """Test security health check when security is disabled."""
        from lib.security_middleware import SecurityHealthCheck

        mock_middleware = Mock()
        mock_middleware.enabled = False

        health_check = SecurityHealthCheck(mock_middleware)
        result = await health_check.check_security_health()

        assert result["security_enabled"] is False
        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_security_health_check_exception(self, mock_security_middleware):
        """Test security health check when an exception occurs."""
        from lib.security_middleware import SecurityHealthCheck

        # Mock rate limiter to raise an exception
        mock_security_middleware.security_manager.rate_limiter.get_stats.side_effect = (
            Exception("Rate limiter error")
        )

        health_check = SecurityHealthCheck(mock_security_middleware)
        result = await health_check.check_security_health()

        assert result["security_enabled"] is True
        assert result["status"] == "unhealthy"
        assert "error" in result


class TestSecurityMiddlewareGlobals:
    """Test cases for global security middleware functions."""

    def test_initialize_security(self):
        """Test initializing global security middleware."""
        from lib.security_middleware import get_security_middleware, initialize_security

        mock_settings = Mock()
        mock_settings.security_enabled = True
        mock_settings.security_rate_limit_enabled = True
        mock_settings.security_input_validation_enabled = True
        mock_settings.security_headers_enabled = True
        mock_settings.security_cors_enabled = True
        mock_settings.security_audit_logging_enabled = True
        mock_settings.security_cors_allowed_origins = ""

        # Initialize security
        middleware = initialize_security(mock_settings)

        assert middleware is not None
        assert get_security_middleware() is middleware

    def test_security_required_decorator_with_middleware(self):
        """Test security_required decorator when middleware is initialized."""
        from lib.security_middleware import initialize_security, security_required

        mock_settings = Mock()
        mock_settings.security_enabled = True
        mock_settings.security_rate_limit_enabled = True
        mock_settings.security_input_validation_enabled = True
        mock_settings.security_headers_enabled = True
        mock_settings.security_cors_enabled = True
        mock_settings.security_audit_logging_enabled = True
        mock_settings.security_cors_allowed_origins = ""

        # Initialize security
        initialize_security(mock_settings)

        # Create decorated function
        @security_required(endpoint="/api/test", method="POST")
        async def test_function():
            return "success"

        # The function should be wrapped
        assert callable(test_function)

    def test_security_required_decorator_without_middleware(self):
        """Test security_required decorator when middleware is not initialized."""
        # Reset global middleware
        import lib.security_middleware
        from lib.security_middleware import security_required

        lib.security_middleware._security_middleware = None

        # Create decorated function
        @security_required(endpoint="/api/test", method="POST")
        async def test_function():
            return "success"

        # The function should be returned unchanged
        assert callable(test_function)


class TestSecurityMiddlewareIntegration:
    """Integration tests for security middleware."""

    def test_security_middleware_module_structure(self):
        """Test that security middleware module has expected structure."""
        import lib.security_middleware as middleware

        # Verify key classes exist
        assert hasattr(middleware, "SecurityMiddleware")
        assert hasattr(middleware, "SecurityHealthCheck")

        # Verify functions exist
        assert hasattr(middleware, "create_security_decorator")
        assert hasattr(middleware, "initialize_security")
        assert hasattr(middleware, "get_security_middleware")
        assert hasattr(middleware, "security_required")

    @pytest.mark.asyncio
    async def test_end_to_end_security_flow(self):
        """Test complete security flow from initialization to request processing."""
        from lib.security_middleware import SecurityMiddleware

        # Create mock settings
        mock_settings = Mock()
        mock_settings.security_enabled = True
        mock_settings.security_rate_limit_enabled = True
        mock_settings.security_rate_limit_per_user_rpm = 30
        mock_settings.security_rate_limit_per_api_key_rpm = 100
        mock_settings.security_input_validation_enabled = True
        mock_settings.security_max_request_size = 1024
        mock_settings.security_max_string_length = 100
        mock_settings.security_headers_enabled = True
        mock_settings.security_cors_enabled = True
        mock_settings.security_cors_allowed_origins = "https://example.com"
        mock_settings.security_audit_logging_enabled = True
        mock_settings.security_audit_log_sensitive_data = False

        # Create middleware
        middleware = SecurityMiddleware(mock_settings)

        # Create mock context
        mock_context = Mock()
        mock_context.metadata = {"x-api-key": "test-key"}

        # Mock security manager
        with patch.object(
            middleware.security_manager, "check_request_security"
        ) as mock_check:
            mock_check.return_value = {
                "rate_limit_passed": True,
                "validation_passed": True,
                "security_headers": {"X-Frame-Options": "DENY"},
                "audit_logged": True,
            }

            # Process request
            result = await middleware.process_request(
                context=mock_context,
                request_data={"test": "data"},
                endpoint="/api/test",
                method="POST",
            )

            # Verify result
            assert result["security_enabled"] is True
            assert result["security_passed"] is True
            assert result["rate_limit_passed"] is True
            assert result["validation_passed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
