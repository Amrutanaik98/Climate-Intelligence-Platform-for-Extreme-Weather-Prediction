import json
import logging
import psycopg2
from kafka import KafkaConsumer
from datetime import datetime
import sys
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "airflow",
    "password": "airflow",
    "database": "airflow"
}

class WeatherDataProcessor:
    def __init__(self):
        """Initialize Kafka consumer and database connection"""
        try:
            self.consumer = KafkaConsumer(
                "weather-events",
                bootstrap_servers=["localhost:9092"],
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                group_id="data-processor"
            )
            logger.info("✅ Connected to Kafka")
            
            # Test database connection
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.close()
            logger.info("✅ Connected to PostgreSQL")
            
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            raise

    def calculate_heat_index(self, temperature: float, humidity: float) -> float:
        """
        Calculate heat index (feels like temperature)
        
        Formula: Only applies when T >= 80°F
        """
        T = temperature
        RH = humidity
        
        # Simple heat index calculation
        if T >= 80 and RH >= 40:
            # Rothfusz regression
            c1 = -42.379
            c2 = 2.04901523
            c3 = 10.14333127
            c4 = -0.22475541
            c5 = -0.00683783
            c6 = -0.05481717
            c7 = 0.00122874
            c8 = 0.00085282
            c9 = -0.00000199
            
            heat_index = (c1 + c2*T + c3*RH + c4*T*RH + 
                         c5*T**2 + c6*RH**2 + c7*T**2*RH + 
                         c8*T*RH**2 + c9*T**2*RH**2)
            return round(heat_index, 2)
        else:
            return round(T, 2)

    def detect_extreme_event(self, temperature: float, wind_speed: float) -> int:
        """
        Detect extreme weather events
        
        Rules:
        - Temperature > 95°F = extreme heat
        - Wind speed > 50 mph = extreme wind
        """
        if temperature > 95 or wind_speed > 50:
            return 1
        return 0

    def transform_data(self, raw_data: dict) -> dict:
        """
        Transform and enrich raw weather data
        
        Steps:
        1. Clean data (handle missing values)
        2. Calculate new features (heat index)
        3. Detect extreme events
        4. Add metadata
        """
        try:
            # Clean data - fill missing values with defaults
            temperature = raw_data.get("temperature", 70.0)
            humidity = raw_data.get("humidity", 50.0)
            wind_speed = raw_data.get("wind_speed", 0.0)
            
            # Validate ranges
            temperature = max(-50, min(150, temperature))  # -50 to 150°F
            humidity = max(0, min(100, humidity))  # 0 to 100%
            wind_speed = max(0, wind_speed)  # Can't be negative
            
            # Calculate heat index
            heat_index = self.calculate_heat_index(temperature, humidity)
            
            # Detect extreme events
            extreme_event = self.detect_extreme_event(temperature, wind_speed)
            
            # Return transformed data
            transformed = {
                "timestamp": raw_data.get("timestamp", datetime.utcnow().isoformat()),
                "location": raw_data.get("location", "Unknown"),
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "pressure": raw_data.get("pressure", 1013.0),
                "precipitation": raw_data.get("precipitation", 0.0),
                "heat_index": heat_index,
                "extreme_event": extreme_event,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            return transformed
            
        except Exception as e:
            logger.error(f"❌ Error transforming data: {e}")
            return None

    def store_data(self, raw_data: dict, processed_data: dict):
        """Store both raw and processed data in PostgreSQL"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Insert raw data
            insert_raw = """
            INSERT INTO raw_events 
            (timestamp, location, temperature, humidity, wind_speed, pressure, precipitation)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_raw, (
                raw_data["timestamp"],
                raw_data["location"],
                raw_data["temperature"],
                raw_data["humidity"],
                raw_data["wind_speed"],
                raw_data["pressure"],
                raw_data["precipitation"]
            ))
            
            # Insert processed data
            insert_processed = """
            INSERT INTO processed_data 
            (timestamp, location, temperature, humidity, wind_speed, pressure, 
             precipitation, heat_index, extreme_event)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_processed, (
                processed_data["timestamp"],
                processed_data["location"],
                processed_data["temperature"],
                processed_data["humidity"],
                processed_data["wind_speed"],
                processed_data["pressure"],
                processed_data["precipitation"],
                processed_data["heat_index"],
                processed_data["extreme_event"]
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"✅ Stored: {processed_data['location']} - "
                       f"Temp: {processed_data['temperature']}°F, "
                       f"Heat Index: {processed_data['heat_index']}°F, "
                       f"Extreme: {processed_data['extreme_event']}")
            
        except Exception as e:
            logger.error(f"❌ Error storing data: {e}")

    def process(self, max_messages: int = None):
        """
        Main processing loop
        
        - Read from Kafka
        - Transform data
        - Store in database
        """
        if max_messages:
            logger.info(f"Starting processor... (will process {max_messages} messages)")
        else:
            logger.info("Starting processor... (will run indefinitely, press Ctrl+C to stop)")
        
        message_count = 0
        
        try:
            for message in self.consumer:
                raw_data = message.value
                
                # Transform
                processed_data = self.transform_data(raw_data)
                
                if processed_data:
                    # Store
                    self.store_data(raw_data, processed_data)
                    message_count += 1
                
                # Stop after processing max_messages (if specified)
                if max_messages and message_count >= max_messages:
                    logger.info(f"✅ Processed {message_count} messages. Stopping.")
                    break
                    
        except KeyboardInterrupt:
            logger.info(f"✅ Stopped. Processed {message_count} messages.")

if __name__ == "__main__":
    processor = WeatherDataProcessor()
    # Run indefinitely (press Ctrl+C to stop)
    processor.process()
