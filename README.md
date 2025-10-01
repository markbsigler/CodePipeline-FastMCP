[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.12.2%2B-green)](https://gofastmcp.com/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/markbsigler/CodePipeline-FastMCP/actions)
[![Tests](https://img.shields.io/badge/tests-373%20passing-brightgreen)](https://github.com/markbsigler/CodePipeline-FastMCP/actions)

A **production-ready FastMCP 2.12.2** Model Context Protocol (MCP) server for **BMC AMI DevX Code Pipeline** mainframe DevOps operations. This server implements real FastMCP with native authentication, comprehensive input validation, retry logic, and enterprise-grade error handling.

## Features

### 🚀 **Production-Ready FastMCP 2.12.2 Implementation**
- ✅ **Real FastMCP Server**: Native FastMCP 2.12.2 implementation (no mock)
- ✅ **Streamable HTTP Transport**: FastMCP's recommended transport protocol
- ✅ **Native Authentication**: Multiple auth providers (JWT, GitHub, Google, WorkOS)
- ✅ **Comprehensive Validation**: Input validation for all API parameters
- ✅ **Retry Logic**: Exponential backoff for resilient API calls
- ✅ **Enterprise Error Handling**: Structured error responses and logging

### 🔐 **Authentication & Security**
- **JWT Token Verification**: Using FastMCP's `JWTVerifier` with JWKS support
- **GitHub OAuth**: `GitHubProvider` for GitHub-based authentication
- **Google OAuth**: `GoogleProvider` for Google Workspace integration
- **WorkOS AuthKit**: `AuthKitProvider` with Dynamic Client Registration
- **Environment Configuration**: Secure configuration via environment variables

### 🏗️ **BMC AMI DevX Code Pipeline Integration**
- **Assignment Management**: Create, list, update, and track mainframe assignments
- **Release Operations**: Manage release lifecycles and promotions
- **Source Code Management**: Handle COBOL, PL/I, and other mainframe source code
- **Real-time Updates**: Streaming build and deployment status via FastMCP Context
- **Mainframe DevOps**: Complete CI/CD pipeline integration with validation

### 🧪 **Testing & Quality** 
- **Comprehensive Test Suite**: 373 passing tests with 85% coverage (enterprise-grade reliability)
- **Consolidated Test Structure**: Streamlined test files with eliminated redundancy
- **Input Validation Tests**: Complete validation function coverage
- **Retry Logic Tests**: Exponential backoff and error handling validation  
- **Server Integration Tests**: FastMCP server creation and configuration
- **Error Handling Tests**: Validation error message testing
- **Enterprise Feature Tests**: Rate limiting, caching, metrics, error recovery

## How it Works

The server implements a real FastMCP 2.12.2 server that provides MCP tools for BMC AMI DevX Code Pipeline operations. Each tool includes comprehensive input validation, retry logic, and proper error handling. The server supports multiple authentication providers and uses FastMCP's native Streamable HTTP transport for real-time capabilities.

```mermaid
flowchart TD
    A[AI Assistant] -->|MCP Protocol| B[FastMCP 2.12.2 Server]
    B -->|Input Validation| V[Parameter Validation]
    B -->|Retry Logic| R[Exponential Backoff]
    B -->|Auth Provider| C[Authentication]
    C -->|JWT/GitHub/Google/WorkOS| D[Auth Verification]
    B -->|Validated Request| E[BMC AMI DevX API]
    E -->|Mainframe Operations| F[COBOL/PL1 Source]
    E -->|Release Management| G[Deployment Pipeline]
    E -->|Assignment Tracking| H[DevOps Workflow]
    B -->|Error Handling| I[Structured Responses]
    B -->|Context Logging| J[Progress Updates]
```

## BMC AMI DevX Code Pipeline OpenAPI Specification

The server uses the BMC AMI DevX Code Pipeline OpenAPI 3.x specification located in `config/openapi.json`. This spec defines mainframe DevOps operations including:

- **Assignment Operations**: Create, list, update assignments for mainframe development
- **Release Management**: Manage release lifecycles, promotions, and deployments
- **Source Code Operations**: Handle COBOL, PL/I, JCL, and other mainframe source files
- **Build Operations**: Trigger and monitor mainframe compilation and builds
- **Deployment Operations**: Deploy applications to mainframe environments

### OpenAPI Requirements

- Each operation must have a unique `operationId`
- Operations are auto-mapped to MCP tools (e.g., `createAssignment` → `create_assignment`)
- Authentication headers are handled automatically by FastMCP's JWT verifier
- Real-time operations use FastMCP's Streamable HTTP for progress updates

## Environment Configuration

The server supports both programmatic and environment-based configuration. Copy `config/.env.example` to `config/.env` and customize for your environment:

### Server Configuration
```bash
# Server settings
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=INFO

# BMC AMI DevX API settings
API_BASE_URL=https://devx.bmc.com/code-pipeline/api/v1
API_TIMEOUT=30
API_RETRY_ATTEMPTS=3
```

### Authentication Configuration

#### Option 1: JWT Token Verification (Recommended)
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.jwt.JWTVerifier
AUTH_JWKS_URI=https://your-auth-system.com/.well-known/jwks.json
AUTH_ISSUER=https://your-auth-system.com
AUTH_AUDIENCE=your-mcp-server
```

#### Option 2: GitHub OAuth
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.github.GitHubProvider
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID=Ov23li...
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET=github_pat_...
```

#### Option 3: Google OAuth
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.google.GoogleProvider
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=123456.apps.googleusercontent.com
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=GOCSPX-...
```

#### Option 4: WorkOS AuthKit (DCR Support)
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.workos.AuthKitProvider
FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN=https://your-project.authkit.app
```

### Development Mode (No Authentication)
```bash
AUTH_ENABLED=false
```

## Input Validation

The server includes comprehensive input validation for all parameters:

### SRID Validation
- **Format**: 1-8 alphanumeric characters
- **Example**: `TEST123`, `A1`, `12345678`
- **Invalid**: Empty strings, special characters, too long

### Assignment/Release ID Validation
- **Format**: 1-20 alphanumeric characters with hyphens/underscores
- **Example**: `ASSIGN-001`, `TASK_123`, `A1B2C3`
- **Invalid**: Empty strings, special characters, too long

### Environment Level Validation
- **Valid Values**: `DEV`, `TEST`, `STAGE`, `PROD`, `UAT`, `QA`
- **Case Insensitive**: `dev` → `DEV`
- **Invalid**: Any other values

## Error Handling

The server provides structured error responses with proper categorization:

### Validation Errors
```json
{
  "error": "Validation error: SRID must be 1-8 alphanumeric characters"
}
```

### HTTP Errors
```json
{
  "error": "HTTP error retrieving assignments: 404 Not Found"
}
```

### General Errors
```json
{
  "error": "Error retrieving assignments: Connection timeout"
}
```

## Troubleshooting

### Common Issues
- **Authentication Errors**: Verify JWT configuration and JWKS URI accessibility
- **Validation Errors**: Check parameter formats (SRID, assignment IDs, levels)
- **Connection Issues**: Verify API_BASE_URL and network connectivity
- **Retry Failures**: Check API timeout and retry attempt settings

## Contributing
- Fork the repo and create a feature branch.
- Follow PEP8 and existing code style.
- Add or update tests for new features.
- Open a pull request with a clear description.

## Example API Calls
```sh
curl -H "Authorization: Bearer <token>" http://localhost:8080/mcp/get_users
```
Or in Python:
```python
import httpx
resp = httpx.get("http://localhost:8080/mcp/get_users", headers={"Authorization": "Bearer <token>"})
print(resp.json())
```

## FastMCP Architecture

This server implements a **production-ready FastMCP implementation** following best practices:

### 🌟 **Unified Implementation**
- **Simplified FastMCP Patterns**: Direct instantiation, built-in auth providers
- **Enterprise Features**: Rate limiting, caching, metrics, error recovery
- **85% Test Coverage**: 373 comprehensive tests ensuring reliability
- **42% Code Reduction**: Maintainable codebase (833 lines vs previous 1,441)
- **FastMCP Best Practices**: Full alignment with official recommendations

### 🏗️ **Enterprise Features**
- **Rate Limiting**: Token bucket algorithm with configurable burst capacity
- **LRU/TTL Caching**: Intelligent caching with comprehensive management
- **Real-time Metrics**: Response times, success rates, uptime tracking
- **Error Recovery**: Exponential backoff retry with smart categorization
- **Connection Pooling**: Optimized HTTP client performance

## Quick Start

### Prerequisites

- Python 3.9+
- Docker (for containerized deployment)
- BMC AMI DevX Code Pipeline access (for production use)

### Local Development Setup

#### Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/markbsigler/CodePipeline-FastMCP.git
cd CodePipeline-FastMCP

# Run comprehensive setup script
./scripts/setup.sh
```

The setup script will:
- ✅ Verify Python 3.9+ requirement
- ✅ Create and configure virtual environment
- ✅ Install all dependencies including FastMCP 2.12.2
- ✅ Copy configuration templates
- ✅ Install pre-commit hooks
- ✅ Verify installation integrity

#### Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and edit)
cp config/.env.example config/.env
# Edit .env with your BMC AMI DevX Code Pipeline settings

# Install pre-commit hooks (optional)
pre-commit install
```

### Run FastMCP Server

```bash
# Development mode (no authentication)
AUTH_ENABLED=false python main.py

# Production mode (with authentication)
python main.py
```

The server will start on `http://localhost:8080` with the following endpoints:

- **MCP Endpoint**: `http://localhost:8080/mcp/` (Streamable HTTP transport)
- **Health Check**: `http://localhost:8080/health`
- **Available Tools**: Auto-generated from BMC AMI DevX Code Pipeline OpenAPI spec

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build Docker image manually
docker build -t fastmcp-code-pipeline .
docker run -p 8080:8080 -e AUTH_ENABLED=false fastmcp-code-pipeline
```

### Testing the Server

#### Automated Testing (Recommended)

```bash
# Run comprehensive test suite
./scripts/test.sh
```

The test script provides:
- ✅ **Automated Server Management**: Starts server, waits for health check, runs tests, cleanup
- ✅ **Multi-tier Testing**: Unit tests, integration tests, coverage analysis
- ✅ **Virtual Environment Detection**: Automatically uses .venv/bin/python if available
- ✅ **Comprehensive Reporting**: Detailed test results and coverage metrics
- ✅ **Error Diagnostics**: Server logs on test failures

#### Manual Testing

```bash
# Check server health
curl http://localhost:8080/health

# Test MCP capabilities endpoint
curl -X POST http://localhost:8080/mcp/capabilities

# Run specific test categories
pytest tests/test_main.py -v                          # Main functionality tests
pytest tests/test_fastmcp_server.py -v                # Integration tests
pytest tests/test_openapi_server.py -v                # OpenAPI server tests
```

## Development Scripts

The project includes comprehensive automation scripts in the `scripts/` directory:

### setup.sh - Development Environment Setup
```bash
./scripts/setup.sh
```

**Features:**
- 🐍 **Python Environment**: Creates virtual environment, installs dependencies
- ⚙️ **Configuration**: Sets up .env files and OpenAPI specifications
- 🔧 **Development Tools**: Installs pre-commit hooks, creates directories
- ✅ **Verification**: Tests imports and dependency availability
- 📋 **Guidance**: Provides next steps and available commands

### test.sh - Comprehensive Testing
```bash
./scripts/test.sh
```

**Features:**
- 🚀 **Server Management**: Background server startup with health checks
- 🧪 **Multi-tier Testing**: Unit, integration, and coverage tests
- 📊 **Detailed Reporting**: Test results summary and coverage metrics
- 🛡️ **Error Handling**: Automatic cleanup and diagnostic logging
- ⏱️ **Timeout Protection**: Prevents hanging on server startup failures

### deploy.sh - Production Deployment
```bash
./scripts/deploy.sh [compose|docker]
```

**Features:**
- 🐳 **Deployment Modes**: Docker Compose (recommended) or plain Docker
- 💾 **Backup & Rollback**: Automatic image backup with rollback on failure
- 🏥 **Health Monitoring**: Comprehensive health checks with timeout
- 🧹 **Cleanup**: Automatic cleanup of old backup images
- 📋 **Management**: Complete deployment verification and status reporting

### NPM-Style Development Commands

The project provides familiar npm-style commands via `package.json`:

```bash
# Development workflow
npm run dev              # Start development server
npm run test             # Run test suite
npm run test:coverage    # Run tests with coverage reporting
npm run test:watch       # Run tests in watch mode

# Code quality
npm run lint:fix         # Auto-fix code formatting (autoflake + isort + black)
npm run format           # Format code with black
npm run style:check      # Check code style without changes
npm run pre-commit:run   # Run all pre-commit hooks

# Docker operations
npm run docker:build     # Build Docker image
npm run docker:up        # Start with docker-compose
npm run docker:down      # Stop docker containers

# Utilities
npm run clean            # Clean build artifacts and cache
npm run health           # Check server health endpoint
```

## MCP Tools Available

The server provides comprehensive MCP tools for BMC AMI DevX Code Pipeline operations with full input validation and error handling:

### Assignment Management Tools
- `get_assignments` - List assignments with filtering by level and assignment ID
- `create_assignment` - Create new mainframe development assignments
- `get_assignment_details` - Get detailed assignment information
- `get_assignment_tasks` - Retrieve tasks for a specific assignment

### Release Management Tools
- `get_releases` - List available releases with optional filtering
- `create_release` - Create new release for deployment

### Operation Tools
- `generate_assignment` - Generate assignment with runtime configuration
- `promote_assignment` - Promote assignment through lifecycle stages
- `deploy_assignment` - Deploy assignment to target environment

### Tool Features
- **Input Validation**: All parameters validated for format and content
- **Error Handling**: Structured error responses with proper categorization
- **Retry Logic**: Automatic retry with exponential backoff for failed requests
- **Progress Reporting**: Real-time updates via FastMCP Context
- **Authentication**: Secure access via configured authentication provider

## Security and Authentication

The server implements enterprise-grade security with multiple authentication options:

### Authentication Providers
- **JWT Token Verification**: Using FastMCP's `JWTVerifier` with JWKS support
- **GitHub OAuth**: `GitHubProvider` for GitHub-based authentication
- **Google OAuth**: `GoogleProvider` for Google Workspace integration
- **WorkOS AuthKit**: `AuthKitProvider` with Dynamic Client Registration support

### Security Features
- **JWKS Support**: Automatic key rotation and validation
- **Token Introspection**: Remote token validation support
- **Environment-based Config**: Secure configuration management
- **Input Validation**: Comprehensive parameter validation
- **HTTPS Support**: TLS termination via reverse proxy
- **Error Handling**: Secure error responses without sensitive data exposure

## Production Deployment

For production deployment with BMC AMI DevX Code Pipeline:

1. **Configure Authentication**: Choose and configure your authentication provider
2. **Set API Base URL**: Point to your BMC AMI DevX Code Pipeline instance
3. **Configure Environment**: Copy `config/.env.example` to `config/.env` and customize
4. **Deploy with Docker**: Use provided Docker Compose configuration
5. **Monitor Health**: Use `/health` endpoint for monitoring
6. **Configure Logging**: Set appropriate log levels for production
7. **Test Validation**: Verify input validation and error handling

## Troubleshooting

### Common Issues

- **Authentication Errors**: Verify JWT configuration and JWKS URI accessibility
- **Connection Issues**: Check API_BASE_URL and network connectivity to BMC AMI DevX
- **Tool Not Found**: Verify OpenAPI spec contains required operationId
- **Performance Issues**: Adjust timeout and retry settings for mainframe operations

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python main.py

# Disable authentication for testing
AUTH_ENABLED=false python main.py

# Run tests to verify functionality
pytest test_simple.py -v
```

## Recent Changes (v2.2.0)

### 🚀 **Major Refactoring - Real FastMCP Implementation**
This version represents a complete transformation from a mock implementation to a production-ready FastMCP 2.12.2 server:

#### ✅ **Completed Improvements**
- **Real FastMCP Server**: Replaced MockFastMCP with native FastMCP 2.12.2 implementation
- **Native Authentication**: Added support for JWT, GitHub, Google, and WorkOS authentication providers
- **Input Validation**: Comprehensive validation for all API parameters (SRID, assignment IDs, levels)
- **Retry Logic**: Exponential backoff for resilient API calls
- **Error Handling**: Structured error responses with proper categorization
- **Testing**: Complete test suite with 373 passing tests and 85% coverage
- **Documentation**: Updated configuration examples and troubleshooting guides

#### 🔧 **Technical Changes**
- Updated dependencies to use real FastMCP 2.12.2
- Implemented `@server.tool` decorators for MCP tool registration
- Added FastMCP Context for logging and progress reporting
- Created comprehensive validation functions with regex patterns
- Implemented retry decorator with exponential backoff
- Added environment-based configuration support

#### 📁 **New Files**
- `config/.env.example` - Comprehensive configuration examples
- `tests/test_main.py` - Consolidated main functionality tests (373 tests, all passing)
- `tests/test_fastmcp_server.py` - Integration test suite
- `tests/test_openapi_server.py` - OpenAPI server test suite

#### 🗑️ **Removed**
- MockFastMCP class and related mock functionality
- Redundant dependencies (starlette, uvicorn, etc.)
- Mock authentication middleware

## Architecture Diagrams

### FastMCP Authentication Flow

```mermaid
sequenceDiagram
    participant Client as AI Assistant
    participant Server as FastMCP Server
    participant Auth as JWT Verifier
    participant API as BMC AMI DevX API

    Client->>Server: MCP Request with JWT
    Server->>Auth: Validate JWT Token
    Auth->>Auth: Check JWKS & Claims
    Auth-->>Server: Token Valid/Invalid
    alt Token Valid
        Server->>API: API Request with Auth
        API-->>Server: BMC AMI DevX Response
        Server-->>Client: MCP Tool Result
    else Token Invalid
        Server-->>Client: Authentication Error
    end
```

### BMC AMI DevX Code Pipeline Integration

```mermaid
sequenceDiagram
    participant AI as AI Assistant
    participant MCP as FastMCP Server
    participant BMC as BMC AMI DevX API
    participant Mainframe as Mainframe System

    AI->>MCP: create_assignment(name, description)
    MCP->>BMC: POST /assignments
    BMC->>Mainframe: Create Assignment
    Mainframe-->>BMC: Assignment Created
    BMC-->>MCP: Assignment Details
    MCP-->>AI: Assignment Created Successfully

    AI->>MCP: get_build_status(assignmentId)
    MCP->>BMC: GET /assignments/{id}/builds
    BMC->>Mainframe: Check Build Status
    Mainframe-->>BMC: Build Progress
    BMC-->>MCP: Streaming Build Status
    MCP-->>AI: Real-time Build Updates
```

### Container Architecture

```mermaid
flowchart TB
    subgraph "Docker Container"
        FastMCP[FastMCP Server - Python 3.11]
        Config[config/openapi.json - BMC AMI DevX Spec]
        Health[Health Endpoint]
    end

    subgraph "External Systems"
        AI[AI Assistant - MCP Client]
        JWT[JWT Provider - JWKS Endpoint]
        BMC[BMC AMI DevX - Code Pipeline API]
        Mainframe[Mainframe - COBOL/PL1/JCL]
    end

    AI -->|MCP Protocol| FastMCP
    FastMCP -->|JWT Validation| JWT
    FastMCP -->|API Requests| BMC
    BMC -->|DevOps Operations| Mainframe
    FastMCP -->|Health Check| Health
    Config -->|OpenAPI Spec| FastMCP
```
