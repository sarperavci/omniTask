# Redis Cache Example

This example demonstrates how to use Redis as a distributed cache for OmniTask workflows.

## Prerequisites

1. **Redis Server**: Make sure Redis is running on your system
   ```bash
   # Install Redis (Ubuntu/Debian)
   sudo apt-get install redis-server
   
   # Start Redis
   sudo systemctl start redis-server
   
   # Or run manually
   redis-server
   ```

2. **Python Redis Package**: Install the required Python package
   ```bash
   pip install redis
   ```

## Features Demonstrated

- **Distributed Caching**: Share cache across multiple workflow instances
- **TTL Support**: Automatic expiration of cache entries
- **Connection Pooling**: Efficient Redis connection management
- **Cache Statistics**: Monitor cache performance and Redis server stats
- **Cache Invalidation**: Clear cache manually or let entries expire

## Usage

### YAML Template Configuration

You can configure Redis cache directly in your YAML workflow templates:

```yaml
name: my_workflow

cache:
  type: redis
  host: localhost
  port: 6379
  db: 0
  password: your_password  # Optional
  default_ttl: 300  # 5 minutes in seconds
  key_prefix: "myapp:"
  max_connections: 10

tasks:
  my_task:
    type: my_task_type
    config:
      param1: value1
    cache_enabled: true
    cache_ttl: 600  # Override default TTL for this task
```

### Supported Cache Types

The template system supports three cache types:

1. **Redis Cache** (distributed):
   ```yaml
   cache:
     type: redis
     host: redis.example.com
     port: 6379
     db: 1
     password: secret
     default_ttl: 3600
     key_prefix: "prod:"
     max_connections: 20
   ```

2. **Memory Cache** (in-process):
   ```yaml
   cache:
     type: memory
     max_size: 1000
     default_ttl: 300
   ```

3. **File Cache** (persistent):
   ```yaml
   cache:
     type: file
     cache_dir: ".my_cache"
     default_ttl: 1800
   ```

### Basic Redis Cache Setup

```python
from omniTask import Workflow
from datetime import timedelta

workflow = Workflow("my_workflow")

# Enable Redis cache
workflow.enable_redis_cache(
    host="localhost",
    port=6379,
    db=0,
    password="your_password",  # Optional
    default_ttl=timedelta(minutes=5),
    key_prefix="myapp:",
    max_connections=10
)
```

### Advanced Configuration

```python
# Custom Redis configuration
workflow.enable_redis_cache(
    host="redis.example.com",
    port=6380,
    db=1,
    password="secret_password",
    default_ttl=timedelta(hours=1),
    key_prefix="production:",
    max_connections=20
)
```

### Cache Management

```python
# Get cache statistics
stats = await workflow.get_cache_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")

# Clear all cached results
await workflow.clear_cache()

# Clean up expired entries
removed_count = await workflow.cleanup_expired_cache()
print(f"Removed {removed_count} expired entries")
```

## Running the Examples

### Basic Redis Cache Example
```bash
cd examples/redis_cache_example
python redis_cache_example.py
```

### YAML Template Example
```bash
cd examples/redis_cache_example
python template_example.py
```

### Test Redis Cache
```bash
cd examples/redis_cache_example
python test_redis_cache.py
```

## Expected Output

```
=== Redis Cache Example ===

1. Setting up Redis cache...
✓ Redis cache enabled successfully

2. Registering tasks...

3. Creating tasks...

4. First execution (cache miss)...
First execution completed in 8.45 seconds
Results: ['process_data_1', 'process_data_2', 'calc_1', 'calc_2']

5. Second execution (cache hit)...
Second execution completed in 0.12 seconds
Results: ['process_data_1', 'process_data_2', 'calc_1', 'calc_2']

6. Performance improvement:
   First run:  8.45s
   Second run: 0.12s
   Speedup:    70.4x

7. Cache statistics:
   Cache type: redis
   Hit rate: 100.00%
   Hits: 4
   Misses: 0
   Puts: 4
   Redis connected clients: 1
   Redis memory usage: 1.23M

8. Testing cache invalidation...
Cache cleared
Third execution (after clear): 8.32 seconds

9. Testing with different TTL...
Executing task with 3-second TTL...
Waiting 4 seconds for cache to expire...
Execution after TTL expired: 2.15 seconds

=== Example completed ===
```

## Benefits of Redis Cache

1. **Distributed**: Share cache across multiple processes/machines
2. **Persistent**: Cache survives application restarts
3. **Scalable**: Handle large amounts of cached data
4. **Fast**: In-memory storage with optional persistence
5. **Flexible**: Configurable TTL, key prefixes, and connection pooling

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `"localhost"` | Redis server hostname |
| `port` | `6379` | Redis server port |
| `db` | `0` | Redis database number |
| `password` | `None` | Redis password (if required) |
| `default_ttl` | `None` | Default time-to-live for cache entries |
| `key_prefix` | `"omnitask:"` | Prefix for all cache keys |
| `max_connections` | `10` | Maximum connections in the pool |

## Error Handling

The Redis cache implementation includes robust error handling:

- **Connection Errors**: Gracefully handles Redis connection issues
- **Serialization Errors**: Handles pickle serialization failures
- **Missing Dependencies**: Clear error message if `redis` package is not installed

## Monitoring

Use Redis CLI to monitor cache usage:

```bash
# Connect to Redis
redis-cli

# Monitor all operations
MONITOR

# Check memory usage
INFO memory

# List all keys with prefix
KEYS omnitask:*
``` 