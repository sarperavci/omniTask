import asyncio
import time
from datetime import timedelta
from omniTask import Workflow
from omniTask.cache import RedisCache

def slow_task(data):
    time.sleep(2)
    return {"processed_data": data, "timestamp": time.time()}

def expensive_calculation(numbers):
    time.sleep(1)
    return {"sum": sum(numbers), "count": len(numbers), "average": sum(numbers) / len(numbers)}

async def main():
    
    workflow = Workflow("redis_cache_demo")
    
    print("1. Setting up Redis cache...")
    try:
        workflow.enable_redis_cache(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            default_ttl=timedelta(minutes=5),
            key_prefix="demo:",
            max_connections=5
        )
        print("✓ Redis cache enabled successfully")
    except Exception as e:
        print(f"✗ Failed to enable Redis cache: {e}")
        print("Make sure Redis server is running and redis package is installed:")
        print("pip install redis")
        return
    
    print("\n2. Registering tasks...")
    workflow.register_function(slow_task, "slow_task")
    workflow.register_function(expensive_calculation, "expensive_calc")
    
    print("3. Creating tasks...")
    workflow.create_task("slow_task", "process_data_1", {"data": "important_data_1"})
    workflow.create_task("slow_task", "process_data_2", {"data": "important_data_2"})
    workflow.create_task("expensive_calc", "calc_1", {"numbers": [1, 2, 3, 4, 5]})
    workflow.create_task("expensive_calc", "calc_2", {"numbers": [10, 20, 30, 40, 50]})
    
    print("\n4. First execution (cache miss)...")
    start_time = time.time()
    results = await workflow.run()
    first_execution_time = time.time() - start_time
    
    print(f"First execution completed in {first_execution_time:.2f} seconds")
    print(f"Results: {list(results.keys())}")
    
    print("\n5. Second execution (cache hit)...")
    start_time = time.time()
    results = await workflow.run()
    second_execution_time = time.time() - start_time
    
    print(f"Second execution completed in {second_execution_time:.2f} seconds")
    print(f"Results: {list(results.keys())}")
    
    print(f"\n6. Performance improvement:")
    print(f"   First run:  {first_execution_time:.2f}s")
    print(f"   Second run: {second_execution_time:.2f}s")
    print(f"   Speedup:    {first_execution_time / second_execution_time:.1f}x")
    
    print("\n7. Cache statistics:")
    stats = await workflow.get_cache_stats()
    if stats:
        print(f"   Cache type: {stats.get('type', 'unknown')}")
        print(f"   Hit rate: {stats.get('hit_rate', 0):.2%}")
        print(f"   Hits: {stats.get('hits', 0)}")
        print(f"   Misses: {stats.get('misses', 0)}")
        print(f"   Puts: {stats.get('puts', 0)}")
        print(f"   Redis connected clients: {stats.get('redis_connected_clients', 0)}")
        print(f"   Redis memory usage: {stats.get('redis_used_memory', 'N/A')}")
    
    print("\n8. Testing cache invalidation...")
    await workflow.clear_cache()
    print("Cache cleared")
    
    start_time = time.time()
    results = await workflow.run()
    third_execution_time = time.time() - start_time
    
    print(f"Third execution (after clear): {third_execution_time:.2f} seconds")
    
    print("\n9. Testing with different TTL...")
    workflow.enable_redis_cache(
        host="localhost",
        port=6379,
        db=0,
        default_ttl=timedelta(seconds=3)
    )
    
    workflow.create_task("slow_task", "short_ttl_task", {"data": "short_lived_data"})
    
    print("Executing task with 3-second TTL...")
    await workflow.run()
    
    print("Waiting 4 seconds for cache to expire...")
    await asyncio.sleep(4)
    
    start_time = time.time()
    await workflow.run()
    expired_execution_time = time.time() - start_time
    
    print(f"Execution after TTL expired: {expired_execution_time:.2f} seconds")
    
    print("\n=== Example completed ===")

if __name__ == "__main__":
    asyncio.run(main()) 