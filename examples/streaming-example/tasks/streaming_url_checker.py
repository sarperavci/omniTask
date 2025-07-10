from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import time
import random
import logging
import asyncio
from datetime import datetime

class StreamingURLChecker(Task):
    task_name = "streaming_url_checker"
    library_dependencies = set()

    async def execute(self) -> TaskResult:
        self.logger = logging.getLogger(f"task.{self.name}")
        
        url = self.config.get("url")
        if not url:
            self.logger.error("URL not specified")
            return TaskResult(success=False, error="URL not specified")

        timeout = self.config.get("timeout", 5)
        start_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.logger.info(f"🌐 [{start_time}] Starting URL check: {url} (timeout: {timeout}s)")
        
        # Simulate URL checking
        await asyncio.sleep(random.uniform(0.1, 1.0))
        status_code = random.choice([200, 200, 200, 301, 302, 404, 403, 500])
        is_live = status_code < 400
        response_time = random.uniform(0.1, 2.0)
        
        end_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        status_emoji = "✅" if is_live else "❌"
        self.logger.info(f"{status_emoji} [{end_time}] URL check completed: {url} - Status: {status_code}, Response Time: {response_time:.2f}s")

        return TaskResult(
            success=True,
            output={
                "url": url,
                "status_code": status_code,
                "is_live": is_live,
                "response_time": response_time,
                "checked_at": time.time(),
                "start_time": start_time,
                "end_time": end_time
            }
        ) 