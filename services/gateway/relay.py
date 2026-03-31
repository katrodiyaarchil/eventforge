import os
import asyncio
from aiokafka import AIOKafkaProducer
from .db_models import OutBox
from .database import session_factory
from sqlalchemy import select
from common.models import OutBoxStatus
import json

## Configure kafka producer
KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")

async def process_outbox(producer: AIOKafkaProducer):
    is_exception = False
    message_processed = 0

    async with session_factory() as session:
        
        ## Query the outbox and read pending messages
        query = (
            select(OutBox)
            .where(OutBox.status == OutBoxStatus.PENDING)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        
        result = await session.execute(query)
        pending_events = result.scalars().all()
        
        # If no events to publish
        if not pending_events:
            return False
        
        # Process all the events one by one and publish one by one to kafka
        for event in pending_events:
            try:
                message = json.dumps(event.payload).encode("utf-8")
                from_account_id:str = event.payload["payload"]["from_account_id"]
                
                await producer.send_and_wait(topic=event.topic, value=message, key=from_account_id.encode("utf-8"))
                
                # Change the status in Outbox
                event.status =  OutBoxStatus.PROCESSED
                message_processed += 1
            
            except Exception as e:
                print(f"Failed to publish event {event.event_id} : {e}")
                
                # Performace Tuning:  as a part of performance tuning, instead of rolling back all 50 messages,
                # Commit whatever was processed and break the loop to maintain strict ordering

                # # Rollback the transaction
                # await session.rollback()
                # return False
                is_exception = True
                break
        
        # Commit the session to permanently save the status to outbox
        await session.commit()
        print(f"Successfully publised {message_processed} events to kafka")
        return True if not is_exception else False

async def main():
    print(f"Connecting to kafka Cluster at {KAFKA_URL}...")

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_URL,
        client_id="gateway_service",
        enable_idempotence=True)

    await producer.start()
    
    try:
        while True:
            
            # Try querying DB and produce a message to kafka
            processed_any = await process_outbox(producer=producer)

            if not processed_any:
                await asyncio.sleep(2)
    
    finally:
        await producer.stop()
        print(f"Kafka shutdown gracefully")
        

if __name__ == "__main__":
    asyncio.run(main())