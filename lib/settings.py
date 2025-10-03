#!/usr/bin/env python3
"""
Configuration and Settings Management

Provides centralized configuration management for the BMC AMI DevX MCP Server
with environment variable integration and validation.
"""

import os
from typing import Optional

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable integration."""

    model_config = ConfigDict(
        env_prefix="FASTMCP_",
        case_sensitive=False,
        validate_assignment=True,
        extra="ignore",
    )

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    log_level: str = Field(default="INFO", description="Logging level")

    # BMC API configuration
    api_base_url: str = Field(
        default="https://devx.bmc.com/code-pipeline/api/v1",
        description="BMC API base URL",
    )
    api_token: Optional[str] = Field(default=None, description="BMC API token")
    api_timeout: int = Field(default=30, description="API request timeout in seconds")

    # Connection pool settings
    connection_pool_size: int = Field(
        default=20, description="HTTP connection pool size"
    )

    # Rate limiting configuration
    rate_limit_requests_per_minute: int = Field(
        default=60, description="Rate limit: requests per minute"
    )
    rate_limit_burst_size: int = Field(default=10, description="Rate limit: burst size")

    # Caching configuration
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_max_size: int = Field(default=1000, description="Maximum cache entries")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    cache_cleanup_interval: int = Field(
        default=60, description="Cache cleanup interval in seconds"
    )

    # Authentication configuration
    auth_enabled: bool = Field(default=False, description="Enable authentication")
    auth_provider: str = Field(default="", description="Authentication provider")

    # Error handling configuration
    max_retry_attempts: int = Field(default=3, description="Maximum retry attempts")
    retry_base_delay: float = Field(
        default=1.0, description="Base retry delay in seconds"
    )
    
    # Circuit breaker configuration
    circuit_breaker_failure_threshold: int = Field(
        default=5, description="Circuit breaker failure threshold"
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=60, description="Circuit breaker recovery timeout in seconds"
    )

    # Observability configuration
    otel_enabled: bool = Field(default=True, description="Enable OpenTelemetry")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(
        default=True, description="Enable distributed tracing"
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings instance from environment variables."""
        # Handle special cases for environment variables
        env_overrides = {}

        # Map environment variables that don't follow the FASTMCP_ prefix
        if os.getenv("HOST"):
            env_overrides["host"] = os.getenv("HOST")
        if os.getenv("PORT"):
            try:
                env_overrides["port"] = int(os.getenv("PORT"))
            except (ValueError, TypeError):
                pass  # Use default
        if os.getenv("API_BASE_URL"):
            env_overrides["api_base_url"] = os.getenv("API_BASE_URL")
        if os.getenv("API_TOKEN"):
            env_overrides["api_token"] = os.getenv("API_TOKEN")
        if os.getenv("LOG_LEVEL"):
            env_overrides["log_level"] = os.getenv("LOG_LEVEL")

        # Handle boolean environment variables
        for bool_field in [
            "cache_enabled",
            "auth_enabled",
            "otel_enabled",
            "metrics_enabled",
            "tracing_enabled",
        ]:
            env_key = f"FASTMCP_{bool_field.upper()}"
            if os.getenv(env_key):
                env_overrides[bool_field] = os.getenv(env_key, "").lower() in (
                    "true",
                    "1",
                    "yes",
                    "on",
                )

        # Handle integer environment variables with validation
        int_fields = [
            "api_timeout",
            "connection_pool_size",
            "rate_limit_requests_per_minute",
            "rate_limit_burst_size",
            "cache_max_size",
            "cache_ttl_seconds",
            "cache_cleanup_interval",
            "max_retry_attempts",
        ]

        for int_field in int_fields:
            env_key = f"FASTMCP_{int_field.upper()}"
            if os.getenv(env_key):
                try:
                    env_overrides[int_field] = int(os.getenv(env_key))
                except (ValueError, TypeError):
                    pass  # Use default

        # Handle float environment variables
        if os.getenv("FASTMCP_RETRY_BASE_DELAY"):
            try:
                env_overrides["retry_base_delay"] = float(
                    os.getenv("FASTMCP_RETRY_BASE_DELAY")
                )
            except (ValueError, TypeError):
                pass  # Use default

        try:
            return cls(**env_overrides)
        except Exception:
            # If validation fails, create instance with defaults only by temporarily
            # clearing environment variables that might cause validation errors

            # Save current environment
            original_env = dict(os.environ)

            try:
                # Clear problematic environment variables temporarily
                env_vars_to_clear = []
                for key in os.environ:
                    if key.startswith("FASTMCP_") or key in [
                        "PORT",
                        "HOST",
                        "API_BASE_URL",
                        "API_TOKEN",
                        "LOG_LEVEL",
                    ]:
                        env_vars_to_clear.append(key)

                for key in env_vars_to_clear:
                    del os.environ[key]

                # Create instance with defaults
                instance = cls()

                # Restore environment
                os.environ.clear()
                os.environ.update(original_env)

                # Apply valid parsed values
                for key, value in env_overrides.items():
                    if hasattr(instance, key):
                        try:
                            setattr(instance, key, value)
                        except Exception:
                            pass  # Keep default value

                return instance

            except Exception:
                # Restore environment in case of any error
                os.environ.clear()
                os.environ.update(original_env)
                raise

    def validate_configuration(self) -> bool:
        """Validate the current configuration."""
        issues = []

        # Validate port range
        if not (1 <= self.port <= 65535):
            issues.append(f"Invalid port: {self.port}")

        # Validate timeout values
        if self.api_timeout <= 0:
            issues.append(f"Invalid API timeout: {self.api_timeout}")

        # Validate cache settings
        if self.cache_max_size <= 0:
            issues.append(f"Invalid cache max size: {self.cache_max_size}")

        if self.cache_ttl_seconds <= 0:
            issues.append(f"Invalid cache TTL: {self.cache_ttl_seconds}")

        # Validate rate limiting
        if self.rate_limit_requests_per_minute <= 0:
            issues.append(f"Invalid rate limit: {self.rate_limit_requests_per_minute}")

        if self.rate_limit_burst_size <= 0:
            issues.append(f"Invalid burst size: {self.rate_limit_burst_size}")

        # Validate retry settings
        if self.max_retry_attempts < 0:
            issues.append(f"Invalid max retry attempts: {self.max_retry_attempts}")

        if self.retry_base_delay <= 0:
            issues.append(f"Invalid retry base delay: {self.retry_base_delay}")

        if issues:
            raise ValueError(f"Configuration validation failed: {'; '.join(issues)}")

        return True


# Global settings instance
settings = Settings.from_env()
