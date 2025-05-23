from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from datetime import datetime

class CountTask(Task):
    task_name = "count"
    
    async def execute(self) -> TaskResult:
        try:
            prev_output = self.get_output("prev")
            text = prev_output.get("content", "")
            # or text = self.get_output("prev.content")
            
            result = {
                "word_count": len(text.split()),
                "char_count": len(text),
                "line_count": len(text.splitlines()),
                "content": text
            }
            
            result["timestamp"] = datetime.now().isoformat()
            return TaskResult(success=True, output=result)
            
        except Exception as e:
            return TaskResult(success=False, output={}, error=e) 