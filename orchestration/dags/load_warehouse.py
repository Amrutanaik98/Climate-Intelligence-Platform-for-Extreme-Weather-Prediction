"""
Gold Layer → PostgreSQL Data Warehouse Loader (Fixed)
======================================================
Matches the actual Gold layer schema produced by spark_batch_gold.py

Run: python orchestration/dags/load_warehouse.py
"""

import os
import logging
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WarehouseLoader")

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "airflow"),
    "user": os.getenv("POSTGRES_USER", "airflow"),
    "password": os.getenv("POSTGRES_PASSWORD", "airflow"),
}

GOLD_PATH = "data/gold/weather_features"


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def create_schema(conn):
    """Create schema and all tables if they don't exist."""
    cur = conn.cursor()

    cur.execute("CREATE SCHEMA IF NOT EXISTS climate_warehouse")

    # dim_location
    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_location (
            location_key SERIAL PRIMARY KEY,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(50),
            latitude FLOAT,
            longitude FLOAT,
            region VARCHAR(50),
            UNIQUE(city, state)
        )
    """)

    # dim_time
    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_time (
            time_key SERIAL PRIMARY KEY,
            reading_timestamp TIMESTAMP,
            hour INT,
            day_of_week INT,
            month INT,
            year INT,
            is_daytime INT,
            UNIQUE(reading_timestamp)
        )
    """)

    # dim_weather_type
    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_weather_type (
            weather_type_key SERIAL PRIMARY KEY,
            weather_condition VARCHAR(100),
            weather_group VARCHAR(50),
            UNIQUE(weather_condition)
        )
    """)

    # fact_weather_readings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.fact_weather_readings (
            reading_key SERIAL PRIMARY KEY,
            location_key INT REFERENCES climate_warehouse.dim_location(location_key),
            time_key INT,
            weather_type_key INT,
            temperature_fahrenheit FLOAT,
            temperature_celsius FLOAT,
            humidity_percent FLOAT,
            pressure_hpa FLOAT,
            wind_speed_mph FLOAT,
            wind_direction_degrees FLOAT,
            precipitation_mm FLOAT,
            visibility_miles FLOAT,
            cloud_cover_percent FLOAT,
            heat_index FLOAT,
            wind_chill FLOAT,
            temperature_anomaly FLOAT,
            temp_anomaly_score FLOAT,
            is_extreme_weather INT,
            data_quality_score FLOAT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info("✅ Schema and tables created/verified")


def get_region(state):
    """Map states to regions."""
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
    return "Other"


def load_dimensions(conn, gold_df):
    """Load dimension tables from Gold data."""
    cur = conn.cursor()

    # ── dim_location ──
    cities = gold_df.drop_duplicates(subset=["city"])
    loc_count = 0
    for _, row in cities.iterrows():
        state = str(row.get("state", ""))
        region = get_region(state)
        cur.execute("""
            INSERT INTO climate_warehouse.dim_location (city, state, latitude, longitude, region)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (city, state) DO NOTHING
        """, (row["city"], state, row.get("latitude"), row.get("longitude"), region))
        loc_count += 1
    conn.commit()
    logger.info(f"✅ dim_location: {loc_count} cities loaded")

    # ── dim_weather_type ──
    if "weather_condition" in gold_df.columns:
        conditions = gold_df["weather_condition"].dropna().unique()
        group_map = {
            "Clear": "Clear", "Clouds": "Cloudy", "Rain": "Precipitation",
            "Drizzle": "Precipitation", "Snow": "Precipitation", "Mist": "Fog",
            "Fog": "Fog", "Haze": "Fog", "Thunderstorm": "Severe",
        }
        wt_count = 0
        for cond in conditions:
            group = group_map.get(str(cond), "Other")
            cur.execute("""
                INSERT INTO climate_warehouse.dim_weather_type (weather_condition, weather_group)
                VALUES (%s, %s) ON CONFLICT (weather_condition) DO NOTHING
            """, (str(cond), group))
            wt_count += 1
        conn.commit()
        logger.info(f"✅ dim_weather_type: {wt_count} conditions loaded")

    # ── Build lookup maps ──
    cur.execute("SELECT location_key, city FROM climate_warehouse.dim_location")
    loc_map = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("SELECT weather_type_key, weather_condition FROM climate_warehouse.dim_weather_type")
    wt_map = {row[1]: row[0] for row in cur.fetchall()}

    return loc_map, wt_map


def load_facts(conn, gold_df, loc_map, wt_map):
    """Load fact table from Gold data."""
    cur = conn.cursor()

    # Clear old data and reload
    cur.execute("TRUNCATE climate_warehouse.fact_weather_readings RESTART IDENTITY")

    loaded = 0
    skipped = 0

    for _, row in gold_df.iterrows():
        loc_key = loc_map.get(row.get("city"))
        wt_key = wt_map.get(str(row.get("weather_condition", "")))

        if not loc_key:
            skipped += 1
            continue

        try:
            cur.execute("""
                INSERT INTO climate_warehouse.fact_weather_readings
                (location_key, weather_type_key, temperature_fahrenheit, temperature_celsius,
                 humidity_percent, pressure_hpa, wind_speed_mph, wind_direction_degrees,
                 precipitation_mm, visibility_miles, cloud_cover_percent, heat_index,
                 wind_chill, temperature_anomaly, temp_anomaly_score, is_extreme_weather,
                 data_quality_score)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                loc_key, wt_key,
                row.get("temperature_fahrenheit"),
                row.get("temperature_celsius"),
                row.get("humidity_percent"),
                row.get("pressure_hpa"),
                row.get("wind_speed_mph"),
                row.get("wind_direction_degrees"),
                row.get("precipitation_mm"),
                row.get("visibility_miles"),
                row.get("cloud_cover_percent"),
                row.get("heat_index"),
                row.get("wind_chill"),
                row.get("temperature_anomaly"),
                row.get("temp_anomaly_score"),
                row.get("is_extreme_weather"),
                row.get("data_quality_score", 1.0),
            ))
            loaded += 1
        except Exception as e:
            logger.error(f"Error: {e}")
            skipped += 1

    conn.commit()
    logger.info(f"✅ fact_weather_readings: {loaded} loaded, {skipped} skipped")
    return loaded


