import asyncio
import os
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080/mcp/")

@pytest.mark.asyncio
async def test_list_tools():
    async with Client(MCP_SERVER_URL) as client:
        tools = await client.list_tools()
        assert isinstance(tools, list)
        assert any(tool.name for tool in tools)
        print("Available tools:", [tool.name for tool in tools])

@pytest.mark.asyncio
async def test_call_get_users_tool():
    async with Client(MCP_SERVER_URL) as client:
        tools = await client.list_tools()
        get_users_tool = next((t for t in tools if "get_users" in t.name.lower()), None)
        assert get_users_tool is not None, "No get_users tool found"
        # Expect a 404 error when calling the tool
        try:
            await client.call_tool(get_users_tool.name, {})
            assert False, "Expected ToolError (404) but call succeeded"
        except ToolError as e:
            assert "404" in str(e) or "Not Found" in str(e), f"Expected 404 error, got: {e}"
        print("get_users tool correctly returned 404 Not Found.")
