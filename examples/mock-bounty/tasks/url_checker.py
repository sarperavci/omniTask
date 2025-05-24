from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import time
import random
import logging
import asyncio

class URLChecker(Task):
    task_name = "url_checker"
    library_dependencies = set()

    async def execute(self) -> TaskResult:
        self.logger = logging.getLogger(f"task.{self.name}")
        self.logger.info(f"Starting URL check for: {self.config.get('url')}")

        url = self.config.get("url")
        if not url:
            self.logger.error("URL not specified")
            return TaskResult(success=False, error="URL not specified")

        timeout = self.config.get("timeout", 5)
        self.logger.info(f"Checking URL with timeout: {timeout}s")
        
        await asyncio.sleep(0)
        status_code = random.choice([200, 200, 200, 301, 302, 404, 403, 500])
        is_live = status_code < 400
        response_time = random.uniform(0.1, 2.0)

        self.logger.info(f"URL check completed - Status: {status_code}, Live: {is_live}, Response Time: {response_time:.2f}s")

        return TaskResult(
            success=True,
            output={
                "url": url,
                "status_code": status_code,
                "is_live": is_live,
                "response_time": response_time
            }
        ) 