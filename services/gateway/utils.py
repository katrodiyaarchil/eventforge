from common.models import RawTransactionV1, EventEnvelope, TransactionStatus, OutBoxStatus
from .db_models import Transaction, OutBox, User
from .models import KYCStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
import os

async def store_transaction(transaction: RawTransactionV1, db: AsyncSession):
    
    KAFKA_TOPIC_TRANSACTIONS_RAW = os.environ.get(
        "KAFKA_TOPIC_TRANSACTIONS_RAW", "transactions.raw")
    ## Create envelop model for transaction event
    outbox_event = EventEnvelope[RawTransactionV1](
        event_type="TransactionCreated",
        schema_version=1,
        producer="gateway_service",
        payload=transaction,
        event_time=transaction.created_at
    )
    
    ## Create Transaction record and outbox record in the database within a transaction
    db_transaction = Transaction(
        transaction_id=transaction.transaction_id,
        idempotency_key=transaction.idempotency_key,
        from_account_id=transaction.from_account_id,
        to_account_id=transaction.to_account_id,
        amount_cents=transaction.amount_cents,
        currency=transaction.currency,
        status=TransactionStatus.PENDING,
        created_at=transaction.created_at
    )
    
    db_outbox = OutBox(
        topic=KAFKA_TOPIC_TRANSACTIONS_RAW,
        payload=outbox_event.model_dump(mode="json"),
        status=OutBoxStatus.PENDING
    )
    
    # Begin database transaction

    async with db.begin():
        db.add(db_transaction)
        db.add(db_outbox)

    return {"message": "Transaction created successfully", "transaction_id": transaction.transaction_id}


async def create_user(email: str, first_name: str, last_name: str, password_hash: str, db_session: AsyncSession):
    """ Register new user. """

    db_user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        kyc_status=KYCStatus.PENDING,
        is_active=True,
        password_hash=password_hash
    )
    try:
        async with db_session.begin():
            db_session.add(db_user)
            await db_session.flush()
            await db_session.refresh(db_user)
    except IntegrityError as err:
        if "email" in str(err.orig):
            raise ValueError("Email Already registered")
        raise
    return db_user


async def get_user_by_email(email: str, db_session: AsyncSession) -> User | None:
    query = (
        select(User)
        .where(User.email == email)
    )

    response = await db_session.execute(query)
    user = response.scalar_one_or_none()

    return user
