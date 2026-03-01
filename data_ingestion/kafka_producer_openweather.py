"""
🌍 Climate Intelligence Platform — Global Kafka Producer
=========================================================
Ingests real-time weather data for 80 major world cities.
Uses OpenWeatherMap API with Avro serialization.

Run: python data_ingestion/kafka_producer_openweather.py
"""

import os
import json
import time
import requests
import fastavro
from io import BytesIO
from datetime import datetime, timezone
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC = "raw-weather-data"
POLL_INTERVAL = 60  # seconds between full cycles

# ============================================================
# 80 MAJOR WORLD CITIES — All Continents
# ============================================================

GLOBAL_CITIES = [
    # ── North America (15) ──
    {"city": "New York", "country": "US", "continent": "North America", "region": "Northeast US", "lat": 40.71, "lon": -74.01},
    {"city": "Los Angeles", "country": "US", "continent": "North America", "region": "West US", "lat": 34.05, "lon": -118.24},
    {"city": "Chicago", "country": "US", "continent": "North America", "region": "Midwest US", "lat": 41.88, "lon": -87.63},
    {"city": "Houston", "country": "US", "continent": "North America", "region": "South US", "lat": 29.76, "lon": -95.37},
    {"city": "Miami", "country": "US", "continent": "North America", "region": "Southeast US", "lat": 25.76, "lon": -80.19},
    {"city": "Seattle", "country": "US", "continent": "North America", "region": "Northwest US", "lat": 47.61, "lon": -122.33},
    {"city": "Denver", "country": "US", "continent": "North America", "region": "West US", "lat": 39.74, "lon": -104.99},
    {"city": "Phoenix", "country": "US", "continent": "North America", "region": "West US", "lat": 33.45, "lon": -112.07},
    {"city": "Boston", "country": "US", "continent": "North America", "region": "Northeast US", "lat": 42.36, "lon": -71.06},
    {"city": "San Francisco", "country": "US", "continent": "North America", "region": "West US", "lat": 37.77, "lon": -122.42},
    {"city": "Toronto", "country": "CA", "continent": "North America", "region": "Canada", "lat": 43.65, "lon": -79.38},
    {"city": "Mexico City", "country": "MX", "continent": "North America", "region": "Mexico", "lat": 19.43, "lon": -99.13},
    {"city": "Vancouver", "country": "CA", "continent": "North America", "region": "Canada", "lat": 49.28, "lon": -123.12},
    {"city": "Montreal", "country": "CA", "continent": "North America", "region": "Canada", "lat": 45.50, "lon": -73.57},
    {"city": "Havana", "country": "CU", "continent": "North America", "region": "Caribbean", "lat": 23.11, "lon": -82.37},

    # ── South America (8) ──
    {"city": "São Paulo", "country": "BR", "continent": "South America", "region": "South America East", "lat": -23.55, "lon": -46.63},
    {"city": "Buenos Aires", "country": "AR", "continent": "South America", "region": "South America South", "lat": -34.60, "lon": -58.38},
    {"city": "Rio de Janeiro", "country": "BR", "continent": "South America", "region": "South America East", "lat": -22.91, "lon": -43.17},
    {"city": "Lima", "country": "PE", "continent": "South America", "region": "South America West", "lat": -12.05, "lon": -77.04},
    {"city": "Bogota", "country": "CO", "continent": "South America", "region": "South America North", "lat": 4.71, "lon": -74.07},
    {"city": "Santiago", "country": "CL", "continent": "South America", "region": "South America South", "lat": -33.45, "lon": -70.67},
    {"city": "Caracas", "country": "VE", "continent": "South America", "region": "South America North", "lat": 10.49, "lon": -66.88},
    {"city": "Quito", "country": "EC", "continent": "South America", "region": "South America West", "lat": -0.18, "lon": -78.47},

    # ── Europe (18) ──
    {"city": "London", "country": "GB", "continent": "Europe", "region": "Western Europe", "lat": 51.51, "lon": -0.13},
    {"city": "Paris", "country": "FR", "continent": "Europe", "region": "Western Europe", "lat": 48.86, "lon": 2.35},
    {"city": "Berlin", "country": "DE", "continent": "Europe", "region": "Central Europe", "lat": 52.52, "lon": 13.41},
    {"city": "Madrid", "country": "ES", "continent": "Europe", "region": "Southern Europe", "lat": 40.42, "lon": -3.70},
    {"city": "Rome", "country": "IT", "continent": "Europe", "region": "Southern Europe", "lat": 41.90, "lon": 12.50},
    {"city": "Amsterdam", "country": "NL", "continent": "Europe", "region": "Western Europe", "lat": 52.37, "lon": 4.90},
    {"city": "Moscow", "country": "RU", "continent": "Europe", "region": "Eastern Europe", "lat": 55.76, "lon": 37.62},
    {"city": "Stockholm", "country": "SE", "continent": "Europe", "region": "Northern Europe", "lat": 59.33, "lon": 18.07},
    {"city": "Vienna", "country": "AT", "continent": "Europe", "region": "Central Europe", "lat": 48.21, "lon": 16.37},
    {"city": "Zurich", "country": "CH", "continent": "Europe", "region": "Central Europe", "lat": 47.38, "lon": 8.54},
    {"city": "Istanbul", "country": "TR", "continent": "Europe", "region": "Eastern Europe", "lat": 41.01, "lon": 28.98},
    {"city": "Athens", "country": "GR", "continent": "Europe", "region": "Southern Europe", "lat": 37.98, "lon": 23.73},
    {"city": "Warsaw", "country": "PL", "continent": "Europe", "region": "Central Europe", "lat": 52.23, "lon": 21.01},
    {"city": "Dublin", "country": "IE", "continent": "Europe", "region": "Western Europe", "lat": 53.35, "lon": -6.26},
    {"city": "Lisbon", "country": "PT", "continent": "Europe", "region": "Southern Europe", "lat": 38.72, "lon": -9.14},
    {"city": "Oslo", "country": "NO", "continent": "Europe", "region": "Northern Europe", "lat": 59.91, "lon": 10.75},
    {"city": "Helsinki", "country": "FI", "continent": "Europe", "region": "Northern Europe", "lat": 60.17, "lon": 24.94},
    {"city": "Prague", "country": "CZ", "continent": "Europe", "region": "Central Europe", "lat": 50.08, "lon": 14.44},

    # ── Asia (20) ──
    {"city": "Tokyo", "country": "JP", "continent": "Asia", "region": "East Asia", "lat": 35.68, "lon": 139.69},
    {"city": "Beijing", "country": "CN", "continent": "Asia", "region": "East Asia", "lat": 39.90, "lon": 116.41},
    {"city": "Shanghai", "country": "CN", "continent": "Asia", "region": "East Asia", "lat": 31.23, "lon": 121.47},
    {"city": "Mumbai", "country": "IN", "continent": "Asia", "region": "South Asia", "lat": 19.08, "lon": 72.88},
    {"city": "Delhi", "country": "IN", "continent": "Asia", "region": "South Asia", "lat": 28.61, "lon": 77.21},
    {"city": "Bangkok", "country": "TH", "continent": "Asia", "region": "Southeast Asia", "lat": 13.76, "lon": 100.50},
    {"city": "Singapore", "country": "SG", "continent": "Asia", "region": "Southeast Asia", "lat": 1.35, "lon": 103.82},
    {"city": "Seoul", "country": "KR", "continent": "Asia", "region": "East Asia", "lat": 37.57, "lon": 126.98},
    {"city": "Dubai", "country": "AE", "continent": "Asia", "region": "Middle East", "lat": 25.20, "lon": 55.27},
    {"city": "Riyadh", "country": "SA", "continent": "Asia", "region": "Middle East", "lat": 24.69, "lon": 46.72},
    {"city": "Hong Kong", "country": "HK", "continent": "Asia", "region": "East Asia", "lat": 22.32, "lon": 114.17},
    {"city": "Jakarta", "country": "ID", "continent": "Asia", "region": "Southeast Asia", "lat": -6.21, "lon": 106.85},
    {"city": "Taipei", "country": "TW", "continent": "Asia", "region": "East Asia", "lat": 25.03, "lon": 121.57},
    {"city": "Tel Aviv", "country": "IL", "continent": "Asia", "region": "Middle East", "lat": 32.09, "lon": 34.78},
    {"city": "Karachi", "country": "PK", "continent": "Asia", "region": "South Asia", "lat": 24.86, "lon": 67.01},
    {"city": "Dhaka", "country": "BD", "continent": "Asia", "region": "South Asia", "lat": 23.81, "lon": 90.41},
    {"city": "Kuala Lumpur", "country": "MY", "continent": "Asia", "region": "Southeast Asia", "lat": 3.14, "lon": 101.69},
    {"city": "Manila", "country": "PH", "continent": "Asia", "region": "Southeast Asia", "lat": 14.60, "lon": 120.98},
    {"city": "Hanoi", "country": "VN", "continent": "Asia", "region": "Southeast Asia", "lat": 21.03, "lon": 105.85},
    {"city": "Doha", "country": "QA", "continent": "Asia", "region": "Middle East", "lat": 25.29, "lon": 51.53},

    # ── Africa (10) ──
    {"city": "Cairo", "country": "EG", "continent": "Africa", "region": "North Africa", "lat": 30.04, "lon": 31.24},
    {"city": "Lagos", "country": "NG", "continent": "Africa", "region": "West Africa", "lat": 6.52, "lon": 3.38},
    {"city": "Nairobi", "country": "KE", "continent": "Africa", "region": "East Africa", "lat": -1.29, "lon": 36.82},
    {"city": "Cape Town", "country": "ZA", "continent": "Africa", "region": "Southern Africa", "lat": -33.93, "lon": 18.42},
    {"city": "Johannesburg", "country": "ZA", "continent": "Africa", "region": "Southern Africa", "lat": -26.20, "lon": 28.04},
    {"city": "Casablanca", "country": "MA", "continent": "Africa", "region": "North Africa", "lat": 33.57, "lon": -7.59},
    {"city": "Accra", "country": "GH", "continent": "Africa", "region": "West Africa", "lat": 5.56, "lon": -0.19},
    {"city": "Addis Ababa", "country": "ET", "continent": "Africa", "region": "East Africa", "lat": 9.02, "lon": 38.75},
    {"city": "Dar es Salaam", "country": "TZ", "continent": "Africa", "region": "East Africa", "lat": -6.79, "lon": 39.28},
    {"city": "Algiers", "country": "DZ", "continent": "Africa", "region": "North Africa", "lat": 36.75, "lon": 3.04},

    # ── Oceania (5) ──
    {"city": "Sydney", "country": "AU", "continent": "Oceania", "region": "Australia", "lat": -33.87, "lon": 151.21},
    {"city": "Melbourne", "country": "AU", "continent": "Oceania", "region": "Australia", "lat": -37.81, "lon": 144.96},
    {"city": "Auckland", "country": "NZ", "continent": "Oceania", "region": "New Zealand", "lat": -36.85, "lon": 174.76},
    {"city": "Brisbane", "country": "AU", "continent": "Oceania", "region": "Australia", "lat": -27.47, "lon": 153.03},
    {"city": "Honolulu", "country": "US", "continent": "Oceania", "region": "Pacific", "lat": 21.31, "lon": -157.86},

    # ── Arctic/Extreme (4) ──
    {"city": "Anchorage", "country": "US", "continent": "North America", "region": "Alaska", "lat": 61.22, "lon": -149.90},
    {"city": "Reykjavik", "country": "IS", "continent": "Europe", "region": "Northern Europe", "lat": 64.15, "lon": -21.94},
    {"city": "Norilsk", "country": "RU", "continent": "Asia", "region": "Siberia", "lat": 69.35, "lon": 88.20},
    {"city": "Ushuaia", "country": "AR", "continent": "South America", "region": "South America South", "lat": -54.80, "lon": -68.30},
]

