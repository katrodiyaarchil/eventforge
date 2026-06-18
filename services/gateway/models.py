from enum import Enum
from pydantic import BaseModel, EmailStr


class KYCStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccountAccessRole(str, Enum):
    OWNER = "OWNER"
    JOINT_OWNER = "JOINT_OWNER"
    AUTHORIZED_USER = "AUTHORIZED_USER"
    POA = "POWER_OF_ATTORNEY"
    POD = "PAYABLE_ON_DEATH"
    ADMINISTRATOR = "VIEW_ONLY"


class JWTPayload(BaseModel):
    user_id: str
    email: EmailStr
    exp: int | None = None
