#!/usr/bin/env python3
"""
Cache Backend Implementations

Provides multiple cache backend implementations including in-memory,
Redis, and multi-tier caching strategies.
"""

import asyncio
import json
import pickle
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from .cache import CacheEntry, IntelligentCache


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class MemoryBackend(CacheBackend):
    """In-memory cache backend using IntelligentCache."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.cache = IntelligentCache(max_size=max_size, default_ttl=default_ttl)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache."""
        return await self.cache.get(key, direct_key=True)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in memory cache."""
        await self.cache.set(key, value, ttl=ttl, direct_key=True)
    
    async def delete(self, key: str) -> bool:
        """Delete key from memory cache."""
        return await self.cache.delete(key, direct_key=True)
    
    async def clear(self) -> None:
        """Clear all memory cache entries."""
        await self.cache.clear()
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in memory cache."""
        return await self.cache.exists(key, direct_key=True)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory cache statistics."""
        return self.cache.get_stats()


class RedisBackend(CacheBackend):
    """Redis cache backend for distributed caching."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "fastmcp:",
        serializer: str = "json"
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Install with: pip install redis")
        
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.serializer = serializer
        self.redis_client = None
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    async def _get_client(self):
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url)
        return self.redis_client
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        if self.serializer == "json":
            return json.dumps(value).encode('utf-8')
        elif self.serializer == "pickle":
            return pickle.dumps(value)
        else:
            raise ValueError(f"Unsupported serializer: {self.serializer}")
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if self.serializer == "json":
            return json.loads(data.decode('utf-8'))
        elif self.serializer == "pickle":
            return pickle.loads(data)
        else:
            raise ValueError(f"Unsupported serializer: {self.serializer}")
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            client = await self._get_client()
            data = await client.get(self._make_key(key))
            
            if data is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return self._deserialize(data)
        except Exception:
            self._stats["errors"] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in Redis cache."""
        try:
            client = await self._get_client()
            data = self._serialize(value)
            
            if ttl:
                await client.setex(self._make_key(key), ttl, data)
            else:
                await client.set(self._make_key(key), data)
            
            self._stats["sets"] += 1
        except Exception:
            self._stats["errors"] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache."""
        try:
            client = await self._get_client()
            result = await client.delete(self._make_key(key))
            self._stats["deletes"] += 1
            return result > 0
        except Exception:
            self._stats["errors"] += 1
            return False
    
    async def clear(self) -> None:
        """Clear all Redis cache entries with prefix."""
        try:
            client = await self._get_client()
            keys = await client.keys(f"{self.key_prefix}*")
            if keys:
                await client.delete(*keys)
        except Exception:
            self._stats["errors"] += 1
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache."""
        try:
            client = await self._get_client()
            result = await client.exists(self._make_key(key))
            return result > 0
        except Exception:
            self._stats["errors"] += 1
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics."""
        try:
            client = await self._get_client()
            info = await client.info("memory")
            
            return {
                **self._stats,
                "backend": "redis",
                "memory_used": info.get("used_memory", 0),
                "memory_peak": info.get("used_memory_peak", 0),
                "hit_rate": self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"])
            }
        except Exception:
            return {
                **self._stats,
                "backend": "redis",
                "error": "Unable to get Redis stats"
            }
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


class MultiTierCache(CacheBackend):
    """
    Multi-tier cache with L1 (memory) and L2 (Redis) backends.
    
    Provides fast local access with distributed cache fallback.
    """
    
    def __init__(
        self,
        l1_backend: CacheBackend,
        l2_backend: CacheBackend,
        l1_ttl_ratio: float = 0.5
    ):
        self.l1 = l1_backend  # Fast local cache (memory)
        self.l2 = l2_backend  # Distributed cache (Redis)
        self.l1_ttl_ratio = l1_ttl_ratio  # L1 TTL as ratio of L2 TTL
        
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "promotions": 0,  # L2 -> L1 promotions
            "evictions": 0    # L1 -> L2 evictions
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-tier cache."""
        # Try L1 first (fastest)
        value = await self.l1.get(key)
        if value is not None:
            self._stats["l1_hits"] += 1
            return value
        
        # Try L2 (distributed)
        value = await self.l2.get(key)
        if value is not None:
            self._stats["l2_hits"] += 1
            self._stats["promotions"] += 1
            
            # Promote to L1 for faster future access
            await self.l1.set(key, value)
            return value
        
        # Cache miss
        self._stats["misses"] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in multi-tier cache."""
        # Set in both tiers
        l1_ttl = int(ttl * self.l1_ttl_ratio) if ttl else None
        
        await asyncio.gather(
            self.l1.set(key, value, ttl=l1_ttl),
            self.l2.set(key, value, ttl=ttl)
        )
    
    async def delete(self, key: str) -> bool:
        """Delete key from both cache tiers."""
        results = await asyncio.gather(
            self.l1.delete(key),
            self.l2.delete(key),
            return_exceptions=True
        )
        return any(results)
    
    async def clear(self) -> None:
        """Clear both cache tiers."""
        await asyncio.gather(
            self.l1.clear(),
            self.l2.clear(),
            return_exceptions=True
        )
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in either cache tier."""
        exists_l1 = await self.l1.exists(key)
        if exists_l1:
            return True
        
        return await self.l2.exists(key)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get multi-tier cache statistics."""
        l1_stats, l2_stats = await asyncio.gather(
            self.l1.get_stats(),
            self.l2.get_stats(),
            return_exceptions=True
        )
        
        total_requests = self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"]
        
        return {
            **self._stats,
            "backend": "multi_tier",
            "total_requests": total_requests,
            "l1_hit_rate": self._stats["l1_hits"] / max(1, total_requests),
            "l2_hit_rate": self._stats["l2_hits"] / max(1, total_requests),
            "overall_hit_rate": (self._stats["l1_hits"] + self._stats["l2_hits"]) / max(1, total_requests),
            "l1_stats": l1_stats if not isinstance(l1_stats, Exception) else {"error": str(l1_stats)},
            "l2_stats": l2_stats if not isinstance(l2_stats, Exception) else {"error": str(l2_stats)}
        }


def create_cache_backend(cache_type: str, **kwargs) -> CacheBackend:
    """Factory function to create cache backends."""
    if cache_type == "memory":
        return MemoryBackend(**kwargs)
    elif cache_type == "redis":
        return RedisBackend(**kwargs)
    elif cache_type == "multi_tier":
        l1 = create_cache_backend("memory", **kwargs.get("l1_config", {}))
        l2_config = kwargs.get("l2_config", {})
        
        # Determine L2 backend type based on config
        if "redis_url" in l2_config and REDIS_AVAILABLE:
            l2 = create_cache_backend("redis", **l2_config)
        else:
            # Fallback to memory backend for L2
            l2 = create_cache_backend("memory", **l2_config)
            
        return MultiTierCache(l1, l2, **kwargs.get("multi_tier_config", {}))
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")
