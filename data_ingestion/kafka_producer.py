import json
import logging
import time
import os
from kafka import KafkaProducer
from datetime import datetime
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherDataProducer:
    def __init__(self):
        self.kafka_brokers = ['localhost:9092']
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info(f"✅ Connected to Kafka: {self.kafka_brokers}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            raise

    def generate_sample_data(self, location: str) -> dict:
        """Generate random weather data for testing"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'location': location,
            'temperature': round(random.uniform(32, 95), 1),
            'humidity': round(random.uniform(30, 100), 1),
            'wind_speed': round(random.uniform(0, 50), 1),
            'pressure': round(random.uniform(990, 1030), 1),
            'precipitation': round(random.uniform(0, 2), 2)
        }

    def produce_data(self, data: dict):
        """Send data to Kafka topic"""
        try:
            self.producer.send('weather-events', value=data)
            logger.info(f"✅ Produced: {data['location']} - Temp: {data['temperature']}°F")
        except Exception as e:
            logger.error(f"❌ Error producing data: {e}")

    def run(self, duration_seconds=60):
        """Produce data for specified duration"""
        logger.info(f"Starting producer for {duration_seconds} seconds...")
        
        locations = [
            'New York',
            'Los Angeles',
            'Chicago',
            'Houston',
            'Phoenix',
            'Miami'
        ]
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_seconds:
                for location in locations:
                    data = self.generate_sample_data(location)
                    self.produce_data(data)
                    time.sleep(1)  # Wait 1 second between messages
            
            logger.info("✅ Producer finished")
            self.producer.close()
        except KeyboardInterrupt:
            logger.info("Producer stopped by user")
            self.producer.close()

if __name__ == '__main__':
    producer = WeatherDataProducer()
    # Run for 30 seconds (produces weather data)
    producer.run(duration_seconds=30)
