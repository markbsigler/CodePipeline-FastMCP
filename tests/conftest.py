"""
Shared pytest configuration and fixtures for the FastMCP test suite.

This module provides common fixtures and configuration that can be used
across all test modules in the test suite.
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing without authentication."""
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
        },
        clear=False,
    ):
        yield


@pytest.fixture
def mock_context():
    """Mock FastMCP context for testing."""
    context = AsyncMock()
    context.info = AsyncMock()
    context.elicit = AsyncMock()
    return context
