#!/usr/bin/env python3
"""
Tests for Security Module
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from lib.security import (
    AdvancedRateLimiter,
    AuditLogger,
    InputValidator,
    RateLimitExceeded,
    SecurityConfig,
    SecurityHeaders,
    SecurityManager,
    TokenBucket,
    ValidationError
)


class TestTokenBucket:
    """Test token bucket implementation."""

    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(rate_per_minute=60, burst_size=10)
        
        assert bucket.rate_per_second == 1.0
        assert bucket.burst_size == 10
        assert bucket.tokens == 10.0

    def test_token_bucket_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(rate_per_minute=60, burst_size=10)
        
        # Should be able to consume tokens
        assert bucket.consume(1) is True
        assert abs(bucket.tokens - 9.0) < 0.1  # Allow for small floating point differences
        
        # Consume multiple tokens
        assert bucket.consume(5) is True
        assert abs(bucket.tokens - 4.0) < 0.1  # Allow for small floating point differences

    def test_token_bucket_consume_failure(self):
        """Test token consumption failure when insufficient tokens."""
        bucket = TokenBucket(rate_per_minute=60, burst_size=5)
        
        # Consume all tokens
        assert bucket.consume(5) is True
        assert bucket.tokens < 0.1  # Should be close to 0
        
        # Should fail to consume more
        assert bucket.consume(1) is False
        assert bucket.tokens < 0.1  # Should still be close to 0

    def test_token_bucket_refill(self):
        """Test token bucket refill over time."""
        bucket = TokenBucket(rate_per_minute=60, burst_size=10)
        
        # Consume all tokens
        bucket.consume(10)
        initial_tokens = bucket.tokens
        
        # Simulate time passage (1 second = 1 token at 60/min rate)
        bucket.last_refill -= 1.0
        bucket._refill()
        
        # Should have approximately 1 more token than before
        assert bucket.tokens > initial_tokens
        assert abs(bucket.tokens - 1.0) < 0.1  # Should be close to 1.0


class TestAdvancedRateLimiter:
    """Test advanced rate limiter."""

    @pytest.fixture
    def config(self):
        """Create test security config."""
        return SecurityConfig(
            rate_limit_requests_per_minute=60,
            rate_limit_burst_size=10,
            rate_limit_per_user_rpm=30,
            rate_limit_per_api_key_rpm=100
        )

    @pytest.fixture
    def rate_limiter(self, config):
        """Create rate limiter instance."""
        return AdvancedRateLimiter(config)

    @pytest.mark.asyncio
    async def test_rate_limiter_success(self, rate_limiter):
        """Test successful rate limit check."""
        result = await rate_limiter.check_rate_limit("user1", "user_id")
        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limiter_user_limit_exceeded(self, rate_limiter):
        """Test user rate limit exceeded."""
        # Exhaust user bucket (30 requests per minute = 0.5 per second)
        user_bucket = rate_limiter.user_buckets.get("user1")
        if user_bucket is None:
            # First request creates the bucket
            await rate_limiter.check_rate_limit("user1", "user_id")
            user_bucket = rate_limiter.user_buckets["user1"]
        
        # Consume all tokens
        user_bucket.tokens = 0
        
        with pytest.raises(RateLimitExceeded) as exc_info:
            await rate_limiter.check_rate_limit("user1", "user_id")
        
        assert "Rate limit exceeded for user_id: user1" in str(exc_info.value)
        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_rate_limiter_api_key_limit(self, rate_limiter):
        """Test API key rate limiting."""
        api_key = "test_api_key_123"
        
        # Should succeed initially
        result = await rate_limiter.check_rate_limit("user1", "user_id", api_key=api_key)
        assert result is True
        
        # Verify API key bucket was created
        assert api_key in rate_limiter.api_key_buckets

    @pytest.mark.asyncio
    async def test_rate_limiter_cleanup(self, rate_limiter):
        """Test cleanup of expired buckets."""
        # Create some buckets
        await rate_limiter.check_rate_limit("user1", "user_id")
        await rate_limiter.check_rate_limit("user2", "user_id", api_key="key1")
        
        # Simulate old buckets
        for bucket in rate_limiter.user_buckets.values():
            bucket.last_refill = time.time() - 7200  # 2 hours ago
        
        for bucket in rate_limiter.api_key_buckets.values():
            bucket.last_refill = time.time() - 7200  # 2 hours ago
        
        # Force cleanup
        await rate_limiter._cleanup_expired_buckets()
        
        # Buckets should be cleaned up
        assert len(rate_limiter.user_buckets) == 0
        assert len(rate_limiter.api_key_buckets) == 0

    def test_rate_limiter_stats(self, rate_limiter):
        """Test rate limiter statistics."""
        stats = rate_limiter.get_stats()
        
        assert "global_tokens" in stats
        assert "active_users" in stats
        assert "active_api_keys" in stats
        assert "total_buckets" in stats
        assert stats["total_buckets"] >= 1  # At least global bucket


class TestInputValidator:
    """Test input validator."""

    @pytest.fixture
    def config(self):
        """Create test security config."""
        return SecurityConfig(
            input_validation_enabled=True,
            max_string_length=100
        )

    @pytest.fixture
    def validator(self, config):
        """Create input validator instance."""
        return InputValidator(config)

    def test_validate_safe_string(self, validator):
        """Test validation of safe string input."""
        safe_string = "This is a safe string with normal content"
        result = validator.validate_input(safe_string, "test_field")
        assert result == safe_string

    def test_validate_sql_injection_detection(self, validator):
        """Test SQL injection detection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "UNION SELECT * FROM passwords",
            "admin'--",
            "1; DELETE FROM users"
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_input(malicious_input, "test_field")
            
            assert "SQL injection" in str(exc_info.value)
            assert exc_info.value.field == "test_field"

    def test_validate_xss_detection(self, validator):
        """Test XSS attack detection."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<object data='javascript:alert(1)'></object>"
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_input(malicious_input, "test_field")
            
            assert "XSS attack" in str(exc_info.value)

    def test_validate_path_traversal_detection(self, validator):
        """Test path traversal detection."""
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd"
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                validator.validate_input(malicious_input, "test_field")
            
            assert "path traversal" in str(exc_info.value)

    def test_validate_string_length_limit(self, validator):
        """Test string length validation."""
        long_string = "a" * 101  # Exceeds max_string_length of 100
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_input(long_string, "test_field")
        
        assert "String too long" in str(exc_info.value)
        assert exc_info.value.field == "test_field"

    def test_validate_dict_input(self, validator):
        """Test dictionary input validation."""
        test_dict = {
            "safe_key": "safe_value",
            "another_key": "another_safe_value"
        }
        
        result = validator.validate_input(test_dict, "test_dict")
        assert result == test_dict

    def test_validate_list_input(self, validator):
        """Test list input validation."""
        test_list = ["safe_item1", "safe_item2", "safe_item3"]
        
        result = validator.validate_input(test_list, "test_list")
        assert result == test_list

    def test_validate_file_extension(self, validator):
        """Test file extension validation."""
        # Valid extensions
        assert validator.validate_file_extension("document.json") is True
        assert validator.validate_file_extension("data.txt") is True
        assert validator.validate_file_extension("report.csv") is True
        
        # Invalid extensions
        assert validator.validate_file_extension("script.exe") is False
        assert validator.validate_file_extension("malware.bat") is False
        assert validator.validate_file_extension("") is False

    def test_sanitize_for_logging(self, validator):
        """Test data sanitization for logging."""
        sensitive_data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "abc123xyz",
            "token": "bearer_token_here",
            "normal_field": "normal_value"
        }
        
        sanitized = validator.sanitize_for_logging(sensitive_data)
        
        assert sanitized["username"] == "testuser"
        assert sanitized["password"] == "***"
        assert sanitized["api_key"] == "***"
        assert sanitized["token"] == "***"
        assert sanitized["normal_field"] == "normal_value"

    def test_validation_disabled(self):
        """Test behavior when validation is disabled."""
        config = SecurityConfig(input_validation_enabled=False)
        validator = InputValidator(config)
        
        malicious_input = "'; DROP TABLE users; --"
        result = validator.validate_input(malicious_input, "test_field")
        
        # Should return input unchanged when validation is disabled
        assert result == malicious_input


class TestSecurityHeaders:
    """Test security headers."""

    @pytest.fixture
    def config(self):
        """Create test security config."""
        return SecurityConfig(
            security_headers_enabled=True,
            cors_enabled=True,
            cors_allowed_origins=["https://example.com", "https://app.example.com"],
            cors_allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )

    @pytest.fixture
    def security_headers(self, config):
        """Create security headers instance."""
        return SecurityHeaders(config)

    def test_get_security_headers(self, security_headers):
        """Test getting security headers."""
        headers = security_headers.get_security_headers()
        
        # Check essential security headers
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in headers
        assert "Strict-Transport-Security" in headers
        
        # Check CORS headers
        assert "Access-Control-Allow-Origin" in headers
        assert "Access-Control-Allow-Methods" in headers
        assert "Access-Control-Allow-Headers" in headers

    def test_security_headers_disabled(self):
        """Test behavior when security headers are disabled."""
        config = SecurityConfig(security_headers_enabled=False)
        security_headers = SecurityHeaders(config)
        
        headers = security_headers.get_security_headers()
        assert headers == {}

    def test_cors_disabled(self):
        """Test behavior when CORS is disabled."""
        config = SecurityConfig(
            security_headers_enabled=True,
            cors_enabled=False
        )
        security_headers = SecurityHeaders(config)
        
        headers = security_headers.get_security_headers()
        
        # Should have security headers but no CORS headers
        assert "X-Frame-Options" in headers
        assert "Access-Control-Allow-Origin" not in headers


class TestAuditLogger:
    """Test audit logger."""

    @pytest.fixture
    def config(self):
        """Create test security config."""
        return SecurityConfig(
            audit_logging_enabled=True,
            audit_log_sensitive_data=False
        )

    @pytest.fixture
    def audit_logger(self, config):
        """Create audit logger instance."""
        return AuditLogger(config)

    @pytest.mark.asyncio
    async def test_log_security_event(self, audit_logger):
        """Test logging security events."""
        with patch('builtins.print') as mock_print:
            await audit_logger.log_security_event(
                event_type="test_event",
                severity="warning",
                message="Test security event",
                details={"test": "data"},
                user_id="user123",
                ip_address="192.168.1.1"
            )
            
            # Verify print was called (in real implementation, this would write to log file)
            mock_print.assert_called_once()
            logged_data = mock_print.call_args[0][0]
            assert "AUDIT:" in logged_data
            assert "test_event" in logged_data

    @pytest.mark.asyncio
    async def test_log_api_access(self, audit_logger):
        """Test logging API access."""
        with patch('builtins.print') as mock_print:
            await audit_logger.log_api_access(
                method="POST",
                endpoint="/api/test",
                status_code=200,
                response_time=0.123,
                user_id="user123",
                ip_address="192.168.1.1",
                api_key="test_key_123"
            )
            
            mock_print.assert_called_once()
            logged_data = mock_print.call_args[0][0]
            assert "ACCESS:" in logged_data
            assert "POST" in logged_data
            assert "/api/test" in logged_data

    @pytest.mark.asyncio
    async def test_log_rate_limit_exceeded(self, audit_logger):
        """Test logging rate limit exceeded events."""
        with patch.object(audit_logger, 'log_security_event') as mock_log:
            await audit_logger.log_rate_limit_exceeded(
                identifier="user123",
                identifier_type="user_id",
                limit_type="api_request",
                ip_address="192.168.1.1"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "rate_limit_exceeded"
            assert call_args[1]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_log_validation_error(self, audit_logger):
        """Test logging validation errors."""
        with patch.object(audit_logger, 'log_security_event') as mock_log:
            await audit_logger.log_validation_error(
                field="test_field",
                error_type="sql_injection",
                ip_address="192.168.1.1",
                user_id="user123"
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "validation_error"
            assert call_args[1]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_logging_disabled(self):
        """Test behavior when logging is disabled."""
        config = SecurityConfig(audit_logging_enabled=False)
        audit_logger = AuditLogger(config)
        
        with patch('builtins.print') as mock_print:
            await audit_logger.log_security_event(
                event_type="test_event",
                severity="info",
                message="Test message"
            )
            
            # Should not print anything when logging is disabled
            mock_print.assert_not_called()


class TestSecurityManager:
    """Test security manager integration."""

    @pytest.fixture
    def config(self):
        """Create test security config."""
        return SecurityConfig(
            rate_limit_enabled=True,
            input_validation_enabled=True,
            security_headers_enabled=True,
            audit_logging_enabled=True
        )

    @pytest.fixture
    def security_manager(self, config):
        """Create security manager instance."""
        return SecurityManager(config)

    @pytest.mark.asyncio
    async def test_check_request_security_success(self, security_manager):
        """Test successful security check."""
        request_data = {"safe_field": "safe_value"}
        
        with patch('builtins.print'):  # Mock audit logging
            result = await security_manager.check_request_security(
                request_data=request_data,
                identifier="user123",
                identifier_type="user_id",
                endpoint="/api/test",
                method="POST"
            )
        
        assert result["rate_limit_passed"] is True
        assert result["validation_passed"] is True
        assert "security_headers" in result
        assert result["audit_logged"] is True

    @pytest.mark.asyncio
    async def test_check_request_security_rate_limit_exceeded(self, security_manager):
        """Test security check with rate limit exceeded."""
        # Exhaust rate limit
        user_bucket = TokenBucket(1, 1)  # Very low limits
        user_bucket.tokens = 0
        security_manager.rate_limiter.user_buckets["user123"] = user_bucket
        
        with pytest.raises(RateLimitExceeded):
            await security_manager.check_request_security(
                request_data=None,
                identifier="user123",
                identifier_type="user_id"
            )

    @pytest.mark.asyncio
    async def test_check_request_security_validation_error(self, security_manager):
        """Test security check with validation error."""
        malicious_data = {"field": "'; DROP TABLE users; --"}
        
        with pytest.raises(ValidationError):
            await security_manager.check_request_security(
                request_data=malicious_data,
                identifier="user123",
                identifier_type="user_id"
            )

    def test_get_security_stats(self, security_manager):
        """Test getting security statistics."""
        stats = security_manager.get_security_stats()
        
        assert "rate_limiter" in stats
        assert "config" in stats
        assert stats["config"]["rate_limiting_enabled"] is True
        assert stats["config"]["input_validation_enabled"] is True
