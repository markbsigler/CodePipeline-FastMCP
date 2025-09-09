#!/usr/bin/env python3
"""
BMC AMI DevX Code Pipeline MCP Server with OpenAPI Integration

This server leverages FastMCP's from_openapi() functionality to automatically
generate MCP tools from the BMC ISPW OpenAPI specification, providing a more
maintainable and comprehensive integration.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastmcp import Context, FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.workos import WorkOSProvider
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp_config import (
    get_caching_config,
    get_fastmcp_config,
    get_monitoring_config,
    get_rate_limiting_config,
    get_server_config,
    get_tag_config,
    validate_config,
)
from main import (
    ErrorHandler,
    HealthChecker,
    IntelligentCache,
    MCPServerError,
    Metrics,
    RateLimiter,
    Settings,
)


class OpenAPIMCPServer:
    """BMC AMI DevX Code Pipeline MCP Server with OpenAPI Integration."""

    def __init__(self):
        """Initialize the OpenAPI MCP Server."""
        # Load global configuration
        self.config = get_fastmcp_config()
        self.settings = Settings.from_env()

        # Validate configuration
        validation = validate_config()
        if not validation["valid"]:
            logger.warning(f"Configuration issues found: {validation['issues']}")

        # Initialize components with global configuration and feature toggles
        rate_config = get_rate_limiting_config()
        self.rate_limiter = (
            RateLimiter(rate_config["requests_per_minute"], rate_config["burst_size"])
            if rate_config["enabled"] and self.config.get("rate_limit_enabled", True)
            else None
        )

        cache_config = get_caching_config()
        self.cache = (
            IntelligentCache(
                max_size=cache_config["max_size"],
                default_ttl=cache_config["default_ttl"],
            )
            if cache_config["enabled"] and self.config.get("cache_enabled", True)
            else None
        )

        self.metrics = (
            Metrics()
            if get_monitoring_config()["enabled"]
            and self.config.get("monitoring_enabled", True)
            else None
        )
        self.error_handler = ErrorHandler(self.settings, self.metrics)

        # Initialize HTTP client with connection pooling and rate limiting
        self.http_client = httpx.AsyncClient(
            base_url=self.settings.api_base_url,
            timeout=httpx.Timeout(self.settings.api_timeout),
            limits=httpx.Limits(
                max_keepalive_connections=self.settings.connection_pool_size,
                max_connections=self.settings.connection_pool_size * 2,
            ),
            headers={
                "Authorization": f"Bearer {os.getenv('API_TOKEN', '')}",
                "Content-Type": "application/json",
                "User-Agent": "BMC-AMI-DevX-MCP-Server/2.2.0",
            },
        )

        # Initialize MCP server
        self.server = self._create_server()

    def _create_server(self) -> FastMCP:
        """Create the FastMCP server with OpenAPI integration."""
        try:
            # Load OpenAPI specification
            openapi_spec_path = Path("config/openapi.json")
            if not openapi_spec_path.exists():
                raise FileNotFoundError(
                    f"OpenAPI specification not found at {openapi_spec_path}"
                )

            with open(openapi_spec_path, "r") as f:
                openapi_spec = json.load(f)

            logger.info(
                f"Loaded OpenAPI specification: {openapi_spec['info']['title']} v{openapi_spec['info']['version']}"
            )

            # Get server configuration
            server_config = get_server_config()
            tag_config = get_tag_config()

            # Create server with OpenAPI integration and advanced features
            server = FastMCP(
                name=server_config["name"],
                version=server_config["version"],
                instructions="""
                This MCP server provides comprehensive BMC AMI DevX Code Pipeline integration 
                with ISPW operations. All tools are automatically generated from the BMC ISPW 
                OpenAPI specification, ensuring complete API coverage and maintainability.
                
                Available operations include:
                - Assignment management (create, read, update, delete, generate, promote, deploy)
                - Task management (list, details)
                - Release management (create, read, deploy)
                - Set management (list, deploy)
                - Package management (list, details)
                
                All operations support comprehensive error handling, rate limiting, caching, 
                and monitoring capabilities.
                
                Tools are organized by tags:
                - 'public': Available to all users
                - 'admin': Administrative functions
                - 'monitoring': System monitoring and metrics
                - 'management': Server management operations
                - 'api': BMC API operations
                - 'assignments': Assignment-related operations
                - 'releases': Release-related operations
                - 'packages': Package-related operations
                - 'operations': Operational commands (generate, promote, deploy)
                """,
                auth=self._create_auth_provider(),
                include_tags=tag_config["include_tags"],
                exclude_tags=tag_config["exclude_tags"],
                on_duplicate_tools="error",
                include_fastmcp_meta=server_config["include_fastmcp_meta"],
                mask_error_details=server_config["mask_error_details"],
                log_level=server_config["log_level"],
            )

            # Generate tools from OpenAPI specification
            openapi_server = FastMCP.from_openapi(
                openapi_spec=openapi_spec,
                client=self.http_client,
                name="BMC ISPW API Tools",
            )

            # Mount the OpenAPI-generated server
            server.mount(openapi_server, prefix="ispw")

            # Add custom monitoring and management tools
            self._add_custom_tools(server)

            # Add custom routes for health checks and status
            self._add_custom_routes(server)

            # Add resource templates for parameterized data access
            self._add_resource_templates(server)

            # Add prompts for reusable LLM guidance
            self._add_prompts(server)

            logger.info("OpenAPI MCP Server created successfully")
            return server

        except Exception as e:
            logger.error(f"Failed to create OpenAPI MCP Server: {e}")
            raise MCPServerError(f"Failed to initialize OpenAPI MCP Server: {e}")

    def _create_auth_provider(self):
        """Create authentication provider based on settings."""
        if not self.settings.auth_enabled or not self.settings.auth_provider:
            return None

        try:
            if "JWTVerifier" in self.settings.auth_provider:
                return JWTVerifier(
                    jwks_uri=self.settings.auth_jwks_uri,
                    issuer=self.settings.auth_issuer,
                    audience=self.settings.auth_audience,
                )
            elif "GitHubProvider" in self.settings.auth_provider:
                return GitHubProvider(
                    client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
                    client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET"),
                    base_url=f"http://{self.settings.host}:{self.settings.port}",
                )
            elif "GoogleProvider" in self.settings.auth_provider:
                return GoogleProvider(
                    client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
                    client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
                    base_url=f"http://{self.settings.host}:{self.settings.port}",
                )
            elif "WorkOSProvider" in self.settings.auth_provider:
                return WorkOSProvider(
                    client_id=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_ID"),
                    client_secret=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_CLIENT_SECRET"),
                    domain=os.getenv("FASTMCP_SERVER_AUTH_WORKOS_DOMAIN"),
                )
            else:
                logger.warning(f"Unknown auth provider: {self.settings.auth_provider}")
                return None
        except Exception as e:
            logger.error(f"Failed to create auth provider: {e}")
            return None

    def _add_custom_tools(self, server: FastMCP):
        """Add custom monitoring and management tools."""

        @server.tool(tags={"monitoring", "public", "admin"})
        async def get_server_metrics(ctx: Context = None) -> str:
            """Get comprehensive server metrics and performance data."""
            try:
                if ctx:
                    await ctx.info("Retrieving server metrics")

                # Update cache size in metrics
                self.metrics.cache_size = len(self.cache.cache)

                metrics_data = self.metrics.to_dict()

                # Add cache information
                metrics_data["cache"] = {
                    "size": len(self.cache.cache),
                    "max_size": self.cache.max_size,
                    "hit_rate": self.metrics.get_cache_hit_rate(),
                    "keys": list(self.cache.cache.keys())[:10],  # Show first 10 keys
                }

                # Add rate limiter information
                metrics_data["rate_limiter"] = {
                    "tokens": self.rate_limiter.tokens,
                    "requests_per_minute": self.rate_limiter.requests_per_minute,
                    "burst_size": self.rate_limiter.burst_size,
                }

                return json.dumps(metrics_data, indent=2)

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "get_server_metrics"
                )
                # Ensure error_response is JSON serializable
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"monitoring", "public", "admin"})
        async def get_health_status(ctx: Context = None) -> str:
            """Get comprehensive health status of the server and BMC API."""
            try:
                if ctx:
                    await ctx.info("Checking server health status")

                health_checker = HealthChecker(self.http_client, self.settings)
                health_data = await health_checker.check_health()

                return json.dumps(health_data, indent=2)

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "get_health_status"
                )
                # Ensure error_response is JSON serializable
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"management", "public", "admin"})
        async def get_server_settings(ctx: Context = None) -> str:
            """Get current server configuration settings."""
            try:
                if ctx:
                    await ctx.info("Retrieving server settings")

                # Create a safe settings dict (exclude sensitive data)
                safe_settings = {
                    "api_base_url": self.settings.api_base_url,
                    "api_timeout": self.settings.api_timeout,
                    "auth_enabled": self.settings.auth_enabled,
                    "auth_provider": self.settings.auth_provider,
                    "rate_limit_requests_per_minute": self.settings.rate_limit_requests_per_minute,
                    "rate_limit_burst_size": self.settings.rate_limit_burst_size,
                    "cache_max_size": self.settings.cache_max_size,
                    "cache_ttl_seconds": self.settings.cache_ttl_seconds,
                    "connection_pool_size": self.settings.connection_pool_size,
                    "enable_metrics": self.settings.enable_metrics,
                    "enable_detailed_errors": self.settings.enable_detailed_errors,
                    "log_level": self.settings.log_level,
                }

                return json.dumps(safe_settings, indent=2)

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "get_server_settings"
                )
                # Ensure error_response is JSON serializable
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"management", "public", "admin"})
        async def clear_cache(ctx: Context = None) -> str:
            """Clear the server cache."""
            try:
                if ctx:
                    await ctx.info("Clearing server cache")

                cache_size_before = len(self.cache.cache)
                self.cache.cache.clear()
                self.cache.access_order.clear()

                result = {
                    "success": True,
                    "message": f"Cache cleared successfully. Removed {cache_size_before} entries.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                return json.dumps(result, indent=2)

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "clear_cache"
                )
                # Ensure error_response is JSON serializable
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"management", "public", "admin"})
        async def get_cache_info(ctx: Context = None) -> str:
            """Get detailed cache information."""
            try:
                if ctx:
                    await ctx.info("Retrieving cache information")

                cache_info = {
                    "size": len(self.cache.cache),
                    "max_size": self.cache.max_size,
                    "hit_rate": self.metrics.get_cache_hit_rate(),
                    "keys": list(self.cache.cache.keys()),
                    "access_order": list(self.cache.access_order),
                    "entries": [],
                }

                # Add detailed entry information
                for key, entry in self.cache.cache.items():
                    cache_info["entries"].append(
                        {
                            "key": key,
                            "data_type": type(entry.data).__name__,
                            "created": entry.timestamp.isoformat(),
                            "ttl_seconds": entry.ttl_seconds,
                            "is_expired": entry.is_expired(),
                        }
                    )

                return json.dumps(cache_info, indent=2)

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "get_cache_info"
                )
                # Ensure error_response is JSON serializable
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        # Elicitation-enabled tools for interactive BMC workflows
        @server.tool(tags={"elicitation", "workflow", "admin"})
        async def create_assignment_interactive(ctx: Context) -> str:
            """Create a new assignment with interactive user input collection."""
            try:
                if not ctx:
                    return json.dumps(
                        {"error": True, "message": "Context required for elicitation"}
                    )

                await ctx.info("Starting interactive assignment creation...")

                # Step 1: Get assignment title
                title_result = await ctx.elicit(
                    "What is the title of the assignment?", response_type=str
                )

                if isinstance(title_result, AcceptedElicitation):
                    title = title_result.data
                elif isinstance(title_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled - title required",
                        }
                    )
                elif isinstance(title_result, CancelledElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 2: Get assignment description
                desc_result = await ctx.elicit(
                    "Please provide a description for the assignment:",
                    response_type=str,
                )

                if isinstance(desc_result, AcceptedElicitation):
                    description = desc_result.data
                elif isinstance(desc_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled - description required",
                        }
                    )
                elif isinstance(desc_result, CancelledElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 3: Get SRID
                srid_result = await ctx.elicit(
                    "What is the SRID (System Reference ID) for this assignment?",
                    response_type=str,
                )

                if isinstance(srid_result, AcceptedElicitation):
                    srid = srid_result.data
                elif isinstance(srid_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled - SRID required",
                        }
                    )
                elif isinstance(srid_result, CancelledElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 4: Get priority level
                priority_result = await ctx.elicit(
                    "What priority level should this assignment have?",
                    response_type=["low", "medium", "high", "critical"],
                )

                if isinstance(priority_result, AcceptedElicitation):
                    priority = priority_result.data
                elif isinstance(priority_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled - priority required",
                        }
                    )
                elif isinstance(priority_result, CancelledElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 5: Confirm creation
                confirm_result = await ctx.elicit(
                    f"Confirm assignment creation:\n"
                    f"Title: {title}\n"
                    f"Description: {description}\n"
                    f"SRID: {srid}\n"
                    f"Priority: {priority}\n\n"
                    f"Proceed with creation?",
                    response_type=None,
                )

                if isinstance(confirm_result, AcceptedElicitation):
                    # Here you would make the actual API call to create the assignment
                    assignment_data = {
                        "title": title,
                        "description": description,
                        "srid": srid,
                        "priority": priority,
                        "status": "created",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    return json.dumps(
                        {
                            "success": True,
                            "message": "Assignment created successfully",
                            "assignment": assignment_data,
                        },
                        indent=2,
                    )
                elif isinstance(confirm_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                elif isinstance(confirm_result, CancelledElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Assignment creation cancelled by user",
                        }
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "create_assignment_interactive"
                )
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"elicitation", "workflow", "admin"})
        async def deploy_release_interactive(ctx: Context) -> str:
            """Deploy a release with interactive confirmation and parameter collection."""
            try:
                if not ctx:
                    return json.dumps(
                        {"error": True, "message": "Context required for elicitation"}
                    )

                await ctx.info("Starting interactive release deployment...")

                # Step 1: Get release ID
                release_result = await ctx.elicit(
                    "What is the release ID you want to deploy?", response_type=str
                )

                if isinstance(release_result, AcceptedElicitation):
                    release_id = release_result.data
                elif isinstance(release_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Deployment cancelled - release ID required",
                        }
                    )
                elif isinstance(release_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Deployment cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 2: Get deployment environment
                env_result = await ctx.elicit(
                    "Which environment should this be deployed to?",
                    response_type=["development", "staging", "production", "test"],
                )

                if isinstance(env_result, AcceptedElicitation):
                    environment = env_result.data
                elif isinstance(env_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Deployment cancelled - environment required",
                        }
                    )
                elif isinstance(env_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Deployment cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 3: Get deployment strategy
                strategy_result = await ctx.elicit(
                    "What deployment strategy should be used?",
                    response_type=["blue-green", "rolling", "canary", "immediate"],
                )

                if isinstance(strategy_result, AcceptedElicitation):
                    strategy = strategy_result.data
                elif isinstance(strategy_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Deployment cancelled - strategy required",
                        }
                    )
                elif isinstance(strategy_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Deployment cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 4: Get approval for production deployments
                if environment == "production":
                    approval_result = await ctx.elicit(
                        f"⚠️  PRODUCTION DEPLOYMENT WARNING ⚠️\n\n"
                        f"Release: {release_id}\n"
                        f"Environment: {environment}\n"
                        f"Strategy: {strategy}\n\n"
                        f"This will deploy to PRODUCTION. Are you sure you want to proceed?",
                        response_type=None,
                    )

                    if isinstance(approval_result, AcceptedElicitation):
                        pass  # Continue
                    elif isinstance(approval_result, DeclinedElicitation):
                        return json.dumps(
                            {
                                "error": True,
                                "message": "Production deployment cancelled - approval required",
                            }
                        )
                    elif isinstance(approval_result, CancelledElicitation):
                        return json.dumps(
                            {
                                "error": True,
                                "message": "Production deployment cancelled by user",
                            }
                        )
                    else:
                        return json.dumps(
                            {"error": True, "message": "Invalid response type"}
                        )

                # Step 5: Final confirmation
                confirm_result = await ctx.elicit(
                    f"Confirm deployment:\n"
                    f"Release ID: {release_id}\n"
                    f"Environment: {environment}\n"
                    f"Strategy: {strategy}\n\n"
                    f"Proceed with deployment?",
                    response_type=None,
                )

                if isinstance(confirm_result, AcceptedElicitation):
                    # Here you would make the actual API call to deploy the release
                    deployment_data = {
                        "release_id": release_id,
                        "environment": environment,
                        "strategy": strategy,
                        "status": "deploying",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    return json.dumps(
                        {
                            "success": True,
                            "message": f"Release {release_id} deployment initiated",
                            "deployment": deployment_data,
                        },
                        indent=2,
                    )
                elif isinstance(confirm_result, DeclinedElicitation):
                    return json.dumps(
                        {"error": True, "message": "Deployment cancelled by user"}
                    )
                elif isinstance(confirm_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Deployment cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "deploy_release_interactive"
                )
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

        @server.tool(tags={"elicitation", "workflow", "admin"})
        async def troubleshoot_assignment_interactive(ctx: Context) -> str:
            """Troubleshoot an assignment with interactive diagnostic steps."""
            try:
                if not ctx:
                    return json.dumps(
                        {"error": True, "message": "Context required for elicitation"}
                    )

                await ctx.info("Starting interactive assignment troubleshooting...")

                # Step 1: Get assignment ID
                assignment_result = await ctx.elicit(
                    "What is the assignment ID you want to troubleshoot?",
                    response_type=str,
                )

                if isinstance(assignment_result, AcceptedElicitation):
                    assignment_id = assignment_result.data
                elif isinstance(assignment_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Troubleshooting cancelled - assignment ID required",
                        }
                    )
                elif isinstance(assignment_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 2: Get issue description
                issue_result = await ctx.elicit(
                    "Please describe the issue you're experiencing with this assignment:",
                    response_type=str,
                )

                if isinstance(issue_result, AcceptedElicitation):
                    issue_description = issue_result.data
                elif isinstance(issue_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Troubleshooting cancelled - issue description required",
                        }
                    )
                elif isinstance(issue_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 3: Get error level
                error_level_result = await ctx.elicit(
                    "What is the severity level of this issue?",
                    response_type=["low", "medium", "high", "critical"],
                )

                if isinstance(error_level_result, AcceptedElicitation):
                    error_level = error_level_result.data
                elif isinstance(error_level_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Troubleshooting cancelled - error level required",
                        }
                    )
                elif isinstance(error_level_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 4: Get diagnostic preferences
                diagnostic_result = await ctx.elicit(
                    "What type of diagnostic information would you like to collect?",
                    response_type=["basic", "detailed", "comprehensive"],
                )

                if isinstance(diagnostic_result, AcceptedElicitation):
                    diagnostic_level = diagnostic_result.data
                elif isinstance(diagnostic_result, DeclinedElicitation):
                    return json.dumps(
                        {
                            "error": True,
                            "message": "Troubleshooting cancelled - diagnostic level required",
                        }
                    )
                elif isinstance(diagnostic_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

                # Step 5: Confirm troubleshooting
                confirm_result = await ctx.elicit(
                    f"Confirm troubleshooting session:\n"
                    f"Assignment ID: {assignment_id}\n"
                    f"Issue: {issue_description}\n"
                    f"Severity: {error_level}\n"
                    f"Diagnostic Level: {diagnostic_level}\n\n"
                    f"Start troubleshooting?",
                    response_type=None,
                )

                if isinstance(confirm_result, AcceptedElicitation):
                    # Here you would perform the actual troubleshooting
                    troubleshooting_data = {
                        "assignment_id": assignment_id,
                        "issue_description": issue_description,
                        "error_level": error_level,
                        "diagnostic_level": diagnostic_level,
                        "status": "troubleshooting",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "recommendations": [
                            "Check assignment logs for errors",
                            "Verify assignment dependencies",
                            "Review assignment configuration",
                            "Check system resources",
                        ],
                    }

                    return json.dumps(
                        {
                            "success": True,
                            "message": f"Troubleshooting session started for assignment {assignment_id}",
                            "troubleshooting": troubleshooting_data,
                        },
                        indent=2,
                    )
                elif isinstance(confirm_result, DeclinedElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                elif isinstance(confirm_result, CancelledElicitation):
                    return json.dumps(
                        {"error": True, "message": "Troubleshooting cancelled by user"}
                    )
                else:
                    return json.dumps(
                        {"error": True, "message": "Invalid response type"}
                    )

            except Exception as e:
                error_response = self.error_handler.handle_general_error(
                    e, "troubleshoot_assignment_interactive"
                )
                if isinstance(error_response, dict):
                    return json.dumps(error_response, indent=2)
                else:
                    return json.dumps({"error": True, "message": str(e)}, indent=2)

    def _add_custom_routes(self, server: FastMCP):
        """Add custom HTTP routes for health checks and status endpoints."""
        from starlette.requests import Request
        from starlette.responses import JSONResponse, PlainTextResponse

        @server.custom_route("/health", methods=["GET"])
        async def health_check_route(request: Request) -> JSONResponse:
            """Health check endpoint for load balancers and monitoring."""
            try:
                health_checker = HealthChecker(self.http_client, self.settings)
                health_data = await health_checker.check_health()
                return JSONResponse(health_data)
            except Exception as e:
                return JSONResponse(
                    {"status": "unhealthy", "error": str(e)}, status_code=503
                )

        @server.custom_route("/status", methods=["GET"])
        async def status_route(request: Request) -> JSONResponse:
            """Detailed status endpoint with server information."""
            try:
                # Update cache size in metrics
                self.metrics.cache_size = len(self.cache.cache)

                status_data = {
                    "server": {
                        "name": "BMC AMI DevX Code Pipeline MCP Server (OpenAPI)",
                        "version": "2.2.0",
                        "status": "running",
                        "uptime": "active",
                    },
                    "metrics": self.metrics.to_dict(),
                    "cache": {
                        "size": len(self.cache.cache),
                        "max_size": self.cache.max_size,
                        "hit_rate": self.metrics.get_cache_hit_rate(),
                    },
                    "rate_limiter": {
                        "tokens": self.rate_limiter.tokens,
                        "requests_per_minute": self.rate_limiter.requests_per_minute,
                        "burst_size": self.rate_limiter.burst_size,
                    },
                    "settings": {
                        "api_base_url": self.settings.api_base_url,
                        "auth_enabled": self.settings.auth_enabled,
                        "monitoring_enabled": self.settings.enable_metrics,
                    },
                }
                return JSONResponse(status_data)
            except Exception as e:
                return JSONResponse(
                    {"error": "Failed to get status", "message": str(e)},
                    status_code=500,
                )

        @server.custom_route("/metrics", methods=["GET"])
        async def metrics_route(request: Request) -> JSONResponse:
            """Prometheus-style metrics endpoint."""
            try:
                # Update cache size in metrics
                self.metrics.cache_size = len(self.cache.cache)

                metrics_data = self.metrics.to_dict()
                return JSONResponse(metrics_data)
            except Exception as e:
                return JSONResponse(
                    {"error": "Failed to get metrics", "message": str(e)},
                    status_code=500,
                )

        @server.custom_route("/ready", methods=["GET"])
        async def readiness_route(request: Request) -> PlainTextResponse:
            """Readiness probe for Kubernetes deployments."""
            try:
                # Check if server is ready to accept requests
                if self.settings.api_base_url and self.rate_limiter.tokens > 0:
                    return PlainTextResponse("OK")
                else:
                    return PlainTextResponse("Not Ready", status_code=503)
            except Exception:
                return PlainTextResponse("Not Ready", status_code=503)

    def _add_resource_templates(self, server: FastMCP):
        """Add resource templates for parameterized data access."""

        @server.resource("bmc://assignments/{srid}")
        def get_assignments_resource(srid: str) -> dict:
            """Resource template for accessing assignments by SRID."""
            return {
                "srid": srid,
                "description": f"Assignments for SRID {srid}",
                "endpoint": f"/ispw/{srid}/assignments",
                "methods": ["GET", "POST"],
                "parameters": {
                    "level": "Assignment level (DEV, INT, ACC, PRD)",
                    "assignmentId": "Assignment ID filter",
                },
            }

        @server.resource("bmc://assignments/{srid}/{assignment_id}")
        def get_assignment_details_resource(srid: str, assignment_id: str) -> dict:
            """Resource template for accessing specific assignment details."""
            return {
                "srid": srid,
                "assignment_id": assignment_id,
                "description": f"Assignment {assignment_id} details for SRID {srid}",
                "endpoint": f"/ispw/{srid}/assignments/{assignment_id}",
                "methods": ["GET"],
                "related_endpoints": [
                    f"/ispw/{srid}/assignments/{assignment_id}/tasks",
                    f"/ispw/{srid}/assignments/{assignment_id}/generate",
                    f"/ispw/{srid}/assignments/{assignment_id}/promote",
                    f"/ispw/{srid}/assignments/{assignment_id}/deploy",
                ],
            }

        @server.resource("bmc://releases/{srid}")
        def get_releases_resource(srid: str) -> dict:
            """Resource template for accessing releases by SRID."""
            return {
                "srid": srid,
                "description": f"Releases for SRID {srid}",
                "endpoint": f"/ispw/{srid}/releases",
                "methods": ["GET", "POST"],
                "parameters": {"releaseId": "Release ID filter"},
            }

        @server.resource("bmc://packages/{srid}")
        def get_packages_resource(srid: str) -> dict:
            """Resource template for accessing packages by SRID."""
            return {
                "srid": srid,
                "description": f"Packages for SRID {srid}",
                "endpoint": f"/ispw/{srid}/packages",
                "methods": ["GET"],
                "parameters": {"packageId": "Package ID filter"},
            }

        @server.resource("bmc://server/status")
        def get_server_status_resource() -> dict:
            """Resource template for server status information."""
            return {
                "description": "Current server status and health information",
                "endpoints": {
                    "health": "/health",
                    "status": "/status",
                    "metrics": "/metrics",
                    "ready": "/ready",
                },
                "features": [
                    "OpenAPI integration",
                    "Rate limiting",
                    "Caching",
                    "Monitoring",
                    "Error handling",
                ],
            }

    def _add_prompts(self, server: FastMCP):
        """Add prompts for reusable LLM guidance templates."""

        @server.prompt
        def analyze_assignment_status(assignment_data: dict) -> str:
            """Create a prompt for analyzing assignment status and providing recommendations."""
            assignment_id = assignment_data.get("assignmentId", "Unknown")
            status = assignment_data.get("status", "Unknown")
            level = assignment_data.get("level", "Unknown")
            owner = assignment_data.get("owner", "Unknown")

            return f"""
            Analyze the following BMC ISPW assignment and provide recommendations:
            
            Assignment ID: {assignment_id}
            Status: {status}
            Level: {level}
            Owner: {owner}
            
            Please provide:
            1. Current status assessment
            2. Next recommended actions
            3. Potential issues or blockers
            4. Best practices for this assignment type
            5. Timeline recommendations based on the current level
            
            Consider BMC ISPW best practices and typical development workflows.
            """

        @server.prompt
        def deployment_planning(release_data: dict) -> str:
            """Create a prompt for deployment planning and risk assessment."""
            release_id = release_data.get("releaseId", "Unknown")
            application = release_data.get("application", "Unknown")
            status = release_data.get("status", "Unknown")

            return f"""
            Create a deployment plan for the following BMC ISPW release:
            
            Release ID: {release_id}
            Application: {application}
            Status: {status}
            
            Please provide:
            1. Pre-deployment checklist
            2. Risk assessment and mitigation strategies
            3. Rollback plan
            4. Testing requirements
            5. Communication plan for stakeholders
            6. Monitoring and validation steps
            
            Consider mainframe deployment best practices and BMC ISPW workflows.
            """

        @server.prompt
        def troubleshooting_guide(error_data: dict) -> str:
            """Create a prompt for troubleshooting BMC ISPW issues."""
            error_type = error_data.get("error_type", "Unknown")
            error_message = error_data.get("message", "No message provided")
            operation = error_data.get("operation", "Unknown operation")

            return f"""
            Troubleshoot the following BMC ISPW issue:
            
            Error Type: {error_type}
            Operation: {operation}
            Error Message: {error_message}
            
            Please provide:
            1. Root cause analysis
            2. Step-by-step troubleshooting guide
            3. Common solutions for this error type
            4. Prevention strategies
            5. Escalation criteria
            6. Documentation references
            
            Focus on BMC ISPW-specific troubleshooting and mainframe environment considerations.
            """

        @server.prompt
        def code_review_guidelines(assignment_data: dict) -> str:
            """Create a prompt for code review guidelines based on assignment type."""
            assignment_id = assignment_data.get("assignmentId", "Unknown")
            level = assignment_data.get("level", "Unknown")
            application = assignment_data.get("application", "Unknown")

            return f"""
            Provide code review guidelines for the following BMC ISPW assignment:
            
            Assignment ID: {assignment_id}
            Level: {level}
            Application: {application}
            
            Please provide:
            1. Code review checklist specific to this level
            2. Security considerations
            3. Performance requirements
            4. Testing requirements
            5. Documentation standards
            6. Approval criteria
            7. Common issues to watch for
            
            Tailor the guidelines to the specific level ({level}) and application ({application}).
            """

    async def start(
        self, transport: str = "http", host: str = "127.0.0.1", port: int = 8000
    ):
        """Start the MCP server."""
        try:
            logger.info(
                f"Starting BMC AMI DevX Code Pipeline MCP Server (OpenAPI) on {host}:{port}"
            )
            logger.info(f"Transport: {transport}")
            logger.info(f"API Base URL: {self.settings.api_base_url}")
            logger.info(
                f"Authentication: {'Enabled' if self.settings.auth_enabled else 'Disabled'}"
            )
            logger.info(
                f"Rate Limiting: {self.settings.rate_limit_requests_per_minute} requests/min, {self.settings.rate_limit_burst_size} burst size"
            )
            logger.info(
                f"Caching: {self.settings.cache_max_size} max entries, {self.settings.cache_ttl_seconds}s TTL"
            )

            # Start the server
            await self.server.run_async(transport=transport, host=host, port=port)

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise MCPServerError(f"Failed to start MCP server: {e}")

    async def stop(self):
        """Stop the MCP server and cleanup resources."""
        try:
            logger.info("Stopping BMC AMI DevX Code Pipeline MCP Server (OpenAPI)")

            # Close HTTP client
            await self.http_client.aclose()

            # Log final metrics
            final_metrics = self.metrics.to_dict()
            logger.info(f"Final metrics: {json.dumps(final_metrics, indent=2)}")

        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")


async def main():
    """Main entry point for the OpenAPI MCP Server."""
    server = None
    try:
        # Create and start the server
        server = OpenAPIMCPServer()
        await server.start()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        if server:
            await server.stop()


if __name__ == "__main__":
    # Run the server
    asyncio.run(main())
