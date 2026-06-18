from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import JSONResponse
import uvicorn

from common.models import RawTransactionV1
from .database import _get_db
from .utils import store_transaction

from .redis_client import init_redis_pool, close_redis_pool, get_redis
from .rate_limiter import check_rate_limit
import redis.asyncio as redis
from sqlalchemy.exc import IntegrityError
from fastapi.encoders import jsonable_encoder

from .routers import accounts, auth

logger = logging.getLogger(__name__)


# Lifespan Manager to init and close the redis connection pool
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init the connection
    await init_redis_pool()
    yield

    # Close the pool
    await close_redis_pool()


app = FastAPI(lifespan=lifespan)

app.include_router(accounts.router)
app.include_router(auth.router)

@app.post("/transactions")
async def create_transaction(
    request: Request,
    transaction: RawTransactionV1,
    db=Depends(_get_db),
    redis_client: redis.Redis = Depends(get_redis)
):

    client_ip = request.client.host

    # Check the rate limit
    await check_rate_limit(redis_client=redis_client, identifier=client_ip)
    
    ## Check in the cache if the TX is already there
    cache_key =  f"idempotency:tx:{transaction.idempotency_key}"
    
    cache_lock_acquired = False

    try:
        # Acquire lock on redis for idempotancy key
        # If already locked by another instance nx will return False
        cache_lock_acquired = await redis_client.set(cache_key, "PENDING", nx=True, ex=60)

        # If lock is not succeed another instance is working on it
        if not cache_lock_acquired:
            # Another instance might be on it
            current_value = await redis_client.get(cache_key)

            if current_value == "PENDING":
                # Transaction is in progress
                return JSONResponse(
                    {"detail": "Transaction is currently being processed. Please wait."},
                    status_code=status.HTTP_409_CONFLICT
                )

            else:
                # Transaction is created and actual transaction_id is in current_value
                return JSONResponse(
                    {"transaction_id": current_value},
                    status_code=status.HTTP_202_ACCEPTED
                )

        # If lock is succeed we can create entry in DB
        response = await store_transaction(transaction, db)

        # Overwrite the cache with the actual transaction_id
        try:
            await redis_client.set(cache_key, str(transaction.transaction_id), ex=24*60*60)
        except redis.RedisError as cache_err:
            logger.error(
                f"Database updated successfully, but failed to update idempotancy cache for TX {transaction.transaction_id} : {cache_err}")

        return JSONResponse(jsonable_encoder(response), status_code=status.HTTP_201_CREATED)

    except IntegrityError as e:
        logger.critical(
            f"DB IntegrityError for {transaction.idempotency_key} : {e}")
        # Transaction already created!!! release the lock
        cache_lock_acquired = False
        # TODO: Add session into the cache again and return transaction ID from the database
        # await cache.set(cache_key, str(transaction.transaction_id), ex=24*60*60)
        return JSONResponse({"messsage": "transaction already created"}, status_code=status.HTTP_202_ACCEPTED)
    except Exception as e:
        logger.error(f"Unknown error occured : {e}")

        # Relese the lock and clear the redis so user can retry
        try:
            if cache_lock_acquired:
               await redis_client.delete(cache_key)
        except:
            pass
        return JSONResponse("Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=8000)
