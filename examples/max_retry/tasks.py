from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import logging
from pathlib import Path
import time

class FileReader(Task):
    task_name="file_reader"
    library_dependencies = set()

    async def execute(self):
        self.logger = logging.getLogger(f"task.{self.name}")
        self.logger.info(f"Starting File Read for {self.config.get('file_name')}")

        self.logger.info("Waiting for 3 seconds")
        time.sleep(3)

        file_name = self.config.get('file_name')
        if file_name is None:
            self.logger.error("File name not specified")
            return TaskResult(success=False, error="File name not specified", output=None)
        
        path = Path(file_name)
        if path.is_file() is False:
            self.logger.error("File not found")
            return TaskResult(success=False, error="File not found", output=None)

        with open(file_name, "r") as file:
            content = file.read()
            return TaskResult(
                success=True,
                output={
                    "content": content
                }
            )
        
        return TaskResult(success=False, error="Error while reading file", output=None)
