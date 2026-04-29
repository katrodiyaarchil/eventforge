from enum import Enum
from pydantic import BaseModel
class KYCStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class AccountType(str, Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"

class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"

class AccountAccessRole(str, Enum):
    OWNER = "OWNER"
    JOINT_OWNER = "JOINT_OWNER"
    AUTHORIZED_USER = "AUTHORIZED_USER"
    POA = "POWER_OF_ATTORNEY"
    POD = "PAYABLE_ON_DEATH"
    ADMINISTRATOR = "VIEW_ONLY"