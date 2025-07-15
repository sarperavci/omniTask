import asyncio
import time
from omniTask.core.template import WorkflowTemplate

async def main():
    print("=== Redis Cache with YAML Template Example ===\n")
    
    try:
        print("1. Loading workflow template...")
        template = WorkflowTemplate("redis_workflow.yaml")
        print("✓ Template loaded successfully")
        
        print("\n2. Creating workflow with Redis cache...")
        workflow = template.create_workflow()
        print("✓ Workflow created with Redis cache enabled")
        
        print("\n3. Workflow configuration:")
        print(f"   Name: {workflow.name}")
        print(f"   Tasks: {list(workflow.tasks.keys())}")
        print(f"   Task groups: {list(workflow.task_groups.keys())}")
        
        print("\n4. Cache configuration:")
        cache_stats = await workflow.get_cache_stats()
        if cache_stats:
            print(f"   Type: {cache_stats.get('type', 'unknown')}")
            print(f"   Host: {cache_stats.get('host', 'unknown')}")
            print(f"   Port: {cache_stats.get('port', 'unknown')}")
            print(f"   Key prefix: {cache_stats.get('key_prefix', 'unknown')}")
        
        print("\n5. Testing cache functionality...")
        print("   Note: This example shows template loading.")
        print("   To run actual tasks, you would need to implement the task types.")
        print("   (file_reader, data_processor, result_analyzer, report_generator)")
        
        print("\n6. Template cache configuration options:")
        print("   - type: redis/memory/file")
        print("   - host: Redis server hostname")
        print("   - port: Redis server port")
        print("   - db: Redis database number")
        print("   - password: Redis password (optional)")
        print("   - default_ttl: Default cache TTL in seconds")
        print("   - key_prefix: Cache key prefix")
        print("   - max_connections: Connection pool size")
        
        print("\n=== Example completed ===")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nMake sure:")
        print("1. Redis server is running")
        print("2. redis package is installed: pip install redis")
        print("3. redis_workflow.yaml file exists in the same directory")

if __name__ == "__main__":
    asyncio.run(main()) 