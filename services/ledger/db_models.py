from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ENUM as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, DateTime
from common.models import LedgerDirection, TransactionStatus, EventEnvelope, OutBoxStatus
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any
class Base(DeclarativeBase):
    pass

class Account(Base):
    __tablename__= "accounts"
    account_id : Mapped[UUID] = mapped_column(primary_key=True)
    balance_cents : Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    __table_args__ = (
        CheckConstraint("balance_cents >= 0 OR account_id='00000000-0000-0000-0000-000000000000'",
                        name='chk_accounts_balance_positive_or_masater'),
    )
    

class LedgerTransaction(Base):
    __tablename__= "ledger_transactions"
    transaction_id: Mapped[UUID] = mapped_column(primary_key=True)
    # is_posted : Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus), nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id : Mapped[UUID] = mapped_column(ForeignKey('ledger_transactions.transaction_id'), nullable=False, index=True)
    account_id : Mapped[UUID] = mapped_column(ForeignKey('accounts.account_id'), index=True, nullable=False)
    direction : Mapped[LedgerDirection] = mapped_column(SQLEnum(LedgerDirection), nullable=False)
    amount_cents : Mapped[int] = mapped_column(nullable=False)


""" Transactional outbox to stream updates on the transactions """
class OutBox(Base):
    __tablename__ = "outbox"
    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status : Mapped[OutBoxStatus] = mapped_column(SQLEnum(OutBoxStatus, create_type=True, name="outboxstatus"), nullable=False, default=OutBoxStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    payload : Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    topic: Mapped[str] = mapped_column(nullable=False, index=True)