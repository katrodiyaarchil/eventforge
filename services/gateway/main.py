from fastapi import FastAPI, Depends, status
from fastapi.responses import JSONResponse
import uvicorn
from common.models import RawTransactionV1
from .database import _get_db
from .utils import store_transaction
from .redis_client import _get_redis_client
import redis.asyncio as redis
from sqlalchemy.exc import IntegrityError

app = FastAPI()


@app.post("/transactions")
async def create_transaction(transaction: RawTransactionV1, db=Depends(_get_db), cache:redis.Redis=Depends(_get_redis_client)):
    # Got the valid transaction data, now we can process it and save to the database
    
    
    ## Check in the cache if the TX is already there
    cache_key =  f"idempotency:tx:{transaction.idempotency_key}"
    
    try:
        tx_id = await cache.get(cache_key)
        if tx_id:
            return JSONResponse({"transaction_id": tx_id.decode('utf-8')}, status_code=status.HTTP_202_ACCEPTED)
        else:
            response = await store_transaction(transaction, db)
            await cache.set(cache_key, str(transaction.transaction_id), ex=24*60*60)
    except IntegrityError as e:
        print(f"Transaction already createde")
        # TODO: Add session into the cache again and return transaction ID from the database
        # await cache.set(cache_key, str(transaction.transaction_id), ex=24*60*60)
        return JSONResponse({"messsage": "transaction already created"}, status_code=status.HTTP_202_ACCEPTED)
    except Exception as e:
        print(f"Error storing transaction: {e}")
        return JSONResponse("Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return JSONResponse(response, status_code=status.HTTP_201_CREATED)