import time
import logging
import redis.asyncio as redis
from fastapi.exceptions import HTTPException
from fastapi import status
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def check_rate_limit(
    redis_client: redis.Redis,
    identifier: str,
    limit: int = 10,
    window: int = 60
) -> None:
    """ 
    Check the requests made in most recent window(seconds) 
    Uses redis pipeline with transaction to prevent race condition
    """
    
    # Calculate the timings
    current_time_ms = int(time.time() * 1000)
    window_start_time = current_time_ms - (window * 1000)
    
    # will be used as key in Set for atomic uniqueness
    current_time_ns = time.time_ns()
    
    redis_key = f"rate_limit:{identifier}"
    
    try:
        
        # Create the redis pipeline with transactions
        
        async with redis_client.pipeline(transaction=True) as pipe:
            
            
            # step 1 : remove the old requests
            pipe.zremrangebyscore(redis_key, 0, window_start_time)
            
            # step 2 : Count the cardinilaty of the set ( How many request are there in current window)
            pipe.zcard(redis_key)
            
            # step 3 : Create the entry in set for the current request
            pipe.zadd(name=redis_key, mapping={str(current_time_ns) : current_time_ms}) 
            
            # step 4 : set TTL for above key as widow size, to prevent OOM
            pipe.expire(redis_key, window)
            
            # step 4 : execute the pipeline and check the zcard to see if it's above limit or not
            _, requests, _, _ =  await pipe.execute()
            
    except redis.RedisError as err:
        logger.error(f"Error while executing redis pipeline : {err}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    except Exception as err:
        logger.error(f"Unknown exception occured : {err}")
        raise
    
    # Check if the limit is already reached or not
    if requests >= limit:
        logger.warning(f"Rate limnit reached : {identifier}")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, 
            detail= "Too Many Requests",
            headers={"Retry-After" : str(window)}
            )
