from common.models import RawTransactionV1, EventEnvelope, TransactionStatus, OutBoxStatus
from .db_models import Transaction, OutBox, User, Account, AccountMapping
from .models import KYCStatus, AccountAccessRole
from common.models import AccountType, AccountStatus, AccountCreatedV1
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from uuid import UUID
import os


KAFKA_TOPIC_ACCOUNTS_CREATED = os.environ.get(
    "KAFKA_TOPIC_ACCOUNTS_CREATED", "accounts.created")
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


async def get_user_by_id(user_id: str, db_session: AsyncSession) -> User | None:
    """ Finds user based on user_id """

    query = (
        select(User)
        .where(User.user_id == user_id)
    )

    response = await db_session.execute(query)
    user = response.scalar_one_or_none()

    return user


async def provision_account(user_id: UUID, account_type: AccountType, db_session: AsyncSession) -> str:

    async with db_session.begin():

        # Create and flush Account object to get Auto-generated account id
        account = Account(
            account_type=account_type,
            account_status=AccountStatus.ACTIVE
        )

        db_session.add(account)
        await db_session.flush()

        # Create AccountMapping entry
        mapping = AccountMapping(
            user_id=user_id,
            account_id=account.account_id,
            role=AccountAccessRole.OWNER
        )

        db_session.add(mapping)

        # Create TransactionOutbox entry to inform Ledger service
        # about newly created account

        account_create_payload = AccountCreatedV1(
            account_id=account.account_id,
            user_id=user_id,
            account_type=account.account_type,
            account_status=account.account_status
        )

        envelop = EventEnvelope[AccountCreatedV1](
            event_type="AccountCreated",
            schema_version=1,
            producer="gateway_service",
            payload=account_create_payload
        )

        # Create entry in Outbox table

        outbox = OutBox(
            topic=KAFKA_TOPIC_ACCOUNTS_CREATED,
            payload=envelop.model_dump(mode="json"),
            status=OutBoxStatus.PENDING,
        )

        db_session.add(outbox)

        return str(account.account_id)
