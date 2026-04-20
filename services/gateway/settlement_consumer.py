from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from .database import session_factory
from .db_models import Transaction
from common.models import EventEnvelope, TransactionSettledV1, TransactionStatus
from sqlalchemy import update
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

async def update_status(settled_tx: TransactionSettledV1) -> None:
    """ Updates status in database and record reason """
    async with session_factory() as session:
        stmt = (
            update(Transaction)
            .where(Transaction.transaction_id == settled_tx.transaction_id)
            .values(
                status = settled_tx.final_status,
                reason = settled_tx.reason
            )
        )
        
        await session.execute(stmt)
        await session.commit()
        
async def read_transaction_status(consumer: AIOKafkaConsumer) -> None:
    """ Reads settled transaction_ids from the kafka topic """
    try:
        async for message in consumer:
            value = message.value
            try:
                envelop = EventEnvelope[TransactionSettledV1].model_validate_json(value.decode("utf-8"))
            except ValueError as err:
                logger.critical(f"Unable to validate message data : {value}")
                await consumer.commit()
                continue
            
            tx_data = envelop.payload
            
            # Update the transaction status
            await update_status(tx_data)
            
            await consumer.commit()
            
    
    except KafkaError as err:
        logger.error(f"Unable to read messages from kafka : {err}")
        
    except Exception as err:
        logger.error(f"Unknown exception occured : {err}")
        
async def main():
    """ Driver code """
    
    KAFKA_TOPIC_TRANSACTIONS_SETTLED = os.environ.get(
        "KAFKA_TOPIC_TRANSACTIONS_SETTLED", "transactions.settled"
        )
    KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
    
    logger.info(f"Connecting to kafka at : {KAFKA_URL}")
    settled_tx_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_SETTLED,
        bootstrap_servers=KAFKA_URL,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        client_id="transaction_status_updater",
        group_id="transaction_status_updater_group"
    )
    
    await settled_tx_consumer.start()
    
    try:
        await read_transaction_status(consumer=settled_tx_consumer)
    finally:
        logger.info("shutting doing kafka")
        await settled_tx_consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())