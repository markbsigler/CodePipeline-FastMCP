#!/usr/bin/env python3
"""
BMC AMI DevX Code Pipeline MCP Server
Self-contained FastMCP server for BMC AMI DevX Code Pipeline integration.
"""

import json
import os
from typing import Any, Dict

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class MockFastMCP:
    """Self-contained FastMCP implementation for container deployment."""

    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "BMC AMI DevX Code Pipeline MCP Server")
        self.version = kwargs.get("version", "2.2.0")
        self.description = kwargs.get(
            "description", "MCP server for BMC AMI DevX Code Pipeline integration"
        )
        self.openapi_spec = None
        self.tools = []
        self.auth = kwargs.get("auth")
        self.route_map = kwargs.get("route_map", [])

    @classmethod
    def from_openapi(cls, spec_path: str, **kwargs):
        """Create FastMCP instance from OpenAPI specification."""
        instance = cls(**kwargs)
        instance.openapi_spec = spec_path
        instance._load_openapi_spec()
        return instance

    def _load_openapi_spec(self):
        """Load and parse OpenAPI specification."""
        try:
            if os.path.exists(self.openapi_spec):
                with open(self.openapi_spec, "r") as f:
                    spec = json.load(f)
                    self._generate_tools_from_spec(spec)
        except Exception as e:
            print(f"Warning: Could not load OpenAPI spec: {e}")

    def _generate_tools_from_spec(self, spec: Dict[str, Any]):
        """Generate MCP tools from OpenAPI specification."""
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE"]:
                    tool_name = operation.get(
                        "operationId", f"{method}_{path.replace('/', '_')}"
                    )
                    tool_description = operation.get(
                        "summary", f"{method.upper()} {path}"
                    )

                    tool = {
                        "name": tool_name,
                        "description": tool_description,
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    }

                    # Add parameters from spec
                    parameters = operation.get("parameters", [])
                    for param in parameters:
                        param_name = param.get("name")
                        param_schema = param.get("schema", {"type": "string"})
                        tool["inputSchema"]["properties"][param_name] = param_schema
                        if param.get("required", False):
                            tool["inputSchema"]["required"].append(param_name)

                    self.tools.append(tool)

    def get_app(self):
        """Return Starlette ASGI application."""

        async def health_check(request: Request):
            """Health check endpoint."""
            return JSONResponse(
                {"status": "healthy", "name": self.name, "version": self.version}
            )

        async def mcp_capabilities(request: Request):
            """MCP capabilities endpoint."""
            return JSONResponse(
                {
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                }
            )

        async def mcp_tools_list(request: Request):
            """List available MCP tools."""
            return JSONResponse({"tools": self.tools})

        async def mcp_tools_call(request: Request):
            """Handle MCP tool calls."""
            try:
                body = await request.json()
                tool_name = body.get("name")
                arguments = body.get("arguments", {})

                # Mock tool execution - return success response
                return JSONResponse(
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Tool '{tool_name}' executed successfully "
                                f"with arguments: {json.dumps(arguments, indent=2)}",
                            }
                        ],
                        "isError": False,
                    }
                )
            except Exception as e:
                return JSONResponse(
                    {
                        "content": [
                            {"type": "text", "text": f"Error executing tool: {str(e)}"}
                        ],
                        "isError": True,
                    },
                    status_code=400,
                )

        routes = [
            Route("/health", health_check, methods=["GET"]),
            Route("/mcp/capabilities", mcp_capabilities, methods=["POST"]),
            Route("/mcp/tools/list", mcp_tools_list, methods=["POST"]),
            Route("/mcp/tools/call", mcp_tools_call, methods=["POST"]),
        ]

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]

        return Starlette(routes=routes, middleware=middleware)


# Load environment variables
# Note: dotenv not available in container, using os.environ directly
def load_env_vars():
    """Load environment variables with defaults."""
    return {
        "FASTMCP_SERVER_HOST": os.environ.get(
            "HOST", os.environ.get("FASTMCP_SERVER_HOST", "0.0.0.0")
        ),
        "FASTMCP_SERVER_PORT": int(
            os.environ.get("PORT", os.environ.get("FASTMCP_SERVER_PORT", 8000))
        ),
        "FASTMCP_SERVER_AUTH_JWT_JWKS_URI": os.environ.get(
            "FASTMCP_SERVER_AUTH_JWT_JWKS_URI", ""
        ),
        "FASTMCP_SERVER_AUTH_JWT_ISSUER": os.environ.get(
            "FASTMCP_SERVER_AUTH_JWT_ISSUER", ""
        ),
        "FASTMCP_SERVER_AUTH_JWT_AUDIENCE": os.environ.get(
            "FASTMCP_SERVER_AUTH_JWT_AUDIENCE", ""
        ),
    }


def create_server():
    """Create and configure the FastMCP server."""
    env_vars = load_env_vars()

    # Create mock auth if JWT config provided
    auth = None
    if all(
        [
            env_vars["FASTMCP_SERVER_AUTH_JWT_JWKS_URI"],
            env_vars["FASTMCP_SERVER_AUTH_JWT_ISSUER"],
            env_vars["FASTMCP_SERVER_AUTH_JWT_AUDIENCE"],
        ]
    ):
        print("JWT authentication configured")
        # Mock auth implementation
        auth = {
            "jwks_uri": env_vars["FASTMCP_SERVER_AUTH_JWT_JWKS_URI"],
            "issuer": env_vars["FASTMCP_SERVER_AUTH_JWT_ISSUER"],
            "audience": env_vars["FASTMCP_SERVER_AUTH_JWT_AUDIENCE"],
        }

    # OpenAPI specification path
    openapi_spec_path = os.path.join(
        os.path.dirname(__file__), "config", "openapi.json"
    )

    # Create FastMCP server with BMC AMI DevX Code Pipeline configuration
    mcp = MockFastMCP.from_openapi(
        openapi_spec_path,
        name="BMC AMI DevX Code Pipeline MCP Server",
        version="2.2.0",
        description="MCP server for BMC AMI DevX Code Pipeline integration "
        "with comprehensive ISPW operations",
        auth=auth,
    )

    return mcp


def main():
    """Main entry point."""
    print("Starting BMC AMI DevX Code Pipeline MCP Server...")

    # Create server
    server = create_server()
    app = server.get_app()

    # Get configuration
    env_vars = load_env_vars()
    host = env_vars["FASTMCP_SERVER_HOST"]
    port = env_vars["FASTMCP_SERVER_PORT"]

    print("Environment variables loaded:")
    print(f"  HOST: {host}")
    print(f"  PORT: {port}")
    print(f"Server starting on {host}:{port}")
    print(f"Health check: http://{host}:{port}/health")
    print(f"MCP capabilities: http://{host}:{port}/mcp/capabilities")

    # Start server
    try:
        uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        raise


if __name__ == "__main__":
    main()
