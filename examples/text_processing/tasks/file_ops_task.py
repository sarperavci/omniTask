from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from datetime import datetime

class FileOpsTask(Task):
    task_name = "file_ops"
    
    async def execute(self) -> TaskResult:
        try:
            operation = self.config.get("operation", "read")
            file_path = self.config.get("file_path")
            
            self.log_info(f"Starting file operation: {operation}", file_path=file_path)
            
            if not file_path:
                self.log_error("file_path is required")
                raise ValueError("file_path is required")
            
            if operation == "read":
                self.log_debug("Reading file contents")
                with open(file_path, 'r') as f:
                    content = f.read()
                result = {"content": content, "operation": "read"}
                self.log_info("File read successful", content_length=len(content))
                
            elif operation == "write":
                if self.task_dependencies:
                    self.log_debug("Getting content from previous task")
                    prev_output = self.get_output("prev")
                    content = prev_output.get("content", "")
                else:
                    content = self.config.get("content", "Hello from OmniTask!")
                    
                self.log_debug("Writing content to file", content_length=len(content))
                with open(file_path, 'w') as f:
                    f.write(content)
                result = {"content": content, "operation": "write"}
                self.log_info("File write successful")
                
            elif operation == "append":
                content = self.config.get("content", "Appended by OmniTask!")
                self.log_debug("Appending content to file", content_length=len(content))
                with open(file_path, 'a') as f:
                    f.write(f"\n{content}")
                result = {"content": content, "operation": "append"}
                self.log_info("File append successful")
            
            result["timestamp"] = datetime.now().isoformat()
            return TaskResult(success=True, output=result)
            
        except Exception as e:
            self.log_error(f"File operation failed: {str(e)}", error_type=type(e).__name__)
            return TaskResult(success=False, output={}, error=e) 