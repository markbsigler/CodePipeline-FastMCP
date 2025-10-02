#!/bin/bash
# Health check script for BMC AMI DevX Code Pipeline FastMCP Server
# Comprehensive health monitoring and diagnostics

set -e

# Configuration
SERVER_HOST=${HOST:-localhost}
SERVER_PORT=${PORT:-8080}
HEALTH_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/health"
STATUS_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/status"
METRICS_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/metrics"
MCP_CAPABILITIES_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/mcp/capabilities"
OPENAPI_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/openapi.json"
PROMETHEUS_ENDPOINT="http://$SERVER_HOST:$SERVER_PORT/metrics"

echo "🏥 BMC AMI DevX Code Pipeline FastMCP Server Health Check"
echo "========================================================"
echo "📍 Server: $SERVER_HOST:$SERVER_PORT"
echo ""

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local name=$2
    local expected_content=$3

    echo -n "🔍 Checking $name... "

    if response=$(curl -s --max-time 10 "$endpoint" 2>/dev/null); then
        if [ -n "$expected_content" ]; then
            if echo "$response" | grep -q "$expected_content"; then
                echo "✅ OK"
                return 0
            else
                echo "❌ FAILED (unexpected content)"
                return 1
            fi
        else
            echo "✅ OK"
            return 0
        fi
    else
        echo "❌ FAILED (connection error)"
        return 1
    fi
}

# Function to get JSON value
get_json_value() {
    local json=$1
    local key=$2
    echo "$json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('$key', 'N/A'))" 2>/dev/null || echo "N/A"
}

# Check basic connectivity
echo "📡 Basic Connectivity Tests:"
echo "----------------------------"

check_endpoint "$HEALTH_ENDPOINT" "Health Check" "healthy"
HEALTH_RESULT=$?

check_endpoint "$STATUS_ENDPOINT" "Status Endpoint" ""
STATUS_RESULT=$?

check_endpoint "$METRICS_ENDPOINT" "Metrics Endpoint" ""
METRICS_RESULT=$?

check_endpoint "$MCP_CAPABILITIES_ENDPOINT" "MCP Capabilities" ""
MCP_RESULT=$?

check_endpoint "$OPENAPI_ENDPOINT" "OpenAPI Specification" ""
OPENAPI_RESULT=$?

check_endpoint "$PROMETHEUS_ENDPOINT" "Prometheus Metrics" ""
PROMETHEUS_RESULT=$?

echo ""

# Detailed health information
if [ $HEALTH_RESULT -eq 0 ]; then
    echo "📊 Detailed Health Information:"
    echo "-------------------------------"

    # Get health data
    health_data=$(curl -s --max-time 10 "$HEALTH_ENDPOINT" 2>/dev/null)

    if [ -n "$health_data" ]; then
        echo "Server Status: $(get_json_value "$health_data" "status")"
        echo "Version: $(get_json_value "$health_data" "version")"
        echo "Uptime: $(get_json_value "$health_data" "uptime")"
        echo "BMC API Status: $(get_json_value "$health_data" "bmc_api_status")"
        echo "Rate Limiter: $(get_json_value "$health_data" "rate_limiter_status")"
        echo "Cache Status: $(get_json_value "$health_data" "cache_status")"
    fi
    echo ""
fi

# MCP capabilities check
if [ $MCP_RESULT -eq 0 ]; then
    echo "🔧 MCP Capabilities:"
    echo "--------------------"

    capabilities_data=$(curl -s --max-time 10 "$MCP_CAPABILITIES_ENDPOINT" 2>/dev/null)

    if [ -n "$capabilities_data" ]; then
        echo "Server Name: $(get_json_value "$capabilities_data" "serverInfo.name")"
        echo "Server Version: $(get_json_value "$capabilities_data" "serverInfo.version")"
        echo "Protocol Version: $(get_json_value "$capabilities_data" "protocolVersion")"

        # Count tools
        tools_count=$(echo "$capabilities_data" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('capabilities', {}).get('tools', {}).get('listChanged', False) and 'tools' in data or []))" 2>/dev/null || echo "Unknown")
        echo "Tools Available: $tools_count"
    fi
    echo ""
fi

# Performance metrics
if [ $METRICS_RESULT -eq 0 ]; then
    echo "📈 Performance Metrics:"
    echo "----------------------"

    metrics_data=$(curl -s --max-time 10 "$METRICS_ENDPOINT" 2>/dev/null)

    if [ -n "$metrics_data" ]; then
        echo "Total Requests: $(get_json_value "$metrics_data" "total_requests")"
        echo "Successful Requests: $(get_json_value "$metrics_data" "successful_requests")"
        echo "Failed Requests: $(get_json_value "$metrics_data" "failed_requests")"
        echo "Average Response Time: $(get_json_value "$metrics_data" "avg_response_time")ms"
        echo "Cache Hit Rate: $(get_json_value "$metrics_data" "cache_hit_rate")%"
        echo "Rate Limiter Tokens: $(get_json_value "$metrics_data" "rate_limiter.tokens")"
    fi
    echo ""
fi

# Overall health status
echo "🎯 Overall Health Status:"
echo "------------------------"

if [ $HEALTH_RESULT -eq 0 ] && [ $STATUS_RESULT -eq 0 ] && [ $METRICS_RESULT -eq 0 ] && [ $MCP_RESULT -eq 0 ] && [ $OPENAPI_RESULT -eq 0 ] && [ $PROMETHEUS_RESULT -eq 0 ]; then
    echo "✅ ALL SYSTEMS OPERATIONAL"
    echo ""
    echo "🚀 Server is ready for production use!"
    echo "📋 Available endpoints:"
    echo "  Health:         $HEALTH_ENDPOINT"
    echo "  Status:         $STATUS_ENDPOINT"
    echo "  Metrics:        $METRICS_ENDPOINT"
    echo "  MCP:            $MCP_CAPABILITIES_ENDPOINT"
    echo "  OpenAPI Spec:   $OPENAPI_ENDPOINT"
    echo "  Prometheus:     $PROMETHEUS_ENDPOINT"
    exit 0
else
    echo "❌ SOME SYSTEMS FAILING"
    echo ""
    echo "🔧 System Status:"
    echo "  Health:         $([ $HEALTH_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo "  Status:         $([ $STATUS_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo "  Metrics:        $([ $METRICS_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo "  MCP:            $([ $MCP_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo "  OpenAPI:        $([ $OPENAPI_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo "  Prometheus:     $([ $PROMETHEUS_RESULT -eq 0 ] && echo "✅ OK" || echo "❌ FAILED")"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "  1. Check if server is running: ps aux | grep openapi_server"
    echo "  2. Check server logs: tail -f server.log"
    echo "  3. Restart server: ./scripts/dev.sh"
    echo "  4. Run tests: ./scripts/test.sh"
    exit 1
fi
