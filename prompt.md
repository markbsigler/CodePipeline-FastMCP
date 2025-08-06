# BMC AMI DevX Code Pipeline MCP Server

## Project Overview

You are building a **FastMCP 2.x compliant** Model Context Protocol (MCP) server for **BMC AMI DevX Code Pipeline**. This server follows FastMCP best practices and uses official FastMCP 2.11.0+ features for authentication and transport.

## Core Requirements

### FastMCP 2.x Compliance
- **Framework**: FastMCP 2.11.0+ with built-in authentication providers
- **Transport**: Streamable HTTP (recommended for web deployments)
- **Authentication**: FastMCP's built-in JWT authentication providers
- **Server Construction**: Follow FastMCP.from_openapi() patterns
- **Environment Variables**: Use `FASTMCP_` prefix for configuration

### BMC AMI DevX Code Pipeline Integration
- **Target Platform**: BMC AMI DevX Code Pipeline (mainframe DevOps platform)
- **OpenAPI Specification**: Use the provided OpenAPI spec for tool generation
- **API Integration**: CRUD operations for assignments, releases, and source code management
- **Real-time Features**: Leverage FastMCP's Streamable HTTP for real-time updates

## Technical Architecture

### Authentication Strategy
```python
# Use FastMCP's built-in JWT verifier (recommended)
from fastmcp.server.auth.providers.jwt import JWTVerifier

auth = JWTVerifier(
    jwks_uri=os.getenv("FASTMCP_SERVER_AUTH_JWT_JWKS_URI"),
    issuer=os.getenv("FASTMCP_SERVER_AUTH_JWT_ISSUER"),
    audience=os.getenv("FASTMCP_SERVER_AUTH_JWT_AUDIENCE")
)
```

### Server Implementation
```python
# FastMCP 2.x best practice pattern
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=httpx.AsyncClient(base_url=API_BASE_URL),
    name="BMC AMI DevX Code Pipeline MCP Server",
    instructions=instructions,
    auth=auth,  # Built-in authentication
    tags={"code-pipeline", "mainframe", "devops", "production"}
)

# Run with Streamable HTTP transport
mcp.run(
    transport="http",  # FastMCP's built-in Streamable HTTP
    host="127.0.0.1",
    port=8080,
    path="/mcp/"
)
```

### Transport Protocol
- **Primary Transport**: Streamable HTTP (FastMCP's recommended transport)
- **Streaming**: Built-in streaming capabilities via FastMCP
- **Real-time**: Server-sent events support through Streamable HTTP
- **Fallback**: Standard HTTP for compatibility

## Project Structure

```
/
├── main.py                 # FastMCP 2.x compliant server implementation
├── config/
│   ├── openapi.json       # BMC AMI DevX Code Pipeline OpenAPI spec
│   └── .env.example       # FastMCP environment variable template
├── pyproject.toml         # Python dependencies with FastMCP 2.11.0+
├── requirements.txt       # Production dependencies
├── docker-compose.yml     # Docker deployment configuration
├── Dockerfile             # Multi-stage Docker build
└── docs/                  # Documentation and architecture diagrams
```

## Environment Configuration

Use FastMCP's standardized environment variable patterns:

```bash
# Server Configuration
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=INFO

# BMC AMI DevX Code Pipeline API
API_BASE_URL=https://devx.bmc.com/code-pipeline/api/v1

# FastMCP Authentication (JWT recommended)
FASTMCP_SERVER_AUTH=JWT
FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://auth.bmc.com/.well-known/jwks.json
FASTMCP_SERVER_AUTH_JWT_ISSUER=https://auth.bmc.com/
FASTMCP_SERVER_AUTH_JWT_AUDIENCE=bmc-ami-devx-code-pipeline
```

## Core Features

### MCP Tools (Auto-generated from OpenAPI)
1. **Assignment Management**
   - `create_assignment()` - Create new assignments
   - `list_assignments()` - List user assignments
   - `get_assignment_details()` - Get assignment details
   - `update_assignment()` - Update assignment status

2. **Release Operations**
   - `create_release()` - Create new releases
   - `promote_release()` - Promote releases through lifecycle
   - `list_releases()` - List available releases
   - `get_release_status()` - Get release status and details

3. **Source Code Management**
   - `list_programs()` - List programs in assignment
   - `get_program_content()` - Retrieve source code
   - `update_program()` - Update source code
   - `generate_program()` - Generate code with specified changes

### Authentication Features
- **JWT Token Validation**: Using FastMCP's built-in JWTVerifier
- **JWKS Support**: Automatic key rotation support
- **Token Introspection**: Remote validation support
- **Environment-based Config**: Auto-configuration with `FASTMCP_` variables

### Real-time Features
- **Streaming Updates**: Assignment and release status updates
- **Build Notifications**: Real-time build and deployment status
- **Event Streaming**: Code pipeline events via Streamable HTTP

## Dependencies

### Core Dependencies (FastMCP 2.x)
```toml
dependencies = [
    "fastmcp>=2.11.0",          # FastMCP framework with auth providers
    "httpx>=0.25.0,<0.26.0",    # HTTP client for API calls
    "python-dotenv>=1.0.0",     # Environment variable management
    "uvicorn>=0.24.0",          # ASGI server
    "starlette>=0.27.0",        # Web framework (FastMCP dependency)
]
```

### Development Dependencies
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx[test]>=0.25.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
]
```

## Deployment

### Docker Support
- **Multi-stage Build**: Optimized for production
- **Health Checks**: Built-in health check endpoint
- **Environment Config**: Docker Compose with environment files
- **Port Configuration**: Standard port 8080 for HTTP

### Production Considerations
- **JWT Authentication**: Required for production deployments
- **HTTPS**: TLS termination via reverse proxy
- **Rate Limiting**: Built into FastMCP transport
- **Monitoring**: Health check endpoint at `/health`

## Standards Compliance

### FastMCP 2.x Best Practices
✅ **Use FastMCP.from_openapi()** - Leverage built-in OpenAPI integration
✅ **Built-in Authentication** - Use JWTVerifier instead of custom OAuth
✅ **Streamable HTTP Transport** - Use recommended transport protocol
✅ **Environment Variables** - Follow `FASTMCP_` prefix convention
✅ **Simple Server Construction** - Avoid complex async patterns
✅ **Health Check Endpoints** - Use custom_route decorators

### Anti-Patterns to Avoid
❌ **Custom WebSocket Implementation** - Not officially supported
❌ **Custom OAuth Implementation** - Use FastMCP's built-in providers
❌ **Complex Async Setup** - Use FastMCP's simple patterns
❌ **Non-standard Environment Variables** - Use `FASTMCP_` prefixes

## Implementation Notes

1. **OpenAPI-First Approach**: All MCP tools are auto-generated from the OpenAPI specification
2. **BMC-Specific Features**: Custom route mappings for BMC AMI DevX Code Pipeline patterns
3. **Production Ready**: Comprehensive error handling, logging, and monitoring
4. **Standards Compliant**: Follows FastMCP 2.x best practices and patterns
5. **Maintainable**: Clean, simple codebase following FastMCP conventions

This project represents a modern, standards-compliant FastMCP 2.x server implementation optimized for BMC AMI DevX Code Pipeline integration with enterprise-grade authentication and real-time capabilities.
