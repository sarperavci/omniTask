from typing import Dict, Type, Any, Callable, Optional, List
import importlib
import os
import inspect
import logging
import subprocess
import sys
from urllib.parse import urlparse
import pkg_resources
import tempfile
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path

from omniTask.models.task_result import TaskResult
from .task import Task

class TaskRegistry:
    """
    A registry for managing task classes and functions.
    
    The TaskRegistry is responsible for:
    - Registering and managing task classes and functions
    - Loading tasks from various sources (local files, directories, remote URLs)
    - Installing required dependencies for tasks
    - Creating task instances with proper configuration
    """

    def __init__(self):
        """Initialize a new task registry."""
        self._tasks: Dict[str, Type[Task]] = {}
        self._functions: Dict[str, Callable] = {}
        self.logger = logging.getLogger("registry")

    def _install_library_dependencies(self, task_class: Type[Task]) -> None:
        """
        Install required Python packages for a task class.

        Args:
            task_class (Type[Task]): The task class requiring dependencies

        Raises:
            subprocess.CalledProcessError: If package installation fails
        """
        if not hasattr(task_class, 'library_dependencies'):
            return

        installed = {pkg.key for pkg in pkg_resources.working_set}
        missing = task_class.library_dependencies - installed

        if missing:
            self.logger.info(f"Installing library dependencies for {task_class.task_name}: {missing}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to install library dependencies for {task_class.task_name}: {e}")
                raise

    def register(self, task_class: Type[Task]) -> None:
        """
        Register a task class in the registry.

        Args:
            task_class (Type[Task]): The task class to register

        Raises:
            ValueError: If the class doesn't inherit from Task or doesn't define task_name
        """
        if not issubclass(task_class, Task):
            raise ValueError(f"Class {task_class.__name__} must inherit from Task")
        if not task_class.task_name:
            raise ValueError(f"Task class {task_class.__name__} must define task_name")
        
        self._install_library_dependencies(task_class)
        self._tasks[task_class.task_name] = task_class

    def create_task(self, task_type: str, name: str, config: Dict[str, Any] = None) -> Task:
        """
        Create a new task instance of the specified type.

        Args:
            task_type (str): The type of task to create (must be registered)
            name (str): A unique name for the task instance
            config (Dict[str, Any], optional): Configuration parameters for the task

        Returns:
            Task: A new task instance

        Raises:
            ValueError: If the task type is not registered
        """
        if task_type not in self._tasks:
            raise ValueError(f"Unknown task type: {task_type}")
        return self._tasks[task_type](name, config)

    def register_function(self, func: Callable, name: Optional[str] = None) -> None:
        """
        Register a function as a task.

        Args:
            func (Callable): The function to register
            name (str, optional): Custom name for the function. If not provided, uses function's __name__

        Raises:
            ValueError: If a function with the same name is already registered
        """
        func_name = name or func.__name__
        if func_name in self._functions:
            raise ValueError(f"Function {func_name} already registered")
        self._functions[func_name] = func

    def create_function_task(self, func_name: str, name: str, config: Dict[str, Any] = None) -> Task:
        """
        Create a task that wraps a registered function.

        Args:
            func_name (str): Name of the registered function
            name (str): A unique name for the task instance
            config (Dict[str, Any], optional): Configuration parameters for the function

        Returns:
            Task: A new task instance that will execute the function

        Raises:
            ValueError: If the function is not registered
        """
        if func_name not in self._functions:
            raise ValueError(f"Unknown function: {func_name}")
        
        func = self._functions[func_name]
        
        class FunctionTask(Task):
            task_name = func_name
            
            async def execute(self) -> TaskResult:
                try:
                    resolved_config = self._resolve_config()
                    result = await func(**resolved_config)
                    return TaskResult(success=True, output=result)
                except Exception as e:
                    return TaskResult(success=False, output={}, error=e)
        
        return FunctionTask(name, config)

    def _process_module(self, module: Any, source: str) -> None:
        """
        Process a Python module to find and register task classes.

        Args:
            module (Any): The Python module to process
            source (str): Source identifier for logging purposes
        """
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, Task) and 
                obj != Task and 
                hasattr(obj, 'task_name')):
                self.register(obj)

    def _load_module_from_file(self, file_path: str) -> None:
        """
        Load and process a Python file to find and register task classes.

        Args:
            file_path (str): Path to the Python file

        Raises:
            Exception: If module loading fails
        """
        module_name = Path(file_path).stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._process_module(module, file_path)
        except Exception as e:
            self.logger.error(f"Failed to load task from {file_path}: {str(e)}")

    def _download_remote_file(self, url: str) -> str:
        """
        Download a Python file from a remote URL.

        Args:
            url (str): URL of the Python file to download

        Returns:
            str: Path to the downloaded temporary file

        Raises:
            RuntimeError: If download fails
        """
        try:
            with urlopen(url) as response:
                content = response.read()
                
                with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp_file:
                    temp_file.write(content)
                    return temp_file.name
        except URLError as e:
            raise RuntimeError(f"Failed to download remote file from {url}: {str(e)}")

    def load_tasks_from_directory(self, directory: str) -> None:
        """
        Load all task classes from Python files in a directory.

        Args:
            directory (str): Path to the directory containing task files

        Raises:
            ValueError: If directory doesn't exist
        """
        if not os.path.exists(directory):
            raise ValueError(f"Directory {directory} does not exist")

        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('__'):
                self._load_module_from_file(os.path.join(directory, filename))

    def load_tasks_from_source(self, source: str) -> None:
        """
        Load tasks from various sources (file, directory, or URL).

        Args:
            source (str): Source to load tasks from (file path, directory path, or URL)

        Raises:
            ValueError: If source is invalid
            RuntimeError: If remote file download fails
        """
        parsed_url = urlparse(source)
        
        if parsed_url.scheme in ('http', 'https'):
            temp_file = self._download_remote_file(source)
            try:
                self._load_module_from_file(temp_file)
            finally:
                os.unlink(temp_file)
        elif os.path.isfile(source):
            self._load_module_from_file(source)
        elif os.path.isdir(source):
            self.load_tasks_from_directory(source)
        else:
            raise ValueError(f"Invalid source: {source}") 