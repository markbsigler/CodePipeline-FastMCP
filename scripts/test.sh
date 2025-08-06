#!/bin/bash
# Run FastMCP server in the background, wait for it to start, then run tests, then kill the server

set -e

SERVER_LOG=server_test.log

# Start the server in the background
python main.py > $SERVER_LOG 2>&1 &
SERVER_PID=$!

# Wait for the server to be ready
for i in {1..10}; do
  if curl -s http://127.0.0.1:8080/health | grep -q 'healthy'; then
    echo "Server is up!"
    break
  fi
  sleep 1
done

# Run the tests
pytest test_mcp_server.py -v
TEST_RESULT=$?

# Kill the server
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true

# Show server log if tests failed
if [ $TEST_RESULT -ne 0 ]; then
  echo "\n--- SERVER LOG ---"
  cat $SERVER_LOG
fi

exit $TEST_RESULT
