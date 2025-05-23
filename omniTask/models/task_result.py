from dataclasses import dataclass
from typing import Any, Optional, Dict

@dataclass
class TaskResult:
    success: bool
    output: Dict[str, Any]
    error: Optional[Exception] = None
    execution_time: Optional[float] = None 