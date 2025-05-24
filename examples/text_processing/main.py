import asyncio
import logging
from omniTask.core.workflow import Workflow
from omniTask.core.registry import TaskRegistry
from omniTask.utils.logging import setup_task_logging

async def main():
    setup_task_logging(level=logging.INFO)
    
    registry = TaskRegistry()
    registry.load_tasks_from_directory("tasks")
    
    workflow = Workflow("text_processing_demo", registry)
    
    # Create a file with some text
    write_task = workflow.create_task(
        "file_ops",
        "create_file",
        {
            "operation": "write",
            "file_path": "demo.txt",
            "content": "Hello! This is a demo of OmniTask.\nIt shows how tasks can work together."
        }
    )
    
    # Read and process the file
    read_task = workflow.create_task(
        "file_ops",
        "read_file",
        {
            "operation": "read",
            "file_path": "demo.txt"
        }
    )
    
    # Count words and characters
    count_task = workflow.create_task(
        "count",
        "count_stats",
        {}
    )
    
    # Convert to uppercase
    uppercase_task = workflow.create_task(
        "uppercase",
        "make_uppercase",
        {}
    )
    
    # Save the uppercase version
    save_task = workflow.create_task(
        "file_ops",
        "save_uppercase",
        {
            "operation": "write",
            "file_path": "uppercase.txt"
        }
    )
    
    # Set up dependencies
    read_task.add_dependency("create_file")
    count_task.add_dependency("read_file")
    uppercase_task.add_dependency("read_file")
    save_task.add_dependency("make_uppercase")
    
    # Run workflow
    result = await workflow.run()
    
    print("\n=== Workflow Results ===\n")
    for task_name, task_result in result.items():
        print(f"Task: {task_name}")
        print(f"Status: {'Success' if task_result.success else 'Failed'}")
        if not task_result.success:
            print(f"Error: {task_result.error}")
        print(f"Output: {task_result.output}")
        print(f"Execution Time: {task_result.execution_time:.2f}s\n")

if __name__ == "__main__":
    asyncio.run(main())
