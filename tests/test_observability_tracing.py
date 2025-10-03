#!/usr/bin/env python3
"""
Tests for observability tracing module - FIXED VERSION

This module provides comprehensive tests for FastMCP tracing utilities
including FastMCPTracer, ElicitationTracer, and convenience functions.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)


def create_mock_context_manager(return_value):
    """Helper to create a proper async context manager mock."""
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=return_value)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    return mock_context_manager


class TestFastMCPTracer:
    """Test FastMCPTracer class."""

    def test_init_with_tracer(self):
        """Test FastMCPTracer initialization with tracer."""
        mock_tracer = Mock()

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            assert tracer.tracer == mock_tracer
            assert tracer.enabled is True

    def test_init_disabled(self):
        """Test FastMCPTracer initialization when disabled."""
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=False,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer", return_value=Mock()
            ),
        ):

            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer()

            assert tracer.enabled is False

    def test_init_no_tracer(self):
        """Test FastMCPTracer initialization with no tracer available."""
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch("observability.tracing.fastmcp_tracer.get_tracer", return_value=None),
        ):

            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer()

            assert tracer.enabled is False

    @pytest.mark.asyncio
    async def test_trace_mcp_request_disabled(self):
        """Test trace_mcp_request when tracing is disabled."""
        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled",
            return_value=False,
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer()

            async with tracer.trace_mcp_request(
                "test", "test_tool", {"arg": "value"}
            ) as span:
                assert span is None

    @pytest.mark.asyncio
    async def test_trace_mcp_request_success(self):
        """Test successful MCP request tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)
            mock_ctx = Mock()

            async with tracer.trace_mcp_request(
                "test", "test_tool", {"arg": "value"}, mock_ctx
            ) as span:
                assert span == mock_span

            # Verify span attributes were set
            mock_span.set_attribute.assert_any_call("mcp.operation", "test")
            mock_span.set_attribute.assert_any_call("mcp.tool_name", "test_tool")
            mock_span.set_attribute.assert_any_call("mcp.arguments_count", 1)
            mock_span.set_attribute.assert_any_call("mcp.context.present", True)
            mock_span.set_attribute.assert_any_call("mcp.arg.arg", "value")
            mock_span.set_status.assert_called()

    @pytest.mark.asyncio
    async def test_trace_mcp_request_sensitive_args(self):
        """Test MCP request tracing with sensitive arguments."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            # Test with sensitive arguments that should be filtered
            sensitive_args = {
                "username": "testuser",
                "password": "secret123",
                "token": "bearer_token",
                "secret": "my_secret",
                "key": "api_key",
                "auth": "auth_header",
            }

            async with tracer.trace_mcp_request("test", "test_tool", sensitive_args):
                pass

            # Verify sensitive arguments were not logged
            call_args = [call[0] for call in mock_span.set_attribute.call_args_list]

            # Only username should be logged, not the sensitive fields
            username_logged = any("mcp.arg.username" in str(call) for call in call_args)
            password_logged = any("mcp.arg.password" in str(call) for call in call_args)

            assert username_logged
            assert not password_logged

    @pytest.mark.asyncio
    async def test_trace_mcp_request_exception(self):
        """Test MCP request tracing with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()
        mock_span.record_exception = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            test_exception = ValueError("Test error")

            with pytest.raises(ValueError):
                async with tracer.trace_mcp_request("test", "test_tool", {}):
                    raise test_exception

            # Verify exception was recorded
            mock_span.record_exception.assert_called_once_with(test_exception)
            mock_span.set_attribute.assert_any_call("error", True)
            mock_span.set_attribute.assert_any_call("error.type", "ValueError")

    @pytest.mark.asyncio
    async def test_trace_bmc_api_call_success(self):
        """Test successful BMC API call tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch("time.time", side_effect=[1000.0, 1000.5]),
        ):  # Mock start and end times

            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            async with tracer.trace_bmc_api_call("test_op", "/test", "POST") as span:
                assert span == mock_span

            # Verify span attributes
            mock_span.set_attribute.assert_any_call("http.method", "POST")
            mock_span.set_attribute.assert_any_call("http.url", "/test")
            mock_span.set_attribute.assert_any_call("bmc.operation", "test_op")
            mock_span.set_attribute.assert_any_call("http.duration", 0.5)

    @pytest.mark.asyncio
    async def test_trace_bmc_api_call_exception(self):
        """Test BMC API call tracing with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()
        mock_span.record_exception = Mock()

        mock_tracer.start_span.return_value = mock_span

        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.time.time",
                side_effect=[1000.0, 1000.3],
            ),
        ):

            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            # Create exception with response attribute
            test_exception = Exception("API error")
            mock_response = Mock()
            mock_response.status_code = 500
            test_exception.response = mock_response

            with pytest.raises(Exception):
                async with tracer.trace_bmc_api_call("test_op", "/test", "GET"):
                    raise test_exception

            # Verify exception handling
            mock_span.record_exception.assert_called_once_with(test_exception)
            mock_span.set_attribute.assert_any_call("error", True)
            mock_span.set_attribute.assert_any_call("http.status_code", 500)

            # Check duration was set (allow for floating point precision)
            duration_calls = [
                call
                for call in mock_span.set_attribute.call_args_list
                if call[0][0] == "http.duration"
            ]
            assert len(duration_calls) == 1
            duration_value = duration_calls[0][0][1]
            assert abs(duration_value - 0.3) < 0.01  # Allow small floating point error

    @pytest.mark.asyncio
    async def test_trace_cache_operation_success(self):
        """Test successful cache operation tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            async with tracer.trace_cache_operation(
                "get", "test_key", "assignment"
            ) as span:
                assert span == mock_span

            # Verify span attributes
            mock_span.set_attribute.assert_any_call("cache.operation", "get")
            mock_span.set_attribute.assert_any_call("cache.key", "test_key")
            mock_span.set_attribute.assert_any_call("cache.key_type", "assignment")

    @pytest.mark.asyncio
    async def test_trace_cache_operation_long_key(self):
        """Test cache operation tracing with long key."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            long_key = "a" * 100  # 100 character key

            async with tracer.trace_cache_operation("set", long_key):
                pass

            # Verify key was truncated to 50 characters
            mock_span.set_attribute.assert_any_call("cache.key", "a" * 50)

    @pytest.mark.asyncio
    async def test_trace_auth_operation_success(self):
        """Test successful auth operation tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            async with tracer.trace_auth_operation("jwt", "validate") as span:
                assert span == mock_span

            # Verify span attributes
            mock_span.set_attribute.assert_any_call("auth.provider", "jwt")
            mock_span.set_attribute.assert_any_call("auth.operation", "validate")
            mock_span.set_attribute.assert_any_call("auth.success", True)

    @pytest.mark.asyncio
    async def test_trace_auth_operation_exception(self):
        """Test auth operation tracing with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()
        mock_span.record_exception = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            with pytest.raises(ValueError):
                async with tracer.trace_auth_operation("github", "authenticate"):
                    raise ValueError("Auth failed")

            # Verify exception handling
            mock_span.set_attribute.assert_any_call("auth.success", False)
            mock_span.set_attribute.assert_any_call("error", True)

    @pytest.mark.asyncio
    async def test_trace_function_decorator_async(self):
        """Test trace_function decorator with async function."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            @tracer.trace_function("custom_span", {"custom": "attribute"})
            async def test_async_function():
                return "async_result"

            result = await test_async_function()

            assert result == "async_result"
            mock_span.set_attribute.assert_any_call(
                "function.name", "test_async_function"
            )
            mock_span.set_attribute.assert_any_call("custom", "attribute")

    def test_trace_function_decorator_sync(self):
        """Test trace_function decorator with sync function."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            @tracer.trace_function()
            def test_sync_function():
                return "sync_result"

            result = test_sync_function()

            assert result == "sync_result"
            mock_span.set_attribute.assert_any_call(
                "function.name", "test_sync_function"
            )

    def test_trace_function_decorator_disabled(self):
        """Test trace_function decorator when tracing is disabled."""
        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled",
            return_value=False,
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer()

            @tracer.trace_function()
            def test_function():
                return "result"

            result = test_function()

            assert result == "result"  # Function should work normally


