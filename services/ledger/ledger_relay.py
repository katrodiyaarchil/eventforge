from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy import select
from .db_models import OutBox
from common.models import OutBoxStatus
from .database import session_maker
import logging
import asyncio
import json
import os
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def process_outbox(producer: AIOKafkaProducer) -> bool:
    is_exception = False
    messages_processed = 0
    
    async with session_maker() as session:
        query = (
            select(OutBox)
            .where(OutBox.status == OutBoxStatus.PENDING)
            .limit(10)
            .with_for_update(skip_locked=True)
        )
        response = await session.execute(query)
        
        pending_events = response.scalars().all()
        
        if not pending_events:
            return False
        
        for pending_event in pending_events:
            try:
                message = json.dumps(pending_event.payload).encode("utf-8")
                
                # Produce the message
                await producer.send_and_wait(pending_event.topic, value=message)
                
                # Update the status as processed
                pending_event.status = OutBoxStatus.PROCESSED
                
                messages_processed += 1
            
            except KafkaError as err:
                logger.error(f"Error Producing message to kafka : {err}")
                is_exception = True
                break
        
        await session.commit()
        logger.info(f"Successfully published {messages_processed} transactions")
        
    return False if is_exception else True
        
async def main():
    KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
    # KAFKA_TOPIC_TRANSACTIONS_SETTLED = os.environ.get("KAFKA_TOPIC_TRANSACTIONS_SETTLED", "transactions.settled")
    
    settled_tx_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_URL,
        enable_idempotence=True,
        client_id="ledger_service"
    )

    await settled_tx_producer.start()
    
    try:
        while True:
            success = await process_outbox(producer=settled_tx_producer)
            if not success:
                await asyncio.sleep(2) 
    finally:
        await settled_tx_producer.stop()
        logger.info("Kafka shutdown gracefully!!!")
        
if __name__ == "__main__":
    asyncio.run(main())