#!/usr/bin/env python3
"""
OpenTelemetry Configuration for FastMCP Server

This module configures OpenTelemetry instrumentation including tracing, metrics,
and logging for the BMC AMI DevX Code Pipeline FastMCP server.
"""

import os
import logging
from typing import Optional, Dict, Any
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.semantic_conventions.resource import ResourceAttributes

logger = logging.getLogger(__name__)


class OTELConfig:
    """OpenTelemetry configuration for FastMCP server."""
    
    def __init__(self):
        """Initialize OTEL configuration with environment variables."""
        # Service identification
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "fastmcp-server")
        self.service_version = os.getenv("OTEL_SERVICE_VERSION", "2.3.1")
        self.service_namespace = os.getenv("OTEL_SERVICE_NAMESPACE", "bmc-devx")
        self.environment = os.getenv("OTEL_ENVIRONMENT", "development")
        
        # OTEL configuration
        self.otel_enabled = os.getenv("OTEL_ENABLED", "true").lower() == "true"
        self.tracing_enabled = os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true"
        self.metrics_enabled = os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true"
        
        # Exporter configuration
        self.otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        self.jaeger_endpoint = os.getenv("OTEL_EXPORTER_JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
        self.prometheus_port = int(os.getenv("OTEL_PROMETHEUS_PORT", "9464"))
        
        # Sampling configuration
        self.trace_sample_rate = float(os.getenv("OTEL_TRACE_SAMPLE_RATE", "1.0"))
        self.console_exporter = os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true"
        
        # Resource attributes
        self.resource_attributes = self._build_resource_attributes()
        
        # Initialize components
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        
    def _build_resource_attributes(self) -> Dict[str, str]:
        """Build resource attributes for OTEL."""
        attributes = {
            ResourceAttributes.SERVICE_NAME: self.service_name,
            ResourceAttributes.SERVICE_VERSION: self.service_version,
            ResourceAttributes.SERVICE_NAMESPACE: self.service_namespace,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            "service.instance.id": os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", "unknown")),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        }
        
        # Add custom attributes from environment
        for key, value in os.environ.items():
            if key.startswith("OTEL_RESOURCE_ATTRIBUTES_"):
                attr_name = key.replace("OTEL_RESOURCE_ATTRIBUTES_", "").lower()
                attributes[attr_name] = value
                
        return attributes
    
    def setup_tracing(self) -> Optional[trace.Tracer]:
        """Configure OpenTelemetry tracing."""
        if not self.otel_enabled or not self.tracing_enabled:
            logger.info("OpenTelemetry tracing is disabled")
            return None
            
        try:
            # Create resource
            resource = Resource.create(self.resource_attributes)
            
            # Set up tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)
            
            # Configure exporters
            exporters = []
            
            # OTLP exporter
            if self.otlp_endpoint:
                try:
                    otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
                    exporters.append(otlp_exporter)
                    logger.info(f"OTLP trace exporter configured: {self.otlp_endpoint}")
                except Exception as e:
                    logger.warning(f"Failed to configure OTLP exporter: {e}")
            
            # Jaeger exporter
            if self.jaeger_endpoint:
                try:
                    jaeger_exporter = JaegerExporter(endpoint=self.jaeger_endpoint)
                    exporters.append(jaeger_exporter)
                    logger.info(f"Jaeger trace exporter configured: {self.jaeger_endpoint}")
                except Exception as e:
                    logger.warning(f"Failed to configure Jaeger exporter: {e}")
            
            # Console exporter for development
            if self.console_exporter:
                console_exporter = ConsoleSpanExporter()
                exporters.append(console_exporter)
                logger.info("Console trace exporter configured")
            
            # Add span processors
            for exporter in exporters:
                span_processor = BatchSpanProcessor(exporter)
                tracer_provider.add_span_processor(span_processor)
            
            # Create tracer
            self.tracer = trace.get_tracer(
                instrumenting_module_name=__name__,
                instrumenting_library_version=self.service_version
            )
            
            logger.info(f"OpenTelemetry tracing initialized for {self.service_name}")
            return self.tracer
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
            return None
    
    def setup_metrics(self) -> Optional[metrics.Meter]:
        """Configure OpenTelemetry metrics."""
        if not self.otel_enabled or not self.metrics_enabled:
            logger.info("OpenTelemetry metrics is disabled")
            return None
            
        try:
            # Create resource
            resource = Resource.create(self.resource_attributes)
            
            # Configure metric readers
            readers = []
            
            # Prometheus metrics reader
            try:
                prometheus_reader = PrometheusMetricReader(port=self.prometheus_port)
                readers.append(prometheus_reader)
                logger.info(f"Prometheus metrics reader configured on port {self.prometheus_port}")
            except Exception as e:
                logger.warning(f"Failed to configure Prometheus reader: {e}")
            
            # OTLP metrics reader
            if self.otlp_endpoint:
                try:
                    otlp_reader = PeriodicExportingMetricReader(
                        OTLPMetricExporter(endpoint=self.otlp_endpoint),
                        export_interval_millis=30000,  # 30 seconds
                    )
                    readers.append(otlp_reader)
                    logger.info(f"OTLP metrics reader configured: {self.otlp_endpoint}")
                except Exception as e:
                    logger.warning(f"Failed to configure OTLP metrics reader: {e}")
            
            # Set up meter provider
            if readers:
                meter_provider = MeterProvider(resource=resource, metric_readers=readers)
                metrics.set_meter_provider(meter_provider)
                
                # Create meter
                self.meter = metrics.get_meter(
                    instrumenting_module_name=__name__,
                    instrumenting_library_version=self.service_version
                )
                
                logger.info(f"OpenTelemetry metrics initialized for {self.service_name}")
                return self.meter
            else:
                logger.warning("No metric readers configured, metrics disabled")
                return None
                
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry metrics: {e}")
            return None
    
    def setup_auto_instrumentation(self):
        """Configure automatic instrumentation."""
        if not self.otel_enabled:
            return
            
        try:
            # HTTPX instrumentation for BMC API calls
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTPX auto-instrumentation enabled")
            
            # Asyncio instrumentation
            AsyncioInstrumentor().instrument()
            logger.info("Asyncio auto-instrumentation enabled")
            
        except Exception as e:
            logger.error(f"Failed to setup auto-instrumentation: {e}")
    
    def initialize(self) -> tuple[Optional[trace.Tracer], Optional[metrics.Meter]]:
        """Initialize all OpenTelemetry components."""
        if not self.otel_enabled:
            logger.info("OpenTelemetry is disabled")
            return None, None
            
        logger.info(f"Initializing OpenTelemetry for {self.service_name} v{self.service_version}")
        
        # Setup components
        tracer = self.setup_tracing()
        meter = self.setup_metrics()
        self.setup_auto_instrumentation()
        
        return tracer, meter
    
    def get_resource_attributes(self) -> Dict[str, Any]:
        """Get resource attributes for manual instrumentation."""
        return self.resource_attributes.copy()


# Global OTEL configuration instance
_otel_config: Optional[OTELConfig] = None
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None


def get_otel_config() -> OTELConfig:
    """Get global OTEL configuration instance."""
    global _otel_config
    if _otel_config is None:
        _otel_config = OTELConfig()
    return _otel_config


def initialize_otel() -> tuple[Optional[trace.Tracer], Optional[metrics.Meter]]:
    """Initialize OpenTelemetry globally."""
    global _tracer, _meter
    
    if _tracer is not None or _meter is not None:
        logger.info("OpenTelemetry already initialized")
        return _tracer, _meter
    
    config = get_otel_config()
    _tracer, _meter = config.initialize()
    
    return _tracer, _meter


def get_tracer() -> Optional[trace.Tracer]:
    """Get global tracer instance."""
    global _tracer
    if _tracer is None:
        initialize_otel()
    return _tracer


def get_meter() -> Optional[metrics.Meter]:
    """Get global meter instance."""
    global _meter
    if _meter is None:
        initialize_otel()
    return _meter


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    config = get_otel_config()
    return config.otel_enabled and config.tracing_enabled


def is_metrics_enabled() -> bool:
    """Check if metrics is enabled."""
    config = get_otel_config()
    return config.otel_enabled and config.metrics_enabled


# Initialize OTEL on module import if enabled
if os.getenv("OTEL_AUTO_INITIALIZE", "true").lower() == "true":
    initialize_otel()
