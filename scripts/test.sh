#!/bin/bash
# Comprehensive test script for BMC AMI DevX Code Pipeline MCP Server
# Runs server in background, waits for startup, executes tests, then cleanup

set -e

# Configuration
SERVER_LOG=server_test.log
SERVER_PORT=${PORT:-8000}  # Use PORT env var or default to 8000 (matches main.py default)
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

# Test 1: Advanced features tests
echo "📋 Running advanced features tests..."
$PYTHON_CMD test_advanced_features.py
ADVANCED_TEST_RESULT=$?

# Test 2: Elicitation tests
echo "📋 Running elicitation tests..."
$PYTHON_CMD test_elicitation.py
ELICITATION_TEST_RESULT=$?

# Test 3: OpenAPI integration tests
echo "📋 Running OpenAPI integration tests..."
$PYTHON_CMD test_openapi_integration.py
OPENAPI_TEST_RESULT=$?

# Test 4: Legacy tests (if they exist)
echo "📋 Running legacy tests..."
if [ -f "test_mcp_server.py" ]; then
    $PYTHON_CMD -m pytest test_mcp_server.py -v
    LEGACY_TEST_RESULT=$?
else
    echo "ℹ️  No legacy tests found, skipping"
    LEGACY_TEST_RESULT=0
fi

echo "=================================="
echo "📊 Test Results Summary:"
echo "  Advanced Features: $([ $ADVANCED_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Elicitation Tests: $([ $ELICITATION_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  OpenAPI Integration: $([ $OPENAPI_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Legacy Tests: $([ $LEGACY_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

# Determine overall result
if [ $ADVANCED_TEST_RESULT -eq 0 ] && [ $ELICITATION_TEST_RESULT -eq 0 ] && [ $OPENAPI_TEST_RESULT -eq 0 ] && [ $LEGACY_TEST_RESULT -eq 0 ]; then
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
