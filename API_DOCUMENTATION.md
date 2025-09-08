# BMC AMI DevX Code Pipeline FastMCP Server API Documentation

## Overview

The BMC AMI DevX Code Pipeline FastMCP Server provides a Model Context Protocol (MCP) interface for mainframe DevOps operations. This server implements FastMCP 2.12.2 with comprehensive input validation, retry logic, and enterprise-grade authentication.

## Server Information

- **Name**: BMC AMI DevX Code Pipeline MCP Server
- **Version**: 2.2.0
- **FastMCP Version**: 2.12.2
- **Transport**: Streamable HTTP
- **Base URL**: `http://localhost:8080/mcp`

## Authentication

The server supports multiple authentication providers:

### JWT Token Verification
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.jwt.JWTVerifier
AUTH_JWKS_URI=https://your-auth-system.com/.well-known/jwks.json
AUTH_ISSUER=https://your-auth-system.com
AUTH_AUDIENCE=your-mcp-server
```

### GitHub OAuth
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.github.GitHubProvider
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID=Ov23li...
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET=github_pat_...
```

### Google OAuth
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.google.GoogleProvider
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=123456.apps.googleusercontent.com
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=GOCSPX-...
```

### WorkOS AuthKit
```bash
AUTH_ENABLED=true
AUTH_PROVIDER=fastmcp.server.auth.providers.workos.AuthKitProvider
FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN=https://your-project.authkit.app
```

## Input Validation

All tools include comprehensive input validation:

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

## MCP Tools

### Assignment Management Tools

#### get_assignments
Retrieve assignments for a specific SRID with optional filtering.

**Parameters:**
- `srid` (string, required): System/Resource ID (1-8 alphanumeric characters)
- `level` (string, optional): Environment level (DEV, TEST, STAGE, PROD, UAT, QA)
- `assignment_id` (string, optional): Specific assignment ID to retrieve

**Example:**
```json
{
  "name": "get_assignments",
  "arguments": {
    "srid": "TEST123",
    "level": "DEV",
    "assignment_id": "ASSIGN-001"
  }
}
```

**Response:**
```json
{
  "assignments": [
    {
      "id": "ASSIGN-001",
      "name": "Test Assignment",
      "status": "active",
      "level": "DEV"
    }
  ]
}
```

#### create_assignment
Create a new mainframe development assignment.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID
- `stream` (string, required): Stream name
- `application` (string, required): Application name

**Example:**
```json
{
  "name": "create_assignment",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-002",
    "stream": "STREAM1",
    "application": "APP1"
  }
}
```

#### get_assignment_details
Get detailed information for a specific assignment.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID

**Example:**
```json
{
  "name": "get_assignment_details",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-001"
  }
}
```

#### get_assignment_tasks
Retrieve tasks for a specific assignment.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID

**Example:**
```json
{
  "name": "get_assignment_tasks",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-001"
  }
}
```

### Release Management Tools

#### get_releases
List available releases with optional filtering.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `release_id` (string, optional): Specific release ID to retrieve

**Example:**
```json
{
  "name": "get_releases",
  "arguments": {
    "srid": "TEST123",
    "release_id": "REL-001"
  }
}
```

#### create_release
Create a new release for deployment.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `release_id` (string, required): Release ID
- `stream` (string, required): Stream name
- `application` (string, required): Application name

**Example:**
```json
{
  "name": "create_release",
  "arguments": {
    "srid": "TEST123",
    "release_id": "REL-002",
    "stream": "STREAM1",
    "application": "APP1"
  }
}
```

### Operation Tools

#### generate_assignment
Generate assignment with runtime configuration.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID
- `level` (string, optional): Environment level
- `runtime_configuration` (string, optional): Runtime configuration

**Example:**
```json
{
  "name": "generate_assignment",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-001",
    "level": "DEV",
    "runtime_configuration": "config1"
  }
}
```

#### promote_assignment
Promote assignment through lifecycle stages.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID
- `level` (string, optional): Target environment level
- `change_type` (string, optional): Type of change

**Example:**
```json
{
  "name": "promote_assignment",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-001",
    "level": "TEST",
    "change_type": "minor"
  }
}
```

#### deploy_assignment
Deploy assignment to target environment.

**Parameters:**
- `srid` (string, required): System/Resource ID
- `assignment_id` (string, required): Assignment ID
- `level` (string, optional): Target environment level
- `deploy_implementation_time` (string, optional): Implementation time

**Example:**
```json
{
  "name": "deploy_assignment",
  "arguments": {
    "srid": "TEST123",
    "assignment_id": "ASSIGN-001",
    "level": "PROD",
    "deploy_implementation_time": "2025-01-09T10:00:00Z"
  }
}
```

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

## Retry Logic

The server implements automatic retry logic with exponential backoff:

- **Max Retries**: 3 attempts (configurable via `API_RETRY_ATTEMPTS`)
- **Backoff Strategy**: Exponential backoff (1s, 2s, 4s)
- **Retry Conditions**: HTTP errors and timeout exceptions
- **No Retry**: Validation errors and other non-retryable errors

## Health Check

The server provides a health check endpoint:

**Endpoint**: `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "name": "BMC AMI DevX Code Pipeline MCP Server",
  "version": "2.2.0",
  "timestamp": "2025-01-09T10:00:00Z"
}
```

## Configuration

### Server Configuration
```bash
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=INFO
API_BASE_URL=https://devx.bmc.com/code-pipeline/api/v1
API_TIMEOUT=30
API_RETRY_ATTEMPTS=3
```

### Authentication Configuration
See the Authentication section above for provider-specific configuration.

## Examples

### Basic Tool Call
```bash
curl -X POST http://localhost:8080/mcp/tools/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "get_assignments",
    "arguments": {
      "srid": "TEST123",
      "level": "DEV"
    }
  }'
```

### Health Check
```bash
curl http://localhost:8080/health
```

### MCP Capabilities
```bash
curl -X POST http://localhost:8080/mcp/capabilities
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify JWT configuration and JWKS URI accessibility
   - Check token validity and expiration
   - Ensure correct audience and issuer settings

2. **Validation Errors**
   - Check parameter formats (SRID, assignment IDs, levels)
   - Verify required parameters are provided
   - Ensure parameter values meet validation criteria

3. **Connection Issues**
   - Verify API_BASE_URL and network connectivity
   - Check firewall and proxy settings
   - Ensure BMC AMI DevX API is accessible

4. **Retry Failures**
   - Check API timeout and retry attempt settings
   - Verify API endpoint availability
   - Review server logs for detailed error information

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
LOG_LEVEL=DEBUG python main.py
```

### Testing

Run the test suite to verify functionality:

```bash
pytest test_simple.py -v
```

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review server logs for detailed error information
3. Run the test suite to verify functionality
4. Check the GitHub repository for known issues
5. Create an issue with detailed error information and logs
