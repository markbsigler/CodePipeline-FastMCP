# 📊 Observability Package

Comprehensive observability capabilities for the FastMCP server, providing monitoring, alerting, and performance insights through OpenTelemetry, Prometheus, and Grafana.

## 🏗️ Package Structure

```
observability/
├── config/           # OpenTelemetry configuration and initialization
├── metrics/          # Hybrid metrics (legacy + OTEL) collection
├── tracing/          # Distributed tracing for FastMCP operations
├── exporters/        # Metrics exporters (Prometheus, OTLP, etc.)
├── dashboards/       # Grafana dashboard configurations
├── alerting/         # Prometheus/Grafana alerting rules
└── tests/           # Observability integration tests
```

## 📈 Components

### **Configuration** (`config/`)
- **`otel_config.py`**: OpenTelemetry initialization and setup
- Manages OTEL providers, exporters, and instrumentation
- Environment-based configuration with fallbacks

### **Metrics** (`metrics/`)
- **`hybrid_metrics.py`**: Dual-mode metrics supporting legacy + OTEL
- Backward compatible with existing metrics interface
- Real-time performance and business metrics collection

### **Tracing** (`tracing/`)
- **`fastmcp_tracer.py`**: Distributed tracing for FastMCP operations
- BMC API call tracing and user elicitation workflows
- Context propagation and span management

### **Exporters** (`exporters/`)
- **`prometheus_exporter.py`**: Prometheus metrics export configuration
- Custom metrics and collectors for FastMCP-specific data
- Integration with Grafana dashboards

### **Dashboards** (`dashboards/`)
- **`fastmcp-overview.json`**: Comprehensive Grafana dashboard
- Real-time server performance, health, and business metrics
- BMC API integration monitoring and user activity tracking

### **Alerting** (`alerting/`)
- **`fastmcp-alerts.yml`**: Prometheus alerting rules
- Critical system alerts (server down, high error rates)
- Performance degradation and resource utilization alerts
- BMC API connectivity and authentication alerts

## 🚀 Usage

### Basic Setup
```python
from observability import initialize_otel, HybridMetrics, get_fastmcp_tracer

# Initialize observability
tracer, meter = initialize_otel()
metrics = HybridMetrics()
fastmcp_tracer = get_fastmcp_tracer()
```

### Metrics Collection
```python
# Record request metrics
metrics.record_request("GET", "/assignments", 200, 0.15)

# Record BMC API calls
metrics.record_bmc_api_call("get_assignments", True, 0.25, 200)

# Record cache operations
metrics.record_cache_operation("get", True, "assignments")
```

### Distributed Tracing
```python
@trace_tool_execution("get_assignments")
async def get_assignments_tool(srid: str, level: str = None):
    # Tool execution automatically traced
    return await bmc_client.get_assignments(srid, level)
```

## 🔧 Configuration

### Environment Variables
```bash
# OTEL Configuration
OTEL_ENABLED=true
OTEL_TRACING_ENABLED=true
OTEL_METRICS_ENABLED=true
OTEL_SERVICE_NAME=fastmcp-server
OTEL_SERVICE_VERSION=2.3.1
OTEL_ENVIRONMENT=production

# Exporters
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_PROMETHEUS_PORT=9464
PROMETHEUS_ENABLED=true
```

### Grafana Dashboard Import
1. Import `dashboards/fastmcp-overview.json` into Grafana
2. Configure Prometheus data source
3. Set up alerting channels for notifications

### Prometheus Alerting
1. Add `alerting/fastmcp-alerts.yml` to Prometheus configuration
2. Configure alert manager for notifications
3. Set up escalation policies for critical alerts

## 📊 Metrics Available

### **Request Metrics**
- Total requests, success/failure rates
- Response time percentiles and averages
- Endpoint-specific performance metrics

### **BMC API Metrics**
- API call success rates and response times
- Authentication and authorization metrics
- Rate limiting and throttling statistics

### **System Metrics**
- Server health and uptime
- Resource utilization (CPU, memory)
- Cache hit rates and performance

### **Business Metrics**
- Assignment operations and success rates
- Release deployment metrics
- User elicitation workflow completion

## 🔍 Monitoring

### **Key Dashboards**
- **FastMCP Overview**: Comprehensive server health and performance
- **BMC API Integration**: API connectivity and performance metrics
- **User Activity**: Elicitation workflows and tool usage patterns

### **Critical Alerts**
- Server downtime or unresponsiveness
- High error rates (>5% over 5 minutes)
- BMC API connectivity issues
- Performance degradation (response times >2s)
- Resource exhaustion (memory >90%, CPU >80%)

## 🧪 Testing

Run observability integration tests:
```bash
python -m pytest observability/tests/ -v
```

Test OTEL configuration:
```bash
python observability/tests/test_integration.py
```

## 📚 Documentation

- [OpenTelemetry Setup Guide](../docs/otel-observability-setup.md)
- [Grafana Dashboard Configuration](../docs/grafana-setup.md)
- [Prometheus Alerting Rules](../docs/prometheus-alerts.md)
- [Performance Monitoring Best Practices](../docs/monitoring-best-practices.md)
