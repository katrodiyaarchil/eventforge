from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import os
from .database import session_maker
from common.models import ScoredTransactionV1, EventEnvelope, LedgerDirection, TransactionStatus
from common.models import FraudDecision, TransactionSettledV1, OutBoxStatus
from .db_models import Account, LedgerTransaction, LedgerEntry, OutBox
import logging
from uuid import UUID
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

KAFKA_TOPIC_TRANSACTIONS_SETTLED = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_SETTLED", "transactions.settled")


async def post_transaction(transaction_id: UUID,  status: TransactionStatus, session: AsyncSession) -> None:
    """ Create a Ledger transaction entry and flush to check if a transaction is already processed or not """
    ledger_tx = LedgerTransaction(
        transaction_id=transaction_id,
        status=status
    )
    session.add(ledger_tx)
    # Flush the session to catch errors early
    await session.flush()


async def create_outbox_entry(
        transaction_id: UUID,
        final_status: TransactionStatus,
        reason: str | None,
        session: AsyncSession) -> None:
    """ Create an transactional  outbox entry to the database """

    # Payload for eventenvelop
    settled_tx = TransactionSettledV1(
        transaction_id=transaction_id,
        final_status=final_status,
        reason=reason
    )

    # Create an eventenvelop
    settled_tx_envelop = EventEnvelope[TransactionSettledV1](
        event_type="TransactionSettled",
        producer="Ledger_service",
        payload=settled_tx,
        schema_version=1
    )

    # Create outbox DB model
    db_outbox = OutBox(
        payload=settled_tx_envelop.model_dump(mode="json"),
        topic=KAFKA_TOPIC_TRANSACTIONS_SETTLED,
        status=OutBoxStatus.PENDING
    )

    session.add(db_outbox)

async def create_ledger(transaction : ScoredTransactionV1) -> None:
    from_account_id = transaction.from_account_id
    to_account_id = transaction.to_account_id
    transaction_id = transaction.transaction_id
    amount_cents = transaction.amount_cents

    # Local variables to track the status of current transaction
    final_status = TransactionStatus.COMPLETED
    failure_reason = None

    async with session_maker() as session:
        try:

            if transaction.decision == FraudDecision.REJECTED:
                # post transaction
                await post_transaction(
                    transaction_id=transaction_id,
                    status=TransactionStatus.REJECTED,
                    session=session
                )

                # Create outbox entry
                await create_outbox_entry(
                    transaction_id=transaction_id,
                    final_status=TransactionStatus.REJECTED,
                    reason="REJECTED_FRAUD",
                    session=session
                )

            elif transaction.decision == FraudDecision.FLAGGED:
                await post_transaction(
                    transaction_id=transaction_id,
                    status=TransactionStatus.BLOCKED,
                    session=session
                )

                # Create outbox entry
                await create_outbox_entry(
                    transaction_id=transaction_id,
                    final_status=TransactionStatus.BLOCKED,
                    reason="BLOCKED_SUSPICIOUS",
                    session=session
                )

            else:

                # Acquire lock on accounts
                sorted_account_ids = sorted([from_account_id, to_account_id])

                query = (
                    select(Account)
                    .where(Account.account_id.in_(sorted_account_ids))
                    .order_by(Account.account_id.asc())
                    .with_for_update()
                )
                result = await session.execute(query)
                accounts = result.scalars().all()

                if len(accounts) != 2:
                    logging.critical(f'''One or more account does not exist :  \n
                        from_account_id : {from_account_id}, to_account_id : {to_account_id}''')
                    final_status = TransactionStatus.REJECTED
                    failure_reason = "ACCOUNT_MISSING"

                else:
                    # extract sender and receiver objects
                    sender = next((account for account in accounts if account.account_id == from_account_id))
                    receiver = next(
                        (account for account in accounts if account.account_id == to_account_id))
                    
                    # Check and update the balance
                    if sender.balance_cents < amount_cents:
                        logging.critical(
                            f"Insufficient funds to complete the transaction : {transaction_id}")
                        final_status = TransactionStatus.REJECTED
                        failure_reason = "INSUFFICIENT_FUNDS"
                    
                    else:
                        sender.balance_cents -= amount_cents
                        receiver.balance_cents += amount_cents
                    
                if final_status == TransactionStatus.COMPLETED:

                    # post transaction
                    await post_transaction(
                        transaction_id=transaction_id,
                        status=TransactionStatus.COMPLETED,
                        session=session
                    )

                    # Create outbox entry
                    await create_outbox_entry(
                        transaction_id=transaction_id,
                        final_status=TransactionStatus.COMPLETED,
                        reason=None,
                        session=session
                    )

                    # Create Doubble entry ledger
                    debit_entry = LedgerEntry(
                        transaction_id=transaction_id,
                        account_id=from_account_id,
                        direction=LedgerDirection.DEBIT,
                        amount_cents=amount_cents
                    )
                    credit_entry = LedgerEntry(
                        transaction_id=transaction_id,
                        account_id=to_account_id,
                        direction=LedgerDirection.CREDIT,
                        amount_cents=amount_cents
                    )

                    session.add_all([debit_entry, credit_entry])

                else:
                    # Transaction failed for a reason

                    # post transaction
                    await post_transaction(
                        transaction_id=transaction_id,
                        status=final_status,
                        session=session
                    )

                    # Create outbox entry
                    await create_outbox_entry(
                        transaction_id=transaction_id,
                        final_status=final_status,
                        reason=failure_reason,
                        session=session
                    )


            # Commit the sessison
            await session.commit()

        except IntegrityError as e:
            logging.info(f"Transaction {transaction_id} will not be processed \nreason : {e}")
            await session.rollback()

        except Exception as e:
            await session.rollback()
            logging.error(e)
            raise Exception(e)

async def process_message(scored_tx_consumer: AIOKafkaConsumer):
    async for message in scored_tx_consumer:
        from_account_id = message.key
        payload = message.value

        # Verify incoming transaction details using Pydantic and extract scored transaction
        try:
            tx_envelop = EventEnvelope[ScoredTransactionV1].model_validate_json(
                payload.decode("utf-8"))
            scored_transaction = tx_envelop.payload

            # Process a message and create ledger using double-entry
            await create_ledger(scored_transaction)

            # Ack kafka for the message
            await scored_tx_consumer.commit()
        except ValidationError:
            logging.warning(
                f"Invalid Transaction data!!! skipping transaction \ndata : {payload.decode("utf-8")}")
            await scored_tx_consumer.commit()
        except Exception as e:
            logging.error(f"Unknown exception occured {e}")
            break

async def main():
    
    # Create a kafka consumer that consumes the scored transactions
    KAFKA_TOPIC_TRANSACTIONS_SCORED = os.environ.get("KAFKA_TOPIC_TRANSACTIONS_SCORED", "transactions.scored")
    KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
    
    scored_tx_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_SCORED,
        bootstrap_servers=KAFKA_URL,
        group_id="ledger_consumer_group",
        client_id="ledger_service",
        auto_offset_reset="earliest",
        enable_auto_commit=False
    )
    
    await scored_tx_consumer.start()
    
    try:
        # Consumes messages and process them
        await process_message(scored_tx_consumer=scored_tx_consumer)
        
    finally:
        await scored_tx_consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())