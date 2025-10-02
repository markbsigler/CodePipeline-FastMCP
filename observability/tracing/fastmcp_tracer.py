#!/usr/bin/env python3
"""
OpenTelemetry Tracing Utilities for FastMCP Server

This module provides tracing utilities for FastMCP operations, BMC API calls,
and user elicitation workflows.
"""

import time
import logging
import functools
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Callable, Union
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.propagate import inject, extract
from fastmcp import Context
from fastmcp.server.elicitation import AcceptedElicitation, DeclinedElicitation, CancelledElicitation
from ..config.otel_config import get_tracer, is_tracing_enabled

logger = logging.getLogger(__name__)


class FastMCPTracer:
    """FastMCP-specific tracing utilities."""
    
    def __init__(self, tracer: Optional[trace.Tracer] = None):
        """Initialize FastMCP tracer."""
        self.tracer = tracer or get_tracer()
        self.enabled = is_tracing_enabled() and self.tracer is not None
        
        if not self.enabled:
            logger.info("FastMCP tracing disabled or tracer not available")
    
    @asynccontextmanager
    async def trace_mcp_request(self, operation: str, tool_name: str, 
                               arguments: Dict[str, Any], ctx: Optional[Context] = None):
        """Trace an MCP request operation."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"mcp.{operation}"
        attributes = {
            "mcp.operation": operation,
            "mcp.tool_name": tool_name,
            "mcp.arguments_count": len(arguments),
            "service.name": "fastmcp-server",
            "component": "mcp-server"
        }
        
        # Add context information if available
        if ctx:
            attributes["mcp.context.present"] = True
            # Add any relevant context attributes here
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                # Add argument details (sanitized for privacy)
                for key, value in arguments.items():
                    if key.lower() not in ["password", "token", "secret", "key", "auth"]:
                        # Truncate long values
                        str_value = str(value)[:100] if len(str(value)) > 100 else str(value)
                        span.set_attribute(f"mcp.arg.{key}", str_value)
                
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                raise
    
    @asynccontextmanager
    async def trace_bmc_api_call(self, operation: str, endpoint: str, method: str = "GET"):
        """Trace BMC API calls."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"bmc.api.{operation}"
        attributes = {
            "http.method": method,
            "http.url": endpoint,
            "bmc.operation": operation,
            "component": "bmc-api-client",
            "span.kind": "client"
        }
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            start_time = time.time()
            try:
                yield span
                
                duration = time.time() - start_time
                span.set_attribute("http.duration", duration)
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                duration = time.time() - start_time
                span.set_attribute("http.duration", duration)
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                
                # Add HTTP-specific error attributes
                if hasattr(e, 'response'):
                    span.set_attribute("http.status_code", getattr(e.response, 'status_code', 'unknown'))
                
                raise
    
    @asynccontextmanager
    async def trace_cache_operation(self, operation: str, key: str, key_type: Optional[str] = None):
        """Trace cache operations."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"cache.{operation}"
        attributes = {
            "cache.operation": operation,
            "cache.key": key[:50],  # Truncate long keys
            "component": "intelligent-cache"
        }
        
        if key_type:
            attributes["cache.key_type"] = key_type
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                raise
    
    @asynccontextmanager
    async def trace_auth_operation(self, provider: str, operation: str):
        """Trace authentication operations."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"auth.{operation}"
        attributes = {
            "auth.provider": provider,
            "auth.operation": operation,
            "component": "authentication"
        }
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("auth.success", False)
                raise
            else:
                span.set_attribute("auth.success", True)
    
    def trace_function(self, span_name: Optional[str] = None, 
                      attributes: Optional[Dict[str, Any]] = None):
        """Decorator for tracing functions."""
        def decorator(func: Callable):
            if not self.enabled:
                return func
                
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                name = span_name or f"{func.__module__}.{func.__name__}"
                span_attributes = {
                    "function.name": func.__name__,
                    "function.module": func.__module__,
                    **(attributes or {})
                }
                
                with self.tracer.start_as_current_span(name, attributes=span_attributes) as span:
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error", True)
                        raise
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                name = span_name or f"{func.__module__}.{func.__name__}"
                span_attributes = {
                    "function.name": func.__name__,
                    "function.module": func.__module__,
                    **(attributes or {})
                }
                
                with self.tracer.start_as_current_span(name, attributes=span_attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                        
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error", True)
                        raise
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator


class ElicitationTracer:
    """Tracing utilities for user elicitation workflows."""
    
    def __init__(self, tracer: Optional[trace.Tracer] = None):
        """Initialize elicitation tracer."""
        self.tracer = tracer or get_tracer()
        self.enabled = is_tracing_enabled() and self.tracer is not None
    
    @asynccontextmanager
    async def trace_elicitation_workflow(self, workflow_name: str, srid: str):
        """Trace complete elicitation workflow."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"elicitation.workflow.{workflow_name}"
        attributes = {
            "elicitation.workflow": workflow_name,
            "elicitation.srid": srid,
            "component": "user-elicitation",
            "elicitation.steps_total": 0,
            "elicitation.steps_completed": 0,
            "elicitation.user_cancelled": False
        }
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                raise
    
    @asynccontextmanager
    async def trace_elicitation_step(self, step_name: str, prompt: str):
        """Trace individual elicitation step."""
        if not self.enabled:
            yield None
            return
            
        span_name = f"elicitation.step.{step_name}"
        attributes = {
            "elicitation.step": step_name,
            "elicitation.prompt_length": len(prompt),
            "component": "user-elicitation"
        }
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                raise
    
    def record_elicitation_response(self, span: Optional[Span], 
                                   response: Union[AcceptedElicitation, DeclinedElicitation, CancelledElicitation]):
        """Record elicitation response (sanitized for privacy)."""
        if not self.enabled or not span:
            return
            
        if isinstance(response, AcceptedElicitation):
            span.set_attribute("elicitation.response.type", "accepted")
            span.set_attribute("elicitation.response.data_length", len(str(response.data)))
            # Don't log actual data for privacy
            
        elif isinstance(response, DeclinedElicitation):
            span.set_attribute("elicitation.response.type", "declined")
            
        elif isinstance(response, CancelledElicitation):
            span.set_attribute("elicitation.response.type", "cancelled")
        
        else:
            span.set_attribute("elicitation.response.type", "unknown")
    
    def update_workflow_progress(self, span: Optional[Span], steps_total: int, 
                                steps_completed: int, user_cancelled: bool = False):
        """Update workflow progress in span."""
        if not self.enabled or not span:
            return
            
        span.set_attribute("elicitation.steps_total", steps_total)
        span.set_attribute("elicitation.steps_completed", steps_completed)
        span.set_attribute("elicitation.user_cancelled", user_cancelled)
        span.set_attribute("elicitation.completion_rate", 
                          steps_completed / steps_total if steps_total > 0 else 0)


# Global tracer instances
_fastmcp_tracer: Optional[FastMCPTracer] = None
_elicitation_tracer: Optional[ElicitationTracer] = None


def get_fastmcp_tracer() -> FastMCPTracer:
    """Get global FastMCP tracer instance."""
    global _fastmcp_tracer
    if _fastmcp_tracer is None:
        _fastmcp_tracer = FastMCPTracer()
    return _fastmcp_tracer


def get_elicitation_tracer() -> ElicitationTracer:
    """Get global elicitation tracer instance."""
    global _elicitation_tracer
    if _elicitation_tracer is None:
        _elicitation_tracer = ElicitationTracer()
    return _elicitation_tracer


# Convenience functions for common tracing patterns
async def trace_tool_execution(tool_name: str, arguments: Dict[str, Any], 
                              func: Callable, ctx: Optional[Context] = None):
    """Trace a tool execution with automatic error handling."""
    tracer = get_fastmcp_tracer()
    
    async with tracer.trace_mcp_request("tool_call", tool_name, arguments, ctx) as span:
        start_time = time.time()
        
        try:
            # Execute the tool
            if ctx:
                result = await func(**arguments, ctx=ctx)
            else:
                result = await func(**arguments)
            
            # Record success metrics
            duration = time.time() - start_time
            if span:
                span.set_attribute("mcp.execution.duration", duration)
                span.set_attribute("mcp.execution.success", True)
                span.set_attribute("mcp.result.type", type(result).__name__)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            if span:
                span.set_attribute("mcp.execution.duration", duration)
                span.set_attribute("mcp.execution.success", False)
                span.set_attribute("mcp.execution.error", str(e))
                span.set_attribute("mcp.execution.error_type", type(e).__name__)
            raise


def trace_bmc_operation(operation: str):
    """Decorator for tracing BMC API operations."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_fastmcp_tracer()
            
            # Extract endpoint from args/kwargs if possible
            endpoint = kwargs.get('endpoint', 'unknown')
            method = kwargs.get('method', 'GET')
            
            async with tracer.trace_bmc_api_call(operation, endpoint, method) as span:
                try:
                    result = await func(*args, **kwargs)
                    
                    # Add success attributes
                    if span:
                        span.set_attribute("bmc.operation.success", True)
                        if hasattr(result, 'status_code'):
                            span.set_attribute("http.status_code", result.status_code)
                    
                    return result
                    
                except Exception as e:
                    if span:
                        span.set_attribute("bmc.operation.success", False)
                        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                            span.set_attribute("http.status_code", e.response.status_code)
                    raise
        
        return wrapper
    return decorator


# Import asyncio at the end to avoid circular imports
import asyncio
