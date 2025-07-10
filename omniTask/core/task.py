from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Union, Callable
from enum import Enum
import logging
import pkg_resources
import subprocess
import sys
import re
import asyncio
from datetime import datetime, timedelta
import time
import json
import ast

from ..models.task_result import TaskResult, StreamingTaskResult, StreamingYielder, TaskProgress
from ..cache import CacheInterface, CacheKeyGenerator

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CONDITION_NOT_MET = "condition_not_met"

def safe_literal_eval(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value
    return value

class Task(ABC):
    task_name: str = None
    library_dependencies: Set[str] = set()
    default_timeout: Optional[float] = None
    default_max_retry: Optional[int] = 0

    def __init__(self, name: str, config: Dict[str, Any] = None):
        if not self.task_name:
            raise ValueError(f"Task class {self.__class__.__name__} must define task_name")
        self.name = name
        self.config = config or {}
        self.status = TaskStatus.PENDING
        self.result: Optional[TaskResult] = None
        self.task_dependencies: List[str] = []
        self.dependency_outputs: Dict[str, Dict[str, Any]] = {}
        self.dependency_order: List[str] = []
        self.logger = logging.getLogger(f"task.{name}")
        self.timeout = self.config.get('timeout', self.default_timeout)
        self.condition = self.config.get('condition')
        self.max_retry = self.config.get('max_retry', self.default_max_retry)
        self.retries = 0
        self._progress_callbacks: List[Callable[[TaskProgress], None]] = []
        self._current_progress: Optional[TaskProgress] = None
        self._progress_enabled = self.config.get('progress_tracking', True)
        self._cache: Optional[CacheInterface] = None
        self._cache_enabled = self.config.get('cache_enabled', False)
        self._cache_ttl = self.config.get('cache_ttl')
        if self._cache_ttl and isinstance(self._cache_ttl, (int, float)):
            self._cache_ttl = timedelta(seconds=self._cache_ttl)

    def log(self, level: int, message: str, **kwargs) -> None:
        extra = {
            "task_name": self.name,
            "task_type": self.task_name,
            "status": self.status.value,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.logger.log(level, message, extra=extra)

    def log_debug(self, message: str, **kwargs) -> None:
        self.log(logging.DEBUG, message, **kwargs)

    def log_info(self, message: str, **kwargs) -> None:
        self.log(logging.INFO, message, **kwargs)

    def log_warning(self, message: str, **kwargs) -> None:
        self.log(logging.WARNING, message, **kwargs)

    def log_error(self, message: str, **kwargs) -> None:
        self.log(logging.ERROR, message, **kwargs)

    def log_critical(self, message: str, **kwargs) -> None:
        self.log(logging.CRITICAL, message, **kwargs)

    def add_progress_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        """Add a callback function to be called when task progress is updated.
        
        Args:
            callback: Function that takes a TaskProgress object as parameter
        """
        if self._progress_enabled:
            self._progress_callbacks.append(callback)

    def update_progress(self, current: int, total: Optional[int] = None, message: str = "") -> None:
        """Update the current progress of the task.
        
        Args:
            current: Current progress value
            total: Total progress value (optional, defaults to existing total or 100)
            message: Progress message (optional)
        """
        if not self._progress_enabled:
            return
            
        if total is None:
            total = self._current_progress.total if self._current_progress else 100
            
        progress = TaskProgress(current=current, total=total, message=message)
        self._current_progress = progress
        
        self.log_info(f"Progress: {progress.percentage:.1f}% ({current}/{total}) - {message}")
        
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                self.log_warning(f"Progress callback failed: {e}")

    def get_progress(self) -> Optional[TaskProgress]:
        """Get the current progress of the task.
        
        Returns:
            TaskProgress object or None if progress tracking is disabled
        """
        return self._current_progress

    def set_progress_enabled(self, enabled: bool) -> None:
        """Enable or disable progress tracking for this task.
        
        Args:
            enabled: Whether to enable progress tracking
        """
        self._progress_enabled = enabled
    
    def set_cache(self, cache: CacheInterface) -> None:
        """Set the cache interface for this task.
        
        Args:
            cache: The cache interface to use
        """
        self._cache = cache
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching for this task.
        
        Args:
            enabled: Whether to enable caching
        """
        self._cache_enabled = enabled
    
    def get_cache_key(self) -> str:
        """Generate a cache key for this task.
        
        Returns:
            The cache key string
        """
        return CacheKeyGenerator.generate_key(self)
    
    async def get_cached_result(self) -> Optional[TaskResult]:
        """Get cached result if available and valid.
        
        Returns:
            Cached TaskResult if available, None otherwise
        """
        if not self._cache_enabled or not self._cache:
            return None
        
        cache_key = self.get_cache_key()
        
        try:
            cache_entry = await self._cache.get(cache_key)
            if cache_entry and cache_entry.is_valid():
                self.log_info(f"Cache hit for task {self.name}")
                return cache_entry.result
        except Exception as e:
            self.log_warning(f"Cache retrieval failed for task {self.name}: {e}")
        
        return None
    
    async def cache_result(self, result: TaskResult) -> None:
        """Cache the task result if caching is enabled.
        
        Args:
            result: The task result to cache
        """
        if not self._cache_enabled or not self._cache or not result.success:
            return
        
        cache_key = self.get_cache_key()
        
        try:
            await self._cache.put(cache_key, result, self._cache_ttl)
            self.log_info(f"Cached result for task {self.name}")
        except Exception as e:
            self.log_warning(f"Cache storage failed for task {self.name}: {e}")
    
    async def invalidate_cache(self) -> bool:
        """Invalidate cached result for this task.
        
        Returns:
            True if cache entry was deleted, False otherwise
        """
        if not self._cache_enabled or not self._cache:
            return False
        
        cache_key = self.get_cache_key()
        
        try:
            deleted = await self._cache.delete(cache_key)
            if deleted:
                self.log_info(f"Invalidated cache for task {self.name}")
            return deleted
        except Exception as e:
            self.log_warning(f"Cache invalidation failed for task {self.name}: {e}")
            return False

    def _evaluate_condition(self) -> bool:
        if not self.condition:
            return True

        if isinstance(self.condition, dict):
            operator = self.condition.get("operator")
            value = self.condition.get("value")
            path = self.condition.get("path")

            if not all([operator, value, path]):
                return False

            task_name, key = path.split(".")
            if task_name not in self.dependency_outputs:
                return False

            task_output = self.dependency_outputs[task_name]
            if key not in task_output:
                return False

            actual_value = task_output[key]
            if operator == "gt":
                return actual_value > value
            elif operator == "gte":
                return actual_value >= value
            elif operator == "lt":
                return actual_value < value
            elif operator == "lte":
                return actual_value <= value
            elif operator == "eq":
                return actual_value == value
            elif operator == "ne":
                return actual_value != value
            return False

        if isinstance(self.condition, str):
            condition = self.condition
            for task_name, output in self.dependency_outputs.items():
                condition = condition.replace(f"${task_name}", json.dumps(output))
            
            parts = condition.split()
            if len(parts) != 3:
                return False
                
            left, op, right = parts
            try:
                left_val = json.loads(left)
                right_val = json.loads(right)
                
                if op == ">":
                    return left_val > right_val
                elif op == ">=":
                    return left_val >= right_val
                elif op == "<":
                    return left_val < right_val
                elif op == "<=":
                    return left_val <= right_val
                elif op == "==":
                    return left_val == right_val
                elif op == "!=":
                    return left_val != right_val
                return False
            except (json.JSONDecodeError, ValueError):
                return False

        return False

    async def execute_with_timeout(self) -> TaskResult:
        if not self._evaluate_condition():
            self.status = TaskStatus.CONDITION_NOT_MET
            self.logger.info(f"Task {self.name} skipped due to condition not met")
            return TaskResult(
                success=True,
                output={"skipped": True, "reason": "condition_not_met"},
                execution_time=0.0,
                progress=self._current_progress
            )

        # Check cache first
        cached_result = await self.get_cached_result()
        if cached_result is not None:
            self.status = TaskStatus.COMPLETED
            self.result = cached_result
            return cached_result

        start_time = time.time()
        result = None
        
        if self.timeout is None:
            while self.retries <= self.max_retry:
                result = await self.execute()
                result.execution_time = time.time() - start_time
                self.retries += 1
                if result.success or self.retries > self.max_retry:
                    break

            if result and self.retries > 1:
                result.retries = self.retries

            # Cache successful result
            if result and result.success:
                await self.cache_result(result)

            return result if result else TaskResult(
                success=False,
                output={},
                error=RuntimeError("Task execution failed"),
                execution_time=time.time() - start_time,
                progress=self._current_progress
            )

        try:
            while self.retries <= self.max_retry:
                result = await asyncio.wait_for(self.execute(), timeout=self.timeout)
                result.execution_time = time.time() - start_time
                self.retries += 1
                if result.success or self.retries > self.max_retry:
                    break

            if result and self.retries > 1:
                result.retries = self.retries

            # Cache successful result
            if result and result.success:
                await self.cache_result(result)

            return result if result else TaskResult(
                success=False,
                output={},
                error=RuntimeError("Task execution failed"),
                execution_time=time.time() - start_time,
                progress=self._current_progress
            )
        except asyncio.TimeoutError:
            self.logger.error(f"Task {self.name} timed out after {self.timeout} seconds")
            return TaskResult(
                success=False,
                output={},
                error=TimeoutError(f"Task execution timed out after {self.timeout} seconds"),
                execution_time=time.time() - start_time,
                retries=self.retries if self.retries > 1 else None,
                progress=self._current_progress
            )

    @classmethod
    def ensure_dependencies(cls) -> None:
        """Ensures all required packages specified in library_dependencies are installed.
        
        Raises:
            RuntimeError: If package installation fails
        """
        if not cls.library_dependencies:
            return

        installed = {pkg.key for pkg in pkg_resources.working_set}
        missing = cls.library_dependencies - installed

        if missing:
            cls.logger.info(f"Installing dependencies for {cls.task_name}: {missing}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to install dependencies for {cls.task_name}: {e}")

    def _resolve_config(self) -> Dict[str, Any]:
        resolved_config = {}
        for key, value in self.config.items():
            if isinstance(value, str):
                matches = re.findall(r'\${([^}]+)}', value)
                if matches:
                    for match in matches:
                        task_name, *path = match.split('.')
                        if task_name not in self.dependency_outputs:
                            raise ValueError(f"Task {task_name} not found in dependencies")
                        
                        current = self.dependency_outputs[task_name]
                        for part in path:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                raise ValueError(f"Path {match} not found in task output")
                        
                        value = value.replace(f"${{{match}}}", str(current))
            resolved_config[key] = safe_literal_eval(value)
        return resolved_config

    def get_config(self, key: str, default: Any = None) -> Any:
        resolved_config = self._resolve_config()
        return resolved_config.get(key, default)

    def add_dependency(self, task_name: str) -> None:
        """Adds a task dependency and updates the dependency order.
        
        Args:
            task_name: Name of the task to add as a dependency
        """
        if task_name not in self.task_dependencies:
            self.task_dependencies.append(task_name)
            self.dependency_order.append(task_name)

    def get_output(self, path: str = None) -> Any:
        """Retrieves output from a dependent task using a path string.
        
        The path can be:
        - A relative path like "prev" or "prev2" to get output from previous tasks
        - A task name to get all output from that task
        - A dot-separated path like "task_name.field.subfield"
        
        Args:
            path: Path to the desired output value. Defaults to "prev"
            
        Returns:
            Any: The value at the specified path
            
        Raises:
            ValueError: If the path is invalid or the value doesn't exist
        """
        if path is None:
            path = "prev"

        if path.startswith("prev"):
            steps_back = 1
            remaining_path = ""
            
            if len(path) > 4:
                dot_index = path.find('.')
                if dot_index != -1:
                    steps_back_str = path[4:dot_index]
                    remaining_path = path[dot_index + 1:]
                    try:
                        steps_back = int(steps_back_str) if steps_back_str else 1
                    except ValueError:
                        raise ValueError(f"Invalid relative path: {path}")
                else:
                    try:
                        steps_back = int(path[4:])
                    except ValueError:
                        raise ValueError(f"Invalid relative path: {path}")
            
            if not self.dependency_order:
                raise ValueError("No dependencies available for relative path")
            
            if steps_back > len(self.dependency_order):
                raise ValueError(f"Not enough previous tasks for path: {path}")
            
            task_name = self.dependency_order[-steps_back]
            path = f"{task_name}.{remaining_path}" if remaining_path else task_name

        parts = path.split('.')
        task_name = parts[0]

        if task_name not in self.dependency_outputs:
            raise ValueError(f"No output available for task: {task_name}")

        current = self.dependency_outputs[task_name]
        
        if len(parts) == 1:
            return current

        for part in parts[1:]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ValueError(f"Path '{path}' not found in task output")

        return current

    def get_outputs(self, paths: List[str]) -> Dict[str, Any]:
        """Retrieves multiple outputs from dependent tasks.
        
        Args:
            paths: List of paths to retrieve values from
            
        Returns:
            Dict[str, Any]: Dictionary mapping paths to their values
        """
        return {path: self.get_output(path) for path in paths}

    @abstractmethod
    async def execute(self) -> TaskResult:
        """Executes the task's main logic.
        
        This method must be implemented by all task classes.
        
        Returns:
            TaskResult: Result of the task execution
        """
        pass

class StreamingTask(Task):
    """
    A task that can yield intermediate results during execution.
    This enables streaming mode where downstream tasks can start processing
    before the task completes.
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.yielder: Optional[StreamingYielder] = None
        self._streaming_enabled = self.config.get('streaming_enabled', False)
    
    @property 
    def streaming_enabled(self) -> bool:
        return self._streaming_enabled
    
    def enable_streaming(self) -> StreamingYielder:
        """Enable streaming mode and return the yielder for this task."""
        if not self.yielder:
            self.yielder = StreamingYielder()
            self._streaming_enabled = True
        return self.yielder
    
    async def yield_result(self, data: Any) -> None:
        """Yield an intermediate result during task execution."""
        if self.yielder and self._streaming_enabled:
            await self.yielder.yield_result(data)
    
    async def execute(self) -> TaskResult:
        """
        Default implementation that calls execute_streaming.
        This allows streaming tasks to only implement execute_streaming.
        """
        return await self.execute_streaming()
    
    async def execute_streaming(self) -> TaskResult:
        """
        Execute the task in streaming mode. Override this method 
        for streaming tasks instead of execute().
        """
        raise NotImplementedError("StreamingTask subclasses must implement execute_streaming method")

    async def execute_with_timeout(self) -> TaskResult:
        """Override to handle streaming execution."""
        if not self._evaluate_condition():
            self.status = TaskStatus.CONDITION_NOT_MET
            self.logger.info(f"Task {self.name} skipped due to condition not met")
            result = TaskResult(
                success=True,
                output={"skipped": True, "reason": "condition_not_met"},
                execution_time=0.0,
                progress=self._current_progress
            )
            if self.yielder:
                await self.yielder.complete(result)
            return result

        start_time = time.time()
        
        try:
            if self._streaming_enabled and self.yielder:
                result = await self.execute_streaming()
                result.execution_time = time.time() - start_time
                await self.yielder.complete(result)
                return result
            else:
                return await super().execute_with_timeout()
                
        except Exception as e:
            error_result = TaskResult(
                success=False,
                output={},
                error=e,
                execution_time=time.time() - start_time,
                progress=self._current_progress
            )
            if self.yielder:
                await self.yielder.complete(error_result)
            return error_result 