import asyncio
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from collections import OrderedDict
from .cache_interface import CacheInterface, CacheEntry
from ..models.task_result import TaskResult

class MemoryCache(CacheInterface):
    """In-memory cache implementation with LRU eviction."""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[timedelta] = None):
        """Initialize the memory cache.
        
        Args:
            max_size: Maximum number of entries to store
            default_ttl: Default time to live for cache entries
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'puts': 0,
            'evictions': 0,
            'expired_removals': 0
        }
    
    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        """Retrieve a cached result by key."""
        async with self._lock:
            if cache_key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            entry = self._cache[cache_key]
            
            # Check if expired
            if entry.is_expired():
                del self._cache[cache_key]
                self._stats['expired_removals'] += 1
                self._stats['misses'] += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            self._stats['hits'] += 1
            return entry
    
    async def put(self, cache_key: str, result: TaskResult, ttl: Optional[timedelta] = None) -> None:
        """Store a task result in the cache."""
        async with self._lock:
            # Use provided TTL or default
            effective_ttl = ttl or self.default_ttl
            
            # Create cache entry
            entry = CacheEntry(result, datetime.now(), effective_ttl)
            
            # Remove existing entry if it exists
            if cache_key in self._cache:
                del self._cache[cache_key]
            
            # Add new entry
            self._cache[cache_key] = entry
            
            # Evict oldest entries if over max size
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats['evictions'] += 1
            
            self._stats['puts'] += 1
    
    async def delete(self, cache_key: str) -> bool:
        """Delete a cached result by key."""
        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cached results."""
        async with self._lock:
            self._cache.clear()
            # Reset stats except for historical data
            self._stats.update({
                'hits': 0,
                'misses': 0,
                'puts': 0,
                'evictions': 0,
                'expired_removals': 0
            })
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests) if total_requests > 0 else 0
            
            return {
                'type': 'memory',
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'puts': self._stats['puts'],
                'evictions': self._stats['evictions'],
                'expired_removals': self._stats['expired_removals']
            }
    
    async def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        async with self._lock:
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._stats['expired_removals'] += 1
            
            return len(expired_keys)
    
    async def get_cache_keys(self) -> List[str]:
        """Get all cache keys (for debugging/inspection)."""
        async with self._lock:
            return list(self._cache.keys())
    
    async def get_cache_size_bytes(self) -> int:
        """Estimate cache size in bytes (approximate)."""
        async with self._lock:
            # This is a rough estimate
            import sys
            total_size = 0
            
            for key, entry in self._cache.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(entry)
                total_size += sys.getsizeof(entry.result)
            
            return total_size 