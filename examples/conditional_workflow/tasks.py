import random
import ast
from typing import List, Dict, Any
from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
import os
from datetime import datetime
import re

def safe_literal_eval(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value
    return value

class DataGeneratorTask(Task):
    task_name = "data_generator"

    async def execute(self) -> TaskResult:
        min_value = self.get_config("min_value", 1)
        max_value = self.get_config("max_value", 100)
        count = self.get_config("count", 10)

        numbers = [random.randint(min_value, max_value) for _ in range(count)]
        return TaskResult(
            success=True,
            output={"numbers": numbers}
        )

class StatsCalculatorTask(Task):
    task_name = "stats_calculator"

    async def execute(self) -> TaskResult:
        input_data = self.get_config("input", [])
        if not input_data:
            return TaskResult(success=False, output={}, error=ValueError("No input numbers provided"))
        numbers = [int(n) for n in input_data]
        if not numbers:
            return TaskResult(success=False, output={}, error=ValueError("Empty input list"))
        return TaskResult(
            success=True,
            output={
                "count": len(numbers),
                "average": sum(numbers) / len(numbers),
                "max": max(numbers),
                "min": min(numbers),
                "numbers": numbers
            }
        )

class NumberProcessorTask(Task):
    task_name = "number_processor"

    async def execute(self) -> TaskResult:
        input_data = self.get_config("input", [])
        threshold = self.get_config("threshold", 50)
        if not input_data:
            return TaskResult(success=False, output={}, error=ValueError("No input numbers provided"))
        numbers = [int(n) for n in input_data]
        if not numbers:
            return TaskResult(success=False, output={}, error=ValueError("Empty input list"))
        processed = [n for n in numbers if n <= threshold]
        return TaskResult(
            success=True,
            output={
                "processed": processed,
                "count": len(processed),
                "threshold": threshold,
                "success": True,
                "numbers": numbers
            }
        )

class FileOperationsTask(Task):
    task_name = "file_ops"

    async def execute(self) -> TaskResult:
        operation = self.get_config("operation")
        file_path = self.get_config("file_path")
        content = self.get_config("content", "")
        self.log_info("csads"+content)

        if not operation or not file_path:
            return TaskResult(
                success=False,
                output={},
                error=ValueError("Operation and file_path are required")
            )

        try:
            if operation == "write":
                if not content:
                    return TaskResult(
                        success=False,
                        output={},
                        error=ValueError("Content is required for write operation")
                    )

                resolved_content = self._resolve_content(content)
                with open(file_path, "w") as f:
                    f.write(resolved_content)

                return TaskResult(
                    success=True,
                    output={
                        "content": resolved_content,
                        "operation": operation,
                        "file_path": file_path,
                        "timestamp": datetime.now().isoformat()
                    }
                )

            elif operation == "read":
                if not os.path.exists(file_path):
                    return TaskResult(
                        success=False,
                        output={},
                        error=FileNotFoundError(f"File not found: {file_path}")
                    )

                with open(file_path, "r") as f:
                    content = f.read()

                return TaskResult(
                    success=True,
                    output={
                        "content": content,
                        "operation": operation,
                        "file_path": file_path,
                        "timestamp": datetime.now().isoformat()
                    }
                )

            else:
                return TaskResult(
                    success=False,
                    output={},
                    error=ValueError(f"Unsupported operation: {operation}")
                )

        except Exception as e:
            return TaskResult(
                success=False,
                output={},
                error=e
            )

    def _resolve_content(self, content: str) -> str:
        if not isinstance(content, str):
            return str(content)

        # Handle conditional expressions: ${a > 50 ? 'X' : 'Y'}
        def conditional_replacer(match):
            expr, true_val, false_val = match.group(1), match.group(2), match.group(3)
            try:
                expr_eval = expr
                for task_name, output in self.dependency_outputs.items():
                    for key, value in output.items():
                        expr_eval = expr_eval.replace(f"{task_name}.{key}", str(value))
                return true_val if eval(expr_eval) else false_val
            except Exception:
                return match.group(0)
        content = re.sub(r"\$\{([^\?\}]+)\s*\?\s*'([^']*)'\s*:\s*'([^']*)'\}", conditional_replacer, content)

        # Handle formatting: ${task.key:.2f}
        def format_replacer(match):
            expr, fmt = match.group(1), match.group(2)
            try:
                task_name, key = expr.split('.')
                value = self.dependency_outputs[task_name][key]
                if isinstance(value, (int, float)):
                    return f"{value:{fmt}}"
                return str(value)
            except Exception:
                return match.group(0)
        content = re.sub(r"\$\{([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+):([^\}]+)\}", format_replacer, content)

        # Handle simple placeholders: ${task.key}
        for task_name, output in self.dependency_outputs.items():
            for key, value in output.items():
                if isinstance(value, (list, tuple)):
                    value = str(value)
                placeholder = f"${{{task_name}.{key}}}"
                content = content.replace(placeholder, str(value))

        content = content.replace('\\n', '\n')
        return content 