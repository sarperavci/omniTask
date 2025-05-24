import asyncio
import logging
from omniTask.core.template import WorkflowTemplate
from omniTask.core.registry import TaskRegistry

async def main():
    logging.basicConfig(level=logging.INFO)
    
    registry = TaskRegistry()
    registry.load_tasks_from_directory("tasks")
    
    template = WorkflowTemplate("workflow.yaml")
    workflow = template.create_workflow(registry)
    
    result = await workflow.run()
    
    print("\n=== Workflow Results ===\n")
    for task_name, task_result in result.items():
        print(f"Task: {task_name}")
        print(f"Status: {'Success' if task_result.success else 'Failed'}")
        if not task_result.success:
            print(f"Error: {task_result.error}")
        print(f"Output: {task_result.output}")
        if task_result.execution_time is not None:
            print(f"Execution Time: {task_result.execution_time:.2f}s")
        print()

if __name__ == "__main__":
    asyncio.run(main()) 