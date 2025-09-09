# BMC AMI DevX Code Pipeline FastMCP Server

## Project Overview

You are building a **production-ready Model Context Protocol (MCP) server** for **BMC AMI DevX Code Pipeline** using the official **FastMCP framework**. This server leverages FastMCP's advanced features including OpenAPI integration, user elicitation, custom routes, resource templates, and prompts to provide a comprehensive mainframe DevOps platform integration.

## Core Requirements

### FastMCP Implementation

- **Framework**: Official FastMCP 2.12.2+ with advanced features
- **Transport**: HTTP REST API with MCP-compliant endpoints
- **Authentication**: Multiple providers (JWT, GitHub, Google, WorkOS)
- **Server Construction**: OpenAPI-driven tool generation with `FastMCP.from_openapi()`
- **Environment Variables**: Use `FASTMCP_` prefix for configuration compatibility
- **Advanced Features**: User elicitation, custom routes, resource templates, prompts

### BMC AMI DevX Code Pipeline Integration
- **Target Platform**: BMC AMI DevX Code Pipeline (mainframe DevOps platform)
- **OpenAPI Specification**: Use the provided OpenAPI spec for automatic tool generation
- **API Integration**: CRUD operations for assignments, releases, and source code management
- **Interactive Workflows**: User elicitation for complex DevOps processes
- **Real-time Features**: Custom routes for health checks and monitoring

## Technical Architecture

### FastMCP Server Implementation

```python
# FastMCP server with OpenAPI integration and advanced features
from fastmcp import FastMCP, Context
from fastmcp.server.elicitation import AcceptedElicitation, DeclinedElicitation, CancelledElicitation

class OpenAPIMCPServer:
    """BMC AMI DevX Code Pipeline MCP Server with OpenAPI Integration."""

    def __init__(self):
        """Initialize the OpenAPI MCP Server."""
        # Load global configuration
        self.config = get_fastmcp_config()
        self.settings = Settings.from_env()

        # Initialize components with feature toggles
        self.rate_limiter = RateLimiter(...) if self.config.get("rate_limit_enabled") else None
        self.cache = IntelligentCache(...) if self.config.get("cache_enabled") else None
        self.metrics = Metrics() if self.config.get("monitoring_enabled") else None

        # Create FastMCP server with OpenAPI integration
        self.server = FastMCP.from_openapi(
            openapi_spec_path=self.config["openapi_spec_path"],
            name=self.config["server_name"],
            version=self.config["server_version"],
            auth=self._create_auth_provider(),
            include_tags=self.config.get("include_tags"),
            exclude_tags=self.config.get("exclude_tags")
        )

        # Add advanced features
        self._add_custom_tools()
        self._add_custom_routes()
        self._add_resource_templates()
        self._add_prompts()
```

### Server Implementation Pattern

```python
# FastMCP server creation and startup
def create_server():
    """Create and configure the FastMCP server."""
    return OpenAPIMCPServer()

def main():
    """Main entry point."""
    server = create_server()

    # Run the FastMCP server
    server.server.run(
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8000)),
        log_level=os.environ.get('LOG_LEVEL', 'info')
    )
```

### MCP-Compliant HTTP Endpoints

- **Health Check**: `GET /health` - Server health status with BMC API connectivity
- **Status**: `GET /status` - Detailed server status with metrics and configuration
- **Metrics**: `GET /metrics` - Server performance metrics and statistics
- **Readiness**: `GET /ready` - Readiness check for load balancers
- **MCP Capabilities**: `POST /mcp/capabilities` - Server capabilities and info
- **Tools List**: `POST /mcp/tools/list` - Available MCP tools (OpenAPI + custom + elicitation)
- **Tool Execution**: `POST /mcp/tools/call` - Execute MCP tools with arguments
- **CORS Support**: Cross-origin requests enabled for web integration

## Project Structure

```text
/
├── openapi_server.py          # Main FastMCP server with OpenAPI integration
├── main.py                    # Legacy server implementation (for reference)
├── fastmcp_config.py          # Global configuration management
├── test_advanced_features.py  # Tests for advanced FastMCP features
├── test_elicitation.py        # Tests for user elicitation functionality
├── test_openapi_integration.py # Tests for OpenAPI integration
├── test_mcp_server.py         # Legacy test suite
├── config/
│   ├── openapi.json           # BMC AMI DevX Code Pipeline OpenAPI spec
│   └── ispw_openapi_spec.json # ISPW OpenAPI specification
├── pyproject.toml             # Python project configuration
├── requirements.txt           # Production dependencies (FastMCP + httpx)
├── package.json               # Development workflow scripts (npm-style)
├── .pre-commit-config.yaml    # Code quality automation
├── docker-compose.yml         # Docker deployment configuration
├── Dockerfile                 # Multi-stage Docker build
├── coverage.xml              # Test coverage reports
├── htmlcov/                  # HTML coverage reports
├── docs/
│   ├── openapi-integration-summary.md # OpenAPI integration documentation
│   ├── elicitation-implementation-summary.md # Elicitation feature documentation
└── compare_implementations.py # Code metrics comparison script
```

