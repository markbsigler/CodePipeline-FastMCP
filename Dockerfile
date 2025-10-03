# FastMCP 2.x Production Dockerfile for BMC AMI DevX Code Pipeline MCP Server
# Multi-stage build optimized for FastMCP Python implementation
# Pure Python project - no Node.js dependencies required

# Build stage
FROM python:3.11-slim AS builder

# Set build environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Set production environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    LOG_LEVEL=INFO

# Install runtime dependencies for health check
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY openapi_server.py ./
COPY entrypoint.py ./
COPY fastmcp_config.py ./
COPY lib/ ./lib/
COPY observability/ ./observability/
COPY config/ ./config/

# Set ownership and permissions
RUN chown -R appuser:appuser /app && \
    chmod +x openapi_server.py entrypoint.py

# Switch to non-root user
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose FastMCP HTTP port
EXPOSE 8080

# Run FastMCP server
CMD ["python", "entrypoint.py"]

# Labels for container metadata
LABEL maintainer="BMC Software <support@bmc.com>"
LABEL version="2.2.0"
LABEL description="BMC AMI DevX Code Pipeline FastMCP 2.x Server with Streamable HTTP and JWT"
LABEL org.opencontainers.image.title="FastMCP Code Pipeline Server"
LABEL org.opencontainers.image.description="FastMCP 2.x compliant server for BMC AMI DevX Code Pipeline"
LABEL org.opencontainers.image.version="2.2.0"
LABEL org.opencontainers.image.vendor="BMC Software"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/markbsigler/CodePipeline-FastMCP"
