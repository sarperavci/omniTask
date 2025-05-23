from typing import Dict, List, Any, Callable, Optional
import logging
from datetime import datetime
import time

from ..models.task_result import TaskResult
from .task import Task, TaskStatus
from .registry import TaskRegistry

class Workflow:
    """
    A workflow is a collection of tasks that are executed in a specific order based on their dependencies.
    It manages task execution, dependency resolution, and output chaining between tasks.
    """

    def __init__(self, name: str, registry: TaskRegistry = None):
        """
        Initialize a new workflow.

        Args:
            name (str): A unique identifier for the workflow
            registry (TaskRegistry, optional): The task registry to use. If not provided, a new one will be created.
        """
        self.name = name
        self.tasks: Dict[str, Task] = {}
        self.registry = registry or TaskRegistry()
        self.logger = logging.getLogger(f"workflow.{name}")
        self.execution_order: List[str] = []

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

    def register_function(self, func: Callable, name: Optional[str] = None) -> None:
        self.registry.register_function(func, name)

    def create_task(self, task_type: str, name: str, config: Dict[str, Any] = None) -> Task:
        """
        Create a new task using the registry and add it to the workflow.

        Args:
            task_type (str): The type of task to create (must be registered in the registry)
            name (str): A unique name for the task instance
            config (Dict[str, Any], optional): Configuration parameters for the task

        Returns:
            Task: The created task instance

        Raises:
            ValueError: If the task type is not registered in the registry
        """
        task = self.registry.create_task(task_type, name, config)
        self.add_task(task)
        return task

    def create_function_task(self, func_name: str, name: str, config: Dict[str, Any] = None) -> Task:
        task = self.registry.create_function_task(func_name, name, config)
        self.add_task(task)
        return task

    async def execute_task(self, task: Task) -> TaskResult:
        """
        Execute a single task and handle its dependencies.

        Args:
            task (Task): The task to execute

        Returns:
            TaskResult: The result of the task execution

        Raises:
            ValueError: If a dependency task is not found or not completed successfully
        """
        start_time = datetime.now()
        task.status = TaskStatus.RUNNING
        
        try:
            for dep_name in task.task_dependencies:
                if dep_name not in self.tasks:
                    raise ValueError(f"Dependency task not found: {dep_name}")
                dep_task = self.tasks[dep_name]
                if dep_task.status != TaskStatus.COMPLETED:
                    raise ValueError(f"Dependency task not completed: {dep_name}")
                if not dep_task.result or not dep_task.result.success:
                    raise ValueError(f"Dependency task {dep_name} did not complete successfully")
                task.dependency_outputs[dep_name] = dep_task.result.output

            result = await task.execute_with_timeout()
            if not isinstance(result.output, dict):
                raise ValueError(f"Task {task.name} must return a dictionary as output")
                
            if isinstance(result.error, TimeoutError):
                task.status = TaskStatus.TIMEOUT
            else:
                task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                
            result.execution_time = (datetime.now() - start_time).total_seconds()
            task.result = result
            return result

        except Exception as e:
            task.status = TaskStatus.FAILED
            result = TaskResult(success=False, output={}, error=e)
            result.execution_time = (datetime.now() - start_time).total_seconds()
            task.result = result
            self.logger.error(f"Task {task.name} failed: {str(e)}")
            return result

    async def run(self) -> Dict[str, TaskResult]:
        """
        Run the entire workflow, executing all tasks in the correct order based on their dependencies.

        Returns:
            Dict[str, TaskResult]: A dictionary mapping task names to their execution results

        Note:
            - Tasks are executed in topological order based on their dependencies
            - If a task fails, the workflow stops and returns the results up to that point
            - Each task's output is made available to its dependent tasks
        """
        results = {}
        self.execution_order = []
        visited = set()
        
        def visit(task_name: str):
            if task_name in visited:
                return
            visited.add(task_name)
            task = self.tasks[task_name]
            for dep in task.task_dependencies:
                visit(dep)
            self.execution_order.append(task_name)
        
        for task_name in self.tasks:
            visit(task_name)
        
        for task_name in self.execution_order:
            task = self.tasks[task_name]
            task.dependency_outputs = {
                prev_task: results[prev_task].output
                for prev_task in self.execution_order[:self.execution_order.index(task_name)]
            }
            task.dependency_order = self.execution_order[:self.execution_order.index(task_name)]
            start_time = time.time()
            result = await task.execute_with_timeout()
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            results[task_name] = result
            
            if not result.success:
                error_type = "timeout" if isinstance(result.error, TimeoutError) else "error"
                self.logger.error(f"Task {task_name} failed with {error_type}: {result.error}")
                break
        
        return results 