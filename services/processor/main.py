import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from .fraud_scorer import evaluate_fraud
from common.models import EventEnvelope, RawTransactionV1, ScoredTransactionV1
from pydantic import ValidationError
import os
import json
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
KAFKA_TOPIC_TRANSACTIONS_RAW = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_RAW", "transactions.raw")
KAFKA_TOPIC_TRANSACTIONS_SCORED = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_SCORED", "transactions.scored")

async def process_and_publish(raw_tx_consumer: AIOKafkaConsumer, scored_tx_producer: AIOKafkaProducer):
    
    async for message in raw_tx_consumer:
        from_account_id = message.key
        payload = message.value.decode("utf-8")
        envelop_json = json.loads(payload)

        try:
            # Validate event envelop
            validated_message = EventEnvelope[RawTransactionV1].model_validate(envelop_json)
            scored_transaction = await evaluate_fraud(validated_message.payload)
            
            # Wrap the scored Transaction in Envelop and produce to kafka
            scored_tx_envelop = EventEnvelope[ScoredTransactionV1] (
                event_type="TransactionScored",
                schema_version=1,
                producer="fraud_processor",
                payload=scored_transaction
            )
            
            await scored_tx_producer.send_and_wait(
                topic=KAFKA_TOPIC_TRANSACTIONS_SCORED, 
                key=from_account_id,
                value=scored_tx_envelop.model_dump_json().encode("utf-8")
            )
            
            # Manually commit the consumer
            await raw_tx_consumer.commit()

        except ValidationError:
            logging.error(f" * Message is not valid * \nMessage : {envelop_json}")
        
        except KafkaError as e:
            logging.error(f" * Error with Kafka *  : \t{e} ")
            break       # Break the entire loop and forece service to restart to prevent dataloss
        
        except Exception as e:
            logging.error(f" * Unknown exception occured * : \t {e}")
            break       # Break the entire loop and forece service to restart to prevent dataloss

async def main():

    logging.info("Booting up Fraud Processor...")

    raw_tx_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_RAW,
        bootstrap_servers=KAFKA_URL,
        client_id="processor_service",
        group_id="transaction_processor_group",
        auto_offset_reset="earliest",
        enable_auto_commit=False
    )
    
    scored_tx_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_URL,
        client_id="processor_service",
        enable_idempotence=True
    )
    await raw_tx_consumer.start()
    await scored_tx_producer.start()
    
    logging.info(f"Connected to Kafka successfully at : {KAFKA_URL}")

    try:
        await process_and_publish(raw_tx_consumer, scored_tx_producer)
    finally:
        await raw_tx_consumer.stop()
        await scored_tx_producer.stop()
    

if __name__ == "__main__":
    asyncio.run(main())