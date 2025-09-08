#!/usr/bin/env python3
"""
BMC AMI DevX Code Pipeline MCP Server
Real FastMCP 2.x server for BMC AMI DevX Code Pipeline integration.
"""

import json
import os
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, ConfigDict, validator
import re


class Settings(BaseModel):
    """Application settings with environment variable support."""
    
    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    log_level: str = Field(default="INFO")
    
    # BMC AMI DevX API configuration
    api_base_url: str = Field(default="https://devx.bmc.com/code-pipeline/api/v1")
    api_timeout: int = Field(default=30)
    api_retry_attempts: int = Field(default=3)
    
    # Authentication configuration (FastMCP native)
    auth_provider: Optional[str] = Field(default=None)  # e.g., "fastmcp.server.auth.providers.jwt.JWTVerifier"
    auth_jwks_uri: Optional[str] = Field(default=None)
    auth_issuer: Optional[str] = Field(default=None)
    auth_audience: Optional[str] = Field(default=None)
    auth_secret: Optional[str] = Field(default=None)
    auth_enabled: bool = Field(default=False)
    
    # OpenAPI specification path
    openapi_spec_path: str = Field(default="config/openapi.json")
    
    model_config = ConfigDict(env_file=".env")


# Global settings instance
settings = Settings()


# Input validation functions
def validate_srid(srid: str) -> str:
    """Validate SRID format."""
    if not srid or not isinstance(srid, str):
        raise ValueError("SRID is required and must be a string")
    
    # SRID should be alphanumeric, typically 1-8 characters
    if not re.match(r'^[A-Z0-9]{1,8}$', srid.upper()):
        raise ValueError("SRID must be 1-8 alphanumeric characters")
    
    return srid.upper()


def validate_assignment_id(assignment_id: str) -> str:
    """Validate assignment ID format."""
    if not assignment_id or not isinstance(assignment_id, str):
        raise ValueError("Assignment ID is required and must be a string")
    
    # Assignment ID should be alphanumeric with possible hyphens/underscores
    if not re.match(r'^[A-Z0-9_-]{1,20}$', assignment_id.upper()):
        raise ValueError("Assignment ID must be 1-20 alphanumeric characters with optional hyphens/underscores")
    
    return assignment_id.upper()


def validate_release_id(release_id: str) -> str:
    """Validate release ID format."""
    if not release_id or not isinstance(release_id, str):
        raise ValueError("Release ID is required and must be a string")
    
    # Release ID should be alphanumeric with possible hyphens/underscores
    if not re.match(r'^[A-Z0-9_-]{1,20}$', release_id.upper()):
        raise ValueError("Release ID must be 1-20 alphanumeric characters with optional hyphens/underscores")
    
    return release_id.upper()


def validate_level(level: str) -> str:
    """Validate level parameter."""
    if not level:
        return level
    
    valid_levels = ["DEV", "TEST", "STAGE", "PROD", "UAT", "QA"]
    if level.upper() not in valid_levels:
        raise ValueError(f"Level must be one of: {', '.join(valid_levels)}")
    
    return level.upper()


def validate_environment(env: str) -> str:
    """Validate environment parameter."""
    if not env:
        return env
    
    valid_envs = ["DEV", "TEST", "STAGE", "PROD", "UAT", "QA"]
    if env.upper() not in valid_envs:
        raise ValueError(f"Environment must be one of: {', '.join(valid_envs)}")
    
    return env.upper()


# Retry logic decorator
def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry API calls on failure."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        raise last_exception
                except Exception as e:
                    # Don't retry on validation errors or other non-retryable errors
                    raise e
            
            raise last_exception
        return wrapper
    return decorator


def create_auth_provider():
    """Create FastMCP authentication provider based on settings."""
    if not settings.auth_enabled or not settings.auth_provider:
        return None
    
    try:
        # Import the authentication provider dynamically
        module_path, class_name = settings.auth_provider.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        provider_class = getattr(module, class_name)
        
        # Configure provider based on type
        if "JWTVerifier" in settings.auth_provider:
            return provider_class(
                jwks_uri=settings.auth_jwks_uri,
                issuer=settings.auth_issuer,
                audience=settings.auth_audience
            )
        elif "GitHubProvider" in settings.auth_provider:
            return provider_class(
                client_id=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
                client_secret=os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET"),
                base_url=f"http://{settings.host}:{settings.port}"
            )
        elif "GoogleProvider" in settings.auth_provider:
            return provider_class(
                client_id=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
                base_url=f"http://{settings.host}:{settings.port}"
            )
        else:
            # Generic provider - pass common settings
            return provider_class()
            
    except Exception as e:
        print(f"Warning: Failed to create auth provider: {e}")
        return None

