#!/usr/bin/env python3
"""
Tests for Cache Backend implementations.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lib.cache_backends import (
    CacheBackend,
    MemoryBackend,
    MultiTierCache,
    create_cache_backend,
    REDIS_AVAILABLE
)

if REDIS_AVAILABLE:
    from lib.cache_backends import RedisBackend


class TestMemoryBackend:
    """Test memory cache backend."""

    @pytest.mark.asyncio
    async def test_memory_backend_basic_operations(self):
        """Test basic memory backend operations."""
        backend = MemoryBackend(max_size=10, default_ttl=300)
        
        # Test set and get
        await backend.set("key1", "value1")
        value = await backend.get("key1")
        assert value == "value1"
        
        # Test exists
        exists = await backend.exists("key1")
        assert exists is True
        
        # Test non-existent key
        value = await backend.get("nonexistent")
        assert value is None
        
        exists = await backend.exists("nonexistent")
        assert exists is False

    @pytest.mark.asyncio
    async def test_memory_backend_ttl(self):
        """Test memory backend TTL functionality."""
        backend = MemoryBackend(max_size=10, default_ttl=1)
        
        # Set with custom TTL
        await backend.set("key1", "value1", ttl=1)
        
        # Should exist immediately
        value = await backend.get("key1")
        assert value == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await backend.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_memory_backend_delete_and_clear(self):
        """Test memory backend delete and clear operations."""
        backend = MemoryBackend(max_size=10)
        
        # Set multiple keys
        await backend.set("key1", "value1")
        await backend.set("key2", "value2")
        
        # Delete one key
        deleted = await backend.delete("key1")
        assert deleted is True
        
        # Verify deletion
        value = await backend.get("key1")
        assert value is None
        
        value = await backend.get("key2")
        assert value == "value2"
        
        # Clear all
        await backend.clear()
        
        # Verify clear
        value = await backend.get("key2")
        assert value is None

    @pytest.mark.asyncio
    async def test_memory_backend_stats(self):
        """Test memory backend statistics."""
        backend = MemoryBackend(max_size=10)
        
        # Perform operations
        await backend.set("key1", "value1")
        await backend.get("key1")  # Hit
        await backend.get("nonexistent")  # Miss
        
        stats = await backend.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
class TestRedisBackend:
    """Test Redis cache backend."""

    @pytest.fixture
    async def redis_backend(self):
        """Create Redis backend for testing."""
        backend = RedisBackend(
            redis_url="redis://localhost:6379/15",  # Use test database
            key_prefix="test:",
            serializer="json"
        )
        yield backend
        await backend.clear()  # Cleanup
        await backend.close()

    @pytest.mark.asyncio
    async def test_redis_backend_basic_operations(self, redis_backend):
        """Test basic Redis backend operations."""
        # Test set and get
        await redis_backend.set("key1", "value1")
        value = await redis_backend.get("key1")
        assert value == "value1"
        
        # Test exists
        exists = await redis_backend.exists("key1")
        assert exists is True
        
        # Test non-existent key
        value = await redis_backend.get("nonexistent")
        assert value is None
        
        exists = await redis_backend.exists("nonexistent")
        assert exists is False

    @pytest.mark.asyncio
    async def test_redis_backend_complex_data(self, redis_backend):
        """Test Redis backend with complex data types."""
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "number": 42,
            "boolean": True
        }
        
        await redis_backend.set("complex", complex_data)
        retrieved = await redis_backend.get("complex")
        
        assert retrieved == complex_data

    @pytest.mark.asyncio
    async def test_redis_backend_ttl(self, redis_backend):
        """Test Redis backend TTL functionality."""
        # Set with TTL
        await redis_backend.set("key1", "value1", ttl=1)
        
        # Should exist immediately
        value = await redis_backend.get("key1")
        assert value == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await redis_backend.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_redis_backend_delete_and_clear(self, redis_backend):
        """Test Redis backend delete and clear operations."""
        # Set multiple keys
        await redis_backend.set("key1", "value1")
        await redis_backend.set("key2", "value2")
        
        # Delete one key
        deleted = await redis_backend.delete("key1")
        assert deleted is True
        
        # Verify deletion
        value = await redis_backend.get("key1")
        assert value is None
        
        value = await redis_backend.get("key2")
        assert value == "value2"
        
        # Clear all
        await redis_backend.clear()
        
        # Verify clear
        value = await redis_backend.get("key2")
        assert value is None

    @pytest.mark.asyncio
    async def test_redis_backend_stats(self, redis_backend):
        """Test Redis backend statistics."""
        # Perform operations
        await redis_backend.set("key1", "value1")
        await redis_backend.get("key1")  # Hit
        await redis_backend.get("nonexistent")  # Miss
        
        stats = await redis_backend.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "backend" in stats
        assert stats["backend"] == "redis"
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1


class TestMultiTierCache:
    """Test multi-tier cache implementation."""

    @pytest.fixture
    def mock_backends(self):
        """Create mock cache backends."""
        l1_backend = AsyncMock(spec=CacheBackend)
        l2_backend = AsyncMock(spec=CacheBackend)
        return l1_backend, l2_backend

    @pytest.mark.asyncio
    async def test_multi_tier_l1_hit(self, mock_backends):
        """Test multi-tier cache L1 hit."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend)
        
        # Configure L1 hit
        l1_backend.get.return_value = "value1"
        
        result = await cache.get("key1")
        
        assert result == "value1"
        l1_backend.get.assert_called_once_with("key1")
        l2_backend.get.assert_not_called()  # Should not reach L2

    @pytest.mark.asyncio
    async def test_multi_tier_l2_hit_with_promotion(self, mock_backends):
        """Test multi-tier cache L2 hit with L1 promotion."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend)
        
        # Configure L1 miss, L2 hit
        l1_backend.get.return_value = None
        l2_backend.get.return_value = "value1"
        
        result = await cache.get("key1")
        
        assert result == "value1"
        l1_backend.get.assert_called_once_with("key1")
        l2_backend.get.assert_called_once_with("key1")
        l1_backend.set.assert_called_once_with("key1", "value1")  # Promotion

    @pytest.mark.asyncio
    async def test_multi_tier_miss(self, mock_backends):
        """Test multi-tier cache complete miss."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend)
        
        # Configure both misses
        l1_backend.get.return_value = None
        l2_backend.get.return_value = None
        
        result = await cache.get("key1")
        
        assert result is None
        l1_backend.get.assert_called_once_with("key1")
        l2_backend.get.assert_called_once_with("key1")
        l1_backend.set.assert_not_called()  # No promotion

    @pytest.mark.asyncio
    async def test_multi_tier_set(self, mock_backends):
        """Test multi-tier cache set operation."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend, l1_ttl_ratio=0.5)
        
        await cache.set("key1", "value1", ttl=100)
        
        # Should set in both tiers with different TTLs
        l1_backend.set.assert_called_once_with("key1", "value1", ttl=50)
        l2_backend.set.assert_called_once_with("key1", "value1", ttl=100)

    @pytest.mark.asyncio
    async def test_multi_tier_delete(self, mock_backends):
        """Test multi-tier cache delete operation."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend)
        
        l1_backend.delete.return_value = True
        l2_backend.delete.return_value = False
        
        result = await cache.delete("key1")
        
        assert result is True  # Any success counts
        l1_backend.delete.assert_called_once_with("key1")
        l2_backend.delete.assert_called_once_with("key1")

    @pytest.mark.asyncio
    async def test_multi_tier_stats(self, mock_backends):
        """Test multi-tier cache statistics."""
        l1_backend, l2_backend = mock_backends
        cache = MultiTierCache(l1_backend, l2_backend)
        
        l1_backend.get_stats.return_value = {"l1": "stats"}
        l2_backend.get_stats.return_value = {"l2": "stats"}
        
        # Simulate some operations for stats
        cache._stats["l1_hits"] = 5
        cache._stats["l2_hits"] = 3
        cache._stats["misses"] = 2
        
        stats = await cache.get_stats()
        
        assert stats["backend"] == "multi_tier"
        assert stats["l1_hits"] == 5
        assert stats["l2_hits"] == 3
        assert stats["misses"] == 2
        assert stats["total_requests"] == 10
        assert "l1_hit_rate" in stats
        assert "l2_hit_rate" in stats
        assert "overall_hit_rate" in stats


