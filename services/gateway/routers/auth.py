import redis.asyncio as redis
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from ..schema import UserRegisterRequest, UserLoginRequest, TokenResponse, JWTPayload
from ..database import _get_db
from ..utils import create_user, get_user_by_email
from sqlalchemy.ext.asyncio import AsyncSession
from ..rate_limiter import check_rate_limit
from ..redis_client import get_redis
from ..security import CryptContext
from datetime import timedelta
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

crypt_context = CryptContext()

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register_user(
    request: Request,
    user_data: UserRegisterRequest,
    db_session: AsyncSession = Depends(_get_db),
    redis_client: redis.Redis = Depends(get_redis)
    ):
    
    client_ip = request.client.host

    await check_rate_limit(redis_client=redis_client, identifier=client_ip)
    
    password_hash = await run_in_threadpool(
        crypt_context.get_password_hash, 
        user_data.password.get_secret_value()
        )
    
    try:
        user = await create_user(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            password_hash=password_hash,
            db_session=db_session
        )
        response = {
            "success" : True,
            "message" : "User registered successfully",
            "user_id" : str(user.user_id)
        }
        return JSONResponse(response, status_code=status.HTTP_201_CREATED)
    
    except ValueError as err:
        logger.critical(f"Email Already registered {user_data.email} : \t{err}")
        raise HTTPException(
            detail="Email already registered",
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as err:
        logger.exception(f"Unknown exception occured : \t{err}")
        raise HTTPException(
            detail="Service Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request, 
    creds: UserLoginRequest,
    db_session = Depends(_get_db),
    redis_client: redis.Redis = Depends(get_redis),
    ):
    
    client_ip = request.client.host
    
    await check_rate_limit(redis_client=redis_client, identifier=client_ip)
    try:
        user = await get_user_by_email(email=creds.email, db_session=db_session)
        
        if not user:
            raise HTTPException(detail="Invalid email or password", status_code=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            raise HTTPException(detail="Account is disabled", status_code=status.HTTP_403_FORBIDDEN)
        ## Verify password
        is_authorized = await run_in_threadpool(
            crypt_context.verify_password,
            password = creds.password.get_secret_value(),
            hashed_password = user.password_hash
        )
        
        if not is_authorized:
            raise HTTPException(detail="Invalid email or password", status_code=status.HTTP_401_UNAUTHORIZED)
        
        # Generate token and retuen it to the user
        data = JWTPayload(
            user_id=str(user.user_id),
            email=user.email
        )
        access_token = crypt_context.create_access_token(data=data, expire_delta=timedelta(minutes=3))
        
        return TokenResponse(
            access_token=access_token
        )
        
    except Exception as err:
        logger.error(f"Unknown error occured : \t{err}")
        raise HTTPException(detail="Service Unavailable", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)