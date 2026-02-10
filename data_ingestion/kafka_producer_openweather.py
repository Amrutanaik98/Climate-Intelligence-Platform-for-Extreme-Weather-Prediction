"""
Climate Intelligence Platform - Weather Data Kafka Producer
============================================================
Fetches real-time weather data from OpenWeatherMap API and
publishes to Kafka with Avro schema validation.

This producer:
- Calls OpenWeatherMap API for 20+ US cities
- Serializes data using Avro (validated by Schema Registry)
- Sends to 'raw-weather-data' Kafka topic
- Falls back to mock data if API fails
- Logs all activity for monitoring
- Handles errors with retries and dead letter queue
"""

import json
import os
import time
import logging
import uuid
from datetime import datetime, timezone

import requests
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import (
    SerializationContext,
    MessageField,
    StringSerializer,
)
from dotenv import load_dotenv

# ============================================================
# SETUP
# ============================================================

# Load environment variables from .env file
load_dotenv()

# Configure logging (production-grade, not just print statements)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WeatherProducer")

# ============================================================
# CONFIGURATION
# ============================================================

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC_WEATHER_DATA = "raw-weather-data"
TOPIC_DLQ = "dead-letter-queue"

# API settings
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "30"))

# Cities to monitor (latitude, longitude)
# These cover diverse US climate zones for better ML training data
MONITORED_CITIES = [
    {"city": "New York",      "state": "NY", "lat": 40.7128, "lon": -74.0060},
    {"city": "Los Angeles",   "state": "CA", "lat": 34.0522, "lon": -118.2437},
    {"city": "Chicago",       "state": "IL", "lat": 41.8781, "lon": -87.6298},
    {"city": "Houston",       "state": "TX", "lat": 29.7604, "lon": -95.3698},
    {"city": "Phoenix",       "state": "AZ", "lat": 33.4484, "lon": -112.0740},
    {"city": "Miami",         "state": "FL", "lat": 25.7617, "lon": -80.1918},
    {"city": "Seattle",       "state": "WA", "lat": 47.6062, "lon": -122.3321},
    {"city": "Denver",        "state": "CO", "lat": 39.7392, "lon": -104.9903},
    {"city": "Atlanta",       "state": "GA", "lat": 33.7490, "lon": -84.3880},
    {"city": "Boston",        "state": "MA", "lat": 42.3601, "lon": -71.0589},
    {"city": "Minneapolis",   "state": "MN", "lat": 44.9778, "lon": -93.2650},
    {"city": "New Orleans",   "state": "LA", "lat": 29.9511, "lon": -90.0715},
    {"city": "Las Vegas",     "state": "NV", "lat": 36.1699, "lon": -115.1398},
    {"city": "Portland",      "state": "OR", "lat": 45.5152, "lon": -122.6784},
    {"city": "Dallas",        "state": "TX", "lat": 32.7767, "lon": -96.7970},
    {"city": "Anchorage",     "state": "AK", "lat": 61.2181, "lon": -149.9003},
    {"city": "Honolulu",      "state": "HI", "lat": 21.3069, "lon": -157.8583},
    {"city": "Detroit",       "state": "MI", "lat": 42.3314, "lon": -83.0458},
    {"city": "San Francisco", "state": "CA", "lat": 37.7749, "lon": -122.4194},
    {"city": "Nashville",     "state": "TN", "lat": 36.1627, "lon": -86.7816},
]


# ============================================================
# AVRO SCHEMA (loaded from file)
# ============================================================

def load_avro_schema(schema_path: str) -> str:
    """Load Avro schema from .avsc file and return as string."""
    with open(schema_path, "r") as f:
        return f.read()


# ============================================================
# WEATHER API CLIENT
# ============================================================

