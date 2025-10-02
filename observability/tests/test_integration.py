#!/usr/bin/env python3
"""
OpenTelemetry Integration Test Script

This script validates that the OTEL observability features are working correctly
in the FastMCP server.
"""

import asyncio
import json
import time
import httpx
import sys
from typing import Dict, Any

# Test configuration
TEST_CONFIG = {
    "server_url": "http://localhost:8080",
    "prometheus_url": "http://localhost:9464",
    "test_timeout": 30,
    "test_requests": 10
}


class OTELIntegrationTester:
    """Test suite for OTEL integration validation."""
    
    def __init__(self):
        self.results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": []
        }
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        self.results["tests_run"] += 1
        if passed:
            self.results["tests_passed"] += 1
            print(f"✅ {test_name}: PASSED {message}")
        else:
            self.results["tests_failed"] += 1
            self.results["errors"].append(f"{test_name}: {message}")
            print(f"❌ {test_name}: FAILED {message}")
    
    async def test_otel_initialization(self):
        """Test OTEL components initialize correctly."""
        try:
            from ..config.otel_config import initialize_otel, is_tracing_enabled, is_metrics_enabled
            
            # Test initialization
            tracer, meter = initialize_otel()
            
            self.log_test(
                "OTEL Initialization",
                tracer is not None or meter is not None,
                f"Tracer: {tracer is not None}, Meter: {meter is not None}"
            )
            
            # Test configuration
            tracing_enabled = is_tracing_enabled()
            metrics_enabled = is_metrics_enabled()
            
            self.log_test(
                "OTEL Configuration",
                True,  # Always pass if no exception
                f"Tracing: {tracing_enabled}, Metrics: {metrics_enabled}"
            )
            
        except Exception as e:
            self.log_test("OTEL Initialization", False, str(e))
    
    async def test_hybrid_metrics(self):
        """Test hybrid metrics system."""
        try:
            from ..metrics.hybrid_metrics import HybridMetrics, get_metrics
            
            # Test metrics initialization
            metrics = get_metrics()
            self.log_test(
                "Hybrid Metrics Initialization",
                metrics is not None,
                f"Type: {type(metrics).__name__}"
            )
            
            # Test metrics recording
            metrics.record_request("GET", "/test", 200, 0.1)
            metrics.record_bmc_api_call("test_operation", True, 0.2)
            metrics.record_cache_operation("get", True, "test")
            
            self.log_test("Metrics Recording", True, "All metric types recorded")
            
            # Test legacy format
            legacy_data = metrics.to_dict()
            self.log_test(
                "Legacy Metrics Format",
                "requests" in legacy_data and "bmc_api" in legacy_data,
                f"Keys: {list(legacy_data.keys())}"
            )
            
        except Exception as e:
            self.log_test("Hybrid Metrics", False, str(e))
    
    async def test_tracing_utilities(self):
        """Test tracing utilities."""
        try:
            from ..tracing.fastmcp_tracer import get_fastmcp_tracer, get_elicitation_tracer
            
            # Test tracer initialization
            fastmcp_tracer = get_fastmcp_tracer()
            elicitation_tracer = get_elicitation_tracer()
            
            self.log_test(
                "Tracer Initialization",
                fastmcp_tracer is not None and elicitation_tracer is not None,
                "Both tracers initialized"
            )
            
            # Test trace context managers
            async with fastmcp_tracer.trace_mcp_request("test", "test_tool", {"arg": "value"}):
                pass
            
            async with fastmcp_tracer.trace_bmc_api_call("test_op", "/test", "GET"):
                pass
            
            async with fastmcp_tracer.trace_cache_operation("get", "test_key", "test"):
                pass
            
            self.log_test("Tracing Context Managers", True, "All context managers work")
            
        except Exception as e:
            self.log_test("Tracing Utilities", False, str(e))
    
    async def test_server_health(self):
        """Test server health and availability."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test server health
                response = await client.get(f"{TEST_CONFIG['server_url']}/health")
                
                self.log_test(
                    "Server Health",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    health_data = response.json()
                    self.log_test(
                        "Health Data Structure",
                        "status" in health_data,
                        f"Keys: {list(health_data.keys())}"
                    )
        
        except Exception as e:
            self.log_test("Server Health", False, str(e))
    
    async def test_mcp_tools(self):
        """Test MCP tool execution with tracing."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test get_metrics tool
                payload = {
                    "name": "get_metrics",
                    "arguments": {}
                }
                
                response = await client.post(
                    f"{TEST_CONFIG['server_url']}/mcp/tools/call",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                self.log_test(
                    "MCP Tool Execution",
                    response.status_code == 200,
                    f"get_metrics status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, str):
                        metrics_data = json.loads(result)
                    else:
                        metrics_data = result
                    
                    self.log_test(
                        "Metrics Tool Response",
                        "requests" in metrics_data,
                        f"Response keys: {list(metrics_data.keys()) if isinstance(metrics_data, dict) else 'Not dict'}"
                    )
        
        except Exception as e:
            self.log_test("MCP Tools", False, str(e))
    
    async def test_prometheus_metrics(self):
        """Test Prometheus metrics endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{TEST_CONFIG['prometheus_url']}/metrics")
                
                self.log_test(
                    "Prometheus Endpoint",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    metrics_text = response.text
                    
                    # Check for key metrics
                    expected_metrics = [
                        "fastmcp_requests_total",
                        "fastmcp_request_duration_seconds",
                        "fastmcp_uptime_seconds"
                    ]
                    
                    found_metrics = [m for m in expected_metrics if m in metrics_text]
                    
                    self.log_test(
                        "Prometheus Metrics Content",
                        len(found_metrics) > 0,
                        f"Found {len(found_metrics)}/{len(expected_metrics)} expected metrics"
                    )
        
        except Exception as e:
            self.log_test("Prometheus Metrics", False, str(e))
    
    async def test_load_generation(self):
        """Generate load to test metrics collection."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Generate multiple requests
                tasks = []
                for i in range(TEST_CONFIG["test_requests"]):
                    payload = {
                        "name": "get_health_status",
                        "arguments": {}
                    }
                    
                    task = client.post(
                        f"{TEST_CONFIG['server_url']}/mcp/tools/call",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    tasks.append(task)
                
                # Execute requests concurrently
                start_time = time.time()
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                duration = time.time() - start_time
                
                # Count successful responses
                successful = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
                
                self.log_test(
                    "Load Generation",
                    successful > 0,
                    f"{successful}/{len(responses)} successful requests in {duration:.2f}s"
                )
                
                # Wait a moment for metrics to be collected
                await asyncio.sleep(2)
                
                # Check if metrics reflect the load
                response = await client.get(f"{TEST_CONFIG['prometheus_url']}/metrics")
                if response.status_code == 200:
                    metrics_text = response.text
                    
                    # Look for request count metrics
                    has_request_metrics = "fastmcp_requests_total" in metrics_text
                    
                    self.log_test(
                        "Metrics Collection Under Load",
                        has_request_metrics,
                        "Request metrics found after load generation"
                    )
        
        except Exception as e:
            self.log_test("Load Generation", False, str(e))
    
    async def run_all_tests(self):
        """Run all integration tests."""
        print("🚀 Starting OTEL Integration Tests")
        print("=" * 50)
        
        # Run tests in order
        await self.test_otel_initialization()
        await self.test_hybrid_metrics()
        await self.test_tracing_utilities()
        await self.test_server_health()
        await self.test_mcp_tools()
        await self.test_prometheus_metrics()
        await self.test_load_generation()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 Test Results Summary")
        print("=" * 50)
        print(f"Tests Run: {self.results['tests_run']}")
        print(f"Tests Passed: {self.results['tests_passed']}")
        print(f"Tests Failed: {self.results['tests_failed']}")
        
        if self.results["errors"]:
            print("\n❌ Errors:")
            for error in self.results["errors"]:
                print(f"  - {error}")
        
        success_rate = (self.results['tests_passed'] / self.results['tests_run']) * 100 if self.results['tests_run'] > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 OTEL Integration: HEALTHY")
            return 0
        else:
            print("⚠️  OTEL Integration: NEEDS ATTENTION")
            return 1


async def main():
    """Main test execution."""
    print("OpenTelemetry Integration Test Suite")
    print("BMC AMI DevX Code Pipeline FastMCP Server")
    print()
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{TEST_CONFIG['server_url']}/health")
            if response.status_code != 200:
                print("❌ FastMCP server is not responding. Please start the server first:")
                print("   python main.py")
                return 1
    except Exception as e:
        print(f"❌ Cannot connect to FastMCP server at {TEST_CONFIG['server_url']}")
        print("   Please ensure the server is running: python main.py")
        print(f"   Error: {e}")
        return 1
    
    # Run tests
    tester = OTELIntegrationTester()
    return await tester.run_all_tests()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)
