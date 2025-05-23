# OmniTask Documentation

## Overview
OmniTask is a powerful Python-based workflow automation tool that enables the creation and execution of dynamic task chains. It provides a flexible framework for building complex workflows with features like task dependencies, output chaining, and dynamic task loading.

## Workflow Templates
OmniTask supports defining workflows using YAML or JSON templates, making it easier to create and maintain workflows without writing Python code.

### Template Format
```yaml
name: my_workflow

tasks:
  task1:
    type: task_type
    config:
      param1: value1
      param2: value2

  task2:
    type: another_task_type
    config:
      param3: value3

dependencies:
  task2:
    - task1
```

### Using Templates
```python
from omniTask.core.template import WorkflowTemplate
from omniTask.core.registry import TaskRegistry

registry = TaskRegistry()
registry.load_tasks_from_directory("tasks")

template = WorkflowTemplate("workflow.yaml")
workflow = template.create_workflow(registry)
result = await workflow.run()
```

## Examples

### Text Processing Workflow
A simple example demonstrating text file processing with multiple tasks:
- File operations (read/write)
- Text statistics counting
- Text case conversion

[View Text Processing Example](examples/text_processing/README.md)

The example shows:
- Task dependency management
- Output chaining between tasks
- Error handling
- Task configuration
- Workflow execution
- Workflow templates

## Core Components

### Task System
The task system is built around the `Task` base class, which provides the foundation for all custom tasks.

#### Key Features:
- **Task Definition**: Each task must define a unique `task_name`
- **Library Dependencies**: Tasks can specify required Python packages
- **Configuration**: Tasks accept configuration parameters
- **Output Handling**: Tasks can access outputs from previous tasks
- **Relative Paths**: Support for accessing previous task outputs using `prev`, `prev2`, etc.

#### Example Task Implementation:
```python
from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
# do not import anything else here

class CustomTask(Task):
    task_name = "custom_task"
    library_dependencies = {"required_package"}

    async def execute(self) -> TaskResult:
        import required_package
        
        prev_data = self.get_output("prev")
        
        result = {
            "processed_data": process_data(prev_data)
        }
        
        return TaskResult(success=True, output=result)
```

### Task Registry

The `TaskRegistry` class handles task discovery and management.

#### Features:
- **Dynamic Task Loading**: Loads tasks from local directories, files, or remote URLs
- **Dependency Management**: Installs required Python packages for tasks
- **Task Creation**: Creates task instances with proper configuration
- **Remote Task Loading**: Supports loading tasks from HTTP/HTTPS sources

#### Example Registry Usage:
```python
registry = TaskRegistry()
registry.load_tasks_from_source("tasks")  # Load from directory
registry.load_tasks_from_source("https://example.com/tasks/remote_task.py")  # Load from URL
registry.load_tasks_from_source("/path/to/local/task.py")  # Load from file
```

### Workflow Management
The `Workflow` class manages task execution and dependency resolution.

#### Features:
- **Registry Integration**: Built-in TaskRegistry for task management
- **Task Creation**: Direct task creation through workflow
- **Dependency Management**: Define task dependencies
- **Execution Order**: Automatic determination of task execution order
- **Output Chaining**: Automatic passing of task outputs to dependent tasks
- **Error Handling**: Graceful handling of task failures

#### Example Workflow Creation:
```python
import asyncio
from omniTask.core.workflow import Workflow
from omniTask.core.registry import TaskRegistry

async def main():
    # Create registry and load tasks
    registry = TaskRegistry()
    registry.load_tasks_from_source("tasks")
    
    # Create workflow with registry
    workflow = Workflow("my_workflow", registry)
    
    # Create tasks directly through workflow
    task1 = workflow.create_task("task1", "instance1", {"config": "value"})
    task2 = workflow.create_task("task2", "instance2")
    
    # Set dependencies
    task2.add_dependency("instance1")
    
    # Run workflow
    result = await workflow.run()
```

## Best Practices

1. **Task Design**
   - Keep tasks focused and single-purpose
   - Import dependencies inside execute() method
   - Handle errors gracefully
   - Document task inputs and outputs
   - Use type hints for better code clarity

2. **Workflow Design**
   - Use a single TaskRegistry instance
   - Create workflow with registry injection
   - Use workflow's create_task method
   - Plan task dependencies carefully
   - Use meaningful task names
   - Consider error handling and recovery
   - Monitor execution times
   - Use templates for complex workflows

3. **Configuration**
   - Use configuration for flexible task behavior
   - Document configuration options
   - Provide sensible defaults
   - Use templates for consistent configuration

4. **Output Handling**
   - Use consistent output formats
   - Include timestamps in outputs
   - Handle missing or invalid outputs gracefully
   - Use relative paths (prev, prev2) for task output access

## Error Handling

The system provides several levels of error handling:

1. **Task Level**
   - Tasks should catch and handle their own errors
   - Return appropriate TaskResult with error information
   - Import dependencies safely inside execute()

2. **Workflow Level**
   - Stops execution on task failure
   - Provides error information in results
   - Maintains execution order integrity

3. **Output Access**
   - Validates task outputs before access
   - Provides clear error messages for missing outputs
   - Handles relative path errors gracefully

4. **Template Level**
   - Validates template structure
   - Provides clear error messages for invalid templates
   - Handles missing or invalid task configurations

## Future Enhancements

1. **Planned Features**
   - [ ] Parallel task execution
   - [ ] Task retry mechanisms
   - [ ] Workflow persistence
   - [ ] Enhanced monitoring and logging
   - [X] Task timeout handling

2. **Potential Improvements**
   - [ ] Web interface for workflow management
   - [ ] Task scheduling capabilities
   - [ ] Enhanced error recovery
   - [x] Workflow templates
   - [ ] Plugin system for custom tasks

## Contributing

1. **Development Setup**
   - Clone the repository
   - Install dependencies
   - Follow coding standards
   - Write tests for new features

2. **Code Style**
   - Follow PEP 8 guidelines
   - Use type hints
   - Document all public interfaces
   - Write clear commit messages

## Installation

You can install OmniTask using pip:

```bash
pip install omniTask
```

## Quick Start

```python
import asyncio
from omniTask import Workflow, TaskRegistry, WorkflowTemplate

async def main():
    # Using Python code
    registry = TaskRegistry()
    workflow = Workflow("my_workflow", registry)
    
    # Register and use functions
    workflow.register_function(my_function)
    task = workflow.create_function_task("my_function", "task1")
    
    result = await workflow.run()

    # Or using templates
    template = WorkflowTemplate("workflow.yaml")
    workflow = template.create_workflow(registry)
    result = await workflow.run()
```