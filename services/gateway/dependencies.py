from fastapi.security import OAuth2PasswordBearer
from fastapi import status, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .database import _get_db
from .security import CryptContext
from .models import JWTPayload
from .db_models import User
from .utils import get_user_by_id
from typing import Annotated
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

auth_schema = OAuth2PasswordBearer(tokenUrl="/auth/login")
crypt_context = CryptContext()


async def get_current_user(token : Annotated[str, Depends(auth_schema)], db_session: AsyncSession = Depends(_get_db)) -> User:
    creds_exception = HTTPException(
        detail="Unable to validate credentials",
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate" : "Bearer"}
    )
    
    try:
        payload = crypt_context.verify_and_decode_access_token(token=token)

        if payload["is_expired"]:
            logger.critical(f"Error validating token {payload['error']}")
            raise HTTPException(
                detail="Token has expired. Please. log in again.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate" : "Bearer"}
            )
        if not payload["is_valid"]:
            raise creds_exception
        
        data : JWTPayload = payload["data"]
        
        user = await get_user_by_id(user_id= data.user_id, db_session=db_session)
        
        if not user:
            raise HTTPException(
                detail="User no longer exist.",
                status_code= status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            raise HTTPException(
                detail="Account is disabled.",
                status_code= status.HTTP_403_FORBIDDEN
            )
            
        return user
    
    except HTTPException:
        raise
    except Exception as err:
        logger.exception(f"Unknown error has occured {err}")
        raise HTTPException(
            detail="service unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )