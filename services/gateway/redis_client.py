import redis.asyncio as redis
from collections.abc import AsyncGenerator
import os


redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_pool = redis.ConnectionPool.from_url(redis_url)
        
async def _get_redis_client()-> AsyncGenerator[redis.Redis, None]:
    async with redis.Redis.from_pool(_pool) as client:
        yield client
        
        
    
    