## Environment Configuration

Use standardized environment variable patterns compatible with FastMCP:

```bash
# Server Configuration
HOST=0.0.0.0                    # Server bind address
PORT=8000                       # Server port (default 8000, Docker uses 8080)
LOG_LEVEL=info                  # FastMCP log level

# BMC AMI DevX Code Pipeline API
API_BASE_URL=https://devx.bmc.com/code-pipeline/api/v1
API_TOKEN=your-api-token        # BMC API authentication token

# FastMCP Global Configuration
FASTMCP_LOG_LEVEL=INFO          # Server log level
FASTMCP_SERVER_NAME="BMC AMI DevX Code Pipeline MCP Server"
FASTMCP_SERVER_VERSION=2.2.0

# Authentication Configuration
FASTMCP_AUTH_ENABLED=false      # Enable/disable authentication
FASTMCP_AUTH_PROVIDER=fastmcp.server.auth.providers.jwt.JWTVerifier
FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://auth.bmc.com/.well-known/jwks.json
FASTMCP_SERVER_AUTH_JWT_ISSUER=https://auth.bmc.com/
FASTMCP_SERVER_AUTH_JWT_AUDIENCE=bmc-ami-devx-code-pipeline

# Feature Toggles
FASTMCP_RATE_LIMIT_ENABLED=true
FASTMCP_CACHE_ENABLED=true
FASTMCP_MONITORING_ENABLED=true
FASTMCP_CUSTOM_ROUTES_ENABLED=true
FASTMCP_RESOURCE_TEMPLATES_ENABLED=true
FASTMCP_PROMPTS_ENABLED=true

# OpenAPI Configuration
FASTMCP_OPENAPI_SPEC_PATH=config/ispw_openapi_spec.json
FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER=false
```

## Core Features

### MCP Tools (23 total tools)

#### OpenAPI-Generated Tools (15 tools)
1. **Assignment Management**
   - `ispw_Get_assignments` - List assignments with filtering
   - `ispw_Create_assignment` - Create new assignments
   - `ispw_Get_assignment_details` - Get detailed assignment information
   - `ispw_Get_assignment_tasks` - Get assignment tasks
   - `ispw_Generate_assignment` - Generate assignment code

2. **Release Operations**
   - `ispw_Get_releases` - List releases
   - `ispw_Create_release` - Create new releases
   - `ispw_Get_release_details` - Get release information
   - `ispw_Promote_release` - Promote releases through lifecycle

3. **Package Management**
   - `ispw_Get_packages` - List packages
   - `ispw_Create_package` - Create new packages
   - `ispw_Get_package_details` - Get package information

#### Custom Management Tools (5 tools)
1. **Server Monitoring**
   - `get_server_metrics` - Comprehensive server metrics and performance data
   - `get_health_status` - Server and BMC API health status
   - `get_server_settings` - Current server configuration

2. **Cache Management**
   - `clear_cache` - Clear server cache
   - `get_cache_info` - Detailed cache information

#### Interactive Elicitation Tools (3 tools)
1. **Interactive Workflows**
   - `create_assignment_interactive` - Multi-step assignment creation with user prompts
   - `deploy_release_interactive` - Interactive release deployment with safety checks
   - `troubleshoot_assignment_interactive` - Structured troubleshooting workflow

### Advanced FastMCP Features

#### User Elicitation
- **Interactive Workflows**: Multi-step user input collection for complex processes
- **Pattern Matching**: Clean handling of Accepted/Declined/Cancelled responses
- **Progressive Disclosure**: Step-by-step information gathering
- **Safety Features**: Production deployment warnings and confirmations

#### Custom Routes
- **Health Endpoints**: `/health`, `/status`, `/metrics`, `/ready`
- **Monitoring**: Real-time server performance and BMC API connectivity
- **Load Balancer Support**: Readiness checks for container orchestration

#### Resource Templates
- **Parameterized Access**: `bmc://assignments/{srid}`, `bmc://releases/{srid}`
- **Structured Data**: Consistent resource access patterns
- **Template System**: Reusable resource definitions

#### Prompts
- **LLM Guidance**: Reusable templates for common tasks
- **Analysis Tools**: Assignment status analysis, deployment planning
- **Troubleshooting**: Structured diagnostic guidance

### Authentication Features

