"""
Gold Layer → PostgreSQL Data Warehouse Loader
==============================================
Reads Parquet from Gold layer and loads into the
star schema (fact + dimension tables) in PostgreSQL.

This same code works with BigQuery — just change the
connection string and use google-cloud-bigquery library.
"""

import os
import logging

from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WarehouseLoader")

# Database connection
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "airflow"),
    "user": os.getenv("POSTGRES_USER", "airflow"),
    "password": os.getenv("POSTGRES_PASSWORD", "airflow"),
}


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def load_dim_location(conn, locations):
    """
    Load/update the location dimension table.
    Uses UPSERT (insert or update) — if the city already exists,
    just update the timestamp. This is SCD Type 1 (overwrite).
    """
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO climate_warehouse.dim_location (city, state, country, latitude, longitude, region)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (city, state)
        DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        RETURNING location_key;
    """

    location_keys = {}

    for loc in locations:
        # Assign region based on state
        region = get_region(loc.get("state", "Unknown"))

        cursor.execute(insert_sql, (
            loc["city"],
            loc.get("state", "Unknown"),
            loc.get("country", "US"),
            loc["latitude"],
            loc["longitude"],
            region,
        ))
        location_keys[(loc["city"], loc.get("state", "Unknown"))] = cursor.fetchone()[0]

    conn.commit()
    logger.info(f"✅ Loaded {len(location_keys)} locations into dim_location")
    return location_keys


def get_region(state):
    """Map US states to regions."""
    regions = {
        "Northeast": ["NY", "MA", "PA", "CT", "NJ", "ME", "NH", "VT", "RI"],
        "Southeast": ["FL", "GA", "NC", "SC", "VA", "TN", "AL", "MS", "LA", "AR", "KY"],
        "Midwest": ["IL", "OH", "MI", "IN", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"],
        "Southwest": ["TX", "AZ", "NM", "OK"],
        "West": ["CA", "WA", "OR", "NV", "CO", "UT", "ID", "MT", "WY"],
        "Pacific": ["HI", "AK"],
    }
    for region, states in regions.items():
        if state in states:
            return region
    return "Unknown"


def get_time_key(conn, timestamp_str):
    """Look up the time_key for a given timestamp."""
    cursor = conn.cursor()
    # Round to nearest hour for lookup
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        rounded = ts.replace(minute=0, second=0, microsecond=0)
        cursor.execute(
            "SELECT time_key FROM climate_warehouse.dim_time WHERE full_timestamp = %s",
            (rounded,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception:
        return None


def get_weather_type_key(conn, condition):
    """Look up or create weather type dimension entry."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT weather_type_key FROM climate_warehouse.dim_weather_type WHERE condition = %s",
        (condition,)
    )
    resultset = cursor.fetchone()
    if result:
        return result[0]

    # Insert new condition
    cursor.execute(
        """INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity)
           VALUES (%s, 'Unknown', 'Normal') RETURNING weather_type_key""",
        (condition,)
    )
    conn.commit()
    return cursor.fetchone()[0]


def load_fact_readings(conn, gold_data, location_keys):
   
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO climate_warehouse.fact_weather_readings (
            location_key, time_key, weather_type_key,
            temperature_fahrenheit, temperature_celsius,
            humidity_percent, pressure_hpa, wind_speed_mph,
            wind_direction_degrees, precipitation_mm,
            visibility_km, cloud_cover_percent, uv_index,
            heat_index, wind_chill, temp_anomaly, temp_anomaly_score,
            is_extreme_weather, is_heatwave, is_extreme_cold,
            is_high_wind, is_heavy_precipitation,
            source, quality_flag
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
    """

    records_loaded = 0
    records_skipped = 0

    for row in gold_data:
        # Look up dimension keys
        loc_key = location_keys.get(
            (row.get("city", ""), row.get("state", "Unknown")),
            None
        )
        time_key = get_time_key(conn, row.get("timestamp", ""))
        weather_key = get_weather_type_key(
            conn, row.get("weather_condition", "Unknown")
        )

        if loc_key is None:
            records_skipped += 1
            continue

        try:
            cursor.execute(insert_sql, (
                loc_key, time_key, weather_key,
                row.get("temperature_fahrenheit"),
                row.get("temperature_celsius"),
                row.get("humidity_percent"),
                row.get("pressure_hpa"),
                row.get("wind_speed_mph"),
                row.get("wind_direction_degrees"),
                row.get("precipitation_mm"),
                row.get("visibility_km"),
                row.get("cloud_cover_percent"),
                row.get("uv_index"),
                row.get("heat_index"),
                row.get("wind_chill"),
                row.get("temp_anomaly"),
                row.get("temp_anomaly_score"),
                row.get("is_extreme_weather", 0),
                row.get("is_heatwave", 0),
                row.get("is_extreme_cold", 0),
                row.get("is_high_wind", 0),
                row.get("is_heavy_precipitation", 0),
                row.get("source", "Unknown"),
                row.get("quality_flag", "Unknown"),
            ))
            records_loaded += 1
        except Exception as e:
            logger.error(f"Error loading record: {e}")
            records_skipped += 1

    conn.commit()
    logger.info(f"✅ Loaded {records_loaded} records into fact_weather_readings")
    logger.info(f"   Skipped: {records_skipped}")


def load_gold_to_warehouse():
    """
    Main function: Read Gold Parquet → Load into Star Schema.
    """
    logger.info("=" * 60)
    logger.info("📦 WAREHOUSE LOADER: Gold → PostgreSQL Star Schema")
    logger.info("=" * 60)

    # Read Gold data using PySpark
    try:
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder
            .appName("WarehouseLoader")
            .master("local[*]")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")

        gold_path = "data/gold/weather_features"
        if not os.path.exists(gold_path):
            logger.error("❌ Gold layer not found! Run Gold job first.")
            return

        gold_df = spark.read.parquet(gold_path)
        gold_data = [row.asDict() for row in gold_df.collect()]
        logger.info(f"📥 Read {len(gold_data)} records from Gold layer")
        spark.stop()

    except Exception as e:
        logger.error(f"❌ Error reading Gold data: {e}")
        return

    # Connect to PostgreSQL
    conn = get_connection()

    # Extract unique locations
    locations = []
    seen = set()
    for row in gold_data:
        key = (row.get("city", ""), row.get("state", "Unknown"))
        if key not in seen:
            locations.append({
                "city": row.get("city", ""),
                "state": row.get("state", "Unknown"),
                "country": row.get("country", "US"),
                "latitude": row.get("latitude", 0),
                "longitude": row.get("longitude", 0),
            })
            seen.add(key)

    # Load dimensions
    location_keys = load_dim_location(conn, locations)

    # Load facts
    load_fact_readings(conn, gold_data, location_keys)

    conn.close()
    logger.info("\n✅ Warehouse loading complete!")


if __name__ == "__main__":
    load_gold_to_warehouse()