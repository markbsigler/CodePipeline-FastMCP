# Mock FastMCP implementation for testing

import sys

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


class MockJWTVerifier:
    def __init__(self, jwks_uri=None, issuer=None, audience=None):
        self.jwks_uri = jwks_uri
        self.issuer = issuer
        self.audience = audience


class MockFastMCP:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "Test Server")
        self.instructions = kwargs.get("instructions", "Test instructions")
        self.auth = kwargs.get("auth")
        self.tags = kwargs.get("tags", [])
        self.openapi_spec = kwargs.get("openapi_spec", {})
        self.client = kwargs.get("client")

    @classmethod
    def from_openapi(cls, **kwargs):
        return cls(**kwargs)

    def custom_route(self, path, methods=None):
        def decorator(func):
            return func

        return decorator

    def run(
        self,
        transport="http",
        host="127.0.0.1",
        port=8080,
        path="/mcp/",
        log_level="INFO",
    ):
        async def health_check(request):
            return JSONResponse(
                {
                    "status": "healthy",
                    "service": self.name,
                    "transport": transport,
                    "authentication": "jwt" if self.auth else "none",
                    "features": ["openapi-tools", "streaming", "real-time"],
                    "timestamp": "2025-01-01T00:00:00Z",
                }
            )

        async def mcp_endpoint(request):
            return JSONResponse({"message": "MCP endpoint", "status": "ok"})

        routes = [
            Route("/health", health_check, methods=["GET"]),
            Route(path.rstrip("/"), mcp_endpoint, methods=["GET", "POST"]),
        ]

        app = Starlette(routes=routes)
        uvicorn.run(app, host=host, port=port, log_level=log_level.lower())


# Mock fastmcp module
class fastmcp:
    FastMCP = MockFastMCP

    class server:
        class openapi:
            class RouteMap:
                def __init__(self, methods=None, pattern=None, mcp_type=None):
                    self.methods = methods
                    self.pattern = pattern
                    self.mcp_type = mcp_type

            class MCPType:
                RESOURCE_TEMPLATE = "resource_template"
                RESOURCE = "resource"

        class auth:
            class providers:
                class jwt:
                    JWTVerifier = MockJWTVerifier


# Mock the fastmcp import
sys.modules["fastmcp"] = fastmcp
sys.modules["fastmcp.server"] = fastmcp.server
sys.modules["fastmcp.server.openapi"] = fastmcp.server.openapi
sys.modules["fastmcp.server.auth"] = fastmcp.server.auth
sys.modules["fastmcp.server.auth.providers"] = fastmcp.server.auth.providers
sys.modules["fastmcp.server.auth.providers.jwt"] = fastmcp.server.auth.providers.jwt
