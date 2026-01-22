import json
import logging
from kafka import KafkaConsumer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def consume_data():
    """Consume weather data from Kafka"""
    try:
        consumer = KafkaConsumer(
            'weather-events',
            bootstrap_servers=['localhost:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id='test-consumer'
        )
        
        logger.info("✅ Started consuming from Kafka...")
        logger.info("Press Ctrl+C to stop")
        
        message_count = 0
        for message in consumer:
            data = message.value
            message_count += 1
            logger.info(f"Message {message_count}: {data['location']} - Temp: {data['temperature']}°F, Humidity: {data['humidity']}%")
    
    except KeyboardInterrupt:
        logger.info(f"\n✅ Stopped. Received {message_count} messages")
        consumer.close()

if __name__ == '__main__':
    consume_data()
