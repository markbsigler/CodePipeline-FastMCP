#!/usr/bin/env python3
"""
Authentication and Rate Limiting

Provides authentication provider creation and rate limiting functionality
for the BMC AMI DevX MCP Server.
"""

import os
from datetime import datetime

from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.workos import WorkOSProvider


class RateLimiter:
    """
    Token bucket rate limiter for API requests.

    Implements a token bucket algorithm with configurable rate and burst capacity.
    """

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        """
        Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_size: Maximum burst capacity (tokens in bucket)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens = float(burst_size)  # Start with full bucket
        self.last_refill = datetime.now()
        self.total_requests = 0
        self.rejected_requests = 0

    async def acquire(self) -> bool:
        """
        Attempt to acquire a token for a request.

        Returns:
            True if token acquired (request allowed), False otherwise
        """
        self.total_requests += 1
        self._refill_tokens()

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        else:
            self.rejected_requests += 1
            return False

    def _refill_tokens(self):
        """Refill tokens based on elapsed time since last refill."""
        now = datetime.now()
        time_elapsed = (now - self.last_refill).total_seconds()

        if time_elapsed > 0:
            # Calculate tokens to add based on rate
            tokens_to_add = (self.requests_per_minute / 60.0) * time_elapsed
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "requests_per_minute": self.requests_per_minute,
            "burst_size": self.burst_size,
            "current_tokens": round(self.tokens, 2),
            "tokens_available": round(
                self.tokens, 2
            ),  # Keep for backward compatibility
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "success_rate": (
                100.0
                if self.total_requests == 0
                else round(
                    (
                        (self.total_requests - self.rejected_requests)
                        / self.total_requests
                    )
                    * 100,
                    2,
                )
            ),
            "rejection_rate": (
                round((self.rejected_requests / max(1, self.total_requests)) * 100, 2)
            ),
            "last_refill": self.last_refill.isoformat(),
        }

    @property
    def tokens_available(self) -> float:
        """Get current number of available tokens."""
        self._refill_tokens()
        return self.tokens

    @property
    def is_full(self) -> bool:
        """Check if token bucket is full."""
        self._refill_tokens()
        return self.tokens >= self.burst_size

    @property
    def time_until_token(self) -> float:
        """Get time in seconds until next token is available."""
        if self.tokens >= 1:
            return 0.0

        # Calculate time needed for one token
        return 60.0 / self.requests_per_minute


def create_auth_provider():
    """
    Create authentication provider based on environment configuration.

    Returns:
        Configured authentication provider or None if auth is disabled
    """
    # Check if authentication is enabled
    if not os.getenv("AUTH_ENABLED", "false").lower() == "true":
        return None

    auth_provider = os.getenv("AUTH_PROVIDER", "").lower()

    if not auth_provider:
        return None

    try:
        if auth_provider == "jwt":
            jwks_uri = os.getenv("FASTMCP_AUTH_JWKS_URI")
            issuer = os.getenv("FASTMCP_AUTH_ISSUER")
            audience = os.getenv("FASTMCP_AUTH_AUDIENCE")

            if not all([jwks_uri, issuer, audience]):
                raise ValueError("JWT auth requires JWKS_URI, ISSUER, and AUDIENCE")

            return JWTVerifier(jwks_uri=jwks_uri, issuer=issuer, audience=audience)

        elif auth_provider == "github":
            client_id = os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID")
            client_secret = os.getenv("FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET")

            if not all([client_id, client_secret]):
                raise ValueError("GitHub auth requires CLIENT_ID and CLIENT_SECRET")

            return GitHubProvider(client_id=client_id, client_secret=client_secret)

        elif auth_provider == "google":
            client_id = os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID")
            client_secret = os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET")

            if not all([client_id, client_secret]):
                raise ValueError("Google auth requires CLIENT_ID and CLIENT_SECRET")

            return GoogleProvider(client_id=client_id, client_secret=client_secret)

        elif auth_provider == "workos":
            client_id = os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_CLIENT_ID")
            client_secret = os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_CLIENT_SECRET")
            authkit_domain = os.getenv("FASTMCP_SERVER_AUTH_AUTHKIT_DOMAIN")

            if not all([client_id, client_secret, authkit_domain]):
                raise ValueError(
                    "WorkOS auth requires CLIENT_ID, CLIENT_SECRET, and AUTHKIT_DOMAIN"
                )

            return WorkOSProvider(
                client_id=client_id, client_secret=client_secret, domain=authkit_domain
            )

        else:
            raise ValueError(f"Unsupported auth provider: {auth_provider}")

    except ImportError as e:
        print(f"Warning: Auth provider {auth_provider} not available: {e}")
        return None
    except Exception as e:
        print(f"Error creating auth provider {auth_provider}: {e}")
        return None
