# OmniTask Documentation

## Overview
OmniTask is a powerful Python-based workflow automation tool that enables the creation and execution of dynamic task chains. It provides a flexible framework for building complex workflows with features like task dependencies, output chaining, dynamic task loading, and dynamic task groups.

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
    for_each: task1.output.items
    config_template:
      param3: $.value
    max_concurrent: 5

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

### Bug Bounty Workflow
A comprehensive example demonstrating dynamic task groups and parallel execution:
- Subdomain discovery
- URL status checking with parallel execution
- Result analysis and aggregation

[View Bug Bounty Example](examples/mock-bounty/README.md)

### Text Processing Workflow
A simple example demonstrating text file processing with multiple tasks:
- File operations (read/write)
- Text statistics counting
- Text case conversion

[View Text Processing Example](examples/text_processing/README.md)

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

### Dynamic Task Groups
OmniTask supports dynamic task groups that can create and execute multiple tasks based on input data.

#### Features:
- **For-Each Execution**: Create tasks for each item in a list
- **Parallel Execution**: Control concurrent task execution
- **Template Configuration**: Use templates for task configuration
- **Output Aggregation**: Combine results from multiple tasks

#### Example Task Group Configuration:
```yaml
task_group:
  type: url_checker
  for_each: subdomain_scanner.subdomains
  config_template:
    url: $.url
    timeout: 5
  max_concurrent: 5
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
- **Dynamic Task Groups**: Support for creating and managing dynamic task groups

#### Example Workflow Creation:
```python
import asyncio
from omniTask.core.workflow import Workflow
from omniTask.core.registry import TaskRegistry

async def main():
    registry = TaskRegistry()
    registry.load_tasks_from_source("tasks")
    
    workflow = Workflow("my_workflow", registry)
    
    task1 = workflow.create_task("task1", "instance1", {"config": "value"})
    task2 = workflow.create_task("task2", "instance2")
    
    task2.add_dependency("instance1")
    
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
   - Leverage dynamic task groups for parallel processing

3. **Configuration**
   - Use configuration for flexible task behavior
   - Document configuration options
   - Provide sensible defaults
   - Use templates for consistent configuration
   - Configure max_concurrent for task groups appropriately

4. **Output Handling**
   - Use consistent output formats
   - Include timestamps in outputs
   - Handle missing or invalid outputs gracefully
   - Use relative paths (prev, prev2) for task output access
   - Aggregate results from dynamic task groups effectively

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
   - Handles dynamic task group failures gracefully

3. **Output Access**
   - Validates task outputs before access
   - Provides clear error messages for missing outputs
   - Handles relative path errors gracefully
   - Manages aggregated outputs from task groups

4. **Template Level**
   - Validates template structure
   - Provides clear error messages for invalid templates
   - Handles missing or invalid task configurations
   - Validates dynamic task group configurations

## Planned Features

   - [X] Workflow templates
   - [X] Parallel task execution
   - [X] Dynamic Task Handling
   - [ ] Dynamic Task Signal Handling 
   - [X] Task retry mechanisms
   - [ ] Workflow persistence
   - [X] Enhanced monitoring and logging
   - [X] Task timeout handling
   - [X] Conditional task execution (if/else branches)
   - [X] Task result streaming
   - [X] Task input/output validation
   - [ ] Resource usage monitoring
   - [ ] Task progress tracking
   - [ ] Workflow versioning
   - [ ] Task caching for repeated executions
   - [ ] Web interface for workflow management
   - [ ] Task scheduling capabilities
   - [ ] Enhanced error recovery
   - [ ] Distributed task execution

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
    registry = TaskRegistry()
    workflow = Workflow("my_workflow", registry)
    
    workflow.register_function(my_function)
    task = workflow.create_function_task("my_function", "task1")
    
    result = await workflow.run()

    template = WorkflowTemplate("workflow.yaml")
    workflow = template.create_workflow(registry)
    result = await workflow.run()
```

### Conditional Task Execution
OmniTask supports conditional task execution using two types of conditions:

1. **String-based Conditions**
   ```yaml
   task_name:
     type: task_type
     condition: "${prev_task.output.count} > 10"
     config:
       param1: value1
   ```

2. **Dictionary-based Conditions**
   ```yaml
   task_name:
     type: task_type
     condition:
       operator: gt
       value: 10
       path: prev_task.output.count
     config:
       param1: value1
   ```

#### Supported Operators
- `eq`: Equal to
- `ne`: Not equal to
- `gt`: Greater than
- `lt`: Less than
- `gte`: Greater than or equal to
- `lte`: Less than or equal to
- `in`: Value is in list
- `not_in`: Value is not in list

#### Example
```yaml
tasks:
  process_data:
    type: data_processor
    config:
      input: ${read_file.content}

  analyze_if_large:
    type: analyzer
    condition:
      operator: gt
      value: 1000
      path: process_data.output.size
    dependencies:
      - process_data

  save_results:
    type: file_ops
    condition: "${analyze_if_large.success} == true"
    config:
      operation: write
      file_path: results.txt
      content: ${analyze_if_large.output}
    dependencies:
      - analyze_if_large
```