class TestElicitationTracer:
    """Test ElicitationTracer class."""

    def test_init(self):
        """Test ElicitationTracer initialization."""
        mock_tracer = Mock()

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer(mock_tracer)

            assert tracer.tracer == mock_tracer
            assert tracer.enabled is True

    @pytest.mark.asyncio
    async def test_trace_elicitation_workflow_success(self):
        """Test successful elicitation workflow tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer(mock_tracer)

            async with tracer.trace_elicitation_workflow(
                "create_assignment", "TEST123"
            ) as span:
                assert span == mock_span

            # Verify span attributes
            mock_span.set_attribute.assert_any_call(
                "elicitation.workflow", "create_assignment"
            )
            mock_span.set_attribute.assert_any_call("elicitation.srid", "TEST123")

    @pytest.mark.asyncio
    async def test_trace_elicitation_step_success(self):
        """Test successful elicitation step tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()
        mock_span.set_status = Mock()
        mock_span.end = Mock()

        mock_tracer.start_span.return_value = mock_span

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer(mock_tracer)

            prompt = "Please enter assignment title:"

            async with tracer.trace_elicitation_step("get_title", prompt) as span:
                assert span == mock_span

            # Verify span attributes
            mock_span.set_attribute.assert_any_call("elicitation.step", "get_title")
            mock_span.set_attribute.assert_any_call(
                "elicitation.prompt_length", len(prompt)
            )

    def test_record_elicitation_response_accepted(self):
        """Test recording accepted elicitation response."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            response = AcceptedElicitation(data="Test data")

            tracer.record_elicitation_response(mock_span, response)

            mock_span.set_attribute.assert_any_call(
                "elicitation.response.type", "accepted"
            )
            mock_span.set_attribute.assert_any_call(
                "elicitation.response.data_length", 9
            )

    def test_record_elicitation_response_declined(self):
        """Test recording declined elicitation response."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            response = DeclinedElicitation()

            tracer.record_elicitation_response(mock_span, response)

            mock_span.set_attribute.assert_called_with(
                "elicitation.response.type", "declined"
            )

    def test_record_elicitation_response_cancelled(self):
        """Test recording cancelled elicitation response."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            response = CancelledElicitation()

            tracer.record_elicitation_response(mock_span, response)

            mock_span.set_attribute.assert_called_with(
                "elicitation.response.type", "cancelled"
            )

    def test_record_elicitation_response_unknown(self):
        """Test recording unknown elicitation response."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            response = "unknown_response"

            tracer.record_elicitation_response(mock_span, response)

            mock_span.set_attribute.assert_called_with(
                "elicitation.response.type", "unknown"
            )

    def test_record_elicitation_response_disabled(self):
        """Test recording elicitation response when disabled."""
        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled",
            return_value=False,
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()

            response = AcceptedElicitation(data="Test")

            # Should not raise exception and not call span methods
            tracer.record_elicitation_response(mock_span, response)

            mock_span.set_attribute.assert_not_called()

    def test_update_workflow_progress(self):
        """Test updating workflow progress."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            tracer.update_workflow_progress(mock_span, 5, 3, False)

            mock_span.set_attribute.assert_any_call("elicitation.steps_total", 5)
            mock_span.set_attribute.assert_any_call("elicitation.steps_completed", 3)
            mock_span.set_attribute.assert_any_call("elicitation.user_cancelled", False)
            mock_span.set_attribute.assert_any_call("elicitation.completion_rate", 0.6)

    def test_update_workflow_progress_zero_total(self):
        """Test updating workflow progress with zero total steps."""
        mock_tracer = Mock()
        with (
            patch(
                "observability.tracing.fastmcp_tracer.is_tracing_enabled",
                return_value=True,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.get_tracer",
                return_value=mock_tracer,
            ),
        ):
            from observability.tracing.fastmcp_tracer import ElicitationTracer

            tracer = ElicitationTracer()
            mock_span = Mock()
            mock_span.set_attribute = Mock()

            tracer.update_workflow_progress(mock_span, 0, 0, True)

            mock_span.set_attribute.assert_any_call("elicitation.completion_rate", 0)


class TestGlobalTracerFunctions:
    """Test global tracer functions."""

    def test_get_fastmcp_tracer_singleton(self):
        """Test that get_fastmcp_tracer returns singleton."""
        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            # Clear global tracer to test singleton behavior
            import observability.tracing.fastmcp_tracer as tracer_module
            from observability.tracing.fastmcp_tracer import get_fastmcp_tracer

            tracer_module._fastmcp_tracer = None

            tracer1 = get_fastmcp_tracer()
            tracer2 = get_fastmcp_tracer()

            assert tracer1 is tracer2

    def test_get_elicitation_tracer_singleton(self):
        """Test that get_elicitation_tracer returns singleton."""
        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            # Clear global tracer to test singleton behavior
            import observability.tracing.fastmcp_tracer as tracer_module
            from observability.tracing.fastmcp_tracer import get_elicitation_tracer

            tracer_module._elicitation_tracer = None

            tracer1 = get_elicitation_tracer()
            tracer2 = get_elicitation_tracer()

            assert tracer1 is tracer2


class TestConvenienceFunctions:
    """Test convenience functions for common tracing patterns."""

    @pytest.mark.asyncio
    async def test_trace_tool_execution_success(self):
        """Test successful tool execution tracing."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_mcp_request.return_value = create_mock_context_manager(
            mock_span
        )

        with (
            patch(
                "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
                return_value=mock_tracer,
            ),
            patch(
                "observability.tracing.fastmcp_tracer.time.time",
                side_effect=[1000.0, 1000.2],
            ),
        ):

            from observability.tracing.fastmcp_tracer import trace_tool_execution

            async def test_tool(**kwargs):
                return "tool_result"

            mock_ctx = Mock()
            result = await trace_tool_execution(
                "test_tool", {"arg": "value"}, test_tool, mock_ctx
            )

            assert result == "tool_result"

            # Check that duration was set (with floating point tolerance)
            duration_calls = [
                call
                for call in mock_span.set_attribute.call_args_list
                if call[0][0] == "mcp.execution.duration"
            ]
            assert len(duration_calls) == 1
            duration_value = duration_calls[0][0][1]
            assert abs(duration_value - 0.2) < 0.001  # Allow small floating point error
            mock_span.set_attribute.assert_any_call("mcp.execution.success", True)

    @pytest.mark.asyncio
    async def test_trace_tool_execution_no_context(self):
        """Test tool execution tracing without context."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_mcp_request.return_value = create_mock_context_manager(
            mock_span
        )

        with (
            patch(
                "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
                return_value=mock_tracer,
            ),
            patch("time.time", side_effect=[1000.0, 1000.1]),
        ):

            from observability.tracing.fastmcp_tracer import trace_tool_execution

            async def test_tool(**kwargs):
                return "no_ctx_result"

            result = await trace_tool_execution(
                "test_tool", {"arg": "value"}, test_tool
            )

            assert result == "no_ctx_result"

    @pytest.mark.asyncio
    async def test_trace_tool_execution_exception(self):
        """Test tool execution tracing with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_mcp_request.return_value = create_mock_context_manager(
            mock_span
        )

        with (
            patch(
                "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
                return_value=mock_tracer,
            ),
            patch("time.time", side_effect=[1000.0, 1000.3]),
        ):

            from observability.tracing.fastmcp_tracer import trace_tool_execution

            async def failing_tool(**kwargs):
                raise ValueError("Tool failed")

            with pytest.raises(ValueError):
                await trace_tool_execution("failing_tool", {}, failing_tool)

            mock_span.set_attribute.assert_any_call("mcp.execution.success", False)
            mock_span.set_attribute.assert_any_call(
                "mcp.execution.error", "Tool failed"
            )
            mock_span.set_attribute.assert_any_call(
                "mcp.execution.error_type", "ValueError"
            )

    @pytest.mark.asyncio
    async def test_trace_bmc_operation_decorator_success(self):
        """Test BMC operation decorator with success."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_bmc_api_call.return_value = create_mock_context_manager(
            mock_span
        )

        with patch(
            "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
            return_value=mock_tracer,
        ):
            from observability.tracing.fastmcp_tracer import trace_bmc_operation

            @trace_bmc_operation("test_operation")
            async def test_bmc_call(endpoint="/test", method="GET"):
                mock_result = Mock()
                mock_result.status_code = 200
                return mock_result

            result = await test_bmc_call(endpoint="/assignments", method="POST")

            assert result.status_code == 200
            mock_span.set_attribute.assert_any_call("bmc.operation.success", True)
            mock_span.set_attribute.assert_any_call("http.status_code", 200)

    @pytest.mark.asyncio
    async def test_trace_bmc_operation_decorator_exception(self):
        """Test BMC operation decorator with exception."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_bmc_api_call.return_value = create_mock_context_manager(
            mock_span
        )

        with patch(
            "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
            return_value=mock_tracer,
        ):
            from observability.tracing.fastmcp_tracer import trace_bmc_operation

            @trace_bmc_operation("failing_operation")
            async def failing_bmc_call(endpoint="/test", method="GET"):
                error = Exception("API Error")
                mock_response = Mock()
                mock_response.status_code = 500
                error.response = mock_response
                raise error

            with pytest.raises(Exception):
                await failing_bmc_call(endpoint="/error", method="POST")

            mock_span.set_attribute.assert_any_call("bmc.operation.success", False)
            mock_span.set_attribute.assert_any_call("http.status_code", 500)

    @pytest.mark.asyncio
    async def test_trace_bmc_operation_decorator_no_response(self):
        """Test BMC operation decorator with exception without response."""
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.set_attribute = Mock()

        mock_tracer.trace_bmc_api_call.return_value = create_mock_context_manager(
            mock_span
        )

        with patch(
            "observability.tracing.fastmcp_tracer.get_fastmcp_tracer",
            return_value=mock_tracer,
        ):
            from observability.tracing.fastmcp_tracer import trace_bmc_operation

            @trace_bmc_operation("connection_error")
            async def connection_error_call():
                raise ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                await connection_error_call()

            mock_span.set_attribute.assert_any_call("bmc.operation.success", False)
            # Should not set http.status_code since there's no response