print(f"🌍 Monitoring {len(GLOBAL_CITIES)} cities across {len(set(c['continent'] for c in GLOBAL_CITIES))} continents")


# ============================================================
# AVRO SCHEMA
# ============================================================

AVRO_SCHEMA = {
    "type": "record",
    "name": "WeatherReading",
    "namespace": "com.climate.weather",
    "fields": [
        {"name": "city", "type": "string"},
        {"name": "country", "type": "string"},
        {"name": "continent", "type": "string"},
        {"name": "region", "type": "string"},
        {"name": "state", "type": ["null", "string"], "default": None},
        {"name": "latitude", "type": "double"},
        {"name": "longitude", "type": "double"},
        {"name": "temperature_fahrenheit", "type": "double"},
        {"name": "temperature_celsius", "type": "double"},
        {"name": "humidity_percent", "type": "double"},
        {"name": "pressure_hpa", "type": "double"},
        {"name": "wind_speed_mph", "type": "double"},
        {"name": "wind_direction_degrees", "type": "double"},
        {"name": "weather_condition", "type": "string"},
        {"name": "weather_description", "type": "string"},
        {"name": "cloud_cover_percent", "type": "double"},
        {"name": "visibility_miles", "type": "double"},
        {"name": "precipitation_mm", "type": "double"},
        {"name": "timestamp", "type": "string"},
        {"name": "ingestion_timestamp", "type": "string"},
    ]
}


