#!/bin/bash
# Comprehensive test script for BMC AMI DevX Code Pipeline MCP Server
# Runs server in background, waits for startup, executes tests, then cleanup

set -e

# Configuration
SERVER_LOG=server_test.log
SERVER_PORT=8080
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

# Start the server in the background
echo "🚀 Starting server in background..."
$PYTHON_CMD main.py > $SERVER_LOG 2>&1 &
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

# Test 1: Unit tests without server dependency
echo "📋 Running unit tests (server-independent)..."
$PYTHON_CMD -m pytest test_mcp_server.py::TestServerConfiguration -v
UNIT_TEST_RESULT=$?

# Test 2: Integration tests with running server
echo "📋 Running integration tests (server-dependent)..."
$PYTHON_CMD -m pytest test_mcp_server.py::TestMCPServer -v
INTEGRATION_TEST_RESULT=$?

# Test 3: Full test suite with coverage
echo "📋 Running full test suite with coverage..."
$PYTHON_CMD -m pytest test_mcp_server.py --cov=main --cov-report=term-missing --cov-report=html -v
COVERAGE_TEST_RESULT=$?

echo "=================================="
echo "📊 Test Results Summary:"
echo "  Unit Tests: $([ $UNIT_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Integration Tests: $([ $INTEGRATION_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo "  Coverage Tests: $([ $COVERAGE_TEST_RESULT -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")"

# Determine overall result
if [ $UNIT_TEST_RESULT -eq 0 ] && [ $INTEGRATION_TEST_RESULT -eq 0 ] && [ $COVERAGE_TEST_RESULT -eq 0 ]; then
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
