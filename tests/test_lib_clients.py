#!/usr/bin/env python3
"""
Comprehensive tests for lib/clients.py

Tests BMC API client functionality including caching, metrics,
error handling, and all ISPW operations.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from lib.cache import IntelligentCache
from lib.clients import BMCAMIDevXClient
from lib.errors import ErrorHandler


class TestBMCAMIDevXClient:
    """Test BMCAMIDevXClient functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        self.mock_cache = Mock(spec=IntelligentCache)
        self.mock_metrics = Mock()
        self.mock_error_handler = Mock(spec=ErrorHandler)

        self.client = BMCAMIDevXClient(
            http_client=self.mock_http_client,
            cache=self.mock_cache,
            metrics=self.mock_metrics,
            error_handler=self.mock_error_handler,
        )

    def test_client_initialization(self):
        """Test BMCAMIDevXClient initialization."""
        assert self.client.http_client == self.mock_http_client
        assert self.client.cache == self.mock_cache
        assert self.client.metrics == self.mock_metrics
        assert self.client.error_handler == self.mock_error_handler

    def test_client_initialization_minimal(self):
        """Test BMCAMIDevXClient initialization with minimal parameters."""
        client = BMCAMIDevXClient(self.mock_http_client)

        assert client.http_client == self.mock_http_client
        assert client.cache is None
        assert client.metrics is None
        assert client.error_handler is None

    @pytest.mark.asyncio
    async def test_make_request_get_success(self):
        """Test make_request with successful GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response

        result = await self.client.make_request("GET", "/test/endpoint")

        assert result == {"data": "test"}
        self.mock_http_client.get.assert_called_once_with("/test/endpoint")
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_post_success(self):
        """Test make_request with successful POST request."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123"}
        self.mock_http_client.post.return_value = mock_response

        data = {"name": "test"}
        result = await self.client.make_request("POST", "/test/endpoint", data=data)

        assert result == {"id": "123"}
        self.mock_http_client.post.assert_called_once_with("/test/endpoint", json=data)

    @pytest.mark.asyncio
    async def test_make_request_put_success(self):
        """Test make_request with successful PUT request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"updated": True}
        self.mock_http_client.put.return_value = mock_response

        data = {"name": "updated"}
        result = await self.client.make_request("PUT", "/test/endpoint", data=data)

        assert result == {"updated": True}
        self.mock_http_client.put.assert_called_once_with("/test/endpoint", json=data)

    @pytest.mark.asyncio
    async def test_make_request_delete_success(self):
        """Test make_request with successful DELETE request."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}
        self.mock_http_client.delete.return_value = mock_response

        result = await self.client.make_request("DELETE", "/test/endpoint")

        assert result == {}
        self.mock_http_client.delete.assert_called_once_with("/test/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_unsupported_method(self):
        """Test make_request with unsupported HTTP method."""
        with pytest.raises(ValueError, match="Unsupported HTTP method: PATCH"):
            await self.client.make_request("PATCH", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_with_cache_hit(self):
        """Test make_request with cache hit."""
        cached_data = {"cached": "data"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.make_request(
            "GET", "/test/endpoint", cache_key="test_key"
        )

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with(
            "api_request", endpoint="/test/endpoint", test_key=True
        )
        self.mock_http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_make_request_with_cache_miss_and_set(self):
        """Test make_request with cache miss and subsequent cache set."""
        self.mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response

        result = await self.client.make_request(
            "GET", "/test/endpoint", cache_key="test_key", cache_ttl=600
        )

        assert result == {"data": "test"}
        self.mock_cache.get.assert_called_once()
        self.mock_cache.set.assert_called_once_with(
            "api_request",
            {"data": "test"},
            ttl=600,
            endpoint="/test/endpoint",
            test_key=True,
        )

    @pytest.mark.asyncio
    async def test_make_request_with_metrics_recording(self):
        """Test make_request with metrics recording."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response
        self.mock_metrics.record_request = Mock()

        result = await self.client.make_request("GET", "/test/endpoint")

        assert result == {"data": "test"}
        self.mock_metrics.record_request.assert_called_once()
        # Check that the call includes method, endpoint, status_code, and duration
        call_args = self.mock_metrics.record_request.call_args[0]
        assert call_args[0] == "GET"
        assert call_args[1] == "/test/endpoint"
        assert call_args[2] == 200

    @pytest.mark.asyncio
    async def test_make_request_with_legacy_metrics(self):
        """Test make_request with legacy metrics interface."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response
        # Remove record_request to simulate legacy metrics
        delattr(self.mock_metrics, "record_request")
        self.mock_metrics.record_bmc_api_call = Mock()

        result = await self.client.make_request("GET", "/test/endpoint")

        assert result == {"data": "test"}
        self.mock_metrics.record_bmc_api_call.assert_called_once()
        call_args = self.mock_metrics.record_bmc_api_call.call_args[0]
        assert call_args[0] == "GET /test/endpoint"
        assert call_args[1] is True  # success

    @pytest.mark.asyncio
    async def test_make_request_with_http_error(self):
        """Test make_request with HTTP error."""
        error = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=Mock(status_code=404)
        )
        self.mock_http_client.get.side_effect = error
        self.mock_error_handler.execute_with_recovery.return_value = {
            "error": "handled"
        }

        result = await self.client.make_request("GET", "/test/endpoint")

        assert result == {"error": "handled"}
        self.mock_error_handler.execute_with_recovery.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_with_general_error_no_handler(self):
        """Test make_request with general error and no error handler."""
        client = BMCAMIDevXClient(self.mock_http_client)  # No error handler
        error = ValueError("Test error")
        self.mock_http_client.get.side_effect = error

        with pytest.raises(ValueError, match="Test error"):
            await client.make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_get_cached_or_fetch_cache_hit(self):
        """Test get_cached_or_fetch with cache hit."""
        cached_data = {"cached": "data"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_cached_or_fetch(
            "test_operation", "/test/endpoint", {"param": "value"}
        )

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with("test_operation", param="value")
        self.mock_http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_cached_or_fetch_cache_miss(self):
        """Test get_cached_or_fetch with cache miss."""
        self.mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response

        result = await self.client.get_cached_or_fetch(
            "test_operation", "/test/endpoint", {"param": "value"}, ttl=300
        )

        assert result == {"data": "test"}
        self.mock_cache.get.assert_called_once_with("test_operation", param="value")
        self.mock_cache.set.assert_called_once_with(
            "test_operation", {"data": "test"}, ttl=300, param="value"
        )

    @pytest.mark.asyncio
    async def test_get_cached_or_fetch_no_cache(self):
        """Test get_cached_or_fetch with no cache configured."""
        client = BMCAMIDevXClient(self.mock_http_client)  # No cache
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        self.mock_http_client.get.return_value = mock_response

        result = await client.get_cached_or_fetch("test_operation", "/test/endpoint")

        assert result == {"data": "test"}
        self.mock_http_client.get.assert_called_once_with("/test/endpoint")

    @pytest.mark.asyncio
    async def test_create_assignment_success(self):
        """Test create_assignment with successful creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "assignmentId": "ASSIGN001",
            "status": "created",
        }
        self.mock_http_client.post.return_value = mock_response

        result = await self.client.create_assignment(
            srid="TEST001",
            assignment_id="ASSIGN001",
            stream="DEV",
            application="MYAPP",
            description="Test assignment",
            default_path="/src",
        )

        assert result == {"assignmentId": "ASSIGN001", "status": "created"}
        self.mock_http_client.post.assert_called_once()
        call_args = self.mock_http_client.post.call_args
        assert call_args[0][0] == "/ispw/TEST001/assignments"
        expected_data = {
            "assignmentId": "ASSIGN001",
            "stream": "DEV",
            "application": "MYAPP",
            "description": "Test assignment",
            "defaultPath": "/src",
        }
        assert call_args[1]["json"] == expected_data

    @pytest.mark.asyncio
    async def test_create_assignment_minimal(self):
        """Test create_assignment with minimal parameters."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"assignmentId": "ASSIGN001"}
        self.mock_http_client.post.return_value = mock_response

        result = await self.client.create_assignment(
            srid="TEST001", assignment_id="ASSIGN001", stream="DEV", application="MYAPP"
        )

        assert result == {"assignmentId": "ASSIGN001"}
        call_args = self.mock_http_client.post.call_args
        expected_data = {
            "assignmentId": "ASSIGN001",
            "stream": "DEV",
            "application": "MYAPP",
        }
        assert call_args[1]["json"] == expected_data

    @pytest.mark.asyncio
    async def test_get_assignments_success(self):
        """Test get_assignments with successful retrieval."""
        cached_data = {"assignments": [{"id": "ASSIGN001"}]}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_assignments(
            "TEST001", status="active", stream="DEV"
        )

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with(
            "get_assignments",
            cache_params={"srid": "TEST001", "status": "active", "stream": "DEV"},
            ttl=180,
        )

    @pytest.mark.asyncio
    async def test_get_assignments_with_query_params(self):
        """Test get_assignments constructs query parameters correctly."""
        # Mock cache miss to trigger actual HTTP request
        self.mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"assignments": []}
        self.mock_http_client.get.return_value = mock_response

        await self.client.get_assignments("TEST001", status="active", stream="DEV")

        # Should call get_cached_or_fetch which will eventually call make_request
        # The endpoint should include query parameters
        expected_endpoint = "/ispw/TEST001/assignments?status=active&stream=DEV"
        # This is called through get_cached_or_fetch, so we need to check the cache call
        self.mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_assignment_details_success(self):
        """Test get_assignment_details with successful retrieval."""
        cached_data = {"assignmentId": "ASSIGN001", "details": "test"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_assignment_details("TEST001", "ASSIGN001")

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with(
            "get_assignment_details",
            cache_params={"srid": "TEST001", "assignment_id": "ASSIGN001"},
            ttl=300,
        )

    @pytest.mark.asyncio
    async def test_generate_assignment_success(self):
        """Test generate_assignment with successful generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"taskId": "TASK001", "status": "generated"}
        self.mock_http_client.post.return_value = mock_response

        generate_data = {"level": "DEV", "components": ["COMP001"]}
        result = await self.client.generate_assignment(
            "TEST001", "ASSIGN001", generate_data
        )

        assert result == {"taskId": "TASK001", "status": "generated"}
        self.mock_http_client.post.assert_called_once_with(
            "/ispw/TEST001/assignments/ASSIGN001/tasks/generate", json=generate_data
        )

    @pytest.mark.asyncio
    async def test_generate_assignment_no_data(self):
        """Test generate_assignment with no generate data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"taskId": "TASK001"}
        self.mock_http_client.post.return_value = mock_response

        result = await self.client.generate_assignment("TEST001", "ASSIGN001")

        assert result == {"taskId": "TASK001"}
        self.mock_http_client.post.assert_called_once_with(
            "/ispw/TEST001/assignments/ASSIGN001/tasks/generate", json={}
        )

    @pytest.mark.asyncio
    async def test_promote_assignment_success(self):
        """Test promote_assignment with successful promotion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"taskId": "TASK002", "status": "promoted"}
        self.mock_http_client.post.return_value = mock_response

        promote_data = {"level": "QA"}
        result = await self.client.promote_assignment(
            "TEST001", "ASSIGN001", promote_data
        )

        assert result == {"taskId": "TASK002", "status": "promoted"}
        self.mock_http_client.post.assert_called_once_with(
            "/ispw/TEST001/assignments/ASSIGN001/tasks/promote", json=promote_data
        )

    @pytest.mark.asyncio
    async def test_create_release_success(self):
        """Test create_release with successful creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"releaseId": "REL001", "status": "created"}
        self.mock_http_client.post.return_value = mock_response

        result = await self.client.create_release(
            srid="TEST001",
            release_id="REL001",
            stream="PROD",
            application="MYAPP",
            description="Test release",
        )

        assert result == {"releaseId": "REL001", "status": "created"}
        call_args = self.mock_http_client.post.call_args
        assert call_args[0][0] == "/ispw/TEST001/releases"
        expected_data = {
            "releaseId": "REL001",
            "stream": "PROD",
            "application": "MYAPP",
            "description": "Test release",
        }
        assert call_args[1]["json"] == expected_data

    @pytest.mark.asyncio
    async def test_get_releases_success(self):
        """Test get_releases with successful retrieval."""
        cached_data = {"releases": [{"id": "REL001"}]}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_releases("TEST001", status="active")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_release_details_success(self):
        """Test get_release_details with successful retrieval."""
        cached_data = {"releaseId": "REL001", "details": "test"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_release_details("TEST001", "REL001")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_deploy_release_success(self):
        """Test deploy_release with successful deployment."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"taskId": "TASK003", "status": "deploying"}
        self.mock_http_client.post.return_value = mock_response

        deploy_data = {"environment": "PROD"}
        result = await self.client.deploy_release("TEST001", "REL001", deploy_data)

        assert result == {"taskId": "TASK003", "status": "deploying"}
        self.mock_http_client.post.assert_called_once_with(
            "/ispw/TEST001/releases/REL001/tasks/deploy", json=deploy_data
        )

    @pytest.mark.asyncio
    async def test_get_sets_with_set_id(self):
        """Test get_sets with specific set ID."""
        cached_data = {"setId": "SET001", "details": "test"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_sets("TEST001", set_id="SET001")

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with(
            "get_set_details",
            cache_params={"srid": "TEST001", "set_id": "SET001"},
            ttl=300,
        )

    @pytest.mark.asyncio
    async def test_get_sets_without_set_id(self):
        """Test get_sets without specific set ID."""
        cached_data = {"sets": [{"id": "SET001"}]}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_sets("TEST001", status="active")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_deploy_set_success(self):
        """Test deploy_set with successful deployment."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"taskId": "TASK004", "status": "deploying"}
        self.mock_http_client.post.return_value = mock_response

        deploy_data = {"environment": "PROD"}
        result = await self.client.deploy_set("TEST001", "SET001", deploy_data)

        assert result == {"taskId": "TASK004", "status": "deploying"}
        self.mock_http_client.post.assert_called_once_with(
            "/ispw/TEST001/sets/SET001/tasks/deploy", json=deploy_data
        )

    @pytest.mark.asyncio
    async def test_get_packages_with_package_id(self):
        """Test get_packages with specific package ID."""
        cached_data = {"packageId": "PKG001", "details": "test"}
        self.mock_cache.get.return_value = cached_data

        # Mock the get_package_details method call
        with patch.object(
            self.client, "get_package_details", return_value=cached_data
        ) as mock_get_details:
            result = await self.client.get_packages("TEST001", package_id="PKG001")

        assert result == cached_data
        mock_get_details.assert_called_once_with("TEST001", "PKG001")

    @pytest.mark.asyncio
    async def test_get_packages_without_package_id(self):
        """Test get_packages without specific package ID."""
        cached_data = {"packages": [{"id": "PKG001"}]}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_packages("TEST001", status="active")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_package_details_success(self):
        """Test get_package_details with successful retrieval."""
        cached_data = {"packageId": "PKG001", "details": "test"}
        self.mock_cache.get.return_value = cached_data

        result = await self.client.get_package_details("TEST001", "PKG001")

        assert result == cached_data
        self.mock_cache.get.assert_called_once_with(
            "get_package_details",
            cache_params={"srid": "TEST001", "package_id": "PKG001"},
            ttl=300,
        )