class TestTracingIntegration:
    """Test tracing integration scenarios."""

    @pytest.mark.asyncio
    async def test_nested_tracing_contexts(self):
        """Test nested tracing contexts."""
        mock_tracer = Mock()
        mock_mcp_span = Mock()
        mock_mcp_span.set_attribute = Mock()
        mock_mcp_span.set_status = Mock()
        mock_mcp_span.end = Mock()

        mock_bmc_span = Mock()
        mock_bmc_span.set_attribute = Mock()
        mock_bmc_span.set_status = Mock()
        mock_bmc_span.end = Mock()

        mock_cache_span = Mock()
        mock_cache_span.set_attribute = Mock()
        mock_cache_span.set_status = Mock()
        mock_cache_span.end = Mock()

        # Setup spans for each call
        mock_tracer.start_span.side_effect = [
            mock_mcp_span,
            mock_bmc_span,
            mock_cache_span,
        ]

        with patch(
            "observability.tracing.fastmcp_tracer.is_tracing_enabled", return_value=True
        ):
            from observability.tracing.fastmcp_tracer import FastMCPTracer

            tracer = FastMCPTracer(mock_tracer)

            # Test nested contexts
            async with tracer.trace_mcp_request(
                "tool_call", "test_tool", {}
            ) as mcp_span:
                async with tracer.trace_bmc_api_call(
                    "get_assignment", "/assignments/123"
                ) as bmc_span:
                    async with tracer.trace_cache_operation(
                        "get", "assignment_123"
                    ) as cache_span:
                        assert mcp_span == mock_mcp_span
                        assert bmc_span == mock_bmc_span
                        assert cache_span == mock_cache_span

    def test_tracing_module_imports(self):
        """Test that all tracing module components can be imported."""
        from observability.tracing.fastmcp_tracer import (
            ElicitationTracer,
            FastMCPTracer,
            get_elicitation_tracer,
            get_fastmcp_tracer,
            trace_bmc_operation,
            trace_tool_execution,
        )

        # All imports successful
        assert FastMCPTracer is not None
        assert ElicitationTracer is not None
        assert get_fastmcp_tracer is not None
        assert get_elicitation_tracer is not None
        assert trace_tool_execution is not None
        assert trace_bmc_operation is not None
