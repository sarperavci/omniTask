from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
import logging
import pkg_resources
import subprocess
import sys
import re
import asyncio
from datetime import datetime
import time
import json
import ast

from ..models.task_result import TaskResult

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
                execution_time=0.0
            )

        start_time = time.time()
        if self.timeout is None:
            result = await self.execute()
            result.execution_time = time.time() - start_time
            return result

        try:
            result = await asyncio.wait_for(self.execute(), timeout=self.timeout)
            result.execution_time = time.time() - start_time
            return result
        except asyncio.TimeoutError:
            self.logger.error(f"Task {self.name} timed out after {self.timeout} seconds")
            return TaskResult(
                success=False,
                output={},
                error=TimeoutError(f"Task execution timed out after {self.timeout} seconds"),
                execution_time=time.time() - start_time
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