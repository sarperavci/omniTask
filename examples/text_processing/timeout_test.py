import asyncio
import logging
from omniTask.core.template import WorkflowTemplate
from omniTask.core.registry import TaskRegistry

async def main():
    logging.basicConfig(level=logging.INFO)
    
    registry = TaskRegistry()
    registry.load_tasks_from_directory("tasks")
    
    template = WorkflowTemplate("timeout_workflow.yaml")
    workflow = template.create_workflow(registry)
    
    result = await workflow.run()
    
    print("\n=== Workflow Results ===\n")
    for task_name, task_result in result.items():
        print(f"Task: {task_name}")
        print(f"Status: {task_result.error.__class__.__name__ if task_result.error else 'Success'}")
        if not task_result.success:
            print(f"Error: {task_result.error}")
        print(f"Output: {task_result.output}")
        print(f"Execution Time: {task_result.execution_time:.2f}s\n")

if __name__ == "__main__":
    asyncio.run(main()) 