# OpenTelemetry Observability Setup Guide
## BMC AMI DevX Code Pipeline FastMCP Server

This guide provides comprehensive instructions for setting up and using the OpenTelemetry observability features in the FastMCP server.

---

## 📋 **Overview**

The FastMCP server now includes comprehensive OpenTelemetry (OTEL) observability with:

- **Distributed Tracing**: Complete request tracing across all operations
- **Metrics Collection**: OTEL-compatible metrics with Prometheus export
- **Hybrid Metrics**: Backward compatibility with existing metrics system
- **Grafana Dashboards**: Pre-built visualization templates
- **Intelligent Alerting**: Prometheus alerting rules with multiple severity levels
- **Performance Monitoring**: Real-time performance insights and SLO tracking

---

## 🚀 **Quick Start**

### **1. Install Dependencies**

The OTEL dependencies are already included in `requirements.txt`. Install them:

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### **2. Basic Configuration**

Set environment variables for OTEL configuration:

```bash
# Enable OpenTelemetry
export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=fastmcp-server
export OTEL_SERVICE_VERSION=2.3.1
export OTEL_ENVIRONMENT=development

# Configure exporters
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_PROMETHEUS_PORT=9464

# Enable tracing and metrics
export OTEL_TRACING_ENABLED=true
export OTEL_METRICS_ENABLED=true
```

### **3. Start the Server**

```bash
# Start FastMCP server with OTEL enabled
python main.py
```

The server will now collect traces and metrics automatically.

---

## 🔧 **Configuration Options**

### **Environment Variables**

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_ENABLED` | `true` | Enable/disable OpenTelemetry |
| `OTEL_SERVICE_NAME` | `fastmcp-server` | Service name for traces/metrics |
| `OTEL_SERVICE_VERSION` | `2.3.1` | Service version |
| `OTEL_ENVIRONMENT` | `development` | Deployment environment |
| `OTEL_TRACING_ENABLED` | `true` | Enable distributed tracing |
| `OTEL_METRICS_ENABLED` | `true` | Enable metrics collection |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP exporter endpoint |
| `OTEL_EXPORTER_JAEGER_ENDPOINT` | `http://localhost:14268/api/traces` | Jaeger exporter endpoint |
| `OTEL_PROMETHEUS_PORT` | `9464` | Prometheus metrics port |
| `OTEL_TRACE_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0-1.0) |
| `OTEL_CONSOLE_EXPORTER` | `false` | Enable console trace output |
| `OTEL_AUTO_INITIALIZE` | `true` | Auto-initialize OTEL on import |

### **Advanced Configuration**

```bash
# Custom resource attributes
export OTEL_RESOURCE_ATTRIBUTES_TEAM=devops
export OTEL_RESOURCE_ATTRIBUTES_REGION=us-east-1

# Sampling configuration for production
export OTEL_TRACE_SAMPLE_RATE=0.1  # 10% sampling

