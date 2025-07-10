from dataclasses import dataclass
from typing import Any, Optional, Dict, AsyncIterator, Callable
import asyncio

@dataclass
class TaskProgress:
    current: int = 0
    total: int = 100
    message: str = ""
    percentage: float = 0.0
    
    def __post_init__(self):
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100

@dataclass
class TaskResult:
    success: bool
    output: Dict[str, Any]
    error: Optional[Exception] = None
    execution_time: Optional[float] = None 
    retries: Optional[int] = None
    progress: Optional[TaskProgress] = None

@dataclass 
class StreamingTaskResult(TaskResult):
    stream_complete: bool = False
    is_streaming: bool = True

class StreamingYielder:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._complete = False
        self._listeners = []
        
    async def yield_result(self, data: Any) -> None:
        if self._complete:
            return
        
        stream_result = StreamingTaskResult(
            success=True,
            output=data,
            stream_complete=False
        )
        
        await self._queue.put(stream_result)
        
        for listener in self._listeners:
            asyncio.create_task(listener(stream_result))
    
    async def complete(self, final_result: TaskResult) -> None:
        if self._complete:
            return
            
        self._complete = True
        
        if isinstance(final_result, StreamingTaskResult):
            final_result.stream_complete = True
        else:
            final_result = StreamingTaskResult(
                success=final_result.success,
                output=final_result.output,
                error=final_result.error,
                execution_time=final_result.execution_time,
                retries=final_result.retries,
                stream_complete=True
            )
        
        await self._queue.put(final_result)
        
        for listener in self._listeners:
            asyncio.create_task(listener(final_result))
    
    def add_listener(self, listener: Callable[[StreamingTaskResult], None]) -> None:
        self._listeners.append(listener)
    
    async def __aiter__(self) -> AsyncIterator[StreamingTaskResult]:
        while True:
            result = await self._queue.get()
            yield result
            if result.stream_complete:
                break
    
    @property
    def is_complete(self) -> bool:
        return self._complete