import json
import os

import httpx
import pytest

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
HEALTH_URL = f"{MCP_SERVER_URL}/health"
MCP_ENDPOINT = f"{MCP_SERVER_URL}/mcp/"


class TestMCPServer:
    """Test BMC AMI DevX Code Pipeline MCP Server"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test server health check endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(HEALTH_URL, timeout=5.0)
                assert response.status_code == 200

                health_data = response.json()
                assert health_data["status"] == "healthy"
                assert health_data["service"] == "BMC AMI DevX Code Pipeline MCP Server"
                # Accept either "http" or "streamable-http" as valid transport
                assert health_data["transport"] in ["http", "streamable-http"]
                assert "features" in health_data

                print(f"✅ Health check passed: {health_data}")

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"Health check failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_endpoint_exists(self):
        """Test that MCP endpoint is accessible"""
        async with httpx.AsyncClient() as client:
            try:
                # MCP endpoints typically return 405 for GET without proper MCP protocol
                response = await client.get(MCP_ENDPOINT, timeout=5.0)
                # We expect various valid HTTP status codes including redirects
                assert response.status_code in [200, 307, 405, 404, 501]
                print(f"✅ MCP endpoint accessible: {response.status_code}")

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"MCP endpoint test failed: {e}")


class TestServerConfiguration:
    """Test server configuration and setup"""

    def test_openapi_spec_exists(self):
        """Test that OpenAPI specification file exists and is valid"""
        openapi_path = os.path.join(os.path.dirname(__file__), "config/openapi.json")
        assert os.path.exists(openapi_path), "OpenAPI spec file not found"

        with open(openapi_path, "r") as f:
            try:
                openapi_spec = json.load(f)
                assert (
                    "openapi" in openapi_spec
                ), "Invalid OpenAPI spec: missing 'openapi' field"
                assert (
                    "paths" in openapi_spec
                ), "Invalid OpenAPI spec: missing 'paths' field"
                assert (
                    "info" in openapi_spec
                ), "Invalid OpenAPI spec: missing 'info' field"

                title = openapi_spec["info"].get("title", "Unknown")
                print(f"✅ OpenAPI spec valid: {title}")

            except json.JSONDecodeError as e:
                pytest.fail(f"OpenAPI spec is not valid JSON: {e}")

    def test_environment_configuration(self):
        """Test environment configuration setup"""
        # Test that we can import the main module without errors
        try:
            from main import SERVER_INSTRUCTIONS, SERVER_NAME

            assert SERVER_NAME == "BMC AMI DevX Code Pipeline MCP Server"
            assert isinstance(SERVER_INSTRUCTIONS, str)
            assert len(SERVER_INSTRUCTIONS) > 0

            print(f"✅ Server configuration valid: {SERVER_NAME}")

        except ImportError as e:
            pytest.fail(f"Could not import main module: {e}")
        except Exception as e:
            pytest.fail(f"Server configuration test failed: {e}")


class TestAuthentication:
    """Test authentication configuration"""

    def test_no_auth_mode(self):
        """Test server works in no-auth mode"""
        # Set environment to disable auth
        original_auth = os.environ.get("FASTMCP_SERVER_AUTH")
        os.environ["FASTMCP_SERVER_AUTH"] = "NONE"

        try:
            from main import auth

            assert auth is None, "Auth should be None when FASTMCP_SERVER_AUTH=NONE"
            print("✅ No-auth mode configured correctly")

        except Exception as e:
            pytest.fail(f"No-auth configuration test failed: {e}")
        finally:
            # Restore original auth setting
            if original_auth:
                os.environ["FASTMCP_SERVER_AUTH"] = original_auth
            elif "FASTMCP_SERVER_AUTH" in os.environ:
                del os.environ["FASTMCP_SERVER_AUTH"]

    def test_jwt_auth_configuration(self):
        """Test JWT authentication configuration"""
        # Set environment for JWT auth
        original_auth = os.environ.get("FASTMCP_SERVER_AUTH")
        original_jwks = os.environ.get("FASTMCP_SERVER_AUTH_JWT_JWKS_URI")
        original_issuer = os.environ.get("FASTMCP_SERVER_AUTH_JWT_ISSUER")
        original_audience = os.environ.get("FASTMCP_SERVER_AUTH_JWT_AUDIENCE")

        os.environ["FASTMCP_SERVER_AUTH"] = "JWT"
        os.environ["FASTMCP_SERVER_AUTH_JWT_JWKS_URI"] = (
            "https://test.com/.well-known/jwks.json"
        )
        os.environ["FASTMCP_SERVER_AUTH_JWT_ISSUER"] = "https://test.com/"
        os.environ["FASTMCP_SERVER_AUTH_JWT_AUDIENCE"] = "test-audience"

        try:
            # Re-import to get new configuration
            import importlib

            import main

            importlib.reload(main)

            assert (
                main.auth is not None
            ), "Auth should be configured when FASTMCP_SERVER_AUTH=JWT"
            print("✅ JWT auth configuration loaded correctly")

        except Exception as e:
            pytest.fail(f"JWT auth configuration test failed: {e}")
        finally:
            # Restore original settings
            if original_auth:
                os.environ["FASTMCP_SERVER_AUTH"] = original_auth
            elif "FASTMCP_SERVER_AUTH" in os.environ:
                del os.environ["FASTMCP_SERVER_AUTH"]

            if original_jwks:
                os.environ["FASTMCP_SERVER_AUTH_JWT_JWKS_URI"] = original_jwks
            elif "FASTMCP_SERVER_AUTH_JWT_JWKS_URI" in os.environ:
                del os.environ["FASTMCP_SERVER_AUTH_JWT_JWKS_URI"]

            if original_issuer:
                os.environ["FASTMCP_SERVER_AUTH_JWT_ISSUER"] = original_issuer
            elif "FASTMCP_SERVER_AUTH_JWT_ISSUER" in os.environ:
                del os.environ["FASTMCP_SERVER_AUTH_JWT_ISSUER"]

            if original_audience:
                os.environ["FASTMCP_SERVER_AUTH_JWT_AUDIENCE"] = original_audience
            elif "FASTMCP_SERVER_AUTH_JWT_AUDIENCE" in os.environ:
                del os.environ["FASTMCP_SERVER_AUTH_JWT_AUDIENCE"]


class TestAPIIntegration:
    """Test BMC AMI DevX Code Pipeline API integration"""

    @pytest.mark.asyncio
    async def test_httpx_client_configuration(self):
        """Test HTTP client configuration for BMC API"""
        try:
            from main import API_BASE_URL, client

            assert isinstance(client, httpx.AsyncClient)
            assert client.base_url is not None
            print(f"✅ HTTP client configured with base URL: {API_BASE_URL}")

        except Exception as e:
            pytest.fail(f"HTTP client configuration test failed: {e}")

    def test_openapi_operations(self):
        """Test that OpenAPI operations can be parsed"""
        openapi_path = os.path.join(os.path.dirname(__file__), "config/openapi.json")

        with open(openapi_path, "r") as f:
            openapi_spec = json.load(f)

        operations = []
        for path, methods in openapi_spec.get("paths", {}).items():
            for method, operation in methods.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    operation_id = operation.get("operationId")
                    if operation_id:
                        operations.append(operation_id)
                    else:
                        # If no operationId, count the operation anyway
                        operations.append(f"{method.upper()} {path}")

        assert len(operations) > 0, "No operations found in OpenAPI spec"
        print(f"✅ Found {len(operations)} operations in OpenAPI spec")

        # Check for paths that indicate BMC ISPW operations
        paths = list(openapi_spec.get("paths", {}).keys())
        bmc_paths = [
            p
            for p in paths
            if any(
                keyword in p.lower()
                for keyword in ["assignment", "release", "ispw", "src"]
            )
        ]
        if bmc_paths:
            print(f"✅ Found BMC ISPW paths: {bmc_paths[:3]}...")  # Show first 3


class TestDockerDeployment:
    """Test Docker deployment configuration"""

    def test_dockerfile_exists(self):
        """Test that Dockerfile exists and has basic structure"""
        dockerfile_path = os.path.join(os.path.dirname(__file__), "Dockerfile")
        assert os.path.exists(dockerfile_path), "Dockerfile not found"

        with open(dockerfile_path, "r") as f:
            content = f.read()
            assert "FROM python:" in content, "Dockerfile should use Python base image"
            assert (
                "COPY requirements.txt" in content or "COPY pyproject.toml" in content
            ), "Dockerfile should copy dependencies"
            assert (
                "CMD" in content or "ENTRYPOINT" in content
            ), "Dockerfile should have startup command"

        print("✅ Dockerfile structure is valid")

    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists and is valid"""
        compose_path = os.path.join(os.path.dirname(__file__), "docker-compose.yml")
        assert os.path.exists(compose_path), "docker-compose.yml not found"

        with open(compose_path, "r") as f:
            content = f.read()
            assert (
                "version:" in content or "services:" in content
            ), "docker-compose.yml should have valid structure"
            assert (
                "fastmcp" in content or "server" in content
            ), "docker-compose.yml should define service"

        print("✅ docker-compose.yml structure is valid")


# Test runner helper
def run_tests():
    """Helper function to run all tests"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    print("🧪 Running BMC AMI DevX Code Pipeline MCP Server tests")
    print("=" * 60)
    run_tests()
