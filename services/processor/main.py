import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from .fraud_scorer import evaluate_fraud
import redis.asyncio as redis
from .redis_client import init_redis_pool, get_redis_client, close_redis_pool
from .velocity_store import rollback_velocity
from common.models import EventEnvelope, RawTransactionV1, ScoredTransactionV1
from common.models import TransactionSettledV1, TransactionStatus
from pydantic import ValidationError
import os
import json
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")
KAFKA_TOPIC_TRANSACTIONS_RAW = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_RAW", "transactions.raw")
KAFKA_TOPIC_TRANSACTIONS_SCORED = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_SCORED", "transactions.scored")
KAFKA_TOPIC_TRANSACTIONS_SETTLED = os.environ.get(
    "KAFKA_TOPIC_TRANSACTIONS_SETTLED", "transactions.settled"
)
VELOCITY_WINDOW = int(os.environ.get("VELOCITY_WINDOW", 300))


async def process_raw_transaction(
    raw_tx_consumer: AIOKafkaConsumer,
    scored_tx_producer: AIOKafkaProducer,
    redis_client: redis.Redis
) -> None:
    """ Scores incoming transactions and updates Redis velocity optimistically. """
    
    async for message in raw_tx_consumer:
        from_account_id = message.key
        payload = message.value.decode("utf-8")
        envelop_json = json.loads(payload)

        try:
            # Validate event envelop
            validated_message = EventEnvelope[RawTransactionV1].model_validate(envelop_json)
            scored_transaction = await evaluate_fraud(
                transaction=validated_message.payload,
                redis_client=redis_client,
                window_size=VELOCITY_WINDOW
            )
            
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
            logger.error(
                f" * Message is not valid * \nMessage : {envelop_json}")
            await raw_tx_consumer.commit()
        
        except KafkaError as e:
            logger.error(f" * Error with Kafka *  : \t{e} ")
            break       # Break the entire loop and forece service to restart to prevent dataloss
        
        except Exception as e:
            logger.error(f" * Unknown exception occured * : \t {e}")
            break       # Break the entire loop and forece service to restart to prevent dataloss


async def process_settled_transaction(settled_tx_consumer: AIOKafkaConsumer, redis_client: redis.Redis) -> None:
    """ Process settled transactions from the Ledger and rolls back redis limits. """

    async for message in settled_tx_consumer:
        payload = message.value.decode("utf-8")

        try:
            envelop = EventEnvelope[TransactionSettledV1].model_validate_json(
                payload)
            settled_tx = envelop.payload

            # If the transaction is rejected free up the velocity limits
            if settled_tx.final_status in [TransactionStatus.REJECTED, TransactionStatus.BLOCKED]:
                await rollback_velocity(
                    redis_client=redis_client,
                    from_account_id=settled_tx.from_account_id,
                    transaction_id=settled_tx.transaction_id,
                    amount_cents=settled_tx.amount_cents
                )
                logger.info(
                    f"Successfully rolled back velocity for rejected transaction: {settled_tx.transaction_id}")

            await settled_tx_consumer.commit()

        except ValidationError:
            logger.critical(
                f"Error validating settled transaction message : \t{payload}")
            await settled_tx_consumer.commit()
        except KafkaError as e:
            logger.error(
                f" * Error with Kafka in Settled Consumer * : \t{e} ")
            break
        except Exception as e:
            logger.error(
                f" * Unknown exception occurred in Settled Consumer * : \t {e}")
            break
async def main():

    logger.info("Booting up Fraud Processor...")

    # Initialize Redis
    await init_redis_pool()
    redis_client = await get_redis_client()

    raw_tx_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_RAW,
        bootstrap_servers=KAFKA_URL,
        client_id="processor_raw_consumer",
        group_id="processor_raw_group",
        auto_offset_reset="earliest",
        enable_auto_commit=False
    )

    settled_tx_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_SETTLED,
        bootstrap_servers=KAFKA_URL,
        auto_offset_reset="earliest",
        client_id="processor_settled_consumer",
        group_id="processor_settled_group",
        enable_auto_commit=False
    )

    scored_tx_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_URL,
        client_id="processor_service",
        enable_idempotence=True
    )
    await raw_tx_consumer.start()
    await scored_tx_producer.start()
    await settled_tx_consumer.start()
    
    logger.info(
        f"Connected to Kafka successfully at : {KAFKA_URL}. Running consumers...")

    try:
        # Run both the cosumer loops concurrently
        await asyncio.gather(
            process_raw_transaction(
                raw_tx_consumer=raw_tx_consumer,
                scored_tx_producer=scored_tx_producer,
                redis_client=redis_client
            ),
            process_settled_transaction(
                settled_tx_consumer=settled_tx_consumer,
                redis_client=redis_client
            )
        )
    finally:
        logger.info("Shutting down Processor gracefully...")
        await raw_tx_consumer.stop()
        await scored_tx_producer.stop()
        await settled_tx_consumer.stop()
        await close_redis_pool()
    

if __name__ == "__main__":
    asyncio.run(main())