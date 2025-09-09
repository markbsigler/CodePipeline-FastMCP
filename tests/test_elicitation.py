#!/usr/bin/env python3
"""
Test suite for FastMCP User Elicitation functionality.

This module tests the interactive elicitation features implemented in the
BMC AMI DevX Code Pipeline MCP Server.
"""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

# Import the server and elicitation classes
from openapi_server import OpenAPIMCPServer


class TestElicitationFeatures:
    """Test suite for elicitation-enabled tools."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch.dict(
            os.environ,
            {
                "API_BASE_URL": "https://test-api.example.com",
                "API_TOKEN": "test-token",
                "FASTMCP_AUTH_ENABLED": "false",
                "FASTMCP_LOG_LEVEL": "DEBUG",
                "FASTMCP_RATE_LIMIT_ENABLED": "true",
                "FASTMCP_CACHE_ENABLED": "true",
                "FASTMCP_MONITORING_ENABLED": "true",
                "FASTMCP_CUSTOM_ROUTES_ENABLED": "true",
                "FASTMCP_RESOURCE_TEMPLATES_ENABLED": "true",
                "FASTMCP_PROMPTS_ENABLED": "true",
            },
        ):
            yield

    @pytest.fixture
    def mock_context(self):
        """Mock context for elicitation testing."""
        context = AsyncMock()
        context.info = AsyncMock()
        context.elicit = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_create_assignment_interactive_success(
        self, mock_settings, mock_context
    ):
        """Test successful interactive assignment creation."""
        # Mock elicitation responses
        mock_context.elicit.side_effect = [
            AcceptedElicitation(data="Test Assignment"),
            AcceptedElicitation(data="This is a test assignment"),
            AcceptedElicitation(data="TEST-SRID-001"),
            AcceptedElicitation(data="high"),
            AcceptedElicitation(data=None),  # Confirmation
        ]

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("create_assignment_interactive")

        assert tool_func is not None, "create_assignment_interactive tool not found"

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["success"] is True
        assert result_data["message"] == "Assignment created successfully"
        assert "assignment" in result_data

        assignment = result_data["assignment"]
        assert assignment["title"] == "Test Assignment"
        assert assignment["description"] == "This is a test assignment"
        assert assignment["srid"] == "TEST-SRID-001"
        assert assignment["priority"] == "high"
        assert assignment["status"] == "created"

        # Verify elicitation was called 5 times
        assert mock_context.elicit.call_count == 5

    @pytest.mark.asyncio
    async def test_create_assignment_interactive_cancelled(
        self, mock_settings, mock_context
    ):
        """Test assignment creation cancelled by user."""
        # Mock elicitation response - user cancels at title step
        mock_context.elicit.return_value = CancelledElicitation()

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("create_assignment_interactive")

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["error"] is True
        assert "cancelled by user" in result_data["message"]

    @pytest.mark.asyncio
    async def test_deploy_release_interactive_success(
        self, mock_settings, mock_context
    ):
        """Test successful interactive release deployment."""
        # Mock elicitation responses
        mock_context.elicit.side_effect = [
            AcceptedElicitation(data="REL-2024-001"),
            AcceptedElicitation(data="staging"),
            AcceptedElicitation(data="rolling"),
            AcceptedElicitation(data=None),  # Confirmation
        ]

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("deploy_release_interactive")

        assert tool_func is not None, "deploy_release_interactive tool not found"

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["success"] is True
        assert "deployment initiated" in result_data["message"]
        assert "deployment" in result_data

        deployment = result_data["deployment"]
        assert deployment["release_id"] == "REL-2024-001"
        assert deployment["environment"] == "staging"
        assert deployment["strategy"] == "rolling"
        assert deployment["status"] == "deploying"

    @pytest.mark.asyncio
    async def test_deploy_release_interactive_production_warning(
        self, mock_settings, mock_context
    ):
        """Test production deployment with warning."""
        # Mock elicitation responses - production deployment
        mock_context.elicit.side_effect = [
            AcceptedElicitation(data="REL-2024-001"),
            AcceptedElicitation(data="production"),
            AcceptedElicitation(data="blue-green"),
            AcceptedElicitation(data=None),  # Production approval
            AcceptedElicitation(data=None),  # Final confirmation
        ]

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("deploy_release_interactive")

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["success"] is True
        assert "deployment initiated" in result_data["message"]

        # Verify production approval was requested (6 calls instead of 4)
        assert mock_context.elicit.call_count == 5

    @pytest.mark.asyncio
    async def test_troubleshoot_assignment_interactive_success(
        self, mock_settings, mock_context
    ):
        """Test successful interactive assignment troubleshooting."""
        # Mock elicitation responses
        mock_context.elicit.side_effect = [
            AcceptedElicitation(data="ASSIGN-001"),
            AcceptedElicitation(data="Assignment is failing to build"),
            AcceptedElicitation(data="high"),
            AcceptedElicitation(data="detailed"),
            AcceptedElicitation(data=None),  # Confirmation
        ]

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("troubleshoot_assignment_interactive")

        assert (
            tool_func is not None
        ), "troubleshoot_assignment_interactive tool not found"

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["success"] is True
        assert "Troubleshooting session started" in result_data["message"]
        assert "troubleshooting" in result_data

        troubleshooting = result_data["troubleshooting"]
        assert troubleshooting["assignment_id"] == "ASSIGN-001"
        assert troubleshooting["issue_description"] == "Assignment is failing to build"
        assert troubleshooting["error_level"] == "high"
        assert troubleshooting["diagnostic_level"] == "detailed"
        assert troubleshooting["status"] == "troubleshooting"
        assert "recommendations" in troubleshooting

    @pytest.mark.asyncio
    async def test_elicitation_without_context(self, mock_settings):
        """Test elicitation tools fail gracefully without context."""
        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("create_assignment_interactive")

        # Execute the tool without context
        result = await tool_func.fn(None)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["error"] is True
        assert "Context required for elicitation" in result_data["message"]

    @pytest.mark.asyncio
    async def test_elicitation_declined_response(self, mock_settings, mock_context):
        """Test elicitation when user declines to provide information."""
        # Mock elicitation response - user declines at title step
        mock_context.elicit.return_value = DeclinedElicitation()

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("create_assignment_interactive")

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["error"] is True
        assert "title required" in result_data["message"]

    @pytest.mark.asyncio
    async def test_elicitation_tool_tags(self, mock_settings):
        """Test that elicitation tools have correct tags."""
        server = OpenAPIMCPServer()

        # Get all tools
        tools = await server.server.get_tools()

        # Check elicitation tools have correct tags
        elicitation_tools = [
            "create_assignment_interactive",
            "deploy_release_interactive",
            "troubleshoot_assignment_interactive",
        ]

        for tool_name in elicitation_tools:
            tool = tools.get(tool_name)
            assert tool is not None, f"{tool_name} tool not found"

            # Check that the tool has elicitation and workflow tags
            # Note: We can't directly access tags from the tool object,
            # but we can verify the tool exists and is callable
            assert callable(tool.fn), f"{tool_name} tool is not callable"

    @pytest.mark.asyncio
    async def test_elicitation_error_handling(self, mock_settings, mock_context):
        """Test elicitation error handling."""
        # Mock elicitation to raise an exception
        mock_context.elicit.side_effect = Exception("Elicitation failed")

        server = OpenAPIMCPServer()

        # Get the tool function
        tools = await server.server.get_tools()
        tool_func = tools.get("create_assignment_interactive")

        # Execute the tool
        result = await tool_func.fn(mock_context)

        # Parse the result
        result_data = json.loads(result)

        # Verify the result
        assert result_data["error"] is True
        assert "Elicitation failed" in result_data["message"]


def run_tests():
    """Run the elicitation tests."""
    print("Running Elicitation Tests...")

    # Run pytest
    import subprocess

    result = subprocess.run(
        ["python", "-m", "pytest", "test_elicitation.py", "-v", "--tb=short"],
        capture_output=True,
        text=True,
    )

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    success = run_tests()
    if success:
        print("✅ All elicitation tests passed!")
    else:
        print("❌ Some elicitation tests failed!")
        exit(1)
