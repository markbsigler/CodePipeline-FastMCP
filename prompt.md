# BMC AMI DevX Code Pipeline MCP Server

## Project Overview

You are building a **self-contained Model Context Protocol (MCP) server** for **BMC AMI DevX Code Pipeline** using a custom MockFastMCP implementation. This server provides MCP-compliant endpoints using Starlette web framework and Uvicorn ASGI server, designed for containerized deployment without external FastMCP dependencies.

## Core Requirements

### Self-Contained MCP Implementation

- **Framework**: Custom MockFastMCP class using Starlette + Uvicorn
- **Transport**: HTTP REST API with MCP-compliant endpoints
- **Authentication**: Environment-configurable JWT token validation (optional)
- **Server Construction**: OpenAPI-driven tool generation pattern
- **Environment Variables**: Use `FASTMCP_` prefix for configuration compatibility

### BMC AMI DevX Code Pipeline Integration
- **Target Platform**: BMC AMI DevX Code Pipeline (mainframe DevOps platform)
- **OpenAPI Specification**: Use the provided OpenAPI spec for tool generation
- **API Integration**: CRUD operations for assignments, releases, and source code management
- **Real-time Features**: Leverage FastMCP's Streamable HTTP for real-time updates

## Technical Architecture

### Self-Contained MockFastMCP Implementation

```python
# Custom MockFastMCP class for container-ready deployment
class MockFastMCP:
    """Self-contained FastMCP implementation for container deployment."""

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', 'BMC AMI DevX Code Pipeline MCP Server')
        self.version = kwargs.get('version', '2.2.0')
        self.description = kwargs.get('description', 'MCP server for BMC AMI DevX Code Pipeline integration')
        self.tools = []
        self.auth = kwargs.get('auth')  # Optional JWT configuration

    @classmethod
    def from_openapi(cls, spec_path: str, **kwargs):
        """Create MockFastMCP instance from OpenAPI specification."""
        instance = cls(**kwargs)
        instance.openapi_spec = spec_path
        instance._load_openapi_spec()
        return instance
```

### Server Implementation Pattern

```python
# Self-contained server creation and startup
def create_server():
    """Create and configure the MockFastMCP server."""
    openapi_spec_path = os.path.join(os.path.dirname(__file__), "config", "openapi.json")

    mcp = MockFastMCP.from_openapi(
        openapi_spec_path,
        name="BMC AMI DevX Code Pipeline MCP Server",
        version="2.2.0",
        description="MCP server for BMC AMI DevX Code Pipeline integration",
        auth=auth  # Optional JWT authentication
    )

    return mcp

def main():
    """Main entry point."""
    server = create_server()
    app = server.get_app()  # Returns Starlette ASGI application

    uvicorn.run(
        app,
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8000)),
        log_level="info"
    )
```

### MCP-Compliant HTTP Endpoints

- **Health Check**: `GET /health` - Server status and version information
- **MCP Capabilities**: `POST /mcp/capabilities` - Server capabilities and info
- **Tools List**: `POST /mcp/tools/list` - Available MCP tools from OpenAPI
- **Tool Execution**: `POST /mcp/tools/call` - Execute MCP tools with arguments
- **CORS Support**: Cross-origin requests enabled for web integration

## Project Structure

```text
/
├── main.py                     # Self-contained MockFastMCP server implementation
├── test_mcp_server.py         # Comprehensive test suite with 100% main.py coverage
├── config/
│   ├── openapi.json           # BMC AMI DevX Code Pipeline OpenAPI spec (1263 lines)
│   ├── ispw_openapi_spec.json # Additional ISPW specifications
│   └── .env.example           # Environment variable template
├── pyproject.toml             # Python project configuration
├── requirements.txt           # Production dependencies (Starlette + Uvicorn)
├── package.json               # Development workflow scripts (npm-style)
├── .pre-commit-config.yaml    # Code quality automation
├── docker-compose.yml         # Docker deployment configuration
├── Dockerfile                 # Multi-stage Docker build (78 lines)
├── coverage.xml              # Test coverage reports
└── htmlcov/                  # HTML coverage reports
```

## Environment Configuration

Use standardized environment variable patterns compatible with FastMCP:

