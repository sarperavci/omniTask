import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))

from omniTask.core.registry import TaskRegistry
from omniTask.core.template import WorkflowTemplate
from omniTask.utils.logging import setup_task_logging, TaskLogFormatter

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(TaskLogFormatter())
    logger.addHandler(console_handler)

async def main():
    setup_logging()
    logger = logging.getLogger("main")
    
    logger.info("Starting bug bounty workflow...")
    start_time = datetime.now()
    
    registry = TaskRegistry()
    registry.load_tasks_from_directory(os.path.join(os.path.dirname(__file__), "tasks"))
    logger.info("Loaded tasks from directory")

    template = WorkflowTemplate(os.path.join(os.path.dirname(__file__), "workflow.yaml"))
    workflow = template.create_workflow(registry)
    logger.info("Created workflow from template")

    results = await workflow.run()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info(f"\nWorkflow completed in {duration:.2f} seconds")
    logger.info("\nWorkflow Results:")
    logger.info("----------------")
    
    scanner_result = results["subdomain_scanner"]
    if scanner_result.success:
        logger.info(f"\nSubdomain Scanner found {scanner_result.output['total_found']} subdomains:")
        for subdomain in scanner_result.output["subdomains"]:
            logger.info(f"  - {subdomain['url']}")

    logger.info("\nURL Checker Results:")
    url_checker_result = results.get("url_checker")
    if url_checker_result and url_checker_result.success:
        url_results = url_checker_result.output["results"]
        live_count = sum(1 for r in url_results if r["is_live"])
        dead_count = sum(1 for r in url_results if not r["is_live"])
        
        logger.info(f"\nSummary: {live_count} live URLs, {dead_count} dead URLs")
        logger.info("\nDetailed Results:")
        
        for result in url_results:
            status = "✅ LIVE" if result["is_live"] else "❌ DEAD"
            logger.info(f"{status} {result['url']}")
            logger.info(f"  Status Code: {result['status_code']}")
            logger.info(f"  Response Time: {result['response_time']:.2f}s")

if __name__ == "__main__":
    asyncio.run(main()) 