class TestCacheBackendFactory:
    """Test cache backend factory function."""

    def test_create_memory_backend(self):
        """Test creating memory backend."""
        backend = create_cache_backend("memory", max_size=100, default_ttl=600)
        assert isinstance(backend, MemoryBackend)

    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
    def test_create_redis_backend(self):
        """Test creating Redis backend."""
        backend = create_cache_backend(
            "redis",
            redis_url="redis://localhost:6379",
            key_prefix="test:",
            serializer="json"
        )
        assert isinstance(backend, RedisBackend)

    def test_create_multi_tier_backend(self):
        """Test creating multi-tier backend."""
        if REDIS_AVAILABLE:
            backend = create_cache_backend(
                "multi_tier",
                l1_config={"max_size": 100},
                l2_config={"redis_url": "redis://localhost:6379"},
                multi_tier_config={"l1_ttl_ratio": 0.3}
            )
            assert isinstance(backend, MultiTierCache)
        else:
            # Test with memory backends when Redis is not available
            backend = create_cache_backend(
                "multi_tier",
                l1_config={"max_size": 100},
                l2_config={"max_size": 200},  # Use memory for L2 as well
                multi_tier_config={"l1_ttl_ratio": 0.3}
            )
            assert isinstance(backend, MultiTierCache)

    def test_create_invalid_backend(self):
        """Test creating invalid backend type."""
        with pytest.raises(ValueError, match="Unsupported cache type"):
            create_cache_backend("invalid_type")
