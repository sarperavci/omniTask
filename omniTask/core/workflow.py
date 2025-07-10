from typing import Dict, List, Any, Callable, Optional, Set
import logging
from datetime import datetime, timedelta
import time
import asyncio
from ..models.task_result import TaskResult, StreamingTaskResult, StreamingYielder, TaskProgress
from ..models.task_group import TaskGroupConfig, TaskGroup, StreamingTaskGroup
from .task import Task, TaskStatus, StreamingTask
from .registry import TaskRegistry
from ..cache import CacheInterface, MemoryCache

class Workflow:
    """
    A workflow is a collection of tasks that are executed in a specific order based on their dependencies.
    It manages task execution, dependency resolution, and output chaining between tasks.
    """

    def __init__(self, name: str, registry: Optional[TaskRegistry] = None):
        """
        Initialize a new workflow.

        Args:
            name (str): A unique identifier for the workflow
            registry (TaskRegistry, optional): The task registry to use. If not provided, a new one will be created.
        """
        self.name = name
        self.registry = registry or TaskRegistry()
        self.tasks: Dict[str, Task] = {}
        self.task_groups: Dict[str, TaskGroup] = {}
        self.logger = logging.getLogger(f"workflow.{name}")
        self.execution_order: List[str] = []
        self.task_dependencies: Dict[str, Set[str]] = {}
        self.task_dependents: Dict[str, Set[str]] = {}
        self._streaming_enabled = False
        self._streaming_task_groups: Dict[str, StreamingTaskGroup] = {}
        self._progress_callbacks: List[Callable[[str, TaskProgress], None]] = []
        self._workflow_progress: Dict[str, TaskProgress] = {}
        self._progress_enabled = True
        self._cache: Optional[CacheInterface] = None
        self._cache_enabled = False

    def add_task(self, task: Task) -> None:
        """
        Add a task to the workflow.

        Args:
            task (Task): The task to add

        Raises:
            ValueError: If a task with the same name already exists in the workflow
        """
        if task.name in self.tasks:
            raise ValueError(f"Task with name {task.name} already exists in workflow")
        self.tasks[task.name] = task

        if self._progress_enabled:
            task_name = task.name  # Capture the task name to avoid closure issues
            task.add_progress_callback(lambda progress, name=task_name: self._on_task_progress(name, progress))
        
        # Set up caching if enabled
        if self._cache_enabled and self._cache:
            task.set_cache(self._cache)
            task.set_cache_enabled(True)

    def add_task_group(self, name: str, config: TaskGroupConfig) -> None:
        if name in self.task_groups:
            raise ValueError(f"Task group {name} already exists")

        if config.streaming_enabled:
            group = StreamingTaskGroup(name, config)
            group.set_registry(self.registry)
            self._streaming_task_groups[name] = group
            self.task_groups[name] = group 
            self._streaming_enabled = True
        else:
            group = TaskGroup(name, config)
            self.task_groups[name] = group

    def register_function(self, func: Callable, name: Optional[str] = None) -> None:
        self.registry.register_function(func, name)

    def create_task(self, task_type: str, name: str, config: Dict[str, Any]) -> Task:
        if name in self.tasks:
            raise ValueError(f"Task {name} already exists")

        task = self.registry.create_task(task_type, name, config)
        self.add_task(task)  # Use add_task to ensure progress tracking is set up
        return task

    def create_function_task(self, func_name: str, name: str, config: Dict[str, Any] = None) -> Task:
        task = self.registry.create_function_task(func_name, name, config)
        self.add_task(task)
        return task

    def _extract_items_from_output(self, result: TaskResult, path: str) -> List[Any]:
        if not result.success:
            raise ValueError(f"Cannot extract items from failed task result: {result.error}")
        
        current = result.output
        for part in path.split('.'):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise ValueError(f"Path {path} not found in task output")
        
        if not isinstance(current, list):
            raise ValueError(f"Expected list at path {path}, got {type(current)}")
        
        return current

    def _prepare_task_config(self, template: Dict[str, Any], item: Any) -> Dict[str, Any]:
        config = {}
        for key, value in template.items():
            if isinstance(value, str) and "${item}" in value:
                config[key] = value.replace("${item}", str(item))
            else:
                config[key] = value
        return config

    async def _execute_task_group(self, group_name: str, parent_result: TaskResult) -> Dict[str, TaskResult]:
        group_config = self.task_groups[group_name]
        items = self._extract_items_from_output(parent_result, group_config.for_each)
        
        tasks = []
        for item in items:
            config = self._prepare_task_config(group_config.config_template, item)
            task = self.create_task(group_config.type, f"{group_name}_{item}", config)
            tasks.append(task)
        
        results = {}
        semaphore = asyncio.Semaphore(group_config.max_concurrent)
        
        async def execute_task(task: Task) -> None:
            async with semaphore:
                try:
                    result = await task.execute_with_timeout()
                    results[task.name] = result
                except Exception as e:
                    results[task.name] = TaskResult(success=False, output={}, error=e)
        
        await asyncio.gather(
            *(execute_task(task) for task in tasks),
            return_exceptions=True
        )
        return results

    def _extract_from_path(self, data, path):
        parts = path.split(".")
        current = data
        for part in parts:
            if part == "output" and isinstance(current, dict) and "output" in current:
                current = current["output"]
            elif part in current:
                current = current[part]
            else:
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Path part '{part}' not found in {current}")
        return current

    def _build_dependency_graph(self) -> None:
        self.task_dependencies = {}
        self.task_dependents = {}
        
        # Build dependencies for regular tasks
        for task_name, task in self.tasks.items():
            self.task_dependencies[task_name] = set(task.task_dependencies)
            for dep in task.task_dependencies:
                if dep not in self.task_dependents:
                    self.task_dependents[dep] = set()
                self.task_dependents[dep].add(task_name)
        
        # Build dependencies for task groups
        for group_name, group in self.task_groups.items():
            # Task groups depend on the task specified in their for_each path
            for_each_parts = group.config.for_each.split('.')
            parent_task = for_each_parts[0]
            
            if parent_task not in self.task_dependents:
                self.task_dependents[parent_task] = set()
            self.task_dependents[parent_task].add(group_name)
            
            # Initialize task group dependencies
            self.task_dependencies[group_name] = {parent_task}

    def _get_ready_tasks(self, completed_tasks: Set[str]) -> Set[str]:
        ready = set()
        
        # Check regular tasks
        for task_name in self.tasks:
            if task_name not in completed_tasks and task_name not in ready:
                deps = self.task_dependencies.get(task_name, set())
                if all(dep in completed_tasks for dep in deps):
                    ready.add(task_name)
        
        # Check task groups
        for group_name in self.task_groups:
            if group_name not in completed_tasks and group_name not in ready:
                deps = self.task_dependencies.get(group_name, set())
                if all(dep in completed_tasks for dep in deps):
                    ready.add(group_name)
                    
        return ready

    async def _execute_task(self, task_name: str, results: Dict[str, TaskResult]) -> TaskResult:
        task = self.tasks[task_name]
        task.dependency_outputs = {
            prev_task: results[prev_task].output
            for prev_task in self.task_dependencies[task_name]
        }
        task.dependency_order = list(self.task_dependencies[task_name])
        
        # Check if this is a streaming task and enable streaming if needed
        if isinstance(task, StreamingTask) and self._has_streaming_dependents(task_name):
            task.enable_streaming()
        
        result = await task.execute_with_timeout()
        results[task_name] = result
        
        if not result.success:
            error_type = "timeout" if isinstance(result.error, TimeoutError) else "error"
            self.logger.error(f"Task {task_name} failed with {error_type}: {result.error}")
        
        return result

    def _has_streaming_dependents(self, task_name: str) -> bool:
        """Check if a task has streaming task groups as dependents."""
        dependents = self.task_dependents.get(task_name, set())
        return any(dep in self._streaming_task_groups for dep in dependents)

    async def _handle_streaming_task_groups(self, task_name: str, task: Task) -> Dict[str, TaskResult]:
        """Handle streaming task groups that depend on this task."""
        streaming_results = {}
        
        for group_name in self.task_dependents.get(task_name, set()):
            if group_name in self._streaming_task_groups:
                streaming_group = self._streaming_task_groups[group_name]
                
                # Check if the for_each path matches this task
                if streaming_group.config.for_each.startswith(task_name):
                    self.logger.info(f"Starting streaming task group {group_name} for task {task_name}")
                    
                    if isinstance(task, StreamingTask) and task.yielder:
                        # Execute streaming task group with the task's yielder
                        result = await streaming_group.execute_streaming(task.yielder)
                        streaming_results[group_name] = result
                    else:
                        self.logger.warning(f"Task {task_name} is not a streaming task but has streaming dependents")
        
        return streaming_results

    async def run(self) -> Dict[str, TaskResult]:
        """
        Run the entire workflow, executing all tasks in the correct order based on their dependencies.
        Supports streaming mode for tasks that can yield intermediate results.

        Returns:
            Dict[str, TaskResult]: A dictionary mapping task names to their execution results

        Note:
            - Tasks are executed in topological order based on their dependencies
            - If a task fails, the workflow stops and returns the results up to that point
            - Each task's output is made available to its dependent tasks
            - Streaming tasks can yield intermediate results to streaming task groups
        """
        results = {}
        completed_tasks = set()
        self._build_dependency_graph()
        
        while True:
            ready_tasks = self._get_ready_tasks(completed_tasks)
            if not ready_tasks:
                break
                
            tasks_to_execute = []
            groups_to_execute = []
            
            for item_name in ready_tasks:
                if item_name in self.tasks:
                    tasks_to_execute.append(item_name)
                elif item_name in self.task_groups:
                    groups_to_execute.append(item_name)
            
            if not tasks_to_execute and not groups_to_execute:
                break
                
            if tasks_to_execute:
                self.logger.info(f"Executing {len(tasks_to_execute)} tasks concurrently: {tasks_to_execute}")
            if groups_to_execute:
                self.logger.info(f"Executing {len(groups_to_execute)} task groups: {groups_to_execute}")
            
            # Create tasks for execution with streaming support
            execution_tasks = []
            streaming_tasks = []
            
            for task_name in tasks_to_execute:
                task = self.tasks[task_name]
                
                # Check if this task has streaming dependents
                if self._has_streaming_dependents(task_name):
                    streaming_tasks.append((task_name, task))
                else:
                    # Regular task execution
                    execution_tasks.append(self._execute_task(task_name, results))
            
            # Execute regular tasks
            if execution_tasks:
                task_results = await asyncio.gather(*execution_tasks, return_exceptions=True)
                
                for task_name, result in zip([t for t in tasks_to_execute if not self._has_streaming_dependents(t)], task_results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Task {task_name} failed with error: {result}")
                        results[task_name] = TaskResult(success=False, output={}, error=result)
                    completed_tasks.add(task_name)
                    
                    if not results[task_name].success:
                        self.logger.error(f"Workflow stopped due to task {task_name} failure")
                        return results
            
            # Execute streaming tasks and their dependent groups
            for task_name, task in streaming_tasks:
                self.logger.info(f"Executing streaming task {task_name}")
                
                # Enable streaming on the task first
                if isinstance(task, StreamingTask):
                    task.enable_streaming()
                
                # Start streaming task groups concurrently with the streaming task
                streaming_group_tasks = []
                for group_name in self.task_dependents.get(task_name, set()):
                    if group_name in self._streaming_task_groups:
                        streaming_group = self._streaming_task_groups[group_name]
                        if streaming_group.config.for_each.startswith(task_name):
                            self.logger.info(f"Starting concurrent streaming task group {group_name}")
                            streaming_group_tasks.append(
                                streaming_group.execute_streaming(task.yielder)
                            )
                
                # Execute the streaming task and streaming groups concurrently
                if streaming_group_tasks:
                    # Run task and streaming groups in parallel
                    task_execution = self._execute_task(task_name, results)
                    all_tasks = [task_execution] + streaming_group_tasks
                    
                    # Wait for all to complete
                    concurrent_results = await asyncio.gather(*all_tasks, return_exceptions=True)
                    
                    # Process task result
                    task_result = concurrent_results[0]
                    if isinstance(task_result, Exception):
                        self.logger.error(f"Streaming task {task_name} failed with error: {task_result}")
                        results[task_name] = TaskResult(success=False, output={}, error=task_result)
                        return results
                    else:
                        results[task_name] = task_result
                        completed_tasks.add(task_name)
                        
                        if not task_result.success:
                            self.logger.error(f"Workflow stopped due to streaming task {task_name} failure")
                            return results
                    
                    # Process streaming group results
                    group_names = [group_name for group_name in self.task_dependents.get(task_name, set()) 
                                 if group_name in self._streaming_task_groups]
                    
                    for i, group_name in enumerate(group_names):
                        group_result = concurrent_results[i + 1]  # +1 because task_result is at index 0
                        if isinstance(group_result, Exception):
                            self.logger.error(f"Streaming group {group_name} failed with error: {group_result}")
                            results[group_name] = TaskResult(success=False, output={}, error=group_result)
                        else:
                            results[group_name] = group_result
                        completed_tasks.add(group_name)
                else:
                    # No streaming dependents, execute normally
                    result = await self._execute_task(task_name, results)
                    results[task_name] = result
                    completed_tasks.add(task_name)
                    
                    if not result.success:
                        self.logger.error(f"Workflow stopped due to streaming task {task_name} failure")
                        return results
            
            # Execute ready task groups
            for group_name in groups_to_execute:
                if group_name in self._streaming_task_groups:
                    # Streaming groups are handled by their parent tasks
                    continue
                    
                group = self.task_groups[group_name]
                self.logger.info(f"Executing task group {group_name}")
                
                # Get parent task result
                for_each_parts = group.config.for_each.split('.')
                parent_task = for_each_parts[0]
                
                if parent_task not in results:
                    self.logger.error(f"Parent task {parent_task} not found for group {group_name}")
                    continue
                
                parent_result = results[parent_task]
                if not parent_result.success:
                    self.logger.error(f"Parent task {parent_task} failed, skipping group {group_name}")
                    continue
                
                # Extract items from parent output
                try:
                    current = parent_result.output
                    for part in for_each_parts[1:]:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            raise ValueError(f"Path {group.config.for_each} not found in task output")
                    
                    if not isinstance(current, list):
                        raise ValueError(f"Expected list at path {group.config.for_each}, got {type(current)}")
                    
                    group.create_tasks(self.registry, current)
                    group_result = await group.execute()
                    results[group_name] = group_result
                    completed_tasks.add(group_name)
                    
                    # Update dependents
                    for next_task_name in self.task_dependents.get(group_name, set()):
                        if next_task_name in self.tasks:
                            next_task = self.tasks[next_task_name]
                            next_task.dependency_outputs[group_name] = group_result.output
                            if group_name not in next_task.dependency_order:
                                next_task.dependency_order.append(group_name)
                                
                except Exception as e:
                    self.logger.error(f"Failed to execute task group {group_name}: {e}")
                    results[group_name] = TaskResult(success=False, output={}, error=e)
                    completed_tasks.add(group_name)
        
        return results

    def get_task(self, name: str) -> Task:
        if name not in self.tasks:
            raise ValueError(f"Task {name} not found")
        return self.tasks[name]

    def get_task_group(self, name: str) -> TaskGroup:
        if name not in self.task_groups:
            raise ValueError(f"Task group {name} not found")
        return self.task_groups[name]

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def get_all_task_groups(self) -> List[TaskGroup]:
        return list(self.task_groups.values())

    def execute(self) -> None:
        for task in self.tasks.values():
            task.execute()

        for group in self.task_groups.values():
            group.execute()

    def get_task_output(self, task_name: str) -> Any:
        if task_name in self.tasks:
            return self.tasks[task_name].get_output()
        elif task_name in self.task_groups:
            return self.task_groups[task_name].get_output()
        raise ValueError(f"Task or group {task_name} not found")

    @property
    def streaming_enabled(self) -> bool:
        """Check if the workflow has streaming capabilities enabled."""
        return self._streaming_enabled

    def add_progress_callback(self, callback: Callable[[str, TaskProgress], None]) -> None:
        """Add a callback function to be called when any task progress is updated.
        
        Args:
            callback: Function that takes task name and TaskProgress object as parameters
        """
        if self._progress_enabled:
            self._progress_callbacks.append(callback)

    def get_task_progress(self, task_name: str) -> Optional[TaskProgress]:
        """Get the current progress of a specific task.
        
        Args:
            task_name: Name of the task
            
        Returns:
            TaskProgress object or None if task not found or progress tracking disabled
        """
        return self._workflow_progress.get(task_name)

    def get_workflow_progress(self) -> Dict[str, TaskProgress]:
        """Get the current progress of all tasks in the workflow.
        
        Returns:
            Dictionary mapping task names to their progress
        """
        return self._workflow_progress.copy()

    def set_progress_enabled(self, enabled: bool) -> None:
        """Enable or disable progress tracking for the workflow.
        
        Args:
            enabled: Whether to enable progress tracking
        """
        self._progress_enabled = enabled
        
        for task in self.tasks.values():
            task.set_progress_enabled(enabled)

    def _on_task_progress(self, task_name: str, progress: TaskProgress) -> None:
        """Internal callback for when a task's progress is updated.
        
        Args:
            task_name: Name of the task that updated its progress
            progress: The new progress information
        """
        self._workflow_progress[task_name] = progress
        
        for callback in self._progress_callbacks:
            try:
                callback(task_name, progress)
            except Exception as e:
                self.logger.warning(f"Workflow progress callback failed: {e}")

    def get_overall_progress(self) -> TaskProgress:
        """Calculate overall workflow progress based on all tasks.
        
        Returns:
            TaskProgress representing the overall workflow progress
        """
        if not self._workflow_progress:
            return TaskProgress(current=0, total=100, message="No tasks started")
        
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for progress in self._workflow_progress.values() 
                            if progress.percentage >= 100)
        
        overall_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        return TaskProgress(
            current=completed_tasks,
            total=total_tasks,
            message=f"{completed_tasks}/{total_tasks} tasks completed",
            percentage=overall_percentage
        )
    
    def set_cache(self, cache: CacheInterface) -> None:
        """Set the cache interface for this workflow and all its tasks.
        
        Args:
            cache: The cache interface to use
        """
        self._cache = cache
        for task in self.tasks.values():
            task.set_cache(cache)
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching for this workflow and all its tasks.
        
        Args:
            enabled: Whether to enable caching
        """
        self._cache_enabled = enabled
        for task in self.tasks.values():
            task.set_cache_enabled(enabled)
    
    def enable_memory_cache(self, max_size: int = 1000, default_ttl: Optional[timedelta] = None) -> None:
        """Enable memory caching for this workflow.
        
        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default time to live for cache entries
        """
        cache = MemoryCache(max_size=max_size, default_ttl=default_ttl)
        self.set_cache(cache)
        self.set_cache_enabled(True)
    
    async def clear_cache(self) -> None:
        """Clear all cached results for this workflow."""
        if self._cache:
            await self._cache.clear()
    
    async def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics for this workflow.
        
        Returns:
            Dictionary containing cache statistics or None if no cache is configured
        """
        if self._cache:
            return await self._cache.get_stats()
        return None
    
    async def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        if self._cache:
            return await self._cache.cleanup_expired()
        return 0 