#!/usr/bin/env python3
"""
FastMCP Global Configuration

This module configures global FastMCP settings using environment variables
and provides a centralized configuration management system.
"""

import os
from pathlib import Path
from typing import Any, Dict

# Global FastMCP Configuration
FASTMCP_CONFIG = {
    # Logging Configuration
    "log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
    "mask_error_details": os.getenv("FASTMCP_MASK_ERROR_DETAILS", "false").lower()
    == "true",
    # Resource Configuration
    "resource_prefix_format": os.getenv("FASTMCP_RESOURCE_PREFIX_FORMAT", "path"),
    # Metadata Configuration
    "include_fastmcp_meta": os.getenv("FASTMCP_INCLUDE_FASTMCP_META", "true").lower()
    == "true",
    # OpenAPI Configuration
    "experimental_enable_new_openapi_parser": os.getenv(
        "FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER", "false"
    ).lower()
    == "true",
    # Server Configuration
    "server_name": os.getenv(
        "FASTMCP_SERVER_NAME", "BMC AMI DevX Code Pipeline MCP Server"
    ),
    "server_version": os.getenv("FASTMCP_SERVER_VERSION", "2.2.0"),
    # Authentication Configuration
    "auth_enabled": os.getenv("FASTMCP_AUTH_ENABLED", "false").lower() == "true",
    "auth_provider": os.getenv("FASTMCP_AUTH_PROVIDER", None),
    # Rate Limiting Configuration
    "rate_limit_enabled": os.getenv("FASTMCP_RATE_LIMIT_ENABLED", "true").lower()
    == "true",
    "rate_limit_requests_per_minute": int(
        os.getenv("FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
    ),
    "rate_limit_burst_size": int(os.getenv("FASTMCP_RATE_LIMIT_BURST_SIZE", "10")),
    # Caching Configuration
    "cache_enabled": os.getenv("FASTMCP_CACHE_ENABLED", "true").lower() == "true",
    "cache_max_size": int(os.getenv("FASTMCP_CACHE_MAX_SIZE", "1000")),
    "cache_default_ttl": int(os.getenv("FASTMCP_CACHE_DEFAULT_TTL", "300")),
    # Monitoring Configuration
    "monitoring_enabled": os.getenv("FASTMCP_MONITORING_ENABLED", "true").lower()
    == "true",
    "metrics_enabled": os.getenv("FASTMCP_METRICS_ENABLED", "true").lower() == "true",
    # Error Handling Configuration
    "error_recovery_enabled": os.getenv(
        "FASTMCP_ERROR_RECOVERY_ENABLED", "true"
    ).lower()
    == "true",
    "max_retry_attempts": int(os.getenv("FASTMCP_MAX_RETRY_ATTEMPTS", "3")),
    # Tag-based Filtering Configuration
    "include_tags": set(
        os.getenv("FASTMCP_INCLUDE_TAGS", "public,api,monitoring,management").split(",")
    ),
    "exclude_tags": set(
        os.getenv("FASTMCP_EXCLUDE_TAGS", "internal,deprecated").split(",")
    ),
    # Custom Routes Configuration
    "custom_routes_enabled": os.getenv("FASTMCP_CUSTOM_ROUTES_ENABLED", "true").lower()
    == "true",
    "health_check_path": os.getenv("FASTMCP_HEALTH_CHECK_PATH", "/health"),
    "status_path": os.getenv("FASTMCP_STATUS_PATH", "/status"),
    "metrics_path": os.getenv("FASTMCP_METRICS_PATH", "/metrics"),
    "ready_path": os.getenv("FASTMCP_READY_PATH", "/ready"),
    # Resource Templates Configuration
    "resource_templates_enabled": os.getenv(
        "FASTMCP_RESOURCE_TEMPLATES_ENABLED", "true"
    ).lower()
    == "true",
    "resource_prefix": os.getenv("FASTMCP_RESOURCE_PREFIX", "bmc://"),
    # Prompts Configuration
    "prompts_enabled": os.getenv("FASTMCP_PROMPTS_ENABLED", "true").lower() == "true",
    # BMC API Configuration
    "bmc_api_base_url": os.getenv(
        "BMC_API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1"
    ),
    "bmc_api_timeout": int(os.getenv("BMC_API_TIMEOUT", "30")),
    "bmc_api_token": os.getenv("BMC_API_TOKEN", ""),
    # OpenAPI Specification Configuration
    "openapi_spec_path": os.getenv("FASTMCP_OPENAPI_SPEC_PATH", "config/openapi.json"),
    "openapi_spec_url": os.getenv("FASTMCP_OPENAPI_SPEC_URL", None),
}


def get_fastmcp_config() -> Dict[str, Any]:
    """Get the current FastMCP configuration."""
    # Read current environment variables dynamically
    return {
        # Global Configuration
        "log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
        "mask_error_details": os.getenv("FASTMCP_MASK_ERROR_DETAILS", "false").lower()
        == "true",
        "on_duplicate_tools": os.getenv("FASTMCP_ON_DUPLICATE_TOOLS", "error"),
        "resource_prefix_format": os.getenv("FASTMCP_RESOURCE_PREFIX_FORMAT", "path"),
        # Metadata Configuration
        "include_fastmcp_meta": os.getenv(
            "FASTMCP_INCLUDE_FASTMCP_META", "true"
        ).lower()
        == "true",
        # OpenAPI Configuration
        "experimental_enable_new_openapi_parser": os.getenv(
            "FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER", "false"
        ).lower()
        == "true",
        # Server Configuration
        "server_name": os.getenv(
            "FASTMCP_SERVER_NAME", "BMC AMI DevX Code Pipeline MCP Server"
        ),
        "server_version": os.getenv("FASTMCP_SERVER_VERSION", "2.2.0"),
        # Authentication Configuration
        "auth_enabled": os.getenv("FASTMCP_AUTH_ENABLED", "false").lower() == "true",
        "auth_provider": os.getenv("FASTMCP_AUTH_PROVIDER", None),
        # Rate Limiting Configuration
        "rate_limit_enabled": os.getenv("FASTMCP_RATE_LIMIT_ENABLED", "true").lower()
        == "true",
        "rate_limit_requests_per_minute": int(
            os.getenv("FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
        ),
        "rate_limit_burst_size": int(os.getenv("FASTMCP_RATE_LIMIT_BURST_SIZE", "10")),
        # Caching Configuration
        "cache_enabled": os.getenv("FASTMCP_CACHE_ENABLED", "true").lower() == "true",
        "cache_max_size": int(os.getenv("FASTMCP_CACHE_MAX_SIZE", "1000")),
        "cache_default_ttl": int(os.getenv("FASTMCP_CACHE_DEFAULT_TTL", "300")),
        # Monitoring Configuration
        "monitoring_enabled": os.getenv("FASTMCP_MONITORING_ENABLED", "true").lower()
        == "true",
        "metrics_enabled": os.getenv("FASTMCP_METRICS_ENABLED", "true").lower()
        == "true",
        # Custom Routes Configuration
        "custom_routes_enabled": os.getenv(
            "FASTMCP_CUSTOM_ROUTES_ENABLED", "true"
        ).lower()
        == "true",
        # Resource Templates Configuration
        "resource_templates_enabled": os.getenv(
            "FASTMCP_RESOURCE_TEMPLATES_ENABLED", "true"
        ).lower()
        == "true",
        # Prompts Configuration
        "prompts_enabled": os.getenv("FASTMCP_PROMPTS_ENABLED", "true").lower()
        == "true",
        # BMC API Configuration
        "bmc_api_base_url": os.getenv(
            "BMC_API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1"
        ),
        "bmc_api_timeout": int(os.getenv("BMC_API_TIMEOUT", "30")),
        "openapi_spec_path": os.getenv(
            "FASTMCP_OPENAPI_SPEC_PATH", "config/ispw_openapi_spec.json"
        ),
    }


def update_fastmcp_config(updates: Dict[str, Any]) -> None:
    """Update FastMCP configuration with new values."""
    global FASTMCP_CONFIG
    FASTMCP_CONFIG.update(updates)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific configuration value."""
    return FASTMCP_CONFIG.get(key, default)


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled."""
    return FASTMCP_CONFIG.get(f"{feature}_enabled", False)


def get_tag_config() -> Dict[str, set]:
    """Get tag-based filtering configuration."""
    return {
        "include_tags": FASTMCP_CONFIG["include_tags"],
        "exclude_tags": FASTMCP_CONFIG["exclude_tags"],
    }


def get_server_config() -> Dict[str, Any]:
    """Get server-specific configuration."""
    return {
        "name": FASTMCP_CONFIG["server_name"],
        "version": FASTMCP_CONFIG["server_version"],
        "auth_enabled": FASTMCP_CONFIG["auth_enabled"],
        "auth_provider": FASTMCP_CONFIG["auth_provider"],
        "log_level": FASTMCP_CONFIG["log_level"],
        "mask_error_details": FASTMCP_CONFIG["mask_error_details"],
        "include_fastmcp_meta": FASTMCP_CONFIG["include_fastmcp_meta"],
    }


def get_rate_limiting_config() -> Dict[str, Any]:
    """Get rate limiting configuration."""
    return {
        "enabled": FASTMCP_CONFIG["rate_limit_enabled"],
        "requests_per_minute": FASTMCP_CONFIG["rate_limit_requests_per_minute"],
        "burst_size": FASTMCP_CONFIG["rate_limit_burst_size"],
    }


def get_caching_config() -> Dict[str, Any]:
    """Get caching configuration."""
    return {
        "enabled": FASTMCP_CONFIG["cache_enabled"],
        "max_size": FASTMCP_CONFIG["cache_max_size"],
        "default_ttl": FASTMCP_CONFIG["cache_default_ttl"],
    }


def get_monitoring_config() -> Dict[str, Any]:
    """Get monitoring configuration."""
    return {
        "enabled": FASTMCP_CONFIG["monitoring_enabled"],
        "metrics_enabled": FASTMCP_CONFIG["metrics_enabled"],
    }


def get_custom_routes_config() -> Dict[str, str]:
    """Get custom routes configuration."""
    return {
        "health_check": FASTMCP_CONFIG["health_check_path"],
        "status": FASTMCP_CONFIG["status_path"],
        "metrics": FASTMCP_CONFIG["metrics_path"],
        "ready": FASTMCP_CONFIG["ready_path"],
    }


def get_bmc_api_config() -> Dict[str, Any]:
    """Get BMC API configuration."""
    return {
        "base_url": FASTMCP_CONFIG["bmc_api_base_url"],
        "timeout": FASTMCP_CONFIG["bmc_api_timeout"],
        "token": FASTMCP_CONFIG["bmc_api_token"],
    }


def validate_config() -> Dict[str, list]:
    """Validate the current configuration and return any issues."""
    issues = []

    # Read current environment variables
    bmc_api_base_url = os.getenv(
        "BMC_API_BASE_URL", "https://devx.bmc.com/code-pipeline/api/v1"
    )
    auth_enabled = os.getenv("FASTMCP_AUTH_ENABLED", "true").lower() == "true"
    auth_provider = os.getenv("FASTMCP_AUTH_PROVIDER", "")

    # Validate required fields
    if not bmc_api_base_url:
        issues.append("BMC_API_BASE_URL is required")

    if auth_enabled and not auth_provider:
        issues.append(
            "FASTMCP_AUTH_PROVIDER is required when authentication is enabled"
        )

    # Validate numeric fields
    try:
        int(os.getenv("FASTMCP_RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
        int(os.getenv("FASTMCP_RATE_LIMIT_BURST_SIZE", "10"))
        int(os.getenv("FASTMCP_CACHE_MAX_SIZE", "1000"))
        int(os.getenv("FASTMCP_CACHE_DEFAULT_TTL", "300"))
        int(os.getenv("BMC_API_TIMEOUT", "30"))
    except ValueError as e:
        issues.append(f"Invalid numeric configuration: {e}")

    # Validate file paths
    openapi_spec_path = Path(FASTMCP_CONFIG["openapi_spec_path"])
    if not openapi_spec_path.exists():
        issues.append(f"OpenAPI specification file not found: {openapi_spec_path}")

    return {"issues": issues, "valid": len(issues) == 0}


def print_config_summary() -> None:
    """Print a summary of the current configuration."""
    print("🔧 FastMCP Global Configuration Summary")
    print("=" * 50)

    # Server Configuration
    server_config = get_server_config()
    print(f"Server: {server_config['name']} v{server_config['version']}")
    print(
        f"Authentication: {'Enabled' if server_config['auth_enabled'] else 'Disabled'}"
    )
    print(f"Log Level: {server_config['log_level']}")

    # Features
    features = [
        ("Rate Limiting", is_feature_enabled("rate_limit")),
        ("Caching", is_feature_enabled("cache")),
        ("Monitoring", is_feature_enabled("monitoring")),
        ("Custom Routes", is_feature_enabled("custom_routes")),
        ("Resource Templates", is_feature_enabled("resource_templates")),
        ("Prompts", is_feature_enabled("prompts")),
    ]

    print("\nFeatures:")
    for feature, enabled in features:
        status = "✅ Enabled" if enabled else "❌ Disabled"
        print(f"  • {feature}: {status}")

    # Tag Configuration
    tag_config = get_tag_config()
    print(f"\nTag Filtering:")
    print(f"  • Include: {', '.join(tag_config['include_tags'])}")
    print(f"  • Exclude: {', '.join(tag_config['exclude_tags'])}")

    # Validation
    validation = validate_config()
    if validation["valid"]:
        print("\n✅ Configuration is valid")
    else:
        print("\n❌ Configuration issues found:")
        for issue in validation["issues"]:
            print(f"  • {issue}")


if __name__ == "__main__":
    print_config_summary()
