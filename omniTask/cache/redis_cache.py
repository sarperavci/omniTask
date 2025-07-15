import asyncio
import pickle
import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from .cache_interface import CacheInterface, CacheEntry
from ..models.task_result import TaskResult

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class RedisCache(CacheInterface):
    """Redis-based cache implementation for distributed task result caching."""
    
    def __init__(self, 
                 host: str = "localhost", 
                 port: int = 6379, 
                 db: int = 0, 
                 password: Optional[str] = None,
                 default_ttl: Optional[timedelta] = None,
                 key_prefix: str = "omnitask:",
                 max_connections: int = 10):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required. Install with: pip install redis")
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.max_connections = max_connections
        
        self._redis: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'puts': 0,
            'deletes': 0,
            'connection_errors': 0
        }
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection, creating it if necessary."""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=False,
                retry_on_timeout=True,
                socket_keepalive=True
            )
        return self._redis
    
    def _make_key(self, cache_key: str) -> str:
        """Create a Redis key with prefix."""
        return f"{self.key_prefix}{cache_key}"
    
    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                key = self._make_key(cache_key)
                
                # Get the cached data
                cached_data = await redis_client.get(key)
                
                if cached_data is None:
                    self._stats['misses'] += 1
                    return None
                
                # Deserialize the cache entry
                entry = pickle.loads(cached_data)
                
                # Check if expired (Redis TTL should handle this, but we double-check)
                if entry.is_expired():
                    await redis_client.delete(key)
                    self._stats['misses'] += 1
                    return None
                
                self._stats['hits'] += 1
                return entry
                
            except (redis.RedisError, pickle.PickleError, OSError) as e:
                self._stats['connection_errors'] += 1
                self._stats['misses'] += 1
                return None
    
    async def put(self, cache_key: str, result: TaskResult, ttl: Optional[timedelta] = None) -> None:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                key = self._make_key(cache_key)
                
                # Use provided TTL or default
                effective_ttl = ttl or self.default_ttl
                
                # Create cache entry
                entry = CacheEntry(result, datetime.now(), effective_ttl)
                
                # Serialize the entry
                serialized_entry = pickle.dumps(entry)
                
                # Calculate Redis TTL in seconds
                redis_ttl = int(effective_ttl.total_seconds()) if effective_ttl else None
                
                # Store in Redis with TTL
                if redis_ttl:
                    await redis_client.setex(key, redis_ttl, serialized_entry)
                else:
                    await redis_client.set(key, serialized_entry)
                
                self._stats['puts'] += 1
                
            except (redis.RedisError, pickle.PickleError, OSError) as e:
                self._stats['connection_errors'] += 1
                raise RuntimeError(f"Failed to write cache entry to Redis: {e}")
    
    async def delete(self, cache_key: str) -> bool:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                key = self._make_key(cache_key)
                
                result = await redis_client.delete(key)
                deleted = result > 0
                
                if deleted:
                    self._stats['deletes'] += 1
                
                return deleted
                
            except redis.RedisError as e:
                self._stats['connection_errors'] += 1
                return False
    
    async def clear(self) -> None:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                
                # Get all keys with our prefix
                pattern = f"{self.key_prefix}*"
                keys = await redis_client.keys(pattern)
                
                if keys:
                    await redis_client.delete(*keys)
                
                # Reset stats
                self._stats.update({
                    'hits': 0,
                    'misses': 0,
                    'puts': 0,
                    'deletes': 0,
                    'connection_errors': 0
                })
                
            except redis.RedisError as e:
                self._stats['connection_errors'] += 1
                raise RuntimeError(f"Failed to clear Redis cache: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                
                # Get Redis info
                info = await redis_client.info()
                
                # Count keys with our prefix
                pattern = f"{self.key_prefix}*"
                keys = await redis_client.keys(pattern)
                
                total_requests = self._stats['hits'] + self._stats['misses']
                hit_rate = (self._stats['hits'] / total_requests) if total_requests > 0 else 0
                
                return {
                    'type': 'redis',
                    'host': self.host,
                    'port': self.port,
                    'db': self.db,
                    'key_prefix': self.key_prefix,
                    'size': len(keys),
                    'hit_rate': hit_rate,
                    'hits': self._stats['hits'],
                    'misses': self._stats['misses'],
                    'puts': self._stats['puts'],
                    'deletes': self._stats['deletes'],
                    'connection_errors': self._stats['connection_errors'],
                    'redis_connected_clients': info.get('connected_clients', 0),
                    'redis_used_memory': info.get('used_memory_human', 'N/A'),
                    'redis_uptime': info.get('uptime_in_seconds', 0)
                }
                
            except redis.RedisError as e:
                self._stats['connection_errors'] += 1
                return {
                    'type': 'redis',
                    'host': self.host,
                    'port': self.port,
                    'db': self.db,
                    'key_prefix': self.key_prefix,
                    'error': f"Failed to get Redis stats: {e}",
                    'connection_errors': self._stats['connection_errors']
                }
    
    async def cleanup_expired(self) -> int:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                pattern = f"{self.key_prefix}*"
                keys = await redis_client.keys(pattern)
                
                removed_count = 0
                for key in keys:
                    try:
                        # Try to get the entry to check if it's expired
                        cached_data = await redis_client.get(key)
                        if cached_data:
                            entry = pickle.loads(cached_data)
                            if entry.is_expired():
                                await redis_client.delete(key)
                                removed_count += 1
                    except (pickle.PickleError, redis.RedisError):
                        # Remove corrupted entries
                        await redis_client.delete(key)
                        removed_count += 1
                
                return removed_count
                
            except redis.RedisError as e:
                self._stats['connection_errors'] += 1
                return 0
    
    async def get_cache_keys(self) -> List[str]:
        async with self._lock:
            try:
                redis_client = await self._get_redis()
                pattern = f"{self.key_prefix}*"
                keys = await redis_client.keys(pattern)
                
                # Remove prefix from keys
                return [key.decode().replace(self.key_prefix, '') for key in keys]
                
            except redis.RedisError as e:
                self._stats['connection_errors'] += 1
                return []
    
    async def ping(self) -> bool:
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            return True
        except redis.RedisError:
            return False
    
    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None 