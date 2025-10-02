#!/usr/bin/env python3
"""
Tests for lib/auth.py to improve coverage to 80%+.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest

from lib.auth import RateLimiter, create_auth_provider


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(requests_per_minute=120, burst_size=20)
        
        assert limiter.requests_per_minute == 120
        assert limiter.burst_size == 20
        assert limiter.tokens == 20.0
        assert limiter.total_requests == 0
        assert limiter.rejected_requests == 0
        assert isinstance(limiter.last_refill, datetime)

    def test_rate_limiter_default_values(self):
        """Test RateLimiter with default values."""
        limiter = RateLimiter()
        
        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 10
        assert limiter.tokens == 10.0

    @pytest.mark.asyncio
    async def test_acquire_success_with_tokens(self):
        """Test successful token acquisition when tokens available."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)
        
        # Should succeed when tokens available
        result = await limiter.acquire()
        assert result is True
        assert limiter.total_requests == 1
        assert limiter.rejected_requests == 0
        assert limiter.tokens < 5.0

    @pytest.mark.asyncio
    async def test_acquire_failure_no_tokens(self):
        """Test token acquisition failure when no tokens available."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        
        # Exhaust all tokens
        await limiter.acquire()  # tokens = 1
        await limiter.acquire()  # tokens = 0
        
        # Should fail when no tokens left
        result = await limiter.acquire()
        assert result is False
        assert limiter.total_requests == 3
        assert limiter.rejected_requests == 1

    def test_refill_tokens(self):
        """Test token refill mechanism."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        
        # Consume some tokens
        limiter.tokens = 5.0
        
        # Simulate time passage (1 minute = 1 token per second for 60 req/min)
        limiter.last_refill = datetime.now() - timedelta(seconds=2)
        
        # Refill should add tokens based on time elapsed
        limiter._refill_tokens()
        
        # Should have gained ~2 tokens (2 seconds * 1 token/second)
        assert limiter.tokens > 5.0
        assert limiter.tokens <= 10.0  # Capped at burst_size

    def test_refill_tokens_cap_at_burst_size(self):
        """Test that token refill is capped at burst size."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)
        
        # Start with no tokens
        limiter.tokens = 0.0
        
        # Simulate long time passage (should cap at burst_size)
        limiter.last_refill = datetime.now() - timedelta(minutes=10)
        
        limiter._refill_tokens()
        
        # Should be capped at burst_size
        assert limiter.tokens == 5.0

    def test_get_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        limiter.total_requests = 100
        limiter.rejected_requests = 5
        
        stats = limiter.get_stats()
        
        assert stats["total_requests"] == 100
        assert stats["rejected_requests"] == 5
        assert stats["success_rate"] == 95.0
        assert stats["current_tokens"] == 10.0
        assert stats["requests_per_minute"] == 60
        assert stats["burst_size"] == 10

    def test_get_stats_zero_requests(self):
        """Test rate limiter statistics with zero requests."""
        limiter = RateLimiter()
        
        stats = limiter.get_stats()
        
        assert stats["total_requests"] == 0
        assert stats["rejected_requests"] == 0
        assert stats["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_rate_limiter_realistic_scenario(self):
        """Test rate limiter in a realistic usage scenario."""
        limiter = RateLimiter(requests_per_minute=6, burst_size=3)  # 1 token per 10 seconds
        
        # Should allow burst requests
        assert await limiter.acquire() is True  # tokens = 2
        assert await limiter.acquire() is True  # tokens = 1
        assert await limiter.acquire() is True  # tokens = 0
        
        # Should reject next request
        assert await limiter.acquire() is False
        
        # Check stats
        stats = limiter.get_stats()
        assert stats["total_requests"] == 4
        assert stats["rejected_requests"] == 1
        assert stats["success_rate"] == 75.0


class TestCreateAuthProvider:
    """Test create_auth_provider function."""

    @patch.dict(os.environ, {"AUTH_ENABLED": "false"})
    def test_create_auth_provider_disabled(self):
        """Test auth provider creation when disabled."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {"AUTH_ENABLED": "true", "AUTH_PROVIDER": ""})
    def test_create_auth_provider_no_provider_specified(self):
        """Test auth provider creation with no provider specified."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "jwt",
        "FASTMCP_AUTH_JWKS_URI": "https://example.com/jwks",
        "FASTMCP_AUTH_ISSUER": "test-issuer",
        "FASTMCP_AUTH_AUDIENCE": "test-audience"
    })
    @patch('lib.auth.JWTVerifier')
    def test_create_auth_provider_jwt(self, mock_jwt_verifier):
        """Test JWT auth provider creation."""
        mock_provider = Mock()
        mock_jwt_verifier.return_value = mock_provider
        
        provider = create_auth_provider()
        
        assert provider == mock_provider
        mock_jwt_verifier.assert_called_once_with(
            jwks_uri="https://example.com/jwks",
            issuer="test-issuer",
            audience="test-audience"
        )

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "github",
        "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID": "test_client_id",
        "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET": "test_client_secret"
    })
    @patch('lib.auth.GitHubProvider')
    def test_create_auth_provider_github(self, mock_github_provider):
        """Test GitHub auth provider creation."""
        mock_provider = Mock()
        mock_github_provider.return_value = mock_provider
        
        provider = create_auth_provider()
        
        assert provider == mock_provider
        mock_github_provider.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret"
        )

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "google",
        "FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID": "test_client_id",
        "FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET": "test_client_secret"
    })
    @patch('lib.auth.GoogleProvider')
    def test_create_auth_provider_google(self, mock_google_provider):
        """Test Google auth provider creation."""
        mock_provider = Mock()
        mock_google_provider.return_value = mock_provider
        
        provider = create_auth_provider()
        
        assert provider == mock_provider
        mock_google_provider.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret"
        )

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "workos",
        "FASTMCP_SERVER_AUTH_AUTHKIT_CLIENT_ID": "test_client_id",
        "FASTMCP_SERVER_AUTH_AUTHKIT_CLIENT_SECRET": "test_client_secret",
        "FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN": "test-domain.com"
    })
    @patch('lib.auth.WorkOSProvider')
    def test_create_auth_provider_workos(self, mock_workos_provider):
        """Test WorkOS auth provider creation."""
        mock_provider = Mock()
        mock_workos_provider.return_value = mock_provider
        
        provider = create_auth_provider()
        
        assert provider == mock_provider
        mock_workos_provider.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret",
            domain="test-domain.com"
        )

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "unknown_provider"
    })
    def test_create_auth_provider_unknown_provider(self):
        """Test auth provider creation with unknown provider."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "jwt"
        # Missing required FASTMCP_AUTH_JWKS_URI
    })
    def test_create_auth_provider_jwt_missing_config(self):
        """Test JWT auth provider creation with missing configuration."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "github"
        # Missing required GitHub client credentials
    })
    def test_create_auth_provider_github_missing_config(self):
        """Test GitHub auth provider creation with missing configuration."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "google"
        # Missing required Google client credentials
    })
    def test_create_auth_provider_google_missing_config(self):
        """Test Google auth provider creation with missing configuration."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "workos"
        # Missing required WorkOS client credentials
    })
    def test_create_auth_provider_workos_missing_config(self):
        """Test WorkOS auth provider creation with missing configuration."""
        provider = create_auth_provider()
        assert provider is None

    @patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_PROVIDER": "jwt",
        "FASTMCP_AUTH_JWKS_URI": "https://example.com/jwks",
        "FASTMCP_AUTH_ISSUER": "test-issuer",
        "FASTMCP_AUTH_AUDIENCE": "test-audience"
    })
    @patch('lib.auth.JWTVerifier')
    def test_create_auth_provider_jwt_exception(self, mock_jwt_verifier):
        """Test JWT auth provider creation with exception."""
        mock_jwt_verifier.side_effect = Exception("JWT creation failed")
        
        provider = create_auth_provider()
        assert provider is None

    def test_module_imports(self):
        """Test that required modules are properly imported."""
        from lib.auth import RateLimiter, create_auth_provider
        
        assert RateLimiter is not None
        assert create_auth_provider is not None
        assert callable(create_auth_provider)
