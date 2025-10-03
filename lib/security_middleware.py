#!/usr/bin/env python3
"""
Security Middleware for FastMCP Integration

Provides middleware components to integrate security features
with the FastMCP server and HTTP requests.
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, Optional

from fastmcp import Context

from .security import SecurityConfig, SecurityManager, RateLimitExceeded, ValidationError
from .settings import Settings


class SecurityMiddleware:
    """
    Security middleware for FastMCP server integration.
    
    Provides request-level security checks including rate limiting,
    input validation, and audit logging.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Create security configuration from settings
        self.security_config = SecurityConfig(
            rate_limit_enabled=settings.security_rate_limit_enabled,
            rate_limit_per_user_rpm=settings.security_rate_limit_per_user_rpm,
            rate_limit_per_api_key_rpm=settings.security_rate_limit_per_api_key_rpm,
            input_validation_enabled=settings.security_input_validation_enabled,
            max_request_size=settings.security_max_request_size,
            max_string_length=settings.security_max_string_length,
            security_headers_enabled=settings.security_headers_enabled,
            cors_enabled=settings.security_cors_enabled,
            cors_allowed_origins=settings.security_cors_allowed_origins.split(","),
            audit_logging_enabled=settings.security_audit_logging_enabled,
            audit_log_sensitive_data=settings.security_audit_log_sensitive_data
        )
        
        self.security_manager = SecurityManager(self.security_config)
        self.enabled = settings.security_enabled
    
    async def process_request(
        self,
        context: Context,
        request_data: Any = None,
        endpoint: str = "",
        method: str = "POST"
    ) -> Dict[str, Any]:
        """
        Process incoming request through security checks.
        
        Args:
            context: FastMCP context
            request_data: Request data to validate
            endpoint: API endpoint being accessed
            method: HTTP method
            
        Returns:
            Security processing results
            
        Raises:
            RateLimitExceeded: If rate limits are exceeded
            ValidationError: If input validation fails
        """
        if not self.enabled:
            return {"security_enabled": False}
        
        # Extract client information from context
        client_info = self._extract_client_info(context)
        
        try:
            # Perform comprehensive security check
            security_result = await self.security_manager.check_request_security(
                request_data=request_data,
                identifier=client_info["identifier"],
                identifier_type=client_info["identifier_type"],
                api_key=client_info.get("api_key"),
                endpoint=endpoint,
                method=method
            )
            
            return {
                "security_enabled": True,
                "security_passed": True,
                **security_result
            }
            
        except RateLimitExceeded as e:
            # Log rate limit exceeded
            await self.security_manager.audit_logger.log_rate_limit_exceeded(
                identifier=client_info["identifier"],
                identifier_type=client_info["identifier_type"],
                limit_type="api_request",
                ip_address=client_info.get("ip_address")
            )
            
            return {
                "security_enabled": True,
                "security_passed": False,
                "error": "rate_limit_exceeded",
                "message": str(e),
                "retry_after": e.retry_after
            }
            
        except ValidationError as e:
            # Log validation error
            await self.security_manager.audit_logger.log_validation_error(
                field=e.field or "unknown",
                error_type="input_validation",
                ip_address=client_info.get("ip_address"),
                user_id=client_info.get("user_id")
            )
            
            return {
                "security_enabled": True,
                "security_passed": False,
                "error": "validation_error",
                "message": str(e),
                "field": e.field
            }
    
    def _extract_client_info(self, context: Context) -> Dict[str, Any]:
        """
        Extract client information from FastMCP context.
        
        Args:
            context: FastMCP context
            
        Returns:
            Dictionary with client information
        """
        # In a real implementation, this would extract actual client info
        # from the context, headers, or connection metadata
        
        # For now, use a placeholder implementation
        client_info = {
            "identifier": "unknown_client",
            "identifier_type": "client_id",
            "ip_address": "127.0.0.1",
            "user_agent": "FastMCP-Client/1.0"
        }
        
        # Try to extract API key from context metadata if available
        if hasattr(context, 'metadata') and context.metadata:
            api_key = context.metadata.get('x-api-key') or context.metadata.get('authorization')
            if api_key:
                client_info["api_key"] = api_key
                client_info["identifier"] = api_key[:16]  # Use API key prefix as identifier
                client_info["identifier_type"] = "api_key"
        
        return client_info
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers to add to responses."""
        if not self.enabled:
            return {}
        
        return self.security_manager.security_headers.get_security_headers()
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        if not self.enabled:
            return {"security_enabled": False}
        
        return {
            "security_enabled": True,
            **self.security_manager.get_security_stats()
        }


def create_security_decorator(security_middleware: SecurityMiddleware):
    """
    Create a decorator for FastMCP tools to add security checks.
    
    Args:
        security_middleware: Security middleware instance
        
    Returns:
        Decorator function
    """
    def security_decorator(endpoint: str = "", method: str = "POST"):
        """
        Decorator to add security checks to FastMCP tools.
        
        Args:
            endpoint: API endpoint name
            method: HTTP method
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                # Extract context from arguments
                context = None
                for arg in args:
                    if isinstance(arg, Context):
                        context = arg
                        break
                
                if context is None:
                    # No context found, proceed without security checks
                    return await func(*args, **kwargs)
                
                # Extract request data from kwargs
                request_data = {k: v for k, v in kwargs.items() if not k.startswith('_')}
                
                # Process security checks
                try:
                    security_result = await security_middleware.process_request(
                        context=context,
                        request_data=request_data,
                        endpoint=endpoint or func.__name__,
                        method=method
                    )
                    
                    if not security_result.get("security_passed", True):
                        # Security check failed, return error response
                        error_response = {
                            "error": True,
                            "error_type": security_result.get("error", "security_error"),
                            "message": security_result.get("message", "Security check failed"),
                            "timestamp": time.time()
                        }
                        
                        if "retry_after" in security_result:
                            error_response["retry_after"] = security_result["retry_after"]
                        
                        if "field" in security_result:
                            error_response["field"] = security_result["field"]
                        
                        return json.dumps(error_response)
                    
                    # Security checks passed, proceed with original function
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    # Log security processing error
                    await security_middleware.security_manager.audit_logger.log_security_event(
                        event_type="security_processing_error",
                        severity="error",
                        message=f"Error in security processing: {str(e)}",
                        details={"function": func.__name__, "endpoint": endpoint}
                    )
                    
                    # Proceed with original function if security processing fails
                    return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    return security_decorator


