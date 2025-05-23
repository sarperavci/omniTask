from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from datetime import datetime

class UppercaseTask(Task):
    task_name = "uppercase"
    
    async def execute(self) -> TaskResult:
        try:
            prev_output = self.get_output("prev")
            text = prev_output.get("content", "")
            
            processed_text = text.upper()
            result = {
                "content": processed_text,
                "processed_text": processed_text
            }
            
            result["timestamp"] = datetime.now().isoformat()
            return TaskResult(success=True, output=result)
            
        except Exception as e:
            return TaskResult(success=False, output={}, error=e) 