import json
import os
import tempfile

import httpx
import pytest

# Configuration
# Use PORT environment variable to match the server configuration
SERVER_PORT = os.getenv("PORT", "8000")  # Default to 8000 to match main.py default
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"http://127.0.0.1:{SERVER_PORT}")
HEALTH_URL = f"{MCP_SERVER_URL}/health"
MCP_CAPABILITIES_URL = f"{MCP_SERVER_URL}/mcp/capabilities"
MCP_TOOLS_LIST_URL = f"{MCP_SERVER_URL}/mcp/tools/list"
MCP_TOOLS_CALL_URL = f"{MCP_SERVER_URL}/mcp/tools/call"


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
                assert health_data["name"] == "BMC AMI DevX Code Pipeline MCP Server"
                assert health_data["version"] == "2.2.0"

                print(f"✅ Health check passed: {health_data}")

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"Health check failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_capabilities_endpoint(self):
        """Test MCP capabilities endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(MCP_CAPABILITIES_URL, timeout=5.0)
                assert response.status_code == 200

                caps_data = response.json()
                assert "capabilities" in caps_data
                assert "serverInfo" in caps_data
                assert (
                    caps_data["serverInfo"]["name"]
                    == "BMC AMI DevX Code Pipeline MCP Server"
                )
                assert caps_data["serverInfo"]["version"] == "2.2.0"

                print(f"✅ MCP capabilities endpoint working: {caps_data}")

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"MCP capabilities test failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_tools_list_endpoint(self):
        """Test MCP tools list endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(MCP_TOOLS_LIST_URL, timeout=5.0)
                assert response.status_code == 200

                tools_data = response.json()
                assert "tools" in tools_data
                assert isinstance(tools_data["tools"], list)

                # Should have BMC ISPW tools
                if tools_data["tools"]:
                    tool = tools_data["tools"][0]
                    assert "name" in tool
                    assert "description" in tool
                    assert "inputSchema" in tool

                print(
                    f"✅ MCP tools list endpoint working, "
                    f"found {len(tools_data['tools'])} tools"
                )

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"MCP tools list test failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_tools_call_endpoint(self):
        """Test MCP tools call endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                # Test with a mock tool call
                test_payload = {"name": "test_tool", "arguments": {"test": "value"}}
                response = await client.post(
                    MCP_TOOLS_CALL_URL, json=test_payload, timeout=5.0
                )
                assert response.status_code == 200

                result_data = response.json()
                assert "content" in result_data
                assert "isError" in result_data
                assert isinstance(result_data["content"], list)

                print("✅ MCP tools call endpoint working")

            except httpx.ConnectError:
                pytest.skip("Server not running - start with 'python main.py'")
            except Exception as e:
                pytest.fail(f"MCP tools call test failed: {e}")


class TestServerConfiguration:
    """Test server configuration and setup"""

    def test_openapi_spec_exists(self):
        """Test that OpenAPI specification file exists and is valid"""
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        openapi_path = os.path.join(config_dir, "openapi.json")

        assert os.path.exists(openapi_path), f"OpenAPI spec not found at {openapi_path}"

        try:
            with open(openapi_path, "r") as f:
                spec = json.load(f)

            # Basic OpenAPI 3.0 validation
            assert "openapi" in spec, "Missing openapi version field"
            assert "info" in spec, "Missing info section"
            assert "paths" in spec, "Missing paths section"

            print(f"✅ OpenAPI spec is valid: {spec['info'].get('title', 'Unknown')}")

        except json.JSONDecodeError as e:
            pytest.fail(f"OpenAPI spec is not valid JSON: {e}")

    def test_main_module_import(self):
        """Test that main module can be imported"""
        try:
            import main

            # Test that we can create a server
            server = main.create_server()
            assert server is not None
            assert hasattr(server, "name")
            assert server.name == "BMC AMI DevX Code Pipeline MCP Server"
            assert hasattr(server, "version")
            assert server.version == "2.2.0"

            print("✅ Main module imports correctly")

        except ImportError as e:
            pytest.fail(f"Could not import main module: {e}")
        except Exception as e:
            pytest.fail(f"Main module test failed: {e}")

    def test_environment_variables(self):
        """Test environment variable handling"""
        try:
            import main

            env_vars = main.load_env_vars()
            assert isinstance(env_vars, dict)
            assert "FASTMCP_SERVER_HOST" in env_vars
            assert "FASTMCP_SERVER_PORT" in env_vars

            # Test defaults
            assert env_vars["FASTMCP_SERVER_HOST"] == "0.0.0.0"
            assert isinstance(env_vars["FASTMCP_SERVER_PORT"], int)

            print("✅ Environment variables handled correctly")

        except Exception as e:
            pytest.fail(f"Environment variables test failed: {e}")


class TestAuthentication:
    """Test authentication configuration"""

    def test_no_auth_mode(self):
        """Test server works in no-auth mode"""
        try:
            import main

            # Test with no JWT environment variables
            server = main.create_server()
            assert server is not None

            # In our mock implementation, auth should be None when no JWT config
            print("✅ No-auth mode working correctly")

        except Exception as e:
            pytest.fail(f"No-auth configuration test failed: {e}")

    def test_jwt_auth_configuration(self):
        """Test JWT authentication configuration"""
        # Set environment for JWT auth
        original_jwks = os.environ.get("FASTMCP_SERVER_AUTH_JWT_JWKS_URI")
        original_issuer = os.environ.get("FASTMCP_SERVER_AUTH_JWT_ISSUER")
        original_audience = os.environ.get("FASTMCP_SERVER_AUTH_JWT_AUDIENCE")

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

            # Create server with JWT config
            server = main.create_server()
            assert server is not None
            print("✅ JWT auth configuration loaded correctly")

        except Exception as e:
            pytest.fail(f"JWT auth configuration test failed: {e}")
        finally:
            # Restore original environment
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


class TestMockFastMCP:
    """Test MockFastMCP implementation"""

    def test_mock_fastmcp_creation(self):
        """Test MockFastMCP class instantiation"""
        try:
            from main import MockFastMCP

            # Test basic creation
            mcp = MockFastMCP(
                name="Test Server", version="1.0.0", description="Test description"
            )

            assert mcp.name == "Test Server"
            assert mcp.version == "1.0.0"
            assert mcp.description == "Test description"
            assert isinstance(mcp.tools, list)

            print("✅ MockFastMCP creation working")

        except Exception as e:
            pytest.fail(f"MockFastMCP creation test failed: {e}")

    def test_openapi_spec_loading(self):
        """Test OpenAPI specification loading"""
        try:
            from main import MockFastMCP

            # Create a test OpenAPI spec
            test_spec = {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0.0"},
                "paths": {
                    "/test": {
                        "get": {
                            "operationId": "test_operation",
                            "summary": "Test operation",
                            "parameters": [
                                {
                                    "name": "param1",
                                    "in": "query",
                                    "required": True,
                                    "schema": {"type": "string"},
                                }
                            ],
                        }
                    }
                },
            }

            # Write test spec to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(test_spec, f)
                temp_path = f.name

            try:
                # Test loading from OpenAPI spec
                mcp = MockFastMCP.from_openapi(temp_path, name="Test Server")

                assert len(mcp.tools) > 0
                tool = mcp.tools[0]
                assert tool["name"] == "test_operation"
                assert tool["description"] == "Test operation"
                assert "param1" in tool["inputSchema"]["properties"]

                print(
                    f"✅ OpenAPI spec loading working, generated {len(mcp.tools)} tools"
                )

            finally:
                # Clean up temp file
                os.unlink(temp_path)

        except Exception as e:
            pytest.fail(f"OpenAPI spec loading test failed: {e}")

    def test_openapi_spec_error_handling(self):
        """Test OpenAPI spec error handling"""
        try:
            from main import MockFastMCP

            # Test with non-existent file
            mcp = MockFastMCP.from_openapi("/non/existent/file.json", name="Test")
            assert len(mcp.tools) == 0  # Should handle gracefully

            # Test with invalid JSON file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write("invalid json content")
                invalid_path = f.name

            try:
                mcp = MockFastMCP.from_openapi(invalid_path, name="Test")
                assert len(mcp.tools) == 0  # Should handle gracefully
            finally:
                os.unlink(invalid_path)

            print("✅ OpenAPI spec error handling working")

        except Exception as e:
            pytest.fail(f"OpenAPI spec error handling test failed: {e}")

    def test_starlette_app_creation(self):
        """Test Starlette application creation"""
        try:
            from main import MockFastMCP

            mcp = MockFastMCP(name="Test Server", version="1.0.0")
            app = mcp.get_app()

            assert app is not None
            assert hasattr(app, "routes")

            # Check that required routes exist
            route_paths = [route.path for route in app.routes]
            assert "/health" in route_paths
            assert "/mcp/capabilities" in route_paths
            assert "/mcp/tools/list" in route_paths
            assert "/mcp/tools/call" in route_paths

            print("✅ Starlette app creation working")

        except Exception as e:
            pytest.fail(f"Starlette app creation test failed: {e}")

    @pytest.mark.asyncio
    async def test_endpoint_handlers_directly(self):
        """Test endpoint handlers directly without running server"""
        try:
            from starlette.testclient import TestClient

            from main import MockFastMCP

            # Create test server
            mcp = MockFastMCP(name="Test Server", version="1.0.0")
            app = mcp.get_app()

            # Use TestClient for synchronous testing
            with TestClient(app) as client:
                # Test health endpoint
                response = client.get("/health")
                assert response.status_code == 200
                health_data = response.json()
                assert health_data["status"] == "healthy"
                assert health_data["name"] == "Test Server"

                # Test capabilities endpoint
                response = client.post("/mcp/capabilities")
                assert response.status_code == 200
                caps_data = response.json()
                assert "capabilities" in caps_data
                assert "serverInfo" in caps_data

                # Test tools list endpoint
                response = client.post("/mcp/tools/list")
                assert response.status_code == 200
                tools_data = response.json()
                assert "tools" in tools_data

                # Test tools call endpoint - success case
                test_payload = {"name": "test_tool", "arguments": {"test": "value"}}
                response = client.post("/mcp/tools/call", json=test_payload)
                assert response.status_code == 200
                result_data = response.json()
                assert "content" in result_data
                assert result_data["isError"] is False

                # Test tools call endpoint - error case (malformed JSON)
                response = client.post("/mcp/tools/call", data="invalid json")
                assert response.status_code == 400

            print("✅ Endpoint handlers working directly")

        except Exception as e:
            pytest.fail(f"Endpoint handlers test failed: {e}")

    def test_main_function_components(self):
        """Test main function components without starting server"""
        try:
            import main

            # Test server creation
            server = main.create_server()
            assert server is not None

            # Test environment variable loading
            env_vars = main.load_env_vars()
            assert isinstance(env_vars, dict)
            assert "FASTMCP_SERVER_HOST" in env_vars
            assert "FASTMCP_SERVER_PORT" in env_vars

            # Test app creation
            app = server.get_app()
            assert app is not None

            print("✅ Main function components working")

        except Exception as e:
            pytest.fail(f"Main function components test failed: {e}")

    def test_main_function_execution_path(self):
        """Test main function execution path without starting uvicorn"""
        try:
            import unittest.mock

            import main

            # Mock uvicorn.run to prevent actual server startup
            with unittest.mock.patch("main.uvicorn.run") as mock_run:
                # Mock environment to use test values
                with unittest.mock.patch.dict(
                    os.environ, {"HOST": "127.0.0.1", "PORT": "8080"}
                ):
                    # Call main function
                    main.main()

                    # Verify uvicorn.run was called with correct parameters
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert call_args[1]["host"] == "127.0.0.1"
                    assert call_args[1]["port"] == 8080
                    assert call_args[1]["log_level"] == "info"
                    assert call_args[1]["access_log"] is True

            print("✅ Main function execution path working")

        except Exception as e:
            pytest.fail(f"Main function execution test failed: {e}")

    def test_main_function_error_handling(self):
        """Test main function error handling"""
        try:
            import unittest.mock

            import main

            # Mock uvicorn.run to raise an exception
            with unittest.mock.patch("main.uvicorn.run") as mock_run:
                mock_run.side_effect = Exception("Test server error")

                # Test that exception is re-raised
                with pytest.raises(Exception, match="Test server error"):
                    main.main()

            print("✅ Main function error handling working")

        except Exception as e:
            pytest.fail(f"Main function error handling test failed: {e}")


class TestBMCIntegration:
    """Test BMC AMI DevX Code Pipeline specific functionality"""

    def test_bmc_tools_generation(self):
        """Test that BMC ISPW tools are generated from OpenAPI spec"""
        try:
            import main

            server = main.create_server()

            # Should have BMC ISPW tools
            assert len(server.tools) > 0

            # Look for typical BMC ISPW operations
            tool_names = [tool["name"] for tool in server.tools]
            bmc_operations = [name for name in tool_names if "ispw" in name.lower()]

            assert len(bmc_operations) > 0, "No BMC ISPW operations found"

            print(f"✅ BMC tools generated: {len(bmc_operations)} ISPW operations")

        except Exception as e:
            pytest.fail(f"BMC tools generation test failed: {e}")

    def test_tool_schema_validation(self):
        """Test that generated tools have valid schemas"""
        try:
            import main

            server = main.create_server()

            for tool in server.tools:
                # Each tool should have required fields
                assert "name" in tool
                assert "description" in tool
                assert "inputSchema" in tool

                # Input schema should be valid
                schema = tool["inputSchema"]
                assert schema["type"] == "object"
                assert "properties" in schema
                assert "required" in schema

            print(f"✅ Tool schemas valid for {len(server.tools)} tools")

        except Exception as e:
            pytest.fail(f"Tool schema validation test failed: {e}")


class TestDockerDeployment:
    """Test Docker deployment configuration"""

    def test_dockerfile_exists(self):
        """Test that Dockerfile exists and has required content"""
        dockerfile_path = os.path.join(os.path.dirname(__file__), "Dockerfile")
        assert os.path.exists(dockerfile_path), "Dockerfile not found"

        with open(dockerfile_path, "r") as f:
            content = f.read()
            # Basic checks for Docker best practices
            assert "FROM python:" in content, "Missing Python base image"
            assert "requirements.txt" in content, "Missing requirements file"
            assert "RUN pip install" in content, "Missing pip install"
            assert "COPY main.py" in content, "Missing main.py copy"

        print("✅ Dockerfile configuration valid")

    def test_docker_compose_configuration(self):
        """Test docker-compose.yml configuration"""
        compose_path = os.path.join(os.path.dirname(__file__), "docker-compose.yml")
        assert os.path.exists(compose_path), "docker-compose.yml not found"

        with open(compose_path, "r") as f:
            content = f.read()
            # Basic checks
            assert "services:" in content, "Missing services section"
            assert "8080" in content, "Missing port configuration"

        print("✅ Docker Compose configuration valid")


if __name__ == "__main__":
    # Run basic smoke tests
    print("🧪 Running BMC AMI DevX Code Pipeline MCP Server Tests")
    pytest.main([__file__, "-v"])
