# FastMCP OpenAPI Server API Reference

This document is auto-generated from your OpenAPI spec (`config/openapi.json`).

## Endpoints
- All endpoints are generated from the OpenAPI paths.
- Each endpoint supports the HTTP methods defined in the spec.
- Request/response schemas are validated automatically.

## Authentication
- All endpoints require a Bearer token in the `Authorization` header.
- Example: `Authorization: Bearer <token>`

## Example Request
```sh
curl -H "Authorization: Bearer <token>" http://localhost:8080/hello
```

## Error Handling
- 401 Unauthorized: Invalid or missing token
- 400 Bad Request: Schema validation error
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Unexpected error

---
For more details, see the OpenAPI spec and `README.md`.
