# FastMCP OpenAPI Server

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your/repo/actions)

A production-ready FastMCP server implementation generated from an OpenAPI/Swagger specification. This server is written in Python, uses the latest FastMCP (2.x), supports real-time streamable HTTP, Bearer token authentication, OpenAPI-based tool generation, and is optimized for Docker deployment.

## Features
- Auto-generates MCP tools from OpenAPI/Swagger specs
- Streamable HTTP endpoints
- Bearer token & API key authentication
- Multi-stage Docker build for production
- Health checks, logging, and monitoring
- Comprehensive error handling
- Automated tests with pytest

## How it Works
FastMCP reads your OpenAPI 3.x spec from `config/openapi.json` and auto-generates MCP tools for each operationId. When a request is made to a tool, FastMCP routes it to the corresponding OpenAPI endpoint. If no backend is implemented, a 404 is returned by default. To use your own API, replace `config/openapi.json` with your actual OpenAPI spec file.

## OpenAPI Spec Requirements
- Place your OpenAPI 3.x spec in `config/openapi.json` (replacing the example if needed).
- Each operation must have a unique `operationId`.
- Only HTTP methods and paths defined in the spec are exposed as tools.
- Example minimal spec:

```json
{
  "openapi": "3.0.0",
  "info": { "title": "Demo API", "version": "1.0" },
  "paths": {
    "/hello": {
      "get": {
        "summary": "Say hello",
        "operationId": "hello_world",
        "responses": { "200": { "description": "A greeting." } }
      }
    }
  }
}
```

## Adding a Real Backend
To implement real logic, add backend handlers in your FastMCP server for each endpoint. See the FastMCP documentation or the `main.py` comments for guidance. Be sure to replace `config/openapi.json` with your actual OpenAPI spec to expose your own API operations as tools.

## Environment Variables
- `PORT`: Port to run the server (default: 8080)
- `API_BASE_URL`: Base URL for HTTP client (default: http://localhost:8080)
- `MCP_SERVER_URL`: URL for test client (default: http://127.0.0.1:8080/mcp/)
- Auth and other variables can be set in `.env`

## Troubleshooting
- **404 on tool calls:** No backend is implemented for the endpoint. Add a handler in your server.
- **Tool not found:** Check your OpenAPI spec for correct `operationId` and path.
- **Dependency issues:** Ensure you are using Python 3.11+ and have installed all requirements.

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

## Quick Start

### Prerequisites
- Python 3.11+
- Docker (for containerized deployment)

### Setup
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or pip install .
cp config/openapi.example.json config/openapi.json
```

### Run Locally
```sh
python main.py
```

### Run Automated Tests
```sh
./scripts/test.sh
# or manually:
pytest
```

### Run with Docker
```sh
docker-compose up --build
```

## Configuration
- See `config/openapi.json` for OpenAPI spec example
- Place your OpenAPI spec in `config/openapi.json`
- Environment variables can be set in `.env` (see Dockerfile and scripts for usage)

## Deployment
- See `docs/deployment.md` for full deployment guide

## API Documentation
- See `docs/api-reference.md` for auto-generated API docs

## Security
- Bearer token validation
- API key management
- CORS & security headers
- Audit logging

## Example Usage
- Load OpenAPI spec: `config/openapi.json`
- Configure tokens: `.env` or environment variables
- Start server: `python main.py` or Docker
- Make authenticated API calls with Bearer token

## Testing & Troubleshooting
- The server exposes tools based on your OpenAPI spec, but without a backend implementation, tool calls will return HTTP 404 Not Found by default.
- The test suite expects and validates this behavior.
- Run `./scripts/test.sh` to start the server, run tests, and shut down
- Logs and errors are output to the console and `server_test.log`
- For advanced usage or debugging, see `test_mcp_server.py` and `scripts/`

## Testing Docker Container Health
To test the Docker container and verify it starts correctly, you can use the built-in healthcheck endpoint. This is useful for CI/CD or local validation.

### Example: Run container, check health, then exit
```sh
docker-compose up --build &
CONTAINER_ID=$(docker ps -qf "name=fastmcp-server")
# Wait for healthcheck to pass (adjust timeout as needed)
docker inspect --format='{{json .State.Health.Status}}' $CONTAINER_ID
# Or poll until healthy:
while [[ $(docker inspect --format='{{json .State.Health.Status}}' $CONTAINER_ID) != '"healthy"' ]]; do sleep 1; done
# Optionally, test the endpoint directly:
curl http://localhost:8080/healthz
# Stop the container after test:
docker-compose down
```

The `/healthz` endpoint returns 200 OK if the server is healthy. You can script this in CI to ensure the container is ready before running further tests or deployments.

---

For more details, see the `docs/` directory.
