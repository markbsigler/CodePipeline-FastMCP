import json
import os

import httpx

# Import mock FastMCP for testing (if real FastMCP not available)
try:
    from fastmcp import FastMCP
    from fastmcp.server.auth.providers.jwt import JWTVerifier
    from fastmcp.server.openapi import MCPType, RouteMap
except ImportError:
    print("FastMCP not available, using mock implementation for testing")
    import mock_fastmcp  # noqa: F401 - This sets up the mock framework
    from fastmcp import FastMCP
    from fastmcp.server.openapi import RouteMap, MCPType
    from fastmcp.server.auth.providers.jwt import JWTVerifier

from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "config/.env"))

# Load OpenAPI spec from file
OPENAPI_PATH = os.path.join(os.path.dirname(__file__), "config/openapi.json")
with open(OPENAPI_PATH, "r") as f:
    # Remove any comment lines (if present)
    lines = [line for line in f if not line.strip().startswith("#")]
    openapi_spec = json.loads("".join(lines))

# Configure HTTP client for BMC AMI DevX Code Pipeline API
API_BASE_URL = os.getenv("API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1")
client = httpx.AsyncClient(base_url=API_BASE_URL)

# Configure authentication using FastMCP's built-in providers
auth = None
if os.getenv("FASTMCP_SERVER_AUTH") == "JWT":
    # Use FastMCP's built-in JWT verifier
    auth = JWTVerifier(
        jwks_uri=os.getenv("FASTMCP_SERVER_AUTH_JWT_JWKS_URI"),
        issuer=os.getenv("FASTMCP_SERVER_AUTH_JWT_ISSUER"),
        audience=os.getenv("FASTMCP_SERVER_AUTH_JWT_AUDIENCE"),
    )

# Custom route mapping for BMC AMI DevX Code Pipeline operations
route_maps = [
    RouteMap(
        methods=["GET"], pattern=r".*\{.*\}.*", mcp_type=MCPType.RESOURCE_TEMPLATE
    ),
    RouteMap(methods=["GET"], mcp_type=MCPType.RESOURCE),
]

# Define constants
SERVER_NAME = "BMC AMI DevX Code Pipeline MCP Server"
SERVER_INSTRUCTIONS = """
This server provides MCP tools for BMC AMI DevX Code Pipeline operations.
Available tools include assignment management, release operations, and
source code lifecycle management for mainframe DevOps workflows.
"""

# Create FastMCP server following best practices
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name=SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
    auth=auth,
    tags={"code-pipeline", "mainframe", "devops", "production"},
    route_maps=route_maps,
    dependencies=["httpx>=0.25.0", "python-dotenv>=1.0.0"],
)


# Add custom health check endpoint using FastMCP's custom_route decorator
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for BMC AMI DevX Code Pipeline MCP Server"""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "healthy",
            "service": SERVER_NAME,
            "transport": "streamable-http",
            "authentication": "jwt" if auth else "none",
            "features": ["openapi-tools", "streaming", "real-time"],
            "timestamp": "2025-01-01T00:00:00Z",
        }
    )


if __name__ == "__main__":
    # Print available tools
    print("🚀 Starting BMC AMI DevX Code Pipeline MCP Server")
    print("📋 Available MCP tools:")

    try:
        if hasattr(mcp, "list_tools"):
            for tool in mcp.list_tools():
                print(f"  • {tool.name}")
        elif hasattr(mcp, "tools"):
            for tool in mcp.tools:
                print(f"  • {tool.name}")
        else:
            print("  (Tools will be dynamically generated from OpenAPI spec)")
    except Exception as e:
        print(f"  Error listing tools: {e}")

    port = os.getenv("PORT", 8080)
    print(f"🌐 Server will be available at: http://localhost:{port}/mcp/")
    print("💡 Use Streamable HTTP transport for web deployments")

    # Run server using FastMCP best practices
    # Streamable HTTP is the recommended transport for web deployments
    mcp.run(
        transport="http",  # Use FastMCP's built-in Streamable HTTP transport
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8080)),
        path="/mcp/",
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
