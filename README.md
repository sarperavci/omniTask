# OmniTask

A powerful, pure Python workflow automation engine designed for simplicity and scalability.

## Overview

OmniTask is a modern workflow automation engine that allows you to build complex data processing pipelines with ease. It provides a clean API for defining tasks, managing dependencies, and executing workflows with features like streaming, caching, and parallel execution.

## Key Features

- **Pure Python**: Built entirely in Python with no external dependencies beyond PyYAML
- **Async/Await Support**: Full asynchronous execution for maximum performance
- **Streaming Tasks**: Real-time data processing with streaming capabilities
- **Intelligent Caching**: Memory and file-based caching for optimized performance
- **Dependency Management**: Automatic dependency resolution and execution ordering
- **Task Groups**: Parallel execution with configurable concurrency limits
- **Conditional Execution**: Execute tasks based on conditions and previous results
- **Progress Tracking**: Built-in progress monitoring and callbacks
- **Error Handling**: Comprehensive error handling with retry mechanisms
- **Workflow Validation**: Static analysis and validation of workflow definitions
- **YAML Configuration**: Define workflows using simple YAML files

## Installation

```bash
pip install omniTask
```

## Quick Start

### Creating a Simple Workflow

```python
from omniTask import Workflow, Task, TaskResult

class DataProcessorTask(Task):
    task_name = "data_processor"
    
    async def execute(self):
        data = self.config.get('data', [])
        result = sum(data)
        return TaskResult(success=True, output={"sum": result})

async def main():
    # Create workflow
    workflow = Workflow("example")
    workflow.registry.register(DataProcessorTask)

    # Add task
    task = workflow.create_task("data_processor", "process", {"data": [1, 2, 3, 4, 5]})

    # Execute
    results = await workflow.run()
    print(results["process"].output)  # {"sum": 15}

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Using YAML Configuration

```yaml
name: data_pipeline
tasks:
  load_data:
    type: file_reader
    config:
      file_path: "data.csv"
  
  process_data:
    type: data_processor
    config:
      operation: "aggregate"
  
  save_results:
    type: file_writer
    config:
      file_path: "results.json"

dependencies:
  process_data:
    - load_data
  save_results:
    - process_data
```

```python
from omniTask import WorkflowTemplate

template = WorkflowTemplate("workflow.yaml")
workflow = template.create_workflow()
results = await workflow.run()
```

## Why OmniTask?

### Simple Yet Powerful
- **Minimal Learning Curve**: Start with basic tasks and grow into complex workflows
- **Intuitive API**: Clean, Pythonic interface that feels natural
- **Flexible Configuration**: Support for both code and YAML-based workflow definitions

### Built for Scale
- **Async-First Design**: Handle thousands of concurrent tasks efficiently
- **Smart Caching**: Avoid redundant computations with intelligent caching
- **Streaming Support**: Process data in real-time as it becomes available

### Production Ready
- **Comprehensive Testing**: Extensive test coverage and validation
- **Error Resilience**: Built-in retry mechanisms and error handling
- **Monitoring**: Progress tracking and detailed logging
- **Validation**: Static analysis of workflow definitions

## Architecture

OmniTask follows a clean, modular architecture:

- **Core Engine**: Task execution, dependency resolution, and workflow management
- **Task System**: Extensible task framework with streaming support
- **Caching Layer**: Pluggable caching system for performance optimization
- **Validation System**: Static analysis and runtime validation
- **Utility Layer**: Logging, path parsing, and helper functions

## Documentation

For comprehensive documentation, visit our [documentation site](docs/):

- **[User Guide](https://sarpers-organization.gitbook.io/omnitask/user-guide/)** - Learn how to use OmniTask
- **[API Reference](https://sarpers-organization.gitbook.io/omnitask/api-reference/)** - Complete API documentation
- **[Architecture Guide](https://sarpers-organization.gitbook.io/omnitask/architecture/)** - Deep dive into system architecture
- **[Examples](https://sarpers-organization.gitbook.io/omnitask/examples/)** - Real-world examples and use cases
- **[Developer Guide](https://sarpers-organization.gitbook.io/omnitask)** - Advanced features and customization

## Examples

Explore our comprehensive examples:

- **[Basic Workflows](examples/text_processing/)** - Simple task chaining
- **[Streaming Processing](examples/streaming-example/)** - Real-time data processing
- **[Conditional Logic](examples/conditional_workflow/)** - Decision-based execution
- **[Caching Demo](examples/caching_example/)** - Performance optimization
- **[Parallel Processing](examples/mock-bounty/)** - Concurrent task execution

## License

OmniTask is released under the MIT License. See [LICENSE](LICENSE) for details.

## Support

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/sarperavci/omniTask/issues)
- **Documentation**: Full documentation at [https://sarpers-organization.gitbook.io/omnitask](https://sarpers-organization.gitbook.io/omnitask)
- **Examples**: Working examples in the [examples/](examples/) directory