```bash
# Server Configuration
HOST=0.0.0.0                    # Server bind address
PORT=8000                       # Server port (default 8000, Docker uses 8080)
LOG_LEVEL=info                  # Uvicorn log level

# BMC AMI DevX Code Pipeline API (Optional - for future real API integration)
API_BASE_URL=https://devx.bmc.com/code-pipeline/api/v1

# Optional JWT Authentication (Mock implementation)
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

- **Mock JWT Configuration**: Environment-configurable JWT settings
- **Optional Authentication**: Works with or without JWT configuration
- **Environment-based Config**: Auto-configuration with `FASTMCP_` variables
- **Container-Ready**: No external authentication dependencies

### Testing and Quality Features

- **100% Main Coverage**: Comprehensive test suite with 100% main.py coverage
- **21 Test Cases**: Including endpoint testing, error handling, and mocking
- **Quality Tools**: Black, flake8, isort, autoflake with pre-commit hooks
- **Coverage Reporting**: HTML and XML coverage reports generated

## Dependencies

### Core Dependencies (Self-Contained Implementation)

```text
# Web framework and ASGI server
starlette>=0.47.0              # Modern async web framework
uvicorn>=0.35.0                # Production ASGI server

# HTTP client for API integration
httpx>=0.28.0                  # Async HTTP client

# Environment variable management
python-dotenv>=1.1.0           # Environment variable loading

# Testing framework
pytest>=8.4.0                 # Testing framework
pytest-asyncio>=1.1.0         # Async testing support
pytest-cov>=6.2.0             # Coverage testing
starlette[testclient]          # TestClient for endpoint testing
```

### Development Dependencies

```text
# Code quality tools
black>=24.0.0                 # Code formatting (88-char lines)
flake8>=7.0.0                 # Linting
isort>=5.13.0                 # Import sorting
autoflake>=2.3.0              # Unused import removal
pre-commit>=3.8.0             # Git hook automation

# Coverage reporting
coverage>=7.10.0              # Coverage analysis and reporting
```

## Deployment

### Docker Support

- **Multi-stage Build**: Optimized for production (78-line Dockerfile)
- **Health Checks**: Built-in health check endpoint at `/health`
- **Environment Config**: Docker Compose with environment files
- **Port Configuration**: Standard port 8080 for HTTP in containers

### Production Considerations

- **Self-Contained**: No external FastMCP dependencies required
- **HTTPS**: TLS termination via reverse proxy recommended
- **Container-Ready**: Designed for containerized deployment
- **Monitoring**: Health check endpoint and comprehensive logging

## Standards Compliance

### Self-Contained MCP Best Practices

✅ **OpenAPI-First Approach** - All tools generated from OpenAPI specification
✅ **Container-Ready Design** - No external framework dependencies
✅ **Environment Variable Support** - FastMCP-compatible configuration
✅ **Comprehensive Testing** - 100% main.py coverage with 21 test cases
✅ **Quality Automation** - Pre-commit hooks with code formatting
✅ **Health Check Endpoints** - Standard `/health` endpoint

### Anti-Patterns to Avoid

❌ **External FastMCP Dependencies** - Use self-contained implementation
❌ **Complex Authentication** - Keep JWT configuration optional and simple
❌ **Non-standard Endpoints** - Follow MCP endpoint conventions
❌ **Missing Test Coverage** - Maintain comprehensive test suite

## Development Workflow

### NPM-Style Scripts (via package.json)

```bash
# Development and testing
npm run dev                    # Start development server
npm run test                   # Run test suite
npm run test:coverage         # Run tests with coverage reporting
npm run test:watch            # Run tests in watch mode

# Code quality and formatting
npm run lint:fix              # Auto-fix linting issues (autoflake + isort + black)
npm run format                # Format code with black (88-char lines)
npm run style:check           # Check code style without changes
npm run pre-commit:run        # Run all pre-commit hooks

# Docker operations
npm run docker:build          # Build Docker image
npm run docker:up            # Start with docker-compose
npm run docker:down          # Stop docker containers

# Utilities
npm run clean                 # Clean build artifacts and cache
npm run health               # Check server health endpoint
```

### Pre-commit Hook Automation

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict

  - repo: https://github.com/PyCQA/autoflake
    hooks:
      - id: autoflake
        args: [--remove-all-unused-imports, --remove-unused-variables, --in-place]

  - repo: https://github.com/PyCQA/isort
    hooks:
      - id: isort

  - repo: https://github.com/psf/black
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/PyCQA/flake8
    hooks:
      - id: flake8
```

## Implementation Notes

### 1. Self-Contained Design Philosophy

