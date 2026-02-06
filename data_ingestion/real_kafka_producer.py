import json
import logging
import time
import sys
import os
from kafka import KafkaProducer

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import from noaa_weather_client
from noaa_weather_client import NOAAWeatherClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealWeatherDataProducer:
    """
    Kafka producer that sends REAL weather data from NOAA
    """
    
    def __init__(self):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info("✅ Connected to Kafka")
            
            # Initialize NOAA client
            self.noaa_client = NOAAWeatherClient()
            logger.info("✅ Connected to NOAA API")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise

    def produce_data(self, data: dict):
        """Send real weather data to Kafka"""
        try:
            self.producer.send('weather-events', value=data)
            logger.info(f"✅ Produced REAL data: {data['location']} - "
                       f"Temp: {data['temperature']}°F, "
                       f"Humidity: {data['humidity']}%")
        except Exception as e:
            logger.error(f"❌ Error producing data: {e}")

    def run(self, duration_seconds=300, interval_seconds=30):
        """
        Continuously fetch REAL weather and produce to Kafka
        
        Args:
            duration_seconds: How long to run (default 5 minutes)
            interval_seconds: Interval between fetches (default 30 seconds)
        """
        logger.info(f"Starting REAL weather producer for {duration_seconds} seconds...")
        logger.info(f"Will fetch weather every {interval_seconds} seconds")
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_seconds:
                # Fetch weather for all locations
                all_weather = self.noaa_client.get_all_locations_weather()
                
                # Send each to Kafka
                for location, weather_data in all_weather.items():
                    self.produce_data(weather_data)
                
                # Wait before next fetch
                logger.info(f"⏳ Waiting {interval_seconds} seconds before next fetch...")
                time.sleep(interval_seconds)
            
            logger.info("✅ Producer finished")
            self.producer.close()
            
        except KeyboardInterrupt:
            logger.info("Producer stopped by user")
            self.producer.close()

if __name__ == '__main__':
    producer = RealWeatherDataProducer()
    # Run for 5 minutes, fetching every 30 seconds
    producer.run(duration_seconds=300, interval_seconds=30)