from services.gateway.database import session_factory
from services.gateway.db_models import OutBox
from common.models import RawTransactionV1, EventEnvelope, OutBoxStatus, TransactionMetadata
from datetime import datetime, timezone
from aiokafka import AIOKafkaConsumer, ConsumerRecord
from sqlalchemy import select, delete
import pytest
import asyncio

from uuid import uuid4
import os
import json

@pytest.mark.asyncio
async def test_relay_integration():

    KAFKA_TOPIC_TRANSACTIONS_RAW = os.environ.get("KAFKA_TOPIC_TRANSACTIONS_RAW", "transactions.raw")
    KAFKA_URL = os.environ.get("KAFKA_URL", "localhost:9092")

    # Simulate fake transaction
    raw_transaction = RawTransactionV1(
        idempotency_key="idem-key-alpha-integration-test",
        from_account_id= uuid4(),
        to_account_id= uuid4(),
        amount_cents= 150000,
        currency= "CAD",
        metadata= TransactionMetadata(
                ip_address= "192.168.1.15",
                device_id= "iphone-17-pro-max-xyz",
                geo_location= "Edmonton, AB",
                user_agent= "Eventforge-iOS-App/1.0"
                ),
        created_at= datetime.now(timezone.utc)
        )

    # Create Envelope for the raw transaction object
    outbox_event = EventEnvelope[RawTransactionV1](
        event_id=uuid4(),
        event_type= "TransactionCreated",
        schema_version=1,
        producer="integration_test",
        payload=raw_transaction,
        event_time=datetime.now(timezone.utc)
    )
    # Create outbox entry
    db_outbox = OutBox(
        topic=KAFKA_TOPIC_TRANSACTIONS_RAW,
        payload=outbox_event.model_dump(mode="json"),
        status=OutBoxStatus.PENDING
    )

    ## Create outbox record in the DB
    async with session_factory() as session:
        try:
            session.add(db_outbox)
            await session.commit()
            await session.refresh(db_outbox)
        except:
            await session.rollback()
            raise Exception("Unable to create outbox into the database")
        
        finally:
            await session.close()
            
    # Hang on for 5 Seconds to make sure that message is deliverd in Kafka
    await asyncio.sleep(5)
    ## Create Kafka consumer that receives the data from the kafka
    
    integration_consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_TRANSACTIONS_RAW,
        bootstrap_servers= KAFKA_URL,
        client_id="integration_test",
        auto_offset_reset="earliest"
    )
    
    await integration_consumer.start()
    
    try:
        
        # Consumer will wait upto 10s to allow realy enough time for publishing
        message = await integration_consumer.getmany(timeout_ms=10000)
        
        if not message:
            raise Exception("--- Message never reached to consumer ---")
        message_found = False
        for tp, records in message.items():
            for record in records:
                # Peek at the JSON to see if it belongs to THIS test run
                payload = json.loads(record.value.decode("utf-8"))
                if payload.get("event_id") == str(outbox_event.event_id):
                    await verify_payload(record, outbox_event)
                    message_found = True
                    break
            if message_found:
                break

        if not message_found:
            raise Exception(
                "Target message was not found in the Kafka stream.")
    
    finally:
        await integration_consumer.stop()
        
    
    
    # Delete the database entry:
    async with session_factory() as session:
        query = (
            select(OutBox.status)
            .where(OutBox.event_id == db_outbox.event_id)
        )
        record = await session.execute(query)
        status = record.scalar_one()
        
        ## Outbox status Must be OutBoxStatus.PROCESSED
        assert status == OutBoxStatus.PROCESSED
        
        ## Delete the record
        query = (
            delete(OutBox)
            .where(OutBox.event_id == db_outbox.event_id)
        )
        
        await session.execute(query)
        await session.commit()
        await session.close()


@pytest.mark.asyncio
async def verify_payload(message: ConsumerRecord, outbox_event: EventEnvelope):
    from_account_id = message.key.decode("utf-8")
    payload = json.loads(message.value.decode("utf-8"))
    
    
    assert str(outbox_event.event_id) == payload["event_id"]
    assert outbox_event.event_type == payload["event_type"]
    assert outbox_event.event_time == datetime.fromisoformat(payload["event_time"])
    assert outbox_event.model_dump(mode='json')["payload"] == payload["payload"]
