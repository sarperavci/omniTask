import os
import pickle
import asyncio
import aiofiles
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from .cache_interface import CacheInterface, CacheEntry
from ..models.task_result import TaskResult

class FileCache(CacheInterface):
    """File-based cache implementation that persists cache entries to disk."""
    
    def __init__(self, cache_dir: str = ".omnitask_cache", default_ttl: Optional[timedelta] = None):
        """Initialize the file cache.
        
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time to live for cache entries
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'puts': 0,
            'expired_removals': 0,
            'file_errors': 0
        }
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.cache"
    
    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        """Retrieve a cached result by key."""
        async with self._lock:
            cache_file = self._get_cache_file_path(cache_key)
            
            if not cache_file.exists():
                self._stats['misses'] += 1
                return None
            
            try:
                async with aiofiles.open(cache_file, 'rb') as f:
                    content = await f.read()
                    entry = pickle.loads(content)
                
                # Check if expired
                if entry.is_expired():
                    await self._remove_cache_file(cache_file)
                    self._stats['expired_removals'] += 1
                    self._stats['misses'] += 1
                    return None
                
                self._stats['hits'] += 1
                return entry
                
            except (pickle.PickleError, OSError, EOFError) as e:
                self._stats['file_errors'] += 1
                self._stats['misses'] += 1
                # Remove corrupted cache file
                await self._remove_cache_file(cache_file)
                return None
    
    async def put(self, cache_key: str, result: TaskResult, ttl: Optional[timedelta] = None) -> None:
        """Store a task result in the cache."""
        async with self._lock:
            # Use provided TTL or default
            effective_ttl = ttl or self.default_ttl
            
            # Create cache entry
            entry = CacheEntry(result, datetime.now(), effective_ttl)
            
            cache_file = self._get_cache_file_path(cache_key)
            
            try:
                # Serialize and write to file
                serialized_entry = pickle.dumps(entry)
                async with aiofiles.open(cache_file, 'wb') as f:
                    await f.write(serialized_entry)
                
                self._stats['puts'] += 1
                
            except (pickle.PickleError, OSError) as e:
                self._stats['file_errors'] += 1
                # Remove failed cache file if it exists
                await self._remove_cache_file(cache_file)
                raise RuntimeError(f"Failed to write cache entry: {e}")
    
    async def delete(self, cache_key: str) -> bool:
        """Delete a cached result by key."""
        async with self._lock:
            cache_file = self._get_cache_file_path(cache_key)
            return await self._remove_cache_file(cache_file)
    
    async def clear(self) -> None:
        """Clear all cached results."""
        async with self._lock:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.cache"):
                await self._remove_cache_file(cache_file)
            
            # Reset stats
            self._stats.update({
                'hits': 0,
                'misses': 0,
                'puts': 0,
                'expired_removals': 0,
                'file_errors': 0
            })
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests) if total_requests > 0 else 0
            
            # Count current cache files
            cache_files = list(self.cache_dir.glob("*.cache"))
            
            # Calculate total cache size
            total_size = 0
            for cache_file in cache_files:
                try:
                    total_size += cache_file.stat().st_size
                except OSError:
                    pass
            
            return {
                'type': 'file',
                'cache_dir': str(self.cache_dir),
                'size': len(cache_files),
                'total_size_bytes': total_size,
                'hit_rate': hit_rate,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'puts': self._stats['puts'],
                'expired_removals': self._stats['expired_removals'],
                'file_errors': self._stats['file_errors']
            }
    
    async def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        async with self._lock:
            removed_count = 0
            
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    async with aiofiles.open(cache_file, 'rb') as f:
                        content = await f.read()
                        entry = pickle.loads(content)
                    
                    if entry.is_expired():
                        await self._remove_cache_file(cache_file)
                        removed_count += 1
                        self._stats['expired_removals'] += 1
                        
                except (pickle.PickleError, OSError, EOFError):
                    # Remove corrupted files
                    await self._remove_cache_file(cache_file)
                    removed_count += 1
                    self._stats['file_errors'] += 1
            
            return removed_count
    
    async def _remove_cache_file(self, cache_file: Path) -> bool:
        """Remove a cache file safely."""
        try:
            if cache_file.exists():
                cache_file.unlink()
                return True
        except OSError:
            pass
        return False
    
    async def get_cache_keys(self) -> List[str]:
        """Get all cache keys (for debugging/inspection)."""
        async with self._lock:
            keys = []
            for cache_file in self.cache_dir.glob("*.cache"):
                # Extract key from filename (remove .cache extension)
                key = cache_file.stem
                keys.append(key)
            return keys 