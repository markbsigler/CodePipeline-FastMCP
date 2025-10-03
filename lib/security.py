#!/usr/bin/env python3
"""
Security Module

Provides comprehensive security features including rate limiting,
input validation, security headers, and audit logging.
"""

import asyncio
import hashlib
import json
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, validator


class SecurityConfig(BaseModel):
    """Security configuration settings."""
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=60, description="Global requests per minute")
    rate_limit_burst_size: int = Field(default=10, description="Burst size for rate limiting")
    rate_limit_per_user_rpm: int = Field(default=30, description="Per-user requests per minute")
    rate_limit_per_api_key_rpm: int = Field(default=100, description="Per-API key requests per minute")
    
    # Input validation
    input_validation_enabled: bool = Field(default=True, description="Enable input validation")
    max_request_size: int = Field(default=1024 * 1024, description="Maximum request size in bytes")
    max_string_length: int = Field(default=1000, description="Maximum string field length")
    allowed_file_extensions: List[str] = Field(default=[".json", ".txt", ".csv"], description="Allowed file extensions")
    
    # Security headers
    security_headers_enabled: bool = Field(default=True, description="Enable security headers")
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_allowed_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    cors_allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE"], description="CORS allowed methods")
    
    # Audit logging
    audit_logging_enabled: bool = Field(default=True, description="Enable audit logging")
    audit_log_sensitive_data: bool = Field(default=False, description="Log sensitive data in audit logs")
    audit_log_retention_days: int = Field(default=90, description="Audit log retention in days")


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(Exception):
    """Exception raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class AdvancedRateLimiter:
    """
    Advanced rate limiter with per-user and per-API key limits.
    
    Features:
    - Global, per-user, and per-API key rate limiting
    - Token bucket algorithm with burst support
    - Sliding window for accurate rate calculation
    - Automatic cleanup of expired entries
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.global_bucket = TokenBucket(
            config.rate_limit_requests_per_minute,
            config.rate_limit_burst_size
        )
        self.user_buckets: Dict[str, TokenBucket] = {}
        self.api_key_buckets: Dict[str, TokenBucket] = {}
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(
        self,
        identifier: str,
        identifier_type: str = "ip",
        api_key: Optional[str] = None
    ) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: User identifier (IP, user ID, etc.)
            identifier_type: Type of identifier (ip, user_id, etc.)
            api_key: API key if provided
            
        Returns:
            True if within limits, False otherwise
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        async with self._lock:
            current_time = time.time()
            
            # Cleanup expired buckets periodically
            if current_time - self.last_cleanup > self.cleanup_interval:
                await self._cleanup_expired_buckets()
                self.last_cleanup = current_time
            
            # Check global rate limit
            if not self.global_bucket.consume():
                raise RateLimitExceeded(
                    "Global rate limit exceeded",
                    retry_after=60
                )
            
            # Check per-user rate limit
            if identifier not in self.user_buckets:
                self.user_buckets[identifier] = TokenBucket(
                    self.config.rate_limit_per_user_rpm,
                    min(self.config.rate_limit_burst_size, 5)
                )
            
            if not self.user_buckets[identifier].consume():
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {identifier_type}: {identifier}",
                    retry_after=60
                )
            
            # Check per-API key rate limit if API key provided
            if api_key:
                if api_key not in self.api_key_buckets:
                    self.api_key_buckets[api_key] = TokenBucket(
                        self.config.rate_limit_per_api_key_rpm,
                        min(self.config.rate_limit_burst_size * 2, 20)
                    )
                
                if not self.api_key_buckets[api_key].consume():
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for API key: {api_key[:8]}...",
                        retry_after=60
                    )
            
            return True
    
    async def _cleanup_expired_buckets(self):
        """Remove expired token buckets to prevent memory leaks."""
        current_time = time.time()
        
        # Clean user buckets
        expired_users = [
            user for user, bucket in self.user_buckets.items()
            if current_time - bucket.last_refill > 3600  # 1 hour
        ]
        for user in expired_users:
            del self.user_buckets[user]
        
        # Clean API key buckets
        expired_keys = [
            key for key, bucket in self.api_key_buckets.items()
            if current_time - bucket.last_refill > 3600  # 1 hour
        ]
        for key in expired_keys:
            del self.api_key_buckets[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "global_tokens": self.global_bucket.tokens,
            "active_users": len(self.user_buckets),
            "active_api_keys": len(self.api_key_buckets),
            "total_buckets": 1 + len(self.user_buckets) + len(self.api_key_buckets)
        }


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, rate_per_minute: int, burst_size: int):
        self.rate_per_second = rate_per_minute / 60.0
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from the bucket."""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.burst_size,
            self.tokens + elapsed * self.rate_per_second
        )
        self.last_refill = now


class InputValidator:
    """
    Comprehensive input validation with security focus.
    
    Features:
    - SQL injection prevention
    - XSS prevention
    - Path traversal prevention
    - Size limits and format validation
    - Custom validation rules
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        
        # Dangerous patterns to detect
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>"
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c"
        ]
        
        # Compile patterns for performance
        self.sql_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.sql_injection_patterns]
        self.xss_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.xss_patterns]
        self.path_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.path_traversal_patterns]
    
    def validate_input(self, data: Any, field_name: str = "input") -> Any:
        """
        Validate input data for security issues.
        
        Args:
            data: Input data to validate
            field_name: Name of the field being validated
            
        Returns:
            Validated and sanitized data
            
        Raises:
            ValidationError: If validation fails
        """
        if not self.config.input_validation_enabled:
            return data
        
        if isinstance(data, str):
            return self._validate_string(data, field_name)
        elif isinstance(data, dict):
            return self._validate_dict(data, field_name)
        elif isinstance(data, list):
            return self._validate_list(data, field_name)
        else:
            return data
    
    def _validate_string(self, value: str, field_name: str) -> str:
        """Validate string input."""
        # Check length
        if len(value) > self.config.max_string_length:
            raise ValidationError(
                f"String too long: {len(value)} > {self.config.max_string_length}",
                field=field_name,
                value=value[:100] + "..." if len(value) > 100 else value
            )
        
        # Check for SQL injection
        for pattern in self.sql_regex:
            if pattern.search(value):
                raise ValidationError(
                    f"Potential SQL injection detected in {field_name}",
                    field=field_name,
                    value=value[:100] + "..." if len(value) > 100 else value
                )
        
        # Check for XSS
        for pattern in self.xss_regex:
            if pattern.search(value):
                raise ValidationError(
                    f"Potential XSS attack detected in {field_name}",
                    field=field_name,
                    value=value[:100] + "..." if len(value) > 100 else value
                )
        
        # Check for path traversal
        for pattern in self.path_regex:
            if pattern.search(value):
                raise ValidationError(
                    f"Potential path traversal detected in {field_name}",
                    field=field_name,
                    value=value[:100] + "..." if len(value) > 100 else value
                )
        
        return value
    
    def _validate_dict(self, data: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Validate dictionary input."""
        validated = {}
        for key, value in data.items():
            validated_key = self._validate_string(str(key), f"{field_name}.key")
            validated_value = self.validate_input(value, f"{field_name}.{key}")
            validated[validated_key] = validated_value
        return validated
    
    def _validate_list(self, data: List[Any], field_name: str) -> List[Any]:
        """Validate list input."""
        return [
            self.validate_input(item, f"{field_name}[{i}]")
            for i, item in enumerate(data)
        ]
    
    def validate_file_extension(self, filename: str) -> bool:
        """Validate file extension."""
        if not filename:
            return False
        
        extension = "." + filename.split(".")[-1].lower()
        return extension in self.config.allowed_file_extensions
    
    def sanitize_for_logging(self, data: Any) -> Any:
        """Sanitize data for safe logging."""
        if isinstance(data, str):
            # Remove potential sensitive patterns
            sanitized = re.sub(r'(password|token|key|secret)=[^&\s]*', r'\1=***', data, flags=re.IGNORECASE)
            return sanitized[:200] + "..." if len(sanitized) > 200 else sanitized
        elif isinstance(data, dict):
            return {
                key: "***" if any(sensitive in key.lower() for sensitive in ["password", "token", "key", "secret"])
                else self.sanitize_for_logging(value)
                for key, value in data.items()
            }
        return data


class SecurityHeaders:
    """Security headers management."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers to add to responses."""
        if not self.config.security_headers_enabled:
            return {}
        
        headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "media-src 'self'; "
                "frame-src 'none';"
            ),
            
            # HSTS (if HTTPS)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Permissions policy
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            )
        }
        
        # CORS headers
        if self.config.cors_enabled:
            headers.update({
                "Access-Control-Allow-Origin": ", ".join(self.config.cors_allowed_origins),
                "Access-Control-Allow-Methods": ", ".join(self.config.cors_allowed_methods),
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                "Access-Control-Max-Age": "86400"
            })
        
        return headers


