#!/usr/bin/env python3
"""
Tests for lib/cache.py to improve coverage to 80%+.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest

from lib.cache import CacheEntry, IntelligentCache


class TestCacheEntry:
    """Test CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test CacheEntry creation."""
        now = datetime.now()
        entry = CacheEntry(
            value={"test": "data"},
            expires_at=now + timedelta(seconds=300),
            created_at=now
        )
        
        assert entry.value == {"test": "data"}
        assert entry.expires_at == now + timedelta(seconds=300)
        assert entry.created_at == now

    def test_cache_entry_is_expired_false(self):
        """Test CacheEntry.is_expired when not expired."""
        now = datetime.now()
        entry = CacheEntry(
            value="test",
            expires_at=now + timedelta(seconds=300),
            created_at=now
        )
        
        assert entry.is_expired() is False

    def test_cache_entry_is_expired_true(self):
        """Test CacheEntry.is_expired when expired."""
        now = datetime.now()
        entry = CacheEntry(
            value="test",
            expires_at=now - timedelta(seconds=10),  # Expired 10 seconds ago
            created_at=now - timedelta(seconds=310)
        )
        
        assert entry.is_expired() is True

    def test_cache_entry_age(self):
        """Test CacheEntry.age property."""
        created_time = datetime.now() - timedelta(seconds=100)
        entry = CacheEntry(
            value="test",
            expires_at=datetime.now() + timedelta(seconds=200),
            created_at=created_time
        )
        
        age = entry.age
        assert 99 <= age <= 101  # Allow for small timing differences


class TestIntelligentCache:
    """Test IntelligentCache class."""

    def test_cache_initialization(self):
        """Test IntelligentCache initialization."""
        cache = IntelligentCache(max_size=100, default_ttl=300)
        
        assert cache.max_size == 100
        assert cache.default_ttl == 300
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_default_initialization(self):
        """Test IntelligentCache with default values."""
        cache = IntelligentCache()
        
        assert cache.max_size == 1000
        assert cache.default_ttl == 300

    def test_generate_key_simple(self):
        """Test key generation with simple parameters."""
        cache = IntelligentCache()
        
        key = cache._generate_key("operation", param1="value1", param2="value2")
        
        assert "operation" in key
        assert "param1:value1" in key
        assert "param2:value2" in key

    def test_generate_key_complex_values(self):
        """Test key generation with complex parameter values."""
        cache = IntelligentCache()
        
        key = cache._generate_key("op", data={"nested": "dict"}, items=[1, 2, 3])
        
        assert "op" in key
        assert key is not None

    @pytest.mark.asyncio
    async def test_set_and_get_success(self):
        """Test successful cache set and get operations."""
        cache = IntelligentCache(max_size=10, default_ttl=300)
        
        await cache.set("test_op", {"result": "data"}, param1="value1")
        
        result = await cache.get("test_op", param1="value1")
        
        assert result == {"result": "data"}
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test cache get with cache miss."""
        cache = IntelligentCache()
        
        result = await cache.get("nonexistent_op", param1="value1")
        
        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_get_expired_entry(self):
        """Test cache get with expired entry."""
        cache = IntelligentCache(default_ttl=1)  # Very short TTL
        
        await cache.set("test_op", {"data": "test"}, param1="value1")
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        result = await cache.get("test_op", param1="value1")
        
        assert result is None
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self):
        """Test cache set with custom TTL."""
        cache = IntelligentCache(default_ttl=300)
        
        await cache.set("test_op", {"data": "test"}, ttl=600, param1="value1")
        
        # Check that entry exists and has correct TTL
        key = cache._generate_key("test_op", param1="value1")
        entry = cache.cache[key]
        
        # TTL should be approximately 600 seconds from now
        expected_expiry = datetime.now() + timedelta(seconds=600)
        time_diff = abs((entry.expires_at - expected_expiry).total_seconds())
        assert time_diff < 5  # Allow 5 seconds tolerance

    @pytest.mark.asyncio
    async def test_cache_eviction_lru(self):
        """Test LRU cache eviction when max size exceeded."""
        cache = IntelligentCache(max_size=2, default_ttl=300)
        
        # Fill cache to capacity
        await cache.set("op1", "data1", key="1")
        await cache.set("op2", "data2", key="2")
        
        # Access first item to make it more recently used
        await cache.get("op1", key="1")
        
        # Add third item (should evict least recently used)
        await cache.set("op3", "data3", key="3")
        
        # First item should still exist (recently accessed)
        assert await cache.get("op1", key="1") == "data1"
        
        # Second item should be evicted
        assert await cache.get("op2", key="2") is None
        
        # Third item should exist
        assert await cache.get("op3", key="3") == "data3"

    @pytest.mark.asyncio
    async def test_set_update_existing_key(self):
        """Test updating an existing cache key."""
        cache = IntelligentCache()
        
        # Set initial value
        await cache.set("test_op", "initial_data", param1="value1")
        
        # Update with new value
        await cache.set("test_op", "updated_data", param1="value1")
        
        result = await cache.get("test_op", param1="value1")
        assert result == "updated_data"

    def test_cleanup_expired_sync(self):
        """Test synchronous cleanup of expired entries."""
        cache = IntelligentCache()
        
        # Add expired entry directly to cache
        expired_key = "expired_key"
        expired_entry = CacheEntry(
            value="expired_data",
            expires_at=datetime.now() - timedelta(seconds=10),
            created_at=datetime.now() - timedelta(seconds=310)
        )
        cache.cache[expired_key] = expired_entry
        cache.access_order[expired_key] = True
        
        # Add valid entry
        valid_key = "valid_key"
        valid_entry = CacheEntry(
            value="valid_data",
            expires_at=datetime.now() + timedelta(seconds=300),
            created_at=datetime.now()
        )
        cache.cache[valid_key] = valid_entry
        cache.access_order[valid_key] = True
        
        initial_size = len(cache.cache)
        cache.cleanup_expired()
        final_size = len(cache.cache)
        
        # Should have removed expired entry
        assert final_size < initial_size
        assert expired_key not in cache.cache
        assert valid_key in cache.cache

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test cache clearing."""
        cache = IntelligentCache()
        
        # Add some entries
        await cache.set("op1", "data1", key="1")
        await cache.set("op2", "data2", key="2")
        
        assert len(cache.cache) == 2
        
        await cache.clear()
        
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0

    def test_get_stats(self):
        """Test cache statistics."""
        cache = IntelligentCache(max_size=100, default_ttl=300)
        cache.hits = 10
        cache.misses = 5
        
        # Add some entries
        cache.cache["key1"] = CacheEntry("data1", datetime.now() + timedelta(seconds=300), datetime.now())
        cache.cache["key2"] = CacheEntry("data2", datetime.now() + timedelta(seconds=300), datetime.now())
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["hit_rate"] == 66.67
        assert stats["default_ttl"] == 300

    def test_get_stats_no_requests(self):
        """Test cache statistics with no requests."""
        cache = IntelligentCache()
        
        stats = cache.get_stats()
        
        assert stats["hit_rate"] == 0.0

    def test_get_hit_rate(self):
        """Test cache hit rate calculation."""
        cache = IntelligentCache()
        cache.hits = 8
        cache.misses = 2
        
        hit_rate = cache.get_hit_rate()
        assert hit_rate == 80.0

    def test_get_hit_rate_no_requests(self):
        """Test cache hit rate with no requests."""
        cache = IntelligentCache()
        
        hit_rate = cache.get_hit_rate()
        assert hit_rate == 0.0

    def test_get_oldest_entry_age_empty_cache(self):
        """Test oldest entry age with empty cache."""
        cache = IntelligentCache()
        
        age = cache.get_oldest_entry_age()
        assert age == 0.0

    def test_get_oldest_entry_age_with_entries(self):
        """Test oldest entry age with entries."""
        cache = IntelligentCache()
        
        # Add entry with known age
        old_time = datetime.now() - timedelta(seconds=100)
        cache.cache["old_key"] = CacheEntry("data", datetime.now() + timedelta(seconds=300), old_time)
        
        # Add newer entry
        new_time = datetime.now() - timedelta(seconds=50)
        cache.cache["new_key"] = CacheEntry("data", datetime.now() + timedelta(seconds=300), new_time)
        
        age = cache.get_oldest_entry_age()
        assert 95 <= age <= 105  # Should be around 100 seconds

    @pytest.mark.asyncio
    async def test_cache_thread_safety_simulation(self):
        """Test cache behavior under concurrent access simulation."""
        cache = IntelligentCache(max_size=5)
        
        # Simulate concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(cache.set(f"op_{i}", f"data_{i}", key=str(i)))
        
        await asyncio.gather(*tasks)
        
        # Cache should not exceed max size
        assert len(cache.cache) <= 5

    def test_cache_key_generation_edge_cases(self):
        """Test cache key generation with edge cases."""
        cache = IntelligentCache()
        
        # Test with None values
        key1 = cache._generate_key("op", param1=None, param2="value")
        assert key1 is not None
        
        # Test with empty strings
        key2 = cache._generate_key("op", param1="", param2="value")
        assert key2 is not None
        
        # Test with special characters
        key3 = cache._generate_key("op", param1="value/with:special&chars")
        assert key3 is not None

    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self):
        """Test cache memory usage patterns."""
        cache = IntelligentCache(max_size=1000)
        
        # Add many entries
        for i in range(100):
            await cache.set(f"op_{i}", f"data_{i}", key=str(i))
        
        # Verify cache size
        assert len(cache.cache) == 100
        
        # Verify access order tracking
        assert len(cache.access_order) == 100
