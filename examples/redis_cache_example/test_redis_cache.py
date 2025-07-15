import asyncio
import time
from datetime import timedelta
from omniTask import Workflow, RedisCache

def simple_task(data):
    time.sleep(0.1)
    return {"input": data, "timestamp": time.time()}

async def test_redis_cache():
    print("Testing Redis Cache Implementation...")
    
    workflow = Workflow("test_workflow")
    
    try:
        workflow.enable_redis_cache(
            host="localhost",
            port=6379,
            default_ttl=timedelta(seconds=10)
        )
        print("✓ Redis cache enabled")
    except Exception as e:
        print(f"✗ Failed to enable Redis cache: {e}")
        return False
    
    workflow.register_function(simple_task, "simple_task")
    workflow.create_task("simple_task", "test_task", {"data": "test_data"})
    
    print("Running workflow first time (cache miss)...")
    start_time = time.time()
    results1 = await workflow.run()
    first_time = time.time() - start_time
    
    print("Running workflow second time (cache hit)...")
    start_time = time.time()
    results2 = await workflow.run()
    second_time = time.time() - start_time
    
    print(f"First run: {first_time:.3f}s")
    print(f"Second run: {second_time:.3f}s")
    print(f"Speedup: {first_time / second_time:.1f}x")
    
    if second_time < first_time * 0.5:
        print("✓ Cache is working (second run was significantly faster)")
    else:
        print("✗ Cache may not be working properly")
        return False
    
    stats = await workflow.get_cache_stats()
    print(f"Cache stats: {stats}")
    
    await workflow.clear_cache()
    print("✓ Cache cleared successfully")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_redis_cache())
    if success:
        print("\n🎉 Redis cache test passed!")
    else:
        print("\n❌ Redis cache test failed!")
        print("Make sure Redis server is running: redis-server") 