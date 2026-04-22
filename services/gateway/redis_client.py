import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
from collections.abc import AsyncGenerator
import os
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


redis_pool: redis.ConnectionPool | None = None


async def init_redis_pool() -> None:
    """ Initialize the global asynchronous Redis connection pool. """
    global redis_pool

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    try:
        redis_pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        logger.info("Redis connection pool initialized")
    except ValueError as err:
        logger.error(f"Invalid redis URL : {err}")
        raise
    except ConnectionError as err:
        logger.error(f"Error connecting to Redis server : {err}")
        raise
    except TimeoutError as err:
        logger.error(f"Connection timeout to server : {err}")
        raise
    except Exception as err:
        logger.error(f"Unknown error occured : {err}")
        raise

async def close_redis_pool() -> None:
    """ Gracefully close the Redis connection pool."""
    global redis_pool

    if redis_pool:
        await redis_pool.disconnect()


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """ FastAPI Dependency that yields a Redis client from the pool."""
    global redis_pool

    if not redis_pool:
        raise RuntimeError("Initialize the redis connection pool first.")

    # Create the client (Context Manager will close the connection automaticallly and return it to the pool)
    async with redis.Redis(connection_pool=redis_pool) as client:
        yield client
    