# ============================================================
# KAFKA PRODUCER SETUP
# ============================================================

def create_producer():
    """Create Kafka producer with Avro serialization."""
    producer = Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "client.id": "global-weather-producer",
        "acks": "all",
    })
    return producer


def serialize_avro(record):
    """Serialize record to Avro bytes."""
    schema = fastavro.parse_schema(AVRO_SCHEMA)
    buf = BytesIO()
    fastavro.schemaless_writer(buf, schema, record)
    return buf.getvalue()


# ============================================================
# FETCH WEATHER FROM OPENWEATHERMAP
# ============================================================

def fetch_weather(city_info):
    """Fetch weather for a city from OpenWeatherMap API."""
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": city_info["lat"],
            "lon": city_info["lon"],
            "appid": OPENWEATHER_API_KEY,
            "units": "imperial"  # Fahrenheit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        temp_f = data["main"]["temp"]
        temp_c = round((temp_f - 32) * 5 / 9, 2)

        record = {
            "city": city_info["city"],
            "country": city_info["country"],
            "continent": city_info["continent"],
            "region": city_info["region"],
            "state": city_info.get("state"),
            "latitude": city_info["lat"],
            "longitude": city_info["lon"],
            "temperature_fahrenheit": round(temp_f, 2),
            "temperature_celsius": temp_c,
            "humidity_percent": float(data["main"]["humidity"]),
            "pressure_hpa": float(data["main"]["pressure"]),
            "wind_speed_mph": round(float(data["wind"]["speed"]), 2),
            "wind_direction_degrees": float(data["wind"].get("deg", 0)),
            "weather_condition": data["weather"][0]["main"],
            "weather_description": data["weather"][0]["description"],
            "cloud_cover_percent": float(data["clouds"]["all"]),
            "visibility_miles": round(float(data.get("visibility", 10000)) / 1609.34, 2),
            "precipitation_mm": float(data.get("rain", {}).get("1h", 0.0)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return record

    except Exception as e:
        print(f"  ❌ Error fetching {city_info['city']}: {e}")
        return None


# ============================================================
# DELIVERY CALLBACK
# ============================================================

def delivery_report(err, msg):
    if err:
        print(f"  ❌ Delivery failed: {err}")


# ============================================================
# MAIN PRODUCER LOOP
# ============================================================

def run_producer():
    """Main loop — fetches weather for all 80 cities and publishes to Kafka."""

    if not OPENWEATHER_API_KEY:
        print("❌ OPENWEATHER_API_KEY not set in .env")
        return

    producer = create_producer()
    cycle = 0

    print("=" * 60)
    print(f"🌍 GLOBAL CLIMATE PRODUCER — {len(GLOBAL_CITIES)} Cities")
    print(f"📡 Kafka: {KAFKA_BOOTSTRAP}")
    print(f"📋 Topic: {TOPIC}")
    print(f"⏱️  Poll interval: {POLL_INTERVAL}s")
    print("=" * 60)

    # Continent breakdown
    from collections import Counter
    continent_counts = Counter(c["continent"] for c in GLOBAL_CITIES)
    for continent, count in sorted(continent_counts.items()):
        print(f"  🌐 {continent}: {count} cities")
    print("=" * 60)

    while True:
        cycle += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n🔄 Cycle {cycle} [{now}] — Fetching {len(GLOBAL_CITIES)} cities...")

        success = 0
        failed = 0

        for city_info in GLOBAL_CITIES:
            record = fetch_weather(city_info)
            if record:
                try:
                    avro_bytes = serialize_avro(record)
                    producer.produce(
                        topic=TOPIC,
                        key=record["city"].encode("utf-8"),
                        value=avro_bytes,
                        callback=delivery_report,
                    )
                    success += 1
                except Exception as e:
                    print(f"  ❌ Kafka error for {city_info['city']}: {e}")
                    failed += 1
            else:
                failed += 1

            # Small delay to respect API rate limits (free tier: 60 calls/min)
            time.sleep(1.1)

        producer.flush()
        print(f"  ✅ Sent: {success} | ❌ Failed: {failed} | Total: {len(GLOBAL_CITIES)}")
        print(f"  ⏳ Next cycle in {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_producer()