class SecurityHealthCheck:
    """Security-focused health check component."""
    
    def __init__(self, security_middleware: SecurityMiddleware):
        self.security_middleware = security_middleware
    
    async def check_security_health(self) -> Dict[str, Any]:
        """
        Perform security-focused health checks.
        
        Returns:
            Dictionary with security health status
        """
        health_status = {
            "security_enabled": self.security_middleware.enabled,
            "timestamp": time.time(),
            "checks": {}
        }
        
        if not self.security_middleware.enabled:
            health_status["status"] = "disabled"
            return health_status
        
        try:
            # Check rate limiter health
            rate_limiter_stats = self.security_middleware.security_manager.rate_limiter.get_stats()
            health_status["checks"]["rate_limiter"] = {
                "status": "healthy",
                "active_buckets": rate_limiter_stats["total_buckets"],
                "global_tokens": rate_limiter_stats["global_tokens"]
            }
            
            # Check input validator health
            health_status["checks"]["input_validator"] = {
                "status": "healthy",
                "validation_enabled": self.security_middleware.security_config.input_validation_enabled
            }
            
            # Check audit logger health
            health_status["checks"]["audit_logger"] = {
                "status": "healthy",
                "logging_enabled": self.security_middleware.security_config.audit_logging_enabled
            }
            
            # Check security headers
            headers = self.security_middleware.get_security_headers()
            health_status["checks"]["security_headers"] = {
                "status": "healthy",
                "headers_count": len(headers),
                "headers_enabled": bool(headers)
            }
            
            # Overall status
            all_healthy = all(
                check["status"] == "healthy" 
                for check in health_status["checks"].values()
            )
            health_status["status"] = "healthy" if all_healthy else "degraded"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


# Global security middleware instance
_security_middleware: Optional[SecurityMiddleware] = None


def initialize_security(settings: Settings) -> SecurityMiddleware:
    """
    Initialize global security middleware.
    
    Args:
        settings: Application settings
        
    Returns:
        Security middleware instance
    """
    global _security_middleware
    _security_middleware = SecurityMiddleware(settings)
    return _security_middleware


def get_security_middleware() -> Optional[SecurityMiddleware]:
    """Get the global security middleware instance."""
    return _security_middleware


def security_required(endpoint: str = "", method: str = "POST"):
    """
    Decorator for FastMCP tools that require security checks.
    
    Args:
        endpoint: API endpoint name
        method: HTTP method
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        if _security_middleware is None:
            # Security not initialized, return original function
            return func
        
        security_decorator = create_security_decorator(_security_middleware)
        return security_decorator(endpoint, method)(func)
    
    return decorator
