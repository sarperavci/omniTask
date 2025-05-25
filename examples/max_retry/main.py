import asyncio
import logging
from omniTask.core.template import WorkflowTemplate
from omniTask.core.registry import TaskRegistry
from omniTask.utils.logging import setup_task_logging

async def main():
    setup_task_logging(level=logging.INFO)

    registry = TaskRegistry()
    registry.load_tasks_from_source("tasks.py")
    
    template = WorkflowTemplate("workflow.yaml")
    workflow = template.create_workflow(registry)
    result = await workflow.run()

    print(result)


if __name__ == "__main__":
    asyncio.run(main())