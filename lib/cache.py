#!/usr/bin/env python3
"""
Intelligent Caching System

Provides advanced caching capabilities with LRU eviction, TTL expiration,
statistics tracking, and async-safe operations.
"""

import asyncio
import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Cache entry with value, expiration time, and metadata."""

    value: Any
    expires_at: datetime
    created_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return datetime.now() > self.expires_at

    def touch(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now()

    @property
    def age(self) -> float:
        """Get the age of the cache entry in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


class IntelligentCache:
    """
    Advanced caching system with LRU eviction, TTL expiration, and statistics.

    Features:
    - LRU (Least Recently Used) eviction policy
    - TTL (Time To Live) expiration
    - Access statistics and hit rate tracking
    - Async-safe operations with locking
    - Automatic cleanup of expired entries
    - Memory usage estimation
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize the intelligent cache.

        Args:
            max_size: Maximum number of entries to store
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: OrderedDict = OrderedDict()
        self.lock = asyncio.Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0
        self.created_at = datetime.now()

    def generate_key(self, operation: str, **kwargs) -> str:
        """Generate a consistent cache key from operation and parameters."""
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        key_data = f"{operation}:{':'.join(f'{k}:{v}' for k, v in sorted_params)}"

        # Use hash for long keys to keep them manageable
        if len(key_data) > 100:
            return f"{operation}:{hashlib.md5(key_data.encode()).hexdigest()}"

        return key_data

    def _generate_key(self, operation: str, **kwargs) -> str:
        """Private method for generating cache keys (for backward compatibility)."""
        return self.generate_key(operation, **kwargs)

    async def get(self, operation: str, direct_key: bool = False, **kwargs) -> Optional[Any]:
        """
        Retrieve a value from the cache.

        Args:
            operation: The operation name or direct key if direct_key=True
            direct_key: If True, use operation as direct key instead of generating one
            **kwargs: Parameters to generate cache key (ignored if direct_key=True)

        Returns:
            Cached value if found and not expired, None otherwise
        """
        key = operation if direct_key else self.generate_key(operation, **kwargs)

        async with self.lock:
            entry = self.cache.get(key)

            if entry is None:
                self.misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self.cache[key]
                if key in self.access_order:
                    del self.access_order[key]
                self.expirations += 1
                self.misses += 1
                return None

            # Update access statistics and LRU order
            entry.touch()
            self.access_order.move_to_end(key)
            self.hits += 1

            return entry.value

    async def set(
        self, operation: str, value: Any, ttl: Optional[int] = None, direct_key: bool = False, **kwargs
    ):
        """
        Store a value in the cache.

        Args:
            operation: The operation name or direct key if direct_key=True
            value: The value to cache
            ttl: Time-to-live in seconds (uses default if None)
            direct_key: If True, use operation as direct key instead of generating one
            **kwargs: Parameters to generate cache key (ignored if direct_key=True)
        """
        key = operation if direct_key else self.generate_key(operation, **kwargs)
        ttl = ttl or self.default_ttl

        async with self.lock:
            # Remove existing entry if present
            if key in self.cache:
                del self.cache[key]
                if key in self.access_order:
                    del self.access_order[key]

            # Evict if at capacity
            if len(self.cache) >= self.max_size:
                await self._evict_lru()

            # Create new entry
            expires_at = datetime.now() + timedelta(seconds=ttl)
            entry = CacheEntry(
                value=value, expires_at=expires_at, created_at=datetime.now()
            )

            self.cache[key] = entry
            self.access_order[key] = True

    async def _evict_lru(self):
        """Evict the least recently used entry."""
        if not self.access_order:
            return

        # Get the least recently used key (first in OrderedDict)
        lru_key = next(iter(self.access_order))

        del self.cache[lru_key]
        del self.access_order[lru_key]
        self.evictions += 1

    async def delete(self, operation: str, direct_key: bool = False, **kwargs) -> bool:
        """
        Delete a specific cache entry.

        Args:
            operation: The operation name or direct key if direct_key=True
            direct_key: If True, use operation as direct key instead of generating one
            **kwargs: Parameters to generate cache key (ignored if direct_key=True)

        Returns:
            True if entry was deleted, False if not found
        """
        key = operation if direct_key else self.generate_key(operation, **kwargs)

        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                if key in self.access_order:
                    del self.access_order[key]
                return True
            return False

    async def clear(self):
        """Clear all cache entries."""
        async with self.lock:
            self.cache.clear()
            self.access_order.clear()
            # Reset statistics except creation time
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.expirations = 0

    def cleanup_expired(self):
        """Remove expired entries (synchronous for background tasks)."""
        current_time = datetime.now()
        expired_keys = []

        for key, entry in self.cache.items():
            if current_time > entry.expires_at:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]
            if key in self.access_order:
                del self.access_order[key]
            self.expirations += 1

    async def exists(self, operation: str, direct_key: bool = False, **kwargs) -> bool:
        """
        Check if a key exists in the cache (without affecting access stats).
        
        Args:
            operation: The operation name or direct key if direct_key=True
            direct_key: If True, use operation as direct key instead of generating one
            **kwargs: Parameters to generate cache key (ignored if direct_key=True)
            
        Returns:
            True if key exists and is not expired, False otherwise
        """
        key = operation if direct_key else self.generate_key(operation, **kwargs)
        
        async with self.lock:
            if key not in self.cache:
                return False
            
            entry = self.cache[key]
            if entry.is_expired():
                # Remove expired entry
                del self.cache[key]
                if key in self.access_order:
                    del self.access_order[key]
                self.expirations += 1
                return False
            
            return True

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total_requests = self.hits + self.misses
        if total_requests == 0:
            return 0.0
        return (self.hits / total_requests) * 100

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        total_requests = self.hits + self.misses
        uptime = (datetime.now() - self.created_at).total_seconds()

        # Calculate memory usage estimate
        estimated_memory = len(self.cache) * 1024  # Rough estimate: 1KB per entry

        # Find oldest entry
        oldest_entry_age = 0
        if self.cache:
            oldest_entry = min(self.cache.values(), key=lambda e: e.created_at)
            oldest_entry_age = (
                datetime.now() - oldest_entry.created_at
            ).total_seconds()

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.get_hit_rate(), 2),
            "hit_rate_percent": round(
                self.get_hit_rate(), 2
            ),  # Keep for backward compatibility
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_requests": total_requests,
            "uptime_seconds": round(uptime, 1),
            "estimated_memory_bytes": estimated_memory,
            "oldest_entry_age_seconds": round(oldest_entry_age, 1),
            "default_ttl": self.default_ttl,
            "default_ttl_seconds": self.default_ttl,  # Keep for backward compatibility
            "expired_entries": sum(
                1 for entry in self.cache.values() if entry.is_expired()
            ),
        }

    def get_oldest_entry_age(self) -> float:
        """Get the age of the oldest entry in seconds."""
        if not self.cache:
            return 0.0

        oldest_entry = min(self.cache.values(), key=lambda e: e.created_at)
        return (datetime.now() - oldest_entry.created_at).total_seconds()

    def __len__(self) -> int:
        """Return the number of entries in the cache."""
        return len(self.cache)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the cache (doesn't check expiration)."""
        return key in self.cache
