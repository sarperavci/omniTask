from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
from ..core.task import Task
from ..core.registry import TaskRegistry
from ..models.task_result import TaskResult
import asyncio

@dataclass
class TaskGroupConfig:
    type: str
    for_each: str
    config_template: Dict[str, Any]
    max_concurrent: int = 10
    error_handling: Optional[str] = None

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