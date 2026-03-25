import asyncio
import os
from aiokafka import AIOKafkaConsumer
from aiokafka import ConsumerRecord

KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
KAFKA_TOPIC_TRANSACTIONS_RAW = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_RAW", "transactions.raw")


async def consume_messages(consumer: AIOKafkaConsumer, topics=[KAFKA_TOPIC_TRANSACTIONS_RAW]):
    
    consumer.subscribe(topics=topics)
    
        
    async for messasge in consumer:
        if messasge:
            from_account_id = messasge.key
            payload = messasge.value
            print(
                f"Received transaction from user : {from_account_id.decode('utf-8')} with the payload : {payload.decode('utf-8')}")



async def main():
    
    print(f"Connecting to kafka at : {KAFKA_URL}")
    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_URL, 
        client_id="transaction_consumer",
        group_id="transaction-processors",
        auto_offset_reset="earliest"
    )
    
    await consumer.start()
    try:
        await consume_messages(consumer=consumer, topics=[KAFKA_TOPIC_TRANSACTIONS_RAW])
        
    finally:
        await consumer.stop()
        

if __name__ == "__main__":
    asyncio.run(main())