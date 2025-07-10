import hashlib
import json
from typing import Any, Dict, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.task import Task

class CacheKeyGenerator:
    """Generates unique cache keys for tasks based on their configuration and dependencies."""
    
    @staticmethod
    def generate_key(task: "Task", include_dependencies: bool = True) -> str:
        """Generate a unique cache key for a task.
        
        Args:
            task: The task to generate a cache key for
            include_dependencies: Whether to include dependency outputs in the key
            
        Returns:
            A unique cache key string
        """
        key_data = {
            'task_type': task.task_name,
            'task_name': task.name,
            'config': CacheKeyGenerator._normalize_config(task.config),
        }
        
        if include_dependencies and task.dependency_outputs:
            key_data['dependencies'] = CacheKeyGenerator._normalize_dependencies(task.dependency_outputs)
        
        # Convert to stable JSON string and hash
        json_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize configuration for consistent cache key generation.
        
        Args:
            config: Task configuration dictionary
            
        Returns:
            Normalized configuration dictionary
        """
        normalized = {}
        
        # Exclude cache-related and non-deterministic configs
        excluded_keys = {
            'cache_enabled', 'cache_ttl', 'cache_key', 
            'progress_tracking', 'timeout', 'max_retry'
        }
        
        for key, value in config.items():
            if key not in excluded_keys:
                normalized[key] = CacheKeyGenerator._normalize_value(value)
        
        return normalized
    
    @staticmethod
    def _normalize_dependencies(dependencies: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize dependency outputs for consistent cache key generation.
        
        Args:
            dependencies: Dictionary of dependency outputs
            
        Returns:
            Normalized dependencies dictionary
        """
        normalized = {}
        
        for dep_name, dep_output in dependencies.items():
            normalized[dep_name] = CacheKeyGenerator._normalize_value(dep_output)
        
        return normalized
    
    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize a value for consistent serialization.
        
        Args:
            value: Value to normalize
            
        Returns:
            Normalized value
        """
        if isinstance(value, dict):
            return {k: CacheKeyGenerator._normalize_value(v) for k, v in sorted(value.items())}
        elif isinstance(value, list):
            return [CacheKeyGenerator._normalize_value(item) for item in value]
        elif isinstance(value, set):
            return sorted([CacheKeyGenerator._normalize_value(item) for item in value])
        elif isinstance(value, (int, float, str, bool, type(None))):
            return value
        else:
            # For other types, convert to string
            return str(value)
    
    @staticmethod
    def generate_partial_key(task_type: str, config: Dict[str, Any]) -> str:
        """Generate a partial cache key without dependency information.
        
        This is useful for cache invalidation based on task type and configuration.
        
        Args:
            task_type: The task type
            config: Task configuration
            
        Returns:
            A partial cache key string
        """
        key_data = {
            'task_type': task_type,
            'config': CacheKeyGenerator._normalize_config(config),
        }
        
        json_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    @staticmethod
    def get_cache_tags(task: "Task") -> Set[str]:
        """Generate cache tags for a task to support tag-based invalidation.
        
        Args:
            task: The task to generate tags for
            
        Returns:
            Set of cache tags
        """
        tags = {
            f"task_type:{task.task_name}",
            f"task_name:{task.name}",
        }
        
        # Add dependency tags
        for dep_name in task.task_dependencies:
            tags.add(f"depends_on:{dep_name}")
        
        # Add configuration-based tags
        if 'category' in task.config:
            tags.add(f"category:{task.config['category']}")
        
        return tags 