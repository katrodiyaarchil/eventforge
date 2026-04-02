from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from pydantic import ValidationError
import asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import os
from .database import session_maker
from common.models import ScoredTransactionV1, EventEnvelope, LedgerDirection
from .db_models import Account, LedgerTransaction, LedgerEntry
import logging
from .custom_exception import AccountDoesNotExistException, InsufficientFundsException

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


async def create_ledger(transaction : ScoredTransactionV1) -> None:
    from_account_id = transaction.from_account_id
    to_account_id = transaction.to_account_id
    transaction_id = transaction.transaction_id
    amount_cents = transaction.amount_cents
 
    async with session_maker() as session:
        try:
            # Update LedgerTransaction table
            ledger_tx = LedgerTransaction(
                transaction_id = transaction_id,
                is_posted = True
            )
            session.add(ledger_tx)
            # Flush the session to catch errors early
            await session.flush()


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
                raise AccountDoesNotExistException(
                    f'''One or more account does not exist :  \n
                    from_account_id : {from_account_id}, to_account_id : {to_account_id}'''
                    )
            # Update the account balance
            for account in accounts:
                if account.account_id == from_account_id:
                    # Not enough balance, Transaction could not be completed
                    if account.balance_cents < amount_cents:
                        raise InsufficientFundsException(f"Insufficient funds to complete the transaction : {transaction_id}")
                    else:
                        account.balance_cents -= amount_cents
                else:
                    account.balance_cents += amount_cents
            
            
            # Create Doubble entry ledger
            debit_entry = LedgerEntry(
                transaction_id = transaction_id,
                account_id = from_account_id,
                direction = LedgerDirection.DEBIT,
                amount_cents = amount_cents
            )
            credit_entry = LedgerEntry(
                transaction_id=transaction_id,
                account_id=to_account_id,
                direction=LedgerDirection.CREDIT,
                amount_cents=amount_cents
            )
            
            session.add_all([debit_entry,credit_entry])
            
            # Commit the sessison
            await session.commit()
        except IntegrityError as e:
            logging.info(f"Transaction {transaction_id} will not be processed \nreason : {e}")
            await session.rollback()
        
        except InsufficientFundsException as e:
            logging.warning(e)
            await session.rollback()
        
        except AccountDoesNotExistException as e:
            logging.error(e)
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