# HTTP client for BMC AMI DevX API
http_client = httpx.AsyncClient(
    base_url=settings.api_base_url,
    timeout=settings.api_timeout,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
)


class BMCAMIDevXClient:
    """Client for BMC AMI DevX Code Pipeline API operations with retry logic."""
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.max_retries = settings.api_retry_attempts
        self.retry_delay = 1.0  # seconds
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_assignments(self, srid: str, level: Optional[str] = None, assignment_id: Optional[str] = None) -> Dict[str, Any]:
        """Get assignments for a specific SRID."""
        params = {}
        if level:
            params["level"] = level
        if assignment_id:
            params["assignmentId"] = assignment_id
            
        response = await self.client.get(f"/ispw/{srid}/assignments", params=params)
        response.raise_for_status()
        return response.json()
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def create_assignment(self, srid: str, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new assignment."""
        response = await self.client.post(f"/ispw/{srid}/assignments", json=assignment_data)
        response.raise_for_status()
        return response.json()
    
    async def get_assignment_details(self, srid: str, assignment_id: str) -> Dict[str, Any]:
        """Get details for a specific assignment."""
        response = await self.client.get(f"/ispw/{srid}/assignments/{assignment_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_assignment_tasks(self, srid: str, assignment_id: str) -> Dict[str, Any]:
        """Get tasks for a specific assignment."""
        response = await self.client.get(f"/ispw/{srid}/assignments/{assignment_id}/tasks")
        response.raise_for_status()
        return response.json()
    
    async def generate_assignment(self, srid: str, assignment_id: str, generate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code for an assignment."""
        response = await self.client.post(f"/ispw/{srid}/assignments/{assignment_id}/generate", json=generate_data)
        response.raise_for_status()
        return response.json()
    
    async def promote_assignment(self, srid: str, assignment_id: str, promote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Promote assignment to next level."""
        response = await self.client.post(f"/ispw/{srid}/assignments/{assignment_id}/promote", json=promote_data)
        response.raise_for_status()
        return response.json()
    
    async def deploy_assignment(self, srid: str, assignment_id: str, deploy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy assignment to target environment."""
        response = await self.client.post(f"/ispw/{srid}/assignments/{assignment_id}/deploy", json=deploy_data)
        response.raise_for_status()
        return response.json()
    
    async def get_releases(self, srid: str, release_id: Optional[str] = None) -> Dict[str, Any]:
        """Get releases for a specific SRID."""
        params = {}
        if release_id:
            params["releaseId"] = release_id
            
        response = await self.client.get(f"/ispw/{srid}/releases", params=params)
        response.raise_for_status()
        return response.json()
    
    async def create_release(self, srid: str, release_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new release."""
        response = await self.client.post(f"/ispw/{srid}/releases", json=release_data)
        response.raise_for_status()
        return response.json()
    
    async def get_release_details(self, srid: str, release_id: str) -> Dict[str, Any]:
        """Get details for a specific release."""
        response = await self.client.get(f"/ispw/{srid}/releases/{release_id}")
        response.raise_for_status()
        return response.json()
    
    async def deploy_release(self, srid: str, release_id: str, deploy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a release."""
        response = await self.client.post(f"/ispw/{srid}/releases/{release_id}/deploy", json=deploy_data)
        response.raise_for_status()
        return response.json()
    
    async def get_sets(self, srid: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        """Get sets for a specific SRID."""
        params = {}
        if set_id:
            params["setId"] = set_id
            
        response = await self.client.get(f"/ispw/{srid}/sets", params=params)
        response.raise_for_status()
        return response.json()
    
    async def deploy_set(self, srid: str, set_id: str, deploy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a set."""
        response = await self.client.post(f"/ispw/{srid}/sets/{set_id}/deploy", json=deploy_data)
        response.raise_for_status()
        return response.json()
    
    async def get_packages(self, srid: str, package_id: Optional[str] = None) -> Dict[str, Any]:
        """Get packages for a specific SRID."""
        params = {}
        if package_id:
            params["packageId"] = package_id
            
        response = await self.client.get(f"/ispw/{srid}/packages", params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_package_details(self, srid: str, package_id: str) -> Dict[str, Any]:
        """Get details for a specific package."""
        response = await self.client.get(f"/ispw/{srid}/packages/{package_id}")
        response.raise_for_status()
        return response.json()


# Initialize BMC AMI DevX client
bmc_client = BMCAMIDevXClient(http_client)

# Create FastMCP server with authentication
auth_provider = create_auth_provider()
server = FastMCP(
    name="BMC AMI DevX Code Pipeline MCP Server",
    version="2.2.0",
    instructions="MCP server for BMC AMI DevX Code Pipeline integration with comprehensive ISPW operations",
    auth=auth_provider
)


# Assignment Management Tools
@server.tool
async def get_assignments(
    srid: str,
    level: Optional[str] = None,
    assignment_id: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Get assignments for a specific SRID (System Resource Identifier).
    
    Args:
        srid: System/Resource ID (1-8 alphanumeric characters)
        level: Environment level (DEV, TEST, STAGE, PROD, UAT, QA)
        assignment_id: Specific assignment ID to retrieve
        ctx: FastMCP context for logging and progress
    
    Returns:
        JSON string containing assignments data
    """
    try:
        # Input validation
        srid = validate_srid(srid)
        if level:
            level = validate_level(level)
        if assignment_id:
            assignment_id = validate_assignment_id(assignment_id)
        
        if ctx:
            await ctx.info(f"Retrieving assignments for SRID: {srid}")
            if level:
                await ctx.info(f"Filtering by level: {level}")
            if assignment_id:
                await ctx.info(f"Filtering by assignment ID: {assignment_id}")
        
        result = await bmc_client.get_assignments(srid, level, assignment_id)
        
        if ctx:
            await ctx.info(f"Successfully retrieved {len(result.get('assignments', []))} assignments")
        
        return json.dumps(result, indent=2)
    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving assignments: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving assignments: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def create_assignment(
    srid: str,
    assignment_id: str,
    stream: str,
    application: str,
    description: Optional[str] = None,
    default_path: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Create a new assignment in BMC AMI DevX."""
    try:
        if ctx:
            await ctx.info(f"Creating assignment {assignment_id} for SRID: {srid}")
        
        assignment_data = {
            "assignmentId": assignment_id,
            "stream": stream,
            "application": application,
        }
        
        if description:
            assignment_data["description"] = description
        if default_path:
            assignment_data["defaultPath"] = default_path
        
        result = await bmc_client.create_assignment(srid, assignment_data)
        
        if ctx:
            await ctx.info(f"Successfully created assignment: {assignment_id}")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error creating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error creating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def get_assignment_details(
    srid: str,
    assignment_id: str,
    ctx: Context = None
) -> str:
    """Get detailed information for a specific assignment."""
    try:
        if ctx:
            await ctx.info(f"Retrieving details for assignment {assignment_id}")
        
        result = await bmc_client.get_assignment_details(srid, assignment_id)
        
        if ctx:
            await ctx.info(f"Successfully retrieved assignment details")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving assignment details: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving assignment details: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def get_assignment_tasks(
    srid: str,
    assignment_id: str,
    ctx: Context = None
) -> str:
    """Get tasks for a specific assignment."""
    try:
        if ctx:
            await ctx.info(f"Retrieving tasks for assignment {assignment_id}")
        
        result = await bmc_client.get_assignment_tasks(srid, assignment_id)
        
        if ctx:
            await ctx.info(f"Successfully retrieved {len(result.get('tasks', []))} tasks")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving assignment tasks: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving assignment tasks: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# Release Management Tools
@server.tool
async def get_releases(
    srid: str,
    release_id: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Get releases for a specific SRID."""
    try:
        if ctx:
            await ctx.info(f"Retrieving releases for SRID: {srid}")
        
        result = await bmc_client.get_releases(srid, release_id)
        
        if ctx:
            await ctx.info(f"Successfully retrieved {len(result.get('releases', []))} releases")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error retrieving releases: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error retrieving releases: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def create_release(
    srid: str,
    release_id: str,
    stream: str,
    application: str,
    description: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Create a new release in BMC AMI DevX."""
    try:
        if ctx:
            await ctx.info(f"Creating release {release_id} for SRID: {srid}")
        
        release_data = {
            "releaseId": release_id,
            "stream": stream,
            "application": application,
        }
        
        if description:
            release_data["description"] = description
        
        result = await bmc_client.create_release(srid, release_data)
        
        if ctx:
            await ctx.info(f"Successfully created release: {release_id}")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error creating release: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error creating release: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# Operation Tools
@server.tool
async def generate_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    runtime_configuration: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Generate code for an assignment."""
    try:
        if ctx:
            await ctx.info(f"Generating code for assignment {assignment_id}")
            await ctx.report_progress(0, 100, "Starting generation")
        
        generate_data = {}
        if level:
            generate_data["level"] = level
        if runtime_configuration:
            generate_data["runtimeConfiguration"] = runtime_configuration
        
        result = await bmc_client.generate_assignment(srid, assignment_id, generate_data)
        
        if ctx:
            await ctx.report_progress(100, 100, "Generation completed")
            await ctx.info(f"Successfully initiated generation for assignment: {assignment_id}")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error generating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error generating assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def promote_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    change_type: Optional[str] = None,
    execution_status: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Promote assignment to next level."""
    try:
        if ctx:
            await ctx.info(f"Promoting assignment {assignment_id} to level: {level or 'next'}")
            await ctx.report_progress(0, 100, "Starting promotion")
        
        promote_data = {}
        if level:
            promote_data["level"] = level
        if change_type:
            promote_data["changeType"] = change_type
        if execution_status:
            promote_data["executionStatus"] = execution_status
        
        result = await bmc_client.promote_assignment(srid, assignment_id, promote_data)
        
        if ctx:
            await ctx.report_progress(100, 100, "Promotion completed")
            await ctx.info(f"Successfully initiated promotion for assignment: {assignment_id}")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error promoting assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error promoting assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


@server.tool
async def deploy_assignment(
    srid: str,
    assignment_id: str,
    level: Optional[str] = None,
    deploy_implementation_time: Optional[str] = None,
    deploy_active: Optional[bool] = None,
    ctx: Context = None
) -> str:
    """Deploy assignment to target environment."""
    try:
        if ctx:
            await ctx.info(f"Deploying assignment {assignment_id} to level: {level or 'default'}")
            await ctx.report_progress(0, 100, "Starting deployment")
        
        deploy_data = {}
        if level:
            deploy_data["level"] = level
        if deploy_implementation_time:
            deploy_data["deployImplementationTime"] = deploy_implementation_time
        if deploy_active is not None:
            deploy_data["deployActive"] = deploy_active
        
        result = await bmc_client.deploy_assignment(srid, assignment_id, deploy_data)
        
        if ctx:
            await ctx.report_progress(100, 100, "Deployment completed")
            await ctx.info(f"Successfully initiated deployment for assignment: {assignment_id}")
        
        return json.dumps(result, indent=2)
    except httpx.HTTPError as e:
        error_msg = f"HTTP error deploying assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)
    except Exception as e:
        error_msg = f"Error deploying assignment: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)


# Health check endpoint
@server.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    
    return JSONResponse({
        "status": "healthy",
        "name": server.name,
        "version": server.version,
        "tools_count": len(await server.get_tools()),
        "api_base_url": settings.api_base_url,
    })


async def main():
    """Main entry point."""
    print("Starting BMC AMI DevX Code Pipeline MCP Server...")
    print(f"Server: {server.name} v{server.version}")
    print(f"Host: {settings.host}:{settings.port}")
    print(f"API Base URL: {settings.api_base_url}")
    print(f"Health check: http://{settings.host}:{settings.port}/health")
    
    # Run the server
    await server.run_http_async(
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        transport="streamable-http"
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
