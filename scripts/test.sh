#!/bin/bash
# Comprehensive test script for BMC AMI DevX Code Pipeline MCP Server
# Runs server in background, waits for startup, executes tests, then cleanup

set -e

# Configuration
SERVER_LOG=server_test.log
SERVER_PORT=${PORT:-8080}  # Use PORT env var or default to 8080 (matches openapi_server.py default)
SERVER_HOST=127.0.0.1
HEALTH_ENDPOINT="http://${SERVER_HOST}:${SERVER_PORT}/health"
STARTUP_TIMEOUT=30
PYTHON_CMD="python"

# Check if virtual environment Python exists
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
fi

echo "🧪 Starting BMC AMI DevX Code Pipeline MCP Server Test Suite"
echo "📍 Using Python: $PYTHON_CMD"
echo "🔗 Health endpoint: $HEALTH_ENDPOINT"

# Clean up any existing log
rm -f $SERVER_LOG

# Start the FastMCP server in the background
echo "🚀 Starting FastMCP server in background..."
$PYTHON_CMD openapi_server.py > $SERVER_LOG 2>&1 &
SERVER_PID=$!

echo "📝 Server PID: $SERVER_PID"
echo "📋 Log file: $SERVER_LOG"

# Function to cleanup on exit
cleanup() {
    echo "🧹 Cleaning up..."
    if kill -0 $SERVER_PID 2>/dev/null; then
        echo "🛑 Stopping server (PID: $SERVER_PID)"
        kill $SERVER_PID
        wait $SERVER_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup on script exit
trap cleanup EXIT

# Wait for the server to be ready with timeout
echo "⏳ Waiting for server to start (timeout: ${STARTUP_TIMEOUT}s)..."
for i in $(seq 1 $STARTUP_TIMEOUT); do
    if curl -s --max-time 2 $HEALTH_ENDPOINT | grep -q 'healthy'; then
        echo "✅ Server is healthy and ready!"
        break
    fi

    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "❌ Server process died during startup"
        echo "\n--- SERVER LOG ---"
        cat $SERVER_LOG
        exit 1
    fi

    echo "⏱️  Attempt $i/$STARTUP_TIMEOUT - waiting for server..."
    sleep 1
done

# Check if server is actually ready
if ! curl -s --max-time 2 $HEALTH_ENDPOINT | grep -q 'healthy'; then
    echo "❌ Server failed to start within $STARTUP_TIMEOUT seconds"
    echo "\n--- SERVER LOG ---"
    cat $SERVER_LOG
    exit 1
fi

# Run the comprehensive test suite
echo "🔬 Running comprehensive test suite..."
echo "=================================="

# Test 1: Main application tests
echo "📋 Running main application tests..."
$PYTHON_CMD -m pytest tests/test_main.py -v
MAIN_TEST_RESULT=$?

# Test 2: OpenAPI server tests
echo "📋 Running OpenAPI server tests..."
$PYTHON_CMD -m pytest tests/test_openapi_server.py -v
OPENAPI_TEST_RESULT=$?

# Test 3: FastMCP server integration tests
echo "📋 Running FastMCP server integration tests..."
$PYTHON_CMD -m pytest tests/test_fastmcp_server.py -v
FASTMCP_TEST_RESULT=$?

# Test 4: Configuration tests
echo "📋 Running configuration tests..."
$PYTHON_CMD -m pytest tests/test_fastmcp_config.py -v
CONFIG_TEST_RESULT=$?

# Test 5: Entrypoint tests
echo "📋 Running entrypoint tests..."
$PYTHON_CMD -m pytest tests/test_entrypoint.py -v
ENTRYPOINT_TEST_RESULT=$?

# Test 6: Debug utility tests
echo "📋 Running debug utility tests..."
$PYTHON_CMD -m pytest tests/test_debug.py -v
DEBUG_TEST_RESULT=$?

# Test 7: OTEL integration tests (if available)
echo "📋 Running OTEL integration tests..."
if [ -f "observability/tests/test_integration.py" ]; then
    $PYTHON_CMD observability/tests/test_integration.py
    OTEL_TEST_RESULT=$?
else
    echo "ℹ️  No OTEL integration tests found, skipping"
    OTEL_TEST_RESULT=0
fi

echo "=================================="
echo "📊 Test Results Summary:"
echo "  Main Application: $([ $MAIN_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  OpenAPI Server: $([ $OPENAPI_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  FastMCP Integration: $([ $FASTMCP_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Configuration: $([ $CONFIG_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Entrypoint: $([ $ENTRYPOINT_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Debug Utilities: $([ $DEBUG_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  OTEL Integration: $([ $OTEL_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

# Determine overall result
if [ $MAIN_TEST_RESULT -eq 0 ] && [ $OPENAPI_TEST_RESULT -eq 0 ] && [ $FASTMCP_TEST_RESULT -eq 0 ] && [ $CONFIG_TEST_RESULT -eq 0 ] && [ $ENTRYPOINT_TEST_RESULT -eq 0 ] && [ $DEBUG_TEST_RESULT -eq 0 ] && [ $OTEL_TEST_RESULT -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    TEST_RESULT=0
else
    echo "💥 SOME TESTS FAILED!"
    TEST_RESULT=1
fi

# Show server log if any tests failed
if [ $TEST_RESULT -ne 0 ]; then
    echo "\n--- SERVER LOG (last 50 lines) ---"
    tail -50 $SERVER_LOG
fi

echo "🏁 Test suite completed"
exit $TEST_RESULT
