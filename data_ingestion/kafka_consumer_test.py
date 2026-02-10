"""
Test Consumer - Reads from Kafka and prints weather data.
Used to verify the producer is working correctly.
This will be REPLACED by Spark Streaming in Week 3.
"""

import json
import os
import logging
from datetime import datetime

from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("WeatherConsumer")

# Config
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC = "raw-weather-data"


def main():
    # Schema Registry for deserialization
    sr_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})

    # Load schema
    with open("avro_schemas/weather_reading.avsc", "r") as f:
        schema_str = f.read()

    avro_deserializer = AvroDeserializer(sr_client, schema_str)

    # Consumer config
    consumer_conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": "test-consumer-group",
        "auto.offset.reset": "earliest",  # Read from beginning
    }

    consumer = Consumer(consumer_conf)
    consumer.subscribe([TOPIC])

    logger.info(f"✅ Subscribed to '{TOPIC}'. Waiting for messages...\n")

    message_count = 0

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            # Deserialize Avro message
            weather = avro_deserializer(
                msg.value(),
                SerializationContext(TOPIC, MessageField.VALUE),
            )

            message_count += 1

            # Pretty print
            logger.info(
                f"📥 Message #{message_count} | "
                f"{weather['location']['city']}, {weather['location']['state']} | "
                f"Temp: {weather.get('temperature_fahrenheit', 'N/A')}°F | "
                f"Humidity: {weather.get('humidity_percent', 'N/A')}% | "
                f"Wind: {weather.get('wind_speed_mph', 'N/A')} mph | "
                f"Condition: {weather.get('weather_condition', 'N/A')} | "
                f"Source: {weather['source']} | "
                f"Partition: {msg.partition()} | "
                f"Offset: {msg.offset()}"
            )

    except KeyboardInterrupt:
        logger.info(f"\n🛑 Stopped. Total messages consumed: {message_count}")
    finally:
        consumer.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🔍 WEATHER DATA TEST CONSUMER")
    logger.info("=" * 60)
    main()
    