# Disable specific components
export OTEL_TRACING_ENABLED=false  # Disable tracing only
export OTEL_METRICS_ENABLED=false  # Disable metrics only
```

---

## 📊 **Metrics**

### **Available Metrics**

#### **Request Metrics**
- `fastmcp_requests_total` - Total HTTP requests
- `fastmcp_request_duration_seconds` - Request duration histogram
- `fastmcp_active_requests` - Currently active requests

#### **BMC API Metrics**
- `fastmcp_bmc_api_calls_total` - Total BMC API calls
- `fastmcp_bmc_api_duration_seconds` - BMC API call duration

#### **Cache Metrics**
- `fastmcp_cache_operations_total` - Cache operations (hits/misses)
- `fastmcp_cache_size` - Current cache size

#### **Tool Execution Metrics**
- `fastmcp_tool_executions_total` - MCP tool executions
- `fastmcp_tool_duration_seconds` - Tool execution duration

#### **Authentication Metrics**
- `fastmcp_auth_attempts_total` - Authentication attempts
- `fastmcp_rate_limit_events_total` - Rate limiting events

#### **Elicitation Metrics**
- `fastmcp_elicitation_workflows_total` - User elicitation workflows
- `fastmcp_elicitation_steps_total` - Individual elicitation steps

#### **System Metrics**
- `fastmcp_uptime_seconds` - Server uptime
- `fastmcp_system_memory_usage_bytes` - Memory usage
- `fastmcp_system_cpu_usage_percent` - CPU usage

### **Accessing Metrics**

#### **Legacy JSON Endpoint**
```bash
curl http://localhost:8080/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_metrics", "arguments": {}}'
```

#### **Prometheus Endpoint**
```bash
curl http://localhost:9464/metrics
```

---

## 🔍 **Distributed Tracing**

### **Trace Structure**

The FastMCP server creates traces for:

1. **MCP Tool Calls** - Complete tool execution with arguments
2. **BMC API Calls** - External API requests with timing
3. **Cache Operations** - Cache hits/misses with keys
4. **Authentication** - Auth provider interactions
5. **Elicitation Workflows** - User interaction flows

### **Trace Attributes**

#### **MCP Tool Traces**
```
mcp.operation: "tool_call"
mcp.tool_name: "ispw_Get_assignments"
mcp.arguments_count: 2
mcp.arg.srid: "TEST123"
mcp.execution.duration: 0.245
mcp.execution.success: true
```

#### **BMC API Traces**
```
http.method: "GET"
http.url: "/api/assignments"
http.status_code: 200
bmc.operation: "get_assignments"
component: "bmc-api-client"
```

#### **Cache Traces**
```
cache.operation: "get"
cache.key: "get_assignments|srid=TEST123"
cache.key_type: "assignments"
component: "intelligent-cache"
```

### **Viewing Traces**

#### **Console Output** (Development)
```bash
export OTEL_CONSOLE_EXPORTER=true
python main.py
```

#### **Jaeger UI**
1. Start Jaeger: `docker run -p 16686:16686 -p 14268:14268 jaegertracing/all-in-one:latest`
2. Configure endpoint: `export OTEL_EXPORTER_JAEGER_ENDPOINT=http://localhost:14268/api/traces`
3. View traces: http://localhost:16686

---

## 📈 **Grafana Dashboards**

### **Dashboard Setup**

1. **Import Dashboard**:
   ```bash
   # Copy dashboard to Grafana
   cp observability/dashboards/fastmcp-overview.json /var/lib/grafana/dashboards/
   ```

2. **Configure Data Source**:
   - Add Prometheus data source: `http://localhost:9090`
   - Test connection and save

3. **Import Dashboard**:
   - Go to Grafana UI → Dashboards → Import
   - Upload `fastmcp-overview.json`
   - Select Prometheus data source

### **Dashboard Panels**

The FastMCP overview dashboard includes:

- **Request Rate** - Requests per second
- **Success Rate** - HTTP success percentage
- **Active Requests** - Current concurrent requests
- **Server Uptime** - Service availability
- **Response Time Distribution** - Latency heatmap
- **Response Time Percentiles** - P50, P95, P99 latencies
- **BMC API Performance** - External API metrics
- **Cache Performance** - Hit rates and size
- **Tool Usage Distribution** - Tool execution patterns
- **Rate Limiting Events** - Rate limiter activity
- **Authentication Success Rate** - Auth performance

---

## 🚨 **Alerting**

### **Prometheus Alerting Rules**

The alerting rules are defined in `observability/alerting/fastmcp-alerts.yml`:

#### **Critical Alerts**
- **FastMCPServerDown** - Server unavailable
- **FastMCPCriticalErrorRate** - >20% error rate
- **FastMCPCriticalLatency** - P95 >5 seconds
- **FastMCPBMCAPIDown** - >50% BMC API failures

#### **Warning Alerts**
- **FastMCPHighErrorRate** - >5% error rate
- **FastMCPHighLatency** - P95 >1 second
- **FastMCPHighMemoryUsage** - >1GB memory
- **FastMCPHighCPUUsage** - >80% CPU

#### **Info Alerts**
- **FastMCPCacheHitRateLow** - <50% cache hit rate
- **FastMCPElicitationFailureRate** - >20% elicitation failures

### **Alert Setup**

1. **Configure Prometheus**:
   ```yaml
   # prometheus.yml
   rule_files:
     - "fastmcp-alerts.yml"
   
   alerting:
     alertmanagers:
       - static_configs:
           - targets:
             - alertmanager:9093
   ```

2. **Set up Alert Manager**:
   ```yaml
   # alertmanager.yml
   route:
     group_by: ['alertname', 'severity']
     group_wait: 10s
     group_interval: 10s
     repeat_interval: 1h
     receiver: 'web.hook'
   
   receivers:
   - name: 'web.hook'
     webhook_configs:
     - url: 'http://localhost:5001/'
   ```

