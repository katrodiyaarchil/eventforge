from fastapi import APIRouter, status, Request, Depends
from fastapi.exceptions import HTTPException
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from common.models import AccountStatus
from ..dependencies import get_current_user
from ..database import _get_db
from ..redis_client import get_redis
from ..rate_limiter import check_rate_limit
from ..utils import provision_account
from ..schema import AccountCreateRequest, AccountResponse
from ..db_models import User
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts")


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: Request,
    account_request: AccountCreateRequest,
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
    db_session: AsyncSession = Depends(_get_db)
):
    """Provisions a new checking or savings account for the authenticated user """

    # check rate limit
    
    client_ip = request.client.host
    
    await check_rate_limit(redis_client=redis_client, identifier=client_ip)
    
    try:
        account_id = await provision_account(
            user_id= current_user.user_id,
            account_type= account_request.account_type,
            db_session=db_session
        )
        
        return AccountResponse(
            account_id= account_id,
            account_type=account_request.account_type,
            account_status=AccountStatus.ACTIVE
        )
    except Exception as err:
        logger.critical(f"Error while provisionning account for user : {current_user.user_id} \n error : {err}")
        raise HTTPException(
            status_code= status.HTTP_503_SERVICE_UNAVAILABLE,
            detail= "Service Unavailable"
        )