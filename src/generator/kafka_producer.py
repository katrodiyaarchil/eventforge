import json
from kafka import KafkaProducer

# Kafka configurations
KAFKA_BROKER_URL = '0.0.0.0:9092'


# Kafka producer to read the events

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER_URL,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
