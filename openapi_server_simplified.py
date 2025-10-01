#!/usr/bin/env python3
"""
Simplified BMC AMI DevX Code Pipeline MCP Server following FastMCP Best Practices
"""

import json
import os
from pathlib import Path
from typing import Optional

import httpx
from fastmcp import Context, FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.workos import WorkOSProvider
from fastmcp.server.elicitation import AcceptedElicitation, DeclinedElicitation
from starlette.requests import Request
from starlette.responses import JSONResponse


def create_auth_provider():
    """Create authentication provider following FastMCP patterns."""
    if not os.getenv("AUTH_ENABLED", "false").lower() == "true":
        return None
    
    auth_provider = os.getenv("AUTH_PROVIDER", "").lower()
    
    if auth_provider == "jwt":
        return JWTVerifier(
            jwks_uri=os.getenv("FASTMCP_AUTH_JWKS_URI"),
            issuer=os.getenv("FASTMCP_AUTH_ISSUER"), 
            audience=os.getenv("FASTMCP_AUTH_AUDIENCE")
        )
    elif auth_provider == "github":
        return GitHubProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET")
        )
    elif auth_provider == "google":
        return GoogleProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET")
        )
    elif auth_provider == "workos":
        return WorkOSProvider(
            client_id=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_ID"),
            client_secret=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_SECRET"),
            authkit_domain=os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN")
        )
    
    return None


# Load OpenAPI specification
openapi_spec_path = Path("config/openapi.json")
if not openapi_spec_path.exists():
    raise FileNotFoundError(f"OpenAPI specification not found at {openapi_spec_path}")

with open(openapi_spec_path, "r") as f:
    openapi_spec = json.load(f)

# Create HTTP client
http_client = httpx.AsyncClient(
    base_url=os.getenv("API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1"),
    timeout=httpx.Timeout(int(os.getenv("API_TIMEOUT", "30"))),
    headers={
        "Authorization": f"Bearer {os.getenv('API_TOKEN', '')}",
        "Content-Type": "application/json",
        "User-Agent": "BMC-AMI-DevX-MCP-Server/2.2.0",
    }
)

# Create main FastMCP server following best practices
mcp = FastMCP(
    name="BMC AMI DevX Code Pipeline MCP Server",
    version="2.2.0",
    instructions="""
    This MCP server provides comprehensive BMC AMI DevX Code Pipeline integration
    with ISPW operations. All tools are automatically generated from the BMC ISPW
    OpenAPI specification, ensuring complete API coverage and maintainability.
    """,
    auth=create_auth_provider(),
    include_tags={"public", "api", "monitoring", "management"},
    exclude_tags={"internal", "deprecated"},
    # Use FastMCP's built-in global settings via environment variables
)

# Create OpenAPI-generated tools server
openapi_server = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=http_client,
    name="BMC ISPW API Tools"
)

# Mount OpenAPI server following FastMCP composition pattern
mcp.mount(openapi_server, prefix="ispw")


# Add custom monitoring tools following FastMCP patterns
@mcp.tool(tags={"monitoring", "public"})
async def get_server_health(ctx: Context = None) -> str:
    """Get comprehensive server health status."""
    if ctx:
        ctx.info("Checking server health status")
    
    try:
        # Test BMC API connectivity
        response = await http_client.get("/health")
        bmc_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        bmc_status = "unreachable"
    
    health_data = {
        "status": "healthy",
        "name": mcp.name,
        "version": "2.2.0", 
        "bmc_api_status": bmc_status,
        "tools_count": len(await mcp.get_tools())
    }
    
    return json.dumps(health_data, indent=2)


@mcp.tool(tags={"monitoring", "admin"})
async def get_server_metrics(ctx: Context = None) -> str:
    """Get server performance metrics."""
    if ctx:
        ctx.info("Retrieving server metrics")
    
    metrics = {
        "uptime": "N/A",  # Would implement actual uptime tracking
        "requests_processed": "N/A",  # Would implement request counter
        "cache_size": "N/A",  # Would implement cache monitoring
        "error_rate": "N/A"  # Would implement error tracking
    }
    
    return json.dumps(metrics, indent=2)


# Add elicitation tool following FastMCP patterns
@mcp.tool(tags={"elicitation", "workflow"})
async def create_assignment_interactive(ctx: Context) -> str:
    """Interactively create a new BMC ISPW assignment with user elicitation."""
    try:
        # Get assignment details through elicitation
        title_result = await ctx.elicit(
            "What is the assignment title?", 
            response_type=str
        )
        
        if isinstance(title_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"
        
        title = title_result.data
        
        description_result = await ctx.elicit(
            "Provide assignment description:", 
            response_type=str
        )
        
        if isinstance(description_result, DeclinedElicitation):
            return "Assignment creation cancelled by user"
        
        description = description_result.data
        
        # Create assignment via BMC API
        assignment_data = {
            "title": title,
            "description": description,
            "level": "DEV"
        }
        
        response = await http_client.post("/assignments", json=assignment_data)
        response.raise_for_status()
        
        result = response.json()
        return json.dumps({
            "success": True, 
            "assignment": result,
            "message": f"Assignment '{title}' created successfully"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": True,
            "message": f"Failed to create assignment: {str(e)}"
        }, indent=2)


# Add custom health check route following FastMCP patterns  
@mcp.custom_route("/health", methods=["GET"])
async def health_check_route(request: Request) -> JSONResponse:
    """Health check endpoint for load balancers."""
    try:
        health_data = await get_server_health()
        return JSONResponse(json.loads(health_data))
    except Exception as e:
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)}, 
            status_code=503
        )


@mcp.custom_route("/metrics", methods=["GET"])  
async def metrics_route(request: Request) -> JSONResponse:
    """Metrics endpoint for monitoring."""
    try:
        metrics_data = await get_server_metrics()
        return JSONResponse(json.loads(metrics_data))
    except Exception as e:
        return JSONResponse(
            {"error": str(e)}, 
            status_code=500
        )


# Add resource template following FastMCP patterns
@mcp.resource("bmc://assignments/{srid}")
async def get_assignment_resource(srid: str) -> dict:
    """Get assignment data as a structured resource."""
    try:
        response = await http_client.get(f"/assignments/{srid}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get assignment {srid}: {str(e)}"}


# Add prompt following FastMCP patterns
@mcp.prompt
def analyze_assignment_status(assignment_data: dict) -> str:
    """Generate analysis prompt for assignment status."""
    assignment_id = assignment_data.get("assignmentId", "Unknown")
    status = assignment_data.get("status", "Unknown")
    level = assignment_data.get("level", "Unknown")
    
    return f"""
    Analyze the following BMC ISPW assignment status:
    
    Assignment ID: {assignment_id}
    Status: {status}
    Level: {level}
    
    Please provide:
    1. Status interpretation and implications
    2. Recommended next actions
    3. Potential issues or risks
    4. Timeline considerations
    5. Dependencies to check
    """


if __name__ == "__main__":
    # Follow FastMCP standard server running pattern
    mcp.run(
        transport="http",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        # FastMCP automatically uses FASTMCP_LOG_LEVEL environment variable
    )
