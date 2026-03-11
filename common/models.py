from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import IPvAnyAddress
from enum import Enum
from uuid import UUID, uuid4
from typing import Annotated, Generic, Literal, TypeVar
from datetime import datetime, timezone


""" Status of the transaction, can be one of the following:"""
class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"

""" Model for the transaction metadata, 
which will be stored in the database and used for processing the transaction. 
"""
class TransactionMetadata(BaseModel):
    ip_address: IPvAnyAddress
    device_id: Annotated[str, Field(min_length=1, max_length=128)]
    geo_location: Annotated[str | None, Field(max_length=64)]
    user_agent: Annotated[str | None, Field(max_length=512)]
    
    model_config = ConfigDict(extra="forbid")
    
    
"""
Main Transaction Model """

class RawTransactionV1(BaseModel):
    transaction_id: UUID = Field(default_factory=uuid4)
    idempotency_key: str = Field(..., min_length=10)
    version: Literal[1] = 1
    
    from_account_id: UUID
    to_account_id: UUID
    
    amount_cents: Annotated[int, Field(strict=True, gt=0)]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    
    metadata: TransactionMetadata
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(timezone.utc))]
    model_config = ConfigDict(extra="forbid", frozen=True)
    

T = TypeVar('T')
""" Define Envelops for kafka messages providing better debugging and monitoring capabilities. """
class EventEnvelope(BaseModel, Generic[T]):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(..., min_length=1, max_length=128)
    schema_version: int
    producer: str
    event_time: Annotated[datetime, Field(default_factory=lambda: datetime.now(timezone.utc))]
    payload: T
    
    model_config = ConfigDict(extra="forbid", frozen=True)