from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ENUM as SQLEnum
from sqlalchemy import String, func, DateTime
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any
from common.models import OutBoxStatus, TransactionStatus

class Base(DeclarativeBase):
    pass
class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id: Mapped[UUID] = mapped_column(primary_key=True, default= uuid4)
    idempotency_key: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    
    from_account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    to_account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus, create_type=False, name="transactionstatus"), nullable=False, default=TransactionStatus.PENDING)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OutBox(Base):
    __tablename__ = "outbox"
    
    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    topic: Mapped[str] = mapped_column(nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutBoxStatus] = mapped_column(
        SQLEnum(OutBoxStatus, create_type=False, name="outboxstatus"), nullable=False, default=OutBoxStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)