class OpenWeatherClient:
    """
    Fetches current weather data from OpenWeatherMap API.
    
    Free tier: 60 calls/minute, 1,000,000 calls/month
    We fetch 20 cities every 30 seconds = 40 calls/minute (within limit)
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()  # Reuse HTTP connections (faster)
        self.session.timeout = 10  # 10 second timeout

    def fetch_weather(self, lat: float, lon: float) -> dict | None:
        """
        Fetch current weather for a location.
        Returns parsed weather dict or None if API call fails.
        """
        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "imperial",  # Fahrenheit
            }
            response = self.session.get(self.BASE_URL, params=params)
            response.raise_for_status()  # Raises exception for 4xx/5xx
            return response.json()

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching weather for ({lat}, {lon})")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error for ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for ({lat}, {lon}): {e}")
            return None


# ============================================================
# MOCK DATA GENERATOR (Fallback)
# ============================================================

import random

def generate_mock_weather(city_info: dict) -> dict:
    """
    Generate realistic mock weather data when API is unavailable.
    Uses city latitude to generate climate-appropriate values.
    
    WHY: During development or API outages, we still want data flowing
    through the pipeline so we can test downstream components.
    """
    lat = city_info["lat"]

    # Temperature varies by latitude (hotter near equator)
    base_temp = 90 - abs(lat - 25) * 1.2  # ~90°F at lat 25, cooler further away
    temp_f = round(base_temp + random.uniform(-10, 10), 1)
    temp_c = round((temp_f - 32) * 5 / 9, 1)

    return {
        "temperature_fahrenheit": temp_f,
        "temperature_celsius": temp_c,
        "humidity_percent": round(random.uniform(20, 95), 1),
        "pressure_hpa": round(random.uniform(990, 1035), 1),
        "wind_speed_mph": round(random.uniform(0, 35), 1),
        "wind_direction_degrees": random.randint(0, 360),
        "precipitation_mm": round(random.uniform(0, 10), 1) if random.random() > 0.6 else 0.0,
        "visibility_km": round(random.uniform(2, 16), 1),
        "cloud_cover_percent": random.randint(0, 100),
        "weather_condition": random.choice([
            "Clear", "Partly Cloudy", "Cloudy", "Rain",
            "Thunderstorm", "Snow", "Fog", "Windy"
        ]),
        "uv_index": round(random.uniform(0, 11), 1),
    }


# ============================================================
# MESSAGE BUILDER
# ============================================================

def build_weather_message(city_info: dict, api_response: dict | None, source: str) -> dict:
    """
    Transform raw API response into our standardized Avro schema format.
    
    This is a critical function — it NORMALIZES data from different sources
    into ONE consistent format. Without this, every consumer would need
    to handle different API response formats.
    """
    now = datetime.now(timezone.utc).isoformat()

    if source == "OPENWEATHERMAP" and api_response:
        weather_data = {
            "temperature_fahrenheit": api_response.get("main", {}).get("temp"),
            "temperature_celsius": round(
                (api_response.get("main", {}).get("temp", 32) - 32) * 5 / 9, 1
            ),
            "humidity_percent": float(api_response.get("main", {}).get("humidity", 0)),
            "pressure_hpa": float(api_response.get("main", {}).get("pressure", 0)),
            "wind_speed_mph": api_response.get("wind", {}).get("speed"),
            "wind_direction_degrees": api_response.get("wind", {}).get("deg"),
            "precipitation_mm": api_response.get("rain", {}).get("1h"),
            "visibility_km": round(api_response.get("visibility", 10000) / 1000, 1),
            "cloud_cover_percent": api_response.get("clouds", {}).get("all"),
            "weather_condition": api_response.get("weather", [{}])[0].get("main", "Unknown"),
            "uv_index": None,  # Not in basic API, needs separate call
        }
    elif source == "MOCK":
        weather_data = generate_mock_weather(city_info)
    else:
        weather_data = generate_mock_weather(city_info)

    # Build the final message matching our Avro schema
    message = {
        "message_id": str(uuid.uuid4()),
        "timestamp": now,
        "ingestion_timestamp": now,
        "source": source,
        "location": {
            "city": city_info["city"],
            "state": city_info["state"],
            "country": "US",
            "latitude": city_info["lat"],
            "longitude": city_info["lon"],
        },
        **weather_data,
    }

    return message


# ============================================================
# KAFKA PRODUCER (with Avro serialization)
# ============================================================

class WeatherKafkaProducer:
    """
    Production Kafka producer with:
    - Avro serialization (validated by Schema Registry)
    - Delivery confirmation callbacks
    - Dead letter queue for failed messages
    - Graceful shutdown
    """

    def __init__(self):
        # --- Schema Registry setup ---
        schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
        schema_registry_client = SchemaRegistryClient(schema_registry_conf)

        # Load Avro schema from file
        schema_str = load_avro_schema("avro_schemas/weather_reading.avsc")

        # Create Avro serializer (validates every message against schema)
        self.avro_serializer = AvroSerializer(
            schema_registry_client,
            schema_str,
            conf={"auto.register.schemas": True},
        )

        self.string_serializer = StringSerializer("utf_8")

        # --- Kafka Producer setup ---
        producer_conf = {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "weather-producer-01",
            # Performance tuning
            "linger.ms": 100,        # Wait 100ms to batch messages (efficiency)
            "batch.size": 65536,     # 64KB batch size
            "compression.type": "snappy",  # Compress messages (saves bandwidth)
            # Reliability
            "acks": "all",           # Wait for ALL brokers to confirm (no data loss)
            "retries": 3,            # Retry failed sends 3 times
            "retry.backoff.ms": 1000,  # Wait 1 second between retries
        }
        self.producer = Producer(producer_conf)

        # --- DLQ Producer (for failed messages) ---
        self.dlq_producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

        # --- Stats ---
        self.messages_sent = 0
        self.messages_failed = 0

        logger.info("✅ Weather Kafka Producer initialized")
        logger.info(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info(f"   Schema Registry: {SCHEMA_REGISTRY_URL}")
        logger.info(f"   Topic: {TOPIC_WEATHER_DATA}")
        logger.info(f"   Cities: {len(MONITORED_CITIES)}")

    def delivery_callback(self, err, msg):
        """Called once for each message produced to indicate delivery result."""
        if err is not None:
            logger.error(f"❌ Delivery failed: {err}")
            self.messages_failed += 1
            # Send to Dead Letter Queue
            self._send_to_dlq(msg)
        else:
            self.messages_sent += 1
            logger.debug(
                f"✅ Delivered to {msg.topic()} "
                f"[partition {msg.partition()}] "
                f"@ offset {msg.offset()}"
            )

    def _send_to_dlq(self, original_msg):
        """Send failed messages to Dead Letter Queue for investigation."""
        try:
            self.dlq_producer.produce(
                TOPIC_DLQ,
                value=original_msg.value(),
                headers=[("error", b"delivery_failed")],
            )
            self.dlq_producer.flush()
            logger.warning("⚠️ Message sent to Dead Letter Queue")
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")

    def produce_weather_data(self, weather_client: OpenWeatherClient):
        """
        Fetch weather for all cities and produce to Kafka.
        This runs once per cycle (called by the scheduler).
        """
        cycle_start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"🌦️  Starting data fetch cycle for {len(MONITORED_CITIES)} cities")
        logger.info(f"{'='*60}")

        for city_info in MONITORED_CITIES:
            try:
                # Try real API first
                if OPENWEATHER_API_KEY:
                    api_response = weather_client.fetch_weather(
                        city_info["lat"], city_info["lon"]
                    )
                    source = "OPENWEATHERMAP"
                else:
                    api_response = None
                    source = "MOCK"

                # Fall back to mock if API fails
                if api_response is None:
                    source = "MOCK"

                # Build standardized message
                message = build_weather_message(city_info, api_response, source)

                # Use city as the Kafka message KEY
                # WHY? Messages with the same key go to the same partition
                # This means all data for "New York" is in the same partition
                # which makes time-series ordering guaranteed per city
                message_key = f"{city_info['city']}_{city_info['state']}"

                # Produce to Kafka with Avro serialization
                self.producer.produce(
                    topic=TOPIC_WEATHER_DATA,
                    key=self.string_serializer(message_key),
                    value=self.avro_serializer(
                        message,
                        SerializationContext(TOPIC_WEATHER_DATA, MessageField.VALUE),
                    ),
                    on_delivery=self.delivery_callback,
                )

                logger.info(
                    f"  📤 {city_info['city']}, {city_info['state']} | "
                    f"{message.get('temperature_fahrenheit', 'N/A')}°F | "
                    f"Humidity: {message.get('humidity_percent', 'N/A')}% | "
                    f"Source: {source}"
                )

            except Exception as e:
                logger.error(f"  ❌ Error processing {city_info['city']}: {e}")
                self.messages_failed += 1

            # Small delay between API calls (respect rate limits)
            time.sleep(0.5)

        # Flush ensures all messages are actually sent
        self.producer.flush()

        cycle_time = round(time.time() - cycle_start, 1)
        logger.info(f"\n📊 Cycle complete in {cycle_time}s")
        logger.info(f"   Total sent: {self.messages_sent} | Failed: {self.messages_failed}")

    def run_continuous(self, weather_client: OpenWeatherClient):
        """
        Run the producer continuously, fetching data every FETCH_INTERVAL_SECONDS.
        
        In production, this would run as a Docker container that never stops.
        Airflow would monitor it, and alerts would fire if it goes down.
        """
        logger.info(f"\n🚀 Starting continuous producer (interval: {FETCH_INTERVAL_SECONDS}s)")
        logger.info("   Press Ctrl+C to stop\n")

        try:
            while True:
                self.produce_weather_data(weather_client)
                logger.info(f"\n⏳ Sleeping {FETCH_INTERVAL_SECONDS}s until next cycle...\n")
                time.sleep(FETCH_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("\n🛑 Producer stopped by user")
        finally:
            self.producer.flush()
            logger.info(f"\n📊 Final stats: Sent={self.messages_sent}, Failed={self.messages_failed}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🌍 CLIMATE INTELLIGENCE PLATFORM")
    logger.info("   Weather Data Kafka Producer")
    logger.info("=" * 60)

    # Check for API key
    if not OPENWEATHER_API_KEY:
        logger.warning("⚠️  No OPENWEATHER_API_KEY found in .env")
        logger.warning("   Will use MOCK data (fine for development)")

    # Initialize weather API client
    weather_client = OpenWeatherClient(OPENWEATHER_API_KEY)

    # Initialize Kafka producer
    kafka_producer = WeatherKafkaProducer()

    # Start producing!
    kafka_producer.run_continuous(weather_client)