def load_gold_to_warehouse():
    """Main: Read Gold Parquet → Load into Star Schema."""
    logger.info("=" * 60)
    logger.info("📦 WAREHOUSE LOADER: Gold → PostgreSQL Star Schema")
    logger.info("=" * 60)

    # Check Gold data exists
    if not os.path.exists(GOLD_PATH):
        logger.error(f"❌ Gold layer not found at {GOLD_PATH}. Run spark_batch_gold.py first.")
        return

    # Read Gold with pandas (fast, no Spark needed)
    logger.info(f"📂 Reading Gold data from: {GOLD_PATH}")
    gold_df = pd.read_parquet(GOLD_PATH)
    logger.info(f"📥 Read {len(gold_df)} records, {len(gold_df.columns)} columns")
    logger.info(f"   Cities: {gold_df['city'].nunique()}")
    logger.info(f"   Columns: {list(gold_df.columns)}")

    # Connect to PostgreSQL
    conn = get_conn()

    # Create schema and tables
    create_schema(conn)

    # Load dimensions
    loc_map, wt_map = load_dimensions(conn, gold_df)
    logger.info(f"   Location map: {len(loc_map)} cities")
    logger.info(f"   Weather type map: {len(wt_map)} conditions")

    # Load facts
    loaded = load_facts(conn, gold_df, loc_map, wt_map)

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather = 1")
    extreme = cur.fetchone()[0]
    logger.info(f"\n📊 Warehouse Summary:")
    logger.info(f"   Total records: {total}")
    logger.info(f"   Extreme events: {extreme}")
    logger.info(f"   Cities: {len(loc_map)}")

    conn.close()
    logger.info("\n✅ Warehouse loading complete!")


if __name__ == "__main__":
    load_gold_to_warehouse()