import os
import json
import httpx
from fastmcp import FastMCP
from fastmcp.server.openapi import RouteMap, MCPType
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'config/.env'))

# Load OpenAPI spec from file
OPENAPI_PATH = os.path.join(os.path.dirname(__file__), 'config/openapi.example.json')
with open(OPENAPI_PATH, 'r') as f:
    # Remove any comment lines (if present)
    lines = [line for line in f if not line.strip().startswith('#')]
    openapi_spec = json.loads(''.join(lines))

# Configure HTTP client (update base_url as needed)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
client = httpx.AsyncClient(base_url=API_BASE_URL)

# Custom route mapping: GET with path params -> ResourceTemplate, other GET -> Resource, others -> Tool
route_maps = [
    RouteMap(methods=["GET"], pattern=r".*\{.*\}.*", mcp_type=MCPType.RESOURCE_TEMPLATE),
    RouteMap(methods=["GET"], mcp_type=MCPType.RESOURCE),
]

# Optional: Add global tags or custom component naming
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="FastMCP OpenAPI Server",
    tags={"openapi", "production"},
    route_maps=route_maps,
    # mcp_names={...},
    # mcp_component_fn=...,
)

if __name__ == "__main__":
    mcp.run(transport="http", port=int(os.getenv("PORT", 8080)))
