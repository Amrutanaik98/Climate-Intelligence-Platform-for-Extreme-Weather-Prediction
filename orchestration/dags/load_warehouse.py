"""
Gold Layer → PostgreSQL Data Warehouse Loader (v4 FIXED)
========================================================
Fully aligned with:
  - create_wh.sql (UNIQUE city,country / condition / full_timestamp)
  - kafka_producer_openweather.py (80 global cities)
  - chatbot_app.py (query expectations)

Run: python orchestration/dags/load_warehouse.py
"""

import os
import logging
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
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


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_int(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ============================================================
# CREATE SCHEMA (matches create_wh.sql)
# ============================================================

def create_schema(conn):
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS climate_warehouse")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_location (
            location_key SERIAL PRIMARY KEY,
            city VARCHAR(100) NOT NULL,
            country VARCHAR(50) DEFAULT 'US',
            continent VARCHAR(50),
            state VARCHAR(50),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            region VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(city, country)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_time (
            time_key SERIAL PRIMARY KEY,
            full_timestamp TIMESTAMP NOT NULL,
            date DATE NOT NULL,
            year INT NOT NULL,
            quarter INT NOT NULL,
            month INT NOT NULL,
            month_name VARCHAR(20) NOT NULL,
            week_of_year INT NOT NULL,
            day_of_month INT NOT NULL,
            day_of_week INT NOT NULL,
            day_name VARCHAR(20) NOT NULL,
            hour INT NOT NULL,
            is_weekend BOOLEAN NOT NULL,
            season VARCHAR(10) NOT NULL,
            UNIQUE(full_timestamp)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_weather_type (
            weather_type_key SERIAL PRIMARY KEY,
            condition VARCHAR(50) NOT NULL,
            category VARCHAR(50),
            severity VARCHAR(20) DEFAULT 'Normal',
            description TEXT,
            UNIQUE(condition)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.fact_weather_readings (
            reading_key SERIAL PRIMARY KEY,
            location_key INT REFERENCES climate_warehouse.dim_location(location_key),
            time_key INT REFERENCES climate_warehouse.dim_time(time_key),
            weather_type_key INT REFERENCES climate_warehouse.dim_weather_type(weather_type_key),
            temperature_fahrenheit DOUBLE PRECISION,
            temperature_celsius DOUBLE PRECISION,
            humidity_percent DOUBLE PRECISION,
            pressure_hpa DOUBLE PRECISION,
            wind_speed_mph DOUBLE PRECISION,
            wind_direction_degrees INT,
            precipitation_mm DOUBLE PRECISION,
            visibility_km DOUBLE PRECISION,
            cloud_cover_percent INT,
            uv_index DOUBLE PRECISION,
            heat_index DOUBLE PRECISION,
            wind_chill DOUBLE PRECISION,
            temp_anomaly DOUBLE PRECISION,
            temp_anomaly_score DOUBLE PRECISION,
            is_extreme_weather INT DEFAULT 0,
            is_heatwave INT DEFAULT 0,
            is_extreme_cold INT DEFAULT 0,
            is_high_wind INT DEFAULT 0,
            is_heavy_precipitation INT DEFAULT 0,
            source VARCHAR(50),
            quality_flag VARCHAR(50),
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_fact_location ON climate_warehouse.fact_weather_readings(location_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_time ON climate_warehouse.fact_weather_readings(time_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_weather_type ON climate_warehouse.fact_weather_readings(weather_type_key)",
        "CREATE INDEX IF NOT EXISTS idx_fact_extreme ON climate_warehouse.fact_weather_readings(is_extreme_weather)",
    ]:
        cur.execute(idx_sql)

    conn.commit()
    logger.info("✅ Schema and tables created/verified")


# ============================================================
# POPULATE dim_time (if empty)
# ============================================================

def populate_dim_time(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.dim_time")
    if cur.fetchone()[0] == 0:
        logger.info("Populating dim_time (2025-2026 hourly)...")
        cur.execute("""
            INSERT INTO climate_warehouse.dim_time (
                full_timestamp, date, year, quarter, month, month_name,
                week_of_year, day_of_month, day_of_week, day_name,
                hour, is_weekend, season
            )
            SELECT ts, ts::date,
                EXTRACT(YEAR FROM ts)::int, EXTRACT(QUARTER FROM ts)::int,
                EXTRACT(MONTH FROM ts)::int, TO_CHAR(ts, 'Month'),
                EXTRACT(WEEK FROM ts)::int, EXTRACT(DAY FROM ts)::int,
                EXTRACT(DOW FROM ts)::int, TO_CHAR(ts, 'Day'),
                EXTRACT(HOUR FROM ts)::int,
                EXTRACT(DOW FROM ts) IN (0, 6),
                CASE
                    WHEN EXTRACT(MONTH FROM ts) IN (12, 1, 2) THEN 'Winter'
                    WHEN EXTRACT(MONTH FROM ts) IN (3, 4, 5) THEN 'Spring'
                    WHEN EXTRACT(MONTH FROM ts) IN (6, 7, 8) THEN 'Summer'
                    ELSE 'Fall'
                END
            FROM generate_series(
                '2025-01-01 00:00:00'::timestamp,
                '2026-12-31 23:00:00'::timestamp,
                '1 hour'::interval
            ) AS ts
            ON CONFLICT (full_timestamp) DO NOTHING
        """)
        conn.commit()
        logger.info("✅ dim_time populated")
    else:
        logger.info("✅ dim_time already populated")


# ============================================================
# LOAD DIMENSIONS
# ============================================================

def load_dimensions(conn, gold_df):
    cur = conn.cursor()

    # ── dim_location: uses (city, country) unique key ──
    loc_cols = [c for c in ["city", "country", "continent", "state", "latitude", "longitude", "region"]
                if c in gold_df.columns]
    cities = gold_df.drop_duplicates(subset=["city"])[loc_cols].copy()
    loc_count = 0

    for _, row in cities.iterrows():
        city = row.get("city", "")
        country = row.get("country", "US")
        continent = row.get("continent", None)
        state = row.get("state", None)
        lat = row.get("latitude", None)
        lon = row.get("longitude", None)
        region = row.get("region", None)

        cur.execute("""
            INSERT INTO climate_warehouse.dim_location
                (city, country, continent, state, latitude, longitude, region)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (city, country) DO UPDATE SET
                continent = EXCLUDED.continent,
                state = EXCLUDED.state,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                region = EXCLUDED.region,
                updated_at = CURRENT_TIMESTAMP
        """, (city, country, continent, state, lat, lon, region))
        loc_count += 1

    conn.commit()
    logger.info(f"✅ dim_location: {loc_count} cities loaded")

    # ── dim_weather_type: uses condition (not weather_condition) ──
    known_conditions = [
        ('Clear', 'Fair', 'Normal', 'Clear skies'),
        ('Clouds', 'Overcast', 'Normal', 'Cloudy skies'),
        ('Rain', 'Precipitation', 'Moderate', 'Rainfall'),
        ('Drizzle', 'Precipitation', 'Normal', 'Light rain'),
        ('Thunderstorm', 'Storm', 'Severe', 'Thunder and lightning'),
        ('Snow', 'Precipitation', 'Moderate', 'Snowfall'),
        ('Mist', 'Visibility', 'Normal', 'Light mist'),
        ('Fog', 'Visibility', 'Moderate', 'Reduced visibility'),
        ('Haze', 'Visibility', 'Normal', 'Light haze'),
        ('Smoke', 'Visibility', 'Moderate', 'Smoke'),
        ('Dust', 'Visibility', 'Moderate', 'Dust in air'),
        ('Sand', 'Visibility', 'Moderate', 'Sand storm'),
        ('Squall', 'Wind', 'Severe', 'Sudden strong wind'),
        ('Tornado', 'Storm', 'Extreme', 'Tornado conditions'),
        ('Unknown', 'Unknown', 'Normal', 'Condition not determined'),
    ]
    for cond, cat, sev, desc in known_conditions:
        cur.execute("""
            INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
            VALUES (%s, %s, %s, %s) ON CONFLICT (condition) DO NOTHING
        """, (cond, cat, sev, desc))

    # Also insert conditions from Gold data
    wt_count = 0
    if "weather_condition" in gold_df.columns:
        category_map = {
            "Clear": "Fair", "Clouds": "Overcast", "Rain": "Precipitation",
            "Drizzle": "Precipitation", "Snow": "Precipitation", "Mist": "Visibility",
            "Fog": "Visibility", "Haze": "Visibility", "Thunderstorm": "Storm",
            "Smoke": "Visibility", "Dust": "Visibility", "Sand": "Visibility",
            "Squall": "Wind", "Tornado": "Storm",
        }
        for cond in gold_df["weather_condition"].dropna().unique():
            cond_str = str(cond).strip()
            if not cond_str:
                continue
            cat = category_map.get(cond_str, "Other")
            cur.execute("""
                INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
                VALUES (%s, %s, %s, %s) ON CONFLICT (condition) DO NOTHING
            """, (cond_str, cat, "Normal", f"{cond_str} conditions"))
            wt_count += 1

    conn.commit()
    logger.info(f"✅ dim_weather_type: {len(known_conditions) + wt_count} conditions loaded")

    # ── Build lookup maps ──
    cur.execute("SELECT location_key, city, country FROM climate_warehouse.dim_location")
    loc_map = {}
    for row in cur.fetchall():
        loc_map[(row[1], row[2])] = row[0]   # (city, country) → key
        loc_map[row[1]] = row[0]               # city → key (fallback)

    cur.execute("SELECT weather_type_key, condition FROM climate_warehouse.dim_weather_type")
    wt_map = {row[1]: row[0] for row in cur.fetchall()}

    return loc_map, wt_map


# ============================================================
# LOAD FACTS (batch insert, time_key populated)
# ============================================================

def load_facts(conn, gold_df, loc_map, wt_map):
    cur = conn.cursor()

    # Build time_key lookup
    cur.execute("SELECT time_key, full_timestamp FROM climate_warehouse.dim_time")
    time_map = {row[1]: row[0] for row in cur.fetchall()}

    # Find timestamp column
    ts_col = None
    for candidate in ["timestamp", "reading_timestamp"]:
        if candidate in gold_df.columns:
            ts_col = candidate
            break

    # Clear old data
    cur.execute("TRUNCATE climate_warehouse.fact_weather_readings RESTART IDENTITY")

    loaded = 0
    skipped = 0
    batch = []
    batch_size = 200

    for _, row in gold_df.iterrows():
        city = row.get("city", "")
        country = row.get("country", "US")

        # Location lookup: (city, country) first, city fallback
        loc_key = loc_map.get((city, country)) or loc_map.get(city)
        if not loc_key:
            skipped += 1
            continue

        # time_key: round timestamp to nearest hour → match dim_time
        time_key = None
        if ts_col and pd.notna(row.get(ts_col)):
            try:
                ts = pd.Timestamp(row[ts_col])
                rounded = ts.floor("h").to_pydatetime().replace(tzinfo=None)
                time_key = time_map.get(rounded)
            except Exception:
                time_key = None

        # weather_type_key: weather_condition → condition
        wt_key = None
        weather_cond = str(row.get("weather_condition", "")).strip()
        if weather_cond:
            wt_key = wt_map.get(weather_cond, wt_map.get("Unknown"))

        # visibility: convert miles → km if needed
        vis_km = safe_float(row.get("visibility_km"))
        if vis_km is None or vis_km == 0:
            vis_miles = safe_float(row.get("visibility_miles"))
            if vis_miles is not None:
                vis_km = round(vis_miles * 1.60934, 2)

        batch.append((
            loc_key,
            time_key,
            wt_key,
            safe_float(row.get("temperature_fahrenheit")),
            safe_float(row.get("temperature_celsius")),
            safe_float(row.get("humidity_percent")),
            safe_float(row.get("pressure_hpa")),
            safe_float(row.get("wind_speed_mph")),
            safe_int(row.get("wind_direction_degrees")),
            safe_float(row.get("precipitation_mm")),
            vis_km,
            safe_int(row.get("cloud_cover_percent")),
            None,  # uv_index (producer doesn't send)
            safe_float(row.get("heat_index")),
            safe_float(row.get("wind_chill")),
            safe_float(row.get("temperature_anomaly")),
            safe_float(row.get("temp_anomaly_score")),
            safe_int(row.get("is_extreme_weather", 0)),
            safe_int(row.get("is_heatwave", 0)),
            safe_int(row.get("is_extreme_cold", 0)),
            safe_int(row.get("is_high_wind", 0)),
            safe_int(row.get("is_heavy_precipitation", 0)),
            "openweathermap",
            str(row.get("quality_flag", row.get("data_quality_flag", "PASSED"))),
        ))
        loaded += 1

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO climate_warehouse.fact_weather_readings
                (location_key, time_key, weather_type_key,
                 temperature_fahrenheit, temperature_celsius,
                 humidity_percent, pressure_hpa, wind_speed_mph,
                 wind_direction_degrees, precipitation_mm, visibility_km,
                 cloud_cover_percent, uv_index, heat_index, wind_chill,
                 temp_anomaly, temp_anomaly_score,
                 is_extreme_weather, is_heatwave, is_extreme_cold,
                 is_high_wind, is_heavy_precipitation,
                 source, quality_flag)
                VALUES %s
            """, batch)
            batch = []

    # Flush remaining
    if batch:
        execute_values(cur, """
            INSERT INTO climate_warehouse.fact_weather_readings
            (location_key, time_key, weather_type_key,
             temperature_fahrenheit, temperature_celsius,
             humidity_percent, pressure_hpa, wind_speed_mph,
             wind_direction_degrees, precipitation_mm, visibility_km,
             cloud_cover_percent, uv_index, heat_index, wind_chill,
             temp_anomaly, temp_anomaly_score,
             is_extreme_weather, is_heatwave, is_extreme_cold,
             is_high_wind, is_heavy_precipitation,
             source, quality_flag)
            VALUES %s
        """, batch)

    conn.commit()
    logger.info(f"✅ fact_weather_readings: {loaded} loaded, {skipped} skipped")
    return loaded


# ============================================================
# MAIN
# ============================================================

def load_gold_to_warehouse():
    logger.info("=" * 60)
    logger.info("📦 WAREHOUSE LOADER: Gold → PostgreSQL Star Schema")
    logger.info("=" * 60)

    if not os.path.exists(GOLD_PATH):
        logger.error(f"❌ Gold layer not found at {GOLD_PATH}. Run spark_batch_gold.py first.")
        return

    logger.info(f"📂 Reading Gold data from: {GOLD_PATH}")
    gold_df = pd.read_parquet(GOLD_PATH)
    logger.info(f"📥 Read {len(gold_df)} records, {len(gold_df.columns)} columns")
    logger.info(f"   Cities: {gold_df['city'].nunique()}")

    conn = get_conn()

    # Create schema + tables
    create_schema(conn)

    # Populate dim_time if empty
    populate_dim_time(conn)

    # Load dimensions
    loc_map, wt_map = load_dimensions(conn, gold_df)
    logger.info(f"   Location map: {len(loc_map)} entries")
    logger.info(f"   Weather type map: {len(wt_map)} conditions")

    # Load facts
    loaded = load_facts(conn, gold_df, loc_map, wt_map)

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather = 1")
    extreme = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE time_key IS NOT NULL")
    has_time = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT l.continent) FROM climate_warehouse.dim_location l")
    continents = cur.fetchone()[0]

    logger.info(f"\n📊 Warehouse Summary:")
    logger.info(f"   Total records: {total}")
    logger.info(f"   With time_key: {has_time}")
    logger.info(f"   Extreme events: {extreme}")
    logger.info(f"   Cities: {gold_df['city'].nunique()}")
    logger.info(f"   Continents: {continents}")

    conn.close()
    logger.info("\n✅ Warehouse loading complete!")


if __name__ == "__main__":
    load_gold_to_warehouse()