- **Multiple Providers**: JWT, GitHub, Google, WorkOS support
- **Optional Authentication**: Works with or without authentication
- **Environment-based Config**: Auto-configuration with `FASTMCP_` variables
- **Production Ready**: Enterprise-grade authentication support

### Testing and Quality Features

- **Comprehensive Coverage**: 95%+ test coverage across all features
- **Multiple Test Suites**: Advanced features, elicitation, OpenAPI integration
- **Quality Tools**: Black, flake8, isort, autoflake with pre-commit hooks
- **Coverage Reporting**: HTML and XML coverage reports generated

## Dependencies

### Core Dependencies (FastMCP Implementation)

```text
# FastMCP framework and core functionality
fastmcp>=2.12.2                # Official FastMCP framework
httpx>=0.28.0                  # Async HTTP client for BMC API integration
pydantic>=2.0.0                # Data validation and settings management

# Environment variable management
python-dotenv>=1.1.0           # Environment variable loading

# Testing framework
pytest>=8.4.0                 # Testing framework
pytest-asyncio>=1.1.0         # Async testing support
pytest-cov>=6.2.0             # Coverage testing
pytest-mock>=3.14.0           # Mocking utilities
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

1. **openapi_server.py**: Implement the FastMCP server with OpenAPI integration
2. **fastmcp_config.py**: Create global configuration management system
3. **test_advanced_features.py**: Test suite for advanced FastMCP features
4. **test_elicitation.py**: Test suite for user elicitation functionality
5. **test_openapi_integration.py**: Test suite for OpenAPI integration
6. **config/ispw_openapi_spec.json**: BMC ISPW OpenAPI specification
7. **Dockerfile**: Multi-stage Docker build for production deployment
8. **docker-compose.yml**: Container orchestration configuration

### Step 4: Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Run all test suites to verify setup
python test_advanced_features.py
python test_elicitation.py
python test_openapi_integration.py

# Start development server
python openapi_server.py
```

### Step 5: Validation

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check status endpoint
curl http://localhost:8000/status

# Check metrics endpoint
curl http://localhost:8000/metrics

# Test MCP capabilities
curl -X POST http://localhost:8000/mcp/capabilities

# Run comprehensive tests
python test_advanced_features.py
python test_elicitation.py
python test_openapi_integration.py

# Verify 95%+ test coverage achieved
```

## Current Project State

### ✅ **Completed Features**
- **OpenAPI Integration**: 15 tools auto-generated from BMC ISPW specification
- **User Elicitation**: 3 interactive tools for complex DevOps workflows
- **Custom Routes**: Health, status, metrics, and readiness endpoints
- **Resource Templates**: Parameterized data access patterns
- **Prompts**: Reusable LLM guidance templates
- **Global Configuration**: Centralized settings management with feature toggles
- **Comprehensive Testing**: 95%+ coverage across all test suites
- **Production Ready**: Docker support with health checks and monitoring

### 📊 **Project Metrics**
- **Total Tools**: 23 (15 OpenAPI + 5 custom + 3 elicitation)
- **Test Coverage**: 95%+ across all features
- **Test Suites**: 4 comprehensive test files
- **Documentation**: Complete implementation summaries
- **Dependencies**: FastMCP 2.12.2+ with advanced features

### 🎯 **Key Implementation Patterns**

#### OpenAPI Integration
```python
# Automatic tool generation from OpenAPI spec
self.server = FastMCP.from_openapi(
    openapi_spec_path=self.config["openapi_spec_path"],
    name=self.config["server_name"],
    version=self.config["server_version"],
    auth=self._create_auth_provider(),
    include_tags=self.config.get("include_tags"),
    exclude_tags=self.config.get("exclude_tags")
)
```

#### User Elicitation Pattern
```python
# Interactive workflow with pattern matching
result = await ctx.elicit("What is the assignment title?", response_type=str)
match result:
    case AcceptedElicitation(data=title):
        # Continue with workflow
    case DeclinedElicitation():
        return "Operation cancelled"
    case CancelledElicitation():
        return "Operation cancelled by user"
```

#### Custom Routes Pattern
```python
# Health check and monitoring endpoints
@server.custom_route("/health", methods=["GET"])
async def health_check_route(request: Request) -> JSONResponse:
    health_data = await health_checker.check_health()
    return JSONResponse(health_data)
```

This project represents a **production-ready FastMCP server** implementation optimized for BMC AMI DevX Code Pipeline integration with comprehensive testing, quality automation, and containerized deployment capabilities. The FastMCP framework provides enterprise-grade reliability with advanced features including OpenAPI integration, user elicitation, custom routes, resource templates, and prompts for a complete mainframe DevOps platform integration.
