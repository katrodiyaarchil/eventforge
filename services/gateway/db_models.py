from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ENUM as SQLEnum
from sqlalchemy import String, func, DateTime, Boolean, ForeignKey
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any
from common.models import OutBoxStatus, TransactionStatus, AccountStatus, AccountType
from .models import KYCStatus, AccountAccessRole

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
    
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True)
    kyc_status: Mapped[KYCStatus] = mapped_column(
        SQLEnum(KYCStatus, create_type=True, name="kycstatus"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now())


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_type: Mapped[AccountType] = mapped_column(
        SQLEnum(AccountType, create_type=True, name="accounttype"), nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(AccountStatus, create_type=True, name="accountstatus"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountMapping(Base):
    __tablename__ = "account_mappings"

    mapping_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(User.user_id), nullable=False, index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey(
        Account.account_id), index=True, nullable=False)
    role: Mapped[AccountAccessRole] = mapped_column(SQLEnum(
        AccountAccessRole, create_type=True, name="accountaccessrole"), nullable=False)