---

## 🧪 **Testing & Validation**

### **Validate OTEL Setup**

```bash
# Check OTEL initialization
python -c "
from otel_config import initialize_otel
tracer, meter = initialize_otel()
print(f'Tracer: {tracer is not None}')
print(f'Meter: {meter is not None}')
"
```

### **Test Metrics Collection**

```bash
# Generate some requests
curl -X POST http://localhost:8080/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_health_status", "arguments": {}}'

# Check Prometheus metrics
curl http://localhost:9464/metrics | grep fastmcp_requests_total
```

### **Test Tracing**

```bash
# Enable console tracing
export OTEL_CONSOLE_EXPORTER=true

# Make a request and observe trace output
python main.py &
curl -X POST http://localhost:8080/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_metrics", "arguments": {}}'
```

### **Load Testing**

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run load test
ab -n 1000 -c 10 -H "Content-Type: application/json" \
  -p test_payload.json http://localhost:8080/mcp/tools/call

# Monitor metrics during load test
watch -n 1 'curl -s http://localhost:9464/metrics | grep fastmcp_requests_total'
```

---

## 🔧 **Troubleshooting**

### **Common Issues**

#### **OTEL Not Initializing**
```bash
# Check environment variables
env | grep OTEL

# Verify dependencies
pip list | grep opentelemetry

# Check logs
python main.py 2>&1 | grep -i otel
```

#### **Metrics Not Appearing**
```bash
# Check Prometheus endpoint
curl http://localhost:9464/metrics

# Verify metrics are enabled
python -c "from otel_config import is_metrics_enabled; print(is_metrics_enabled())"

# Check for errors
tail -f server.log | grep -i metric
```

#### **Traces Not Exported**
```bash
# Verify tracing is enabled
python -c "from otel_config import is_tracing_enabled; print(is_tracing_enabled())"

# Check exporter endpoint
curl http://localhost:4317/v1/traces

# Enable console output for debugging
export OTEL_CONSOLE_EXPORTER=true
```

#### **High Performance Impact**
```bash
# Reduce sampling rate
export OTEL_TRACE_SAMPLE_RATE=0.1

# Disable tracing temporarily
export OTEL_TRACING_ENABLED=false

# Monitor resource usage
top -p $(pgrep -f "python main.py")
```

### **Performance Tuning**

#### **Production Settings**
```bash
# Optimized for production
export OTEL_TRACE_SAMPLE_RATE=0.05  # 5% sampling
export OTEL_CONSOLE_EXPORTER=false
export OTEL_PROMETHEUS_PORT=9464

# Batch exporter settings
export OTEL_BSP_MAX_QUEUE_SIZE=2048
export OTEL_BSP_EXPORT_TIMEOUT=30000
export OTEL_BSP_SCHEDULE_DELAY=5000
```

#### **Development Settings**
```bash
# Full observability for development
export OTEL_TRACE_SAMPLE_RATE=1.0
export OTEL_CONSOLE_EXPORTER=true
export OTEL_TRACING_ENABLED=true
export OTEL_METRICS_ENABLED=true
```

---

## 📚 **Best Practices**

### **Configuration Management**
- Use environment-specific configuration files
- Store sensitive configuration in secrets management
- Document all configuration changes
- Test configuration in staging before production

### **Monitoring Strategy**
- Start with basic metrics and expand gradually
- Focus on business-critical SLIs first
- Set up alerting for actionable issues only
- Regular review and tuning of alert thresholds

### **Performance Considerations**
- Use appropriate sampling rates for tracing
- Monitor OTEL overhead in production
- Implement circuit breakers for exporters
- Regular cleanup of old metrics and traces

### **Security**
- Sanitize sensitive data in traces
- Use secure transport for exporter endpoints
- Implement proper authentication for monitoring endpoints
- Regular security reviews of observability configuration

---

## 🎯 **Next Steps**

1. **Deploy to Staging**: Test full observability stack in staging environment
2. **Set up Alerting**: Configure alert routing to appropriate channels
3. **Create Runbooks**: Document response procedures for each alert
4. **Train Team**: Provide training on new observability tools
5. **Iterate**: Continuously improve based on operational experience

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**Status**: ✅ Implementation Complete
