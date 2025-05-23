from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from datetime import datetime
import asyncio

class TimeoutTask(Task):
    task_name = "timeout_test"
    default_timeout = 3.0
    
    async def execute(self) -> TaskResult:
        try:
            await asyncio.sleep(5.0)
            result = {
                "message": "This should not be reached due to timeout",
                "timestamp": datetime.now().isoformat()
            }
            return TaskResult(success=True, output=result)
            
        except Exception as e:
            return TaskResult(success=False, output={}, error=e) 