import redis.asyncio as redis
from uuid import UUID
import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def extract_total_tx_value(velocity_txs: list[str]) -> int:
    """ Parse transaction_id:amount format redis keys and extract total amount """
    
    func = lambda x: x.split(":")[-1]
    if velocity_txs:
        total_amount = sum([int(func(tx)) for tx in velocity_txs])
        return total_amount
    return 0

async def check_and_update_velocity(
    redis_client : redis.Redis,
    from_account_id : UUID,
    transaction_id : UUID,
    amount_cents : int,
    window : int = 300
) -> int:
    """ 
    Check total sum of the transactions done in last window(seconds) and,
    Update new incoming transaction to the redis and return the score based 
    on condition.
    """
    
    redis_key = f"velocity:{from_account_id}"
    current_time = time.time_ns()
    window_start_time = current_time - (window * 10**9)
    
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            
            # Remove the old tx 
            pipe.zremrangebyscore(redis_key, 0, window_start_time)
            
            # Add the current transaction
            pipe.zadd(redis_key, {f"{transaction_id}:{amount_cents}" : current_time})

            # Fetch all remaining transactions ( always last windows(seconds))
            pipe.zrange(redis_key, 0, -1)
            
            # Set expiry of windows seconds
            pipe.expire(redis_key, window)
            
            _,_, all_tx,_ = await pipe.execute()
    except redis.RedisError as err:
        logger.error(f"Error while executing redis pipeline : {err}")
        raise

    except Exception as err:
        logger.error(f"Unknown exception occured : {err}")
        raise
    
    return extract_total_tx_value(all_tx)


async def rollback_velocity(
    redis_client: redis.Redis,
    from_account_id: UUID,
    transaction_id: UUID,
    amount_cents: int
) -> None:
    """ Rollback transaction that are rejected by the ledger service to free-up the user limit """
    
    redis_key = f"velocity:{from_account_id}"
    member = f"{transaction_id}:{amount_cents}"
    
    try:
        await redis_client.zrem(redis_key, member)
        
    except redis.RedisError as err:
        logger.error(f"Error rolling back transaction {from_account_id} : {transaction_id} : {err}")
        raise

    except Exception as err:
        logger.error(f"Unknown exception occured : {err}")
        raise
