from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
import logging
import asyncio
from ..core.task import Task
from ..core.registry import TaskRegistry
from ..models.task_result import TaskResult, StreamingTaskResult, StreamingYielder

@dataclass
class TaskGroupConfig:
    type: str
    for_each: str
    config_template: Dict[str, Any]
    max_concurrent: int = 10
    error_handling: Optional[str] = None
    streaming_enabled: bool = False

class TaskGroup:
    def __init__(self, name: str, config: TaskGroupConfig):
        self.name = name
        self.config = config
        self.tasks: List[Task] = []
        self.output: List[Any] = []
        self.logger = logging.getLogger(f"task_group.{name}")

    def create_tasks(self, registry: TaskRegistry, parent_output: Any) -> None:
        if not isinstance(parent_output, list):
            raise ValueError(f"Parent output must be a list for task group {self.name}")

        self.logger.info(f"Creating tasks for {len(parent_output)} items")
        for item in parent_output:
            config = self._create_task_config(item)
            task = registry.create_task(self.config.type, f"{self.name}_{len(self.tasks)}", config)
            self.tasks.append(task)
            self.logger.info(f"Created task {task.name}")

    def _create_task_config(self, item: Any) -> Dict[str, Any]:
        config = {}
        for key, value in self.config.config_template.items():
            if isinstance(value, str):
                if value == "${item}":
                    config[key] = item
                elif value.startswith("$"):
                    path = value[1:]
                    if path.startswith("."):
                        path = path[1:]
                    config[key] = self._get_value_from_path(item, path)
                else:
                    config[key] = value
            else:
                config[key] = value
        return config

    def _get_value_from_path(self, item: Any, path: str) -> Any:
        parts = path.split(".")
        current = item
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                raise ValueError(f"Invalid path {path} in task group {self.name}")
        return current

    async def execute(self) -> TaskResult:
        self.logger.info(f"Executing {len(self.tasks)} tasks")
        results = []
        
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def execute_task(task: Task) -> None:
            async with semaphore:
                self.logger.info(f"Executing task {task.name}")
                result = await task.execute_with_timeout()
                if result.success:
                    results.append(result.output)
                else:
                    self.logger.error(f"Task {task.name} failed: {result.error}")
        
        await asyncio.gather(*(execute_task(task) for task in self.tasks))
        
        self.output = results
        return TaskResult(
            success=True,
            output={"results": results}
        )

    def get_output(self) -> List[Any]:
        return self.output

class StreamingTaskGroup(TaskGroup):
    """
    A task group that can process streaming data from parent tasks.
    Creates and executes tasks as soon as data becomes available.
    """
    
    def __init__(self, name: str, config: TaskGroupConfig):
        super().__init__(name, config)
        self._active_tasks: Dict[str, Task] = {}
        self._completed_results: List[Any] = []
        self._result_lock = asyncio.Lock()
        self.registry: Optional[TaskRegistry] = None
        
    async def execute_streaming(self, stream_yielder: StreamingYielder) -> TaskResult:
        """Execute the task group in streaming mode, processing data as it arrives."""
        self.logger.info(f"Starting streaming execution for task group {self.name}")
        
        if not self.registry:
            self.logger.error("Registry not set for streaming task group")
            return TaskResult(
                success=False,
                error="Registry not available for streaming task creation"
            )
        
        results = []
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def process_streaming_item(item_data: Any, item_index: int) -> None:
            """Process a single streamed item by creating and executing a task."""
            task_name = f"{self.name}_streaming_{item_index}"
            config = self._create_task_config(item_data)
            
            try:
                task = self.registry.create_task(self.config.type, task_name, config)
                self._active_tasks[task_name] = task
                
                async with semaphore:
                    self.logger.info(f"Executing streaming task {task_name}")
                    result = await task.execute_with_timeout()
                    
                    async with self._result_lock:
                        if result.success:
                            results.append(result.output)
                            self._completed_results.append(result.output)
                            self.logger.info(f"Streaming task {task_name} completed successfully")
                        else:
                            self.logger.error(f"Streaming task {task_name} failed: {result.error}")
                    
                    del self._active_tasks[task_name]
                    
            except Exception as e:
                self.logger.error(f"Failed to create/execute streaming task for item {item_data}: {e}")
        
        # Process streaming results
        tasks_created = []
        item_count = 0
        
        async for stream_result in stream_yielder:
            if isinstance(stream_result, StreamingTaskResult) and stream_result.success:
                # Extract items from the streamed output
                try:
                    items = self._extract_streaming_items(stream_result.output)
                    self.logger.info(f"Extracted {len(items)} items from streaming result")
                    
                    for item in items:
                        task = asyncio.create_task(process_streaming_item(item, item_count))
                        tasks_created.append(task)
                        item_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to extract items from streaming result: {e}")
                    
            if stream_result.stream_complete:
                self.logger.info("Streaming completed, waiting for all tasks to finish")
                break
        
        # Wait for all streaming tasks to complete
        if tasks_created:
            self.logger.info(f"Waiting for {len(tasks_created)} streaming tasks to complete")
            await asyncio.gather(*tasks_created, return_exceptions=True)
        
        self.output = results
        self.logger.info(f"Streaming task group {self.name} completed with {len(results)} results")
        
        return TaskResult(
            success=True,
            output={"results": results}
        )
    
    def _extract_streaming_items(self, output_data: Any) -> List[Any]:
        """Extract items from streaming output data based on for_each configuration."""
        if not isinstance(output_data, dict):
            return []
            
        # Parse the for_each path to extract items
        path_parts = self.config.for_each.split('.')
        current = output_data
        
        # Skip the first part if it's a task name (we're already in the right context)
        if len(path_parts) > 1:
            path_parts = path_parts[1:]
        
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                self.logger.debug(f"Path part '{part}' not found in streaming data")
                return []
        
        if isinstance(current, list):
            return current
        elif current is not None:
            return [current]
        
        return []
    
    def set_registry(self, registry: TaskRegistry) -> None:
        """Set the registry for creating streaming tasks."""
        self.registry = registry 