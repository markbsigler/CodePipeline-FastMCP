# FastMCP OpenAPI Server

A production-ready FastMCP server implementation generated from an OpenAPI/Swagger specification. This server supports real-time streamable HTTP, Bearer token authentication, OpenAPI-based tool generation, and is optimized for Docker deployment.

## Features
- Auto-generates MCP tools from OpenAPI/Swagger specs
- Streamable HTTP endpoints
- Bearer token & API key authentication
- Multi-stage Docker build for production
- Health checks, logging, and monitoring
- Comprehensive error handling

## Architecture

### System Overview
```mermaid
flowchart TD
    Client-->|HTTP/WebSocket|FastMCP[FastMCP Server]
    FastMCP-->|OpenAPI Tools|Tools[Generated MCP Tools]
    FastMCP-->|Auth|Auth[Authentication Middleware]
    FastMCP-->|Config|Config[OpenAPI & Env Config]
    FastMCP-->|Docker|Docker[Dockerized Deployment]
```

### Authentication Flow
```mermaid
sequenceDiagram
    participant Client
    participant Server
    participant Auth
    Client->>Server: Request with Bearer Token
    Server->>Auth: Validate Token
    Auth-->>Server: Valid/Invalid
    Server-->>Client: Response/Error
```

### Request/Response Flow
```mermaid
sequenceDiagram
    participant Client
    participant Server
    participant Tools
    Client->>Server: API Request
    Server->>Tools: Route to MCP Tool
    Tools-->>Server: Response
    Server-->>Client: API Response
```

### Docker Deployment
```mermaid
flowchart TD
    Dev[Developer]-->|docker-compose up|Docker[Docker Compose]
    Docker-->|Builds|Image[Multi-stage Docker Image]
    Image-->|Runs|Server[FastMCP Server]
    Server-->|Health|Health[Health Checks]
```

## Quick Start

### Prerequisites
- Node.js 18+
- Docker (for containerized deployment)

### Setup
```sh
cp config/.env.example config/.env
cp config/openapi.example.json config/openapi.json
npm install
```

### Run Locally
```sh
npm run dev
```

### Run with Docker
```sh
docker-compose up --build
```

## Configuration
- See `config/.env.example` for environment variables
- Place your OpenAPI spec in `config/openapi.json`

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
- Configure tokens: `config/.env`
- Start server: `npm run dev` or Docker
- Make authenticated API calls with Bearer token

---

For more details, see the `docs/` directory.
