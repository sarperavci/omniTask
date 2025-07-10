#!/usr/bin/env python3

import asyncio
import time
from datetime import timedelta
from omniTask.core.workflow import Workflow
from omniTask.core.task import Task
from omniTask.models.task_result import TaskResult
from omniTask.cache import MemoryCache, FileCache

class SlowComputationTask(Task):
    """A task that simulates expensive computation."""
    task_name = "slow_computation"
    
    async def execute(self) -> TaskResult:
        # Simulate expensive computation
        computation_time = self.config.get('computation_time', 2.0)
        input_value = self.config.get('input_value', 10)
        
        self.log_info(f"Starting expensive computation with input {input_value}")
        await asyncio.sleep(computation_time)
        
        # Simulate some computation result
        result = input_value ** 2 + 42
        
        self.log_info(f"Computation completed: {input_value}^2 + 42 = {result}")
        return TaskResult(
            success=True,
            output={"result": result, "input": input_value}
        )

class DataProcessingTask(Task):
    """A task that processes data from dependencies."""
    task_name = "data_processing"
    
    async def execute(self) -> TaskResult:
        # Get data from dependencies
        computation_result = self.get_output("computation.result")
        
        # Simulate processing
        processing_time = self.config.get('processing_time', 1.0)
        await asyncio.sleep(processing_time)
        
        processed_result = computation_result * 2
        
        self.log_info(f"Processed {computation_result} -> {processed_result}")
        return TaskResult(
            success=True,
            output={"processed_result": processed_result}
        )

async def demonstrate_memory_cache():
    """Demonstrate memory caching with cache hits and misses."""
    print("=== Memory Cache Demo ===")
    
    # Create workflow with memory cache
    workflow = Workflow("memory_cache_demo")
    workflow.registry.register(SlowComputationTask)
    workflow.registry.register(DataProcessingTask)
    
    # Enable memory cache with 100 entries, 5 minute TTL
    workflow.enable_memory_cache(max_size=100, default_ttl=timedelta(minutes=5))
    
    # Create tasks with caching enabled
    computation_task = workflow.create_task(
        "slow_computation", 
        "computation", 
        {
            "input_value": 5,
            "computation_time": 2.0,
            "cache_enabled": True
        }
    )
    
    processing_task = workflow.create_task(
        "data_processing",
        "processing",
        {
            "processing_time": 1.0,
            "cache_enabled": True
        }
    )
    
    # Set up dependency
    processing_task.add_dependency("computation")
    
    print("First execution (cache miss):")
    start_time = time.time()
    results = await workflow.run()
    first_execution_time = time.time() - start_time
    
    print(f"Results: {results['computation'].output}")
    print(f"Execution time: {first_execution_time:.2f} seconds")
    
    # Show cache stats
    cache_stats = await workflow.get_cache_stats()
    print(f"Cache stats: {cache_stats}")
    
    print("\nSecond execution (cache hit):")
    start_time = time.time()
    results = await workflow.run()
    second_execution_time = time.time() - start_time
    
    print(f"Results: {results['computation'].output}")
    print(f"Execution time: {second_execution_time:.2f} seconds")
    print(f"Speedup: {first_execution_time / second_execution_time:.2f}x")
    
    # Show updated cache stats
    cache_stats = await workflow.get_cache_stats()
    print(f"Cache stats: {cache_stats}")

async def demonstrate_file_cache():
    """Demonstrate file-based caching with persistence."""
    print("\n=== File Cache Demo ===")
    
    # Create workflow with file cache
    workflow = Workflow("file_cache_demo")
    workflow.registry.register(SlowComputationTask)
    
    # Set up file cache with 1 hour TTL
    file_cache = FileCache(cache_dir=".cache_demo", default_ttl=timedelta(hours=1))
    workflow.set_cache(file_cache)
    workflow.set_cache_enabled(True)
    
    # Create task with different input
    computation_task = workflow.create_task(
        "slow_computation",
        "computation",
        {
            "input_value": 7,
            "computation_time": 1.5,
            "cache_enabled": True
        }
    )
    
    print("First execution (cache miss):")
    start_time = time.time()
    results = await workflow.run()
    first_execution_time = time.time() - start_time
    
    print(f"Results: {results['computation'].output}")
    print(f"Execution time: {first_execution_time:.2f} seconds")
    
    # Show cache stats
    cache_stats = await workflow.get_cache_stats()
    print(f"Cache stats: {cache_stats}")
    
    print("\nSecond execution (cache hit from file):")
    start_time = time.time()
    results = await workflow.run()
    second_execution_time = time.time() - start_time
    
    print(f"Results: {results['computation'].output}")
    print(f"Execution time: {second_execution_time:.2f} seconds")
    print(f"Speedup: {first_execution_time / second_execution_time:.2f}x")
    
    # Show updated cache stats
    cache_stats = await workflow.get_cache_stats()
    print(f"Cache stats: {cache_stats}")

