from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ENUM as SQLEnum
from sqlalchemy import func
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey
from common.models import LedgerDirection, TransactionStatus
from uuid import UUID
from datetime import datetime
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
    created_at : Mapped[datetime] = mapped_column(server_default=func.now())
    
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id : Mapped[UUID] = mapped_column(ForeignKey('ledger_transactions.transaction_id'), nullable=False, index=True)
    account_id : Mapped[UUID] = mapped_column(ForeignKey('accounts.account_id'), index=True, nullable=False)
    direction : Mapped[LedgerDirection] = mapped_column(SQLEnum(LedgerDirection), nullable=False)
    amount_cents : Mapped[int] = mapped_column(nullable=False)