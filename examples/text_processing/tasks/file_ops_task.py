from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from datetime import datetime

class FileOpsTask(Task):
    task_name = "file_ops"
    
    async def execute(self) -> TaskResult:
        try:
            operation = self.config.get("operation", "read")
            file_path = self.config.get("file_path")
            
            if not file_path:
                raise ValueError("file_path is required")
            
            if operation == "read":
                with open(file_path, 'r') as f:
                    content = f.read()
                result = {"content": content, "operation": "read"}
                
            elif operation == "write":
                if self.task_dependencies:
                    prev_output = self.get_output("prev")
                    content = prev_output.get("content", "")
                else:
                    content = self.config.get("content", "Hello from OmniTask!")
                    
                with open(file_path, 'w') as f:
                    f.write(content)
                result = {"content": content, "operation": "write"}
                
            elif operation == "append":
                content = self.config.get("content", "Appended by OmniTask!")
                with open(file_path, 'a') as f:
                    f.write(f"\n{content}")
                result = {"content": content, "operation": "append"}
            
            result["timestamp"] = datetime.now().isoformat()
            return TaskResult(success=True, output=result)
            
        except Exception as e:
            return TaskResult(success=False, output={}, error=e) 