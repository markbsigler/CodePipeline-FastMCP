#!/bin/bash
# Development server script for BMC AMI DevX Code Pipeline FastMCP Server
# Starts the FastMCP server with development settings and hot reload

set -e

# Configuration
SERVER_PORT=${PORT:-8000}
SERVER_HOST=${HOST:-0.0.0.0}
LOG_LEVEL=${LOG_LEVEL:-DEBUG}
PYTHON_CMD="python"
SERVER_FILE="openapi_server.py"

# Check if virtual environment Python exists
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
fi

echo "🚀 Starting BMC AMI DevX Code Pipeline FastMCP Server (Development Mode)"
echo "======================================================================"
echo "📁 Server File: $SERVER_FILE"
echo "📍 Server: $SERVER_HOST:$SERVER_PORT"
echo "🐍 Python: $PYTHON_CMD"
echo "📊 Log Level: $LOG_LEVEL"
echo ""

# Check if server file exists
if [ ! -f "$SERVER_FILE" ]; then
    echo "❌ $SERVER_FILE not found"
    echo "Please run ./scripts/setup.sh first"
    exit 1
fi

# Set development environment variables
export FASTMCP_LOG_LEVEL=$LOG_LEVEL
export FASTMCP_RATE_LIMIT_ENABLED=true
export FASTMCP_CACHE_ENABLED=true
export FASTMCP_MONITORING_ENABLED=true
export FASTMCP_CUSTOM_ROUTES_ENABLED=true
export FASTMCP_RESOURCE_TEMPLATES_ENABLED=true
export FASTMCP_PROMPTS_ENABLED=true

echo "🔧 Development environment configured"
echo "📋 Available endpoints:"
echo "  Health Check:     http://$SERVER_HOST:$SERVER_PORT/health"
echo "  Status:           http://$SERVER_HOST:$SERVER_PORT/status"
echo "  Metrics:          http://$SERVER_HOST:$SERVER_PORT/metrics"
echo "  MCP Capabilities: http://$SERVER_HOST:$SERVER_PORT/mcp/capabilities"
echo "  MCP Tools:        http://$SERVER_HOST:$SERVER_PORT/mcp/tools/list"
echo ""
echo "🛑 Press Ctrl+C to stop the server"
echo ""

# Start the FastMCP server
$PYTHON_CMD $SERVER_FILE