- **No External Framework Dependencies**: Custom MockFastMCP implementation eliminates FastMCP framework dependency
- **Container-Ready**: Designed specifically for Docker deployment without complex dependencies
- **OpenAPI-First**: All MCP tools automatically generated from comprehensive BMC OpenAPI specification (1263 lines)
- **Environment Flexible**: Works with or without authentication configuration

### 2. Production-Ready Features

- **Comprehensive Test Coverage**: 100% main.py coverage with 21 test cases including endpoint testing, error handling, and execution path validation
- **Quality Automation**: Pre-commit hooks with black (88-char), flake8, isort, autoflake
- **Docker Multi-stage Build**: Optimized 78-line Dockerfile with production best practices
- **Health Monitoring**: Standard `/health` endpoint for container orchestration

### 3. BMC AMI DevX Code Pipeline Integration

- **ISPW Operations**: Full CRUD operations for assignments, releases, and source code management
- **Mainframe DevOps**: Specialized tools for mainframe development lifecycle
- **Real BMC OpenAPI**: Uses actual BMC Compuware ISPW REST API specification
- **Token-Based Auth**: Optional JWT configuration for enterprise deployment

### 4. Testing Strategy

- **TestClient Integration**: Starlette TestClient for direct endpoint testing without running server
- **Mock Implementations**: unittest.mock for isolated component testing
- **Error Path Coverage**: Comprehensive error handling validation
- **Production Scenarios**: Container deployment testing and validation

### 5. Standards Compliance

- **MCP Protocol**: Standard MCP endpoints (`/mcp/capabilities`, `/mcp/tools/list`, `/mcp/tools/call`)
- **HTTP REST API**: Standard HTTP methods with JSON responses
- **CORS Enabled**: Cross-origin resource sharing for web integration
- **Environment Variables**: FastMCP-compatible variable naming patterns

## Recreating This Project

### Step 1: Project Setup

```bash
# Create project directory
mkdir fastmcp-code-pipeline-server
cd fastmcp-code-pipeline-server

# Initialize Python project
touch main.py test_mcp_server.py
mkdir config
touch config/openapi.json
```

### Step 2: Dependencies and Configuration

```bash
# Create requirements.txt with core dependencies
cat > requirements.txt << 'EOF'
starlette>=0.47.0
uvicorn>=0.35.0
httpx>=0.28.0
python-dotenv>=1.1.0
pytest>=8.4.0
pytest-asyncio>=1.1.0
pytest-cov>=6.2.0
black>=24.0.0
flake8>=7.0.0
isort>=5.13.0
autoflake>=2.3.0
pre-commit>=3.8.0
coverage>=7.10.0
EOF

# Create package.json for development workflow
cat > package.json << 'EOF'
{
  "name": "fastmcp-code-pipeline-server",
  "version": "2.2.0",
  "scripts": {
    "dev": "python main.py",
    "test": "python -m pytest",
    "test:coverage": "pytest --cov=. --cov-report=html --cov-report=term",
    "lint:fix": "python -m autoflake --remove-all-unused-imports --remove-unused-variables --in-place *.py && python -m isort *.py && python -m black *.py",
    "format": "python -m black *.py",
    "pre-commit:install": "pre-commit install",
    "docker:build": "docker-compose build",
    "docker:up": "docker-compose up --build"
  }
}
EOF

# Setup pre-commit hooks
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict
  - repo: https://github.com/PyCQA/autoflake
    rev: v2.3.1
    hooks:
      - id: autoflake
        args: [--remove-all-unused-imports, --remove-unused-variables, --in-place]
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.1
    hooks:
      - id: flake8
EOF
```

### Step 3: Core Implementation

1. **main.py**: Implement the MockFastMCP class with Starlette endpoints
2. **test_mcp_server.py**: Create comprehensive test suite with TestClient
3. **config/openapi.json**: Add BMC AMI DevX Code Pipeline OpenAPI specification
4. **Dockerfile**: Multi-stage Docker build for production deployment
5. **docker-compose.yml**: Container orchestration configuration

### Step 4: Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
npm run test:coverage

# Start development server
npm run dev
```

### Step 5: Validation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Test MCP capabilities
curl -X POST http://localhost:8000/mcp/capabilities

# Run comprehensive tests
npm run test:coverage

# Verify 100% main.py coverage achieved
```

This project represents a **self-contained, production-ready MCP server** implementation optimized for BMC AMI DevX Code Pipeline integration with comprehensive testing, quality automation, and containerized deployment capabilities. The MockFastMCP approach eliminates external framework dependencies while maintaining MCP protocol compliance and enterprise-grade reliability.
