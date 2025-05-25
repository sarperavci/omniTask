import asyncio
import logging
import os
from pathlib import Path

from omniTask.core.registry import TaskRegistry
from omniTask.core.template import WorkflowTemplate
from omniTask.utils.logging import setup_task_logging
from tasks import DataGeneratorTask, StatsCalculatorTask, NumberProcessorTask, FileOperationsTask

async def main():
    setup_task_logging(logging.INFO)
    logger = logging.getLogger("main")

    registry = TaskRegistry()
    registry.register(DataGeneratorTask)
    registry.register(StatsCalculatorTask)
    registry.register(NumberProcessorTask)
    registry.register(FileOperationsTask)
    

    template = WorkflowTemplate("workflow.yaml")
    workflow = template.create_workflow(registry)

    logger.info("Starting conditional workflow")
    try:
        results = await workflow.run()

        for task_name, result in results.items():
            if result.execution_time is not None:
                status = "Success" if result.success else "Failed"
                logger.info(f"Task {task_name}: {status}")
                logger.info(f"Execution time: {result.execution_time:.3f}s")
                
                if result.success:
                    if "skipped" in result.output and result.output["skipped"]:
                        logger.info(f"Task skipped: {result.output.get('reason', 'Unknown reason')}")
                    else:
                        logger.info(f"Output: {result.output}")
                else:
                    logger.error(f"Error: {result.error}")

        output_files = ["large_numbers.txt", "small_numbers.txt", "summary.txt"]
        logger.info("\nGenerated files:")
        for file in output_files:
            if os.path.exists(file):
                with open(file, 'r') as f:
                    content = f.read()
                    logger.info(f"- {file}:\n{content}")
            else:
                logger.info(f"- {file} (not generated)")

    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 