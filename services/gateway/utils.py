
from fastapi import Depends
from .database import _get_db
from common.models import RawTransactionV1, EventEnvelope
from .db_models import Transaction, OutBox
from sqlalchemy.ext.asyncio import AsyncSession

async def store_transaction(transaction: RawTransactionV1, db: AsyncSession):
    
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
        status="PENDING",
        created_at=transaction.created_at
    )
    
    db_outbox = OutBox(
        topic="transaction_events",
        payload=outbox_event.model_dump(mode="json"),
        status="PENDING"
    )
    
    # Begin database transaction
    try:
        async with db.begin():
            db.add(db_transaction)
            db.add(db_outbox)
    except Exception as e:
        raise e
    return {"message": "Transaction created successfully", "transaction_id": transaction.transaction_id}