from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from ..models.task_result import TaskResult

class CacheEntry:
    """Represents a cached task result with metadata."""
    
    def __init__(self, result: TaskResult, cached_at: datetime, ttl: Optional[timedelta] = None):
        self.result = result
        self.cached_at = cached_at
        self.ttl = ttl
        self.expires_at = cached_at + ttl if ttl else None
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the cache entry is valid (not expired and result is successful)."""
        return not self.is_expired() and self.result.success

class CacheInterface(ABC):
    """Abstract interface for task result caching."""
    
    @abstractmethod
    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        """Retrieve a cached result by key.
        
        Args:
            cache_key: The cache key to look up
            
        Returns:
            CacheEntry if found and valid, None otherwise
        """
        pass
    
    @abstractmethod
    async def put(self, cache_key: str, result: TaskResult, ttl: Optional[timedelta] = None) -> None:
        """Store a task result in the cache.
        
        Args:
            cache_key: The cache key to store under
            result: The task result to cache
            ttl: Time to live for the cache entry (optional)
        """
        pass
    
    @abstractmethod
    async def delete(self, cache_key: str) -> bool:
        """Delete a cached result by key.
        
        Args:
            cache_key: The cache key to delete
            
        Returns:
            True if the key was deleted, False if it didn't exist
        """
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached results."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics like hit rate, size, etc.
        """
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        pass 