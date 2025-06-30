# FastMCP Python Project Generation Prompt

Generate a production-ready Python FastMCP server project with the following best practices:

## Project Structure and Standards
- Use a modular `src/` layout and include a `tests/` directory with pytest-based tests.
- Use `pyproject.toml` for build and dependency management; include `requirements.txt` and `requirements-dev.txt`.
- Enforce PEP8, type annotations, and include linting/formatting tools (`black`, `flake8`, `isort`).
- Provide a multi-stage `Dockerfile` and `docker-compose.yml` with a healthcheck endpoint.

## API and Security
- Implement Bearer token authentication and CORS/security headers.
- Include a `config/openapi.json` file and document how to add endpoints/tools.
- Add a `/healthz` endpoint for health checks.

## Documentation
- Add a `README.md` with setup, usage, API examples, and Mermaid architecture diagrams for:
  - Authentication with Bearer Token
  - OpenAPI endpoint flow
  - Container deployment overview
- Add scripts for setup, testing, and deployment.
- Support environment variable configuration via `.env`.

## Testing and CI/CD
- Require a test suite using `pytest` with at least one test per endpoint/tool.
- Include code coverage reporting (e.g., `pytest-cov`).
- Add linting and formatting checks, and pre-commit hooks.
- Include a basic GitHub Actions workflow for linting, testing, and building the Docker image.

## Extensibility
- Make it easy to add new endpoints/tools by editing the OpenAPI spec and adding backend handlers.
- Document the process for extending the API and adding new features.

## Example API and Usage
- Provide example OpenAPI spec in `config/openapi.json`.
- Document how to test the Docker container health and exit after verification.
- Include example API calls (curl, Python `httpx`).

---

**Follow best practices for Python web APIs and containerized deployment.**