class AuditLogger:
    """
    Audit logging for security events and API access.
    
    Features:
    - Structured logging with JSON format
    - Sensitive data filtering
    - Event categorization
    - Retention management
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.validator = InputValidator(config)
    
    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log a security event."""
        if not self.config.audit_logging_enabled:
            return
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": self.validator.sanitize_for_logging(details) if details else None
        }
        
        # In a real implementation, this would write to a secure log file or service
        print(f"AUDIT: {json.dumps(event, default=str)}")
    
    async def log_api_access(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        api_key: Optional[str] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None
    ):
        """Log API access."""
        if not self.config.audit_logging_enabled:
            return
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "api_access",
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": round(response_time * 1000, 2),
            "user_id": user_id,
            "ip_address": ip_address,
            "api_key": api_key[:8] + "..." if api_key else None,
            "request_size": request_size,
            "response_size": response_size
        }
        
        # In a real implementation, this would write to a secure log file or service
        print(f"ACCESS: {json.dumps(event, default=str)}")
    
    async def log_rate_limit_exceeded(
        self,
        identifier: str,
        identifier_type: str,
        limit_type: str,
        ip_address: Optional[str] = None
    ):
        """Log rate limit exceeded event."""
        await self.log_security_event(
            event_type="rate_limit_exceeded",
            severity="warning",
            message=f"Rate limit exceeded for {identifier_type}: {identifier}",
            details={
                "identifier": identifier,
                "identifier_type": identifier_type,
                "limit_type": limit_type
            },
            ip_address=ip_address
        )
    
    async def log_validation_error(
        self,
        field: str,
        error_type: str,
        ip_address: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Log input validation error."""
        await self.log_security_event(
            event_type="validation_error",
            severity="warning",
            message=f"Input validation failed for field: {field}",
            details={
                "field": field,
                "error_type": error_type
            },
            user_id=user_id,
            ip_address=ip_address
        )


class SecurityManager:
    """
    Central security manager that coordinates all security features.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.rate_limiter = AdvancedRateLimiter(config)
        self.input_validator = InputValidator(config)
        self.security_headers = SecurityHeaders(config)
        self.audit_logger = AuditLogger(config)
    
    async def check_request_security(
        self,
        request_data: Any,
        identifier: str,
        identifier_type: str = "ip",
        api_key: Optional[str] = None,
        endpoint: str = "",
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Comprehensive security check for incoming requests.
        
        Returns:
            Dictionary with security check results and metadata
        """
        start_time = time.time()
        security_info = {
            "rate_limit_passed": False,
            "validation_passed": False,
            "security_headers": {},
            "audit_logged": False
        }
        
        try:
            # Rate limiting check
            await self.rate_limiter.check_rate_limit(identifier, identifier_type, api_key)
            security_info["rate_limit_passed"] = True
            
            # Input validation
            if request_data is not None:
                validated_data = self.input_validator.validate_input(request_data, "request")
                security_info["validation_passed"] = True
                security_info["validated_data"] = validated_data
            else:
                security_info["validation_passed"] = True
            
            # Security headers
            security_info["security_headers"] = self.security_headers.get_security_headers()
            
            # Audit logging for successful request
            await self.audit_logger.log_api_access(
                method=method,
                endpoint=endpoint,
                status_code=200,
                response_time=time.time() - start_time,
                user_id=identifier if identifier_type == "user_id" else None,
                ip_address=identifier if identifier_type == "ip" else None,
                api_key=api_key
            )
            security_info["audit_logged"] = True
            
            return security_info
            
        except RateLimitExceeded as e:
            await self.audit_logger.log_rate_limit_exceeded(
                identifier=identifier,
                identifier_type=identifier_type,
                limit_type="request_rate",
                ip_address=identifier if identifier_type == "ip" else None
            )
            raise e
            
        except ValidationError as e:
            await self.audit_logger.log_validation_error(
                field=e.field or "unknown",
                error_type=type(e).__name__,
                ip_address=identifier if identifier_type == "ip" else None,
                user_id=identifier if identifier_type == "user_id" else None
            )
            raise e
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics."""
        return {
            "rate_limiter": self.rate_limiter.get_stats(),
            "config": {
                "rate_limiting_enabled": self.config.rate_limit_enabled,
                "input_validation_enabled": self.config.input_validation_enabled,
                "security_headers_enabled": self.config.security_headers_enabled,
                "audit_logging_enabled": self.config.audit_logging_enabled
            }
        }
