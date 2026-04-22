import redis.asyncio as redis
from collections.abc import AsyncGenerator
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

redis_pool : redis.ConnectionPool | None = None

async def init_redis_pool() -> None:
    """ Initialize the global redis connection pool """
    global redis_pool
    
    REDIS_URL = os.environ.get("REDIS_URL", "redis://0.0.0.0:6379/0")
    
    try:
        redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
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
    """ Close redis connection pool and close all the connections """
    global redis_pool
    
    if redis_pool:
        await redis_pool.disconnect()
        

async def get_redis_client() -> redis.Redis:
    """ Yields redis client to be used by the processor process """
    global redis_pool
    
    if not redis_pool:
        raise RuntimeError("Initialize the redis connection pool first.")
    
    return redis.Redis(connection_pool=redis_pool)