async def demonstrate_cache_invalidation():
    """Demonstrate cache invalidation."""
    print("\n=== Cache Invalidation Demo ===")
    
    workflow = Workflow("cache_invalidation_demo")
    workflow.registry.register(SlowComputationTask)
    workflow.enable_memory_cache(max_size=50)
    
    # Create task
    computation_task = workflow.create_task(
        "slow_computation",
        "computation",
        {
            "input_value": 3,
            "computation_time": 1.0,
            "cache_enabled": True
        }
    )
    
    print("First execution (cache miss):")
    await workflow.run()
    
    print("Second execution (cache hit):")
    await workflow.run()
    
    # Invalidate cache for this task
    print("\nInvalidating cache...")
    invalidated = await computation_task.invalidate_cache()
    print(f"Cache invalidated: {invalidated}")
    
    print("Third execution (cache miss after invalidation):")
    start_time = time.time()
    await workflow.run()
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.2f} seconds")

async def demonstrate_cache_expiration():
    """Demonstrate cache expiration with short TTL."""
    print("\n=== Cache Expiration Demo ===")
    
    workflow = Workflow("cache_expiration_demo")
    workflow.registry.register(SlowComputationTask)
    
    # Set up cache with very short TTL (3 seconds)
    workflow.enable_memory_cache(max_size=50, default_ttl=timedelta(seconds=3))
    
    # Create task
    computation_task = workflow.create_task(
        "slow_computation",
        "computation",
        {
            "input_value": 8,
            "computation_time": 1.0,
            "cache_enabled": True
        }
    )
    
    print("First execution (cache miss):")
    await workflow.run()
    
    print("Second execution (cache hit):")
    await workflow.run()
    
    print("Waiting for cache to expire...")
    await asyncio.sleep(4)  # Wait for cache to expire
    
    print("Third execution (cache miss after expiration):")
    start_time = time.time()
    await workflow.run()
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.2f} seconds")

async def demonstrate_cache_with_different_configs():
    """Demonstrate how cache keys work with different configurations."""
    print("\n=== Cache Key Demo ===")
    
    workflow = Workflow("cache_key_demo")
    workflow.registry.register(SlowComputationTask)
    workflow.enable_memory_cache(max_size=100)
    
    # Create tasks with different configurations
    task1 = workflow.create_task(
        "slow_computation",
        "computation1",
        {
            "input_value": 5,
            "computation_time": 1.0,
            "cache_enabled": True
        }
    )
    
    task2 = workflow.create_task(
        "slow_computation",
        "computation2",
        {
            "input_value": 10,  # Different input
            "computation_time": 1.0,
            "cache_enabled": True
        }
    )
    
    task3 = workflow.create_task(
        "slow_computation",
        "computation3",
        {
            "input_value": 5,  # Same input as task1
            "computation_time": 1.0,
            "cache_enabled": True
        }
    )
    
    print("Task 1 cache key:", task1.get_cache_key())
    print("Task 2 cache key:", task2.get_cache_key())
    print("Task 3 cache key:", task3.get_cache_key())
    
    print(f"Task 1 and Task 2 have same cache key: {task1.get_cache_key() == task2.get_cache_key()}")
    print(f"Task 1 and Task 3 have same cache key: {task1.get_cache_key() == task3.get_cache_key()}")
    
    # Execute tasks
    print("\nExecuting tasks...")
    await task1.execute_with_timeout()
    await task2.execute_with_timeout()
    await task3.execute_with_timeout()  # Should be cache hit for task1's result
    
    cache_stats = await workflow.get_cache_stats()
    print(f"Final cache stats: {cache_stats}")

async def main():
    """Run all cache demonstrations."""
    print("🚀 OmniTask Caching System Demo")
    print("=" * 50)
    
    try:
        await demonstrate_memory_cache()
        await demonstrate_file_cache()
        await demonstrate_cache_invalidation()
        await demonstrate_cache_expiration()
        await demonstrate_cache_with_different_configs()
        
        print("\n✅ All caching demonstrations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 