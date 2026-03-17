"""
Climate Intelligence Platform - Main Pipeline DAG (v5 + GCS)
=============================================================
Fully aligned with:
  - kafka_producer_openweather.py (80 global cities)
  - create_wh.sql (star schema)
  - chatbot_app.py (Streamlit UI)

NEW in v5:
  - Automatic GCS upload after Silver and Gold stages
  - Bronze upload option (from Spark streaming output)
  - GCS bucket structure mirrors local: bronze/, silver/, gold/

Schedule: Daily at 6:00 AM UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.log.logging_mixin import LoggingMixin

log = LoggingMixin().log

# ============================================================
# DAG CONFIGURATION
# ============================================================

default_args = {
    "owner": "climate-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "start_date": datetime(2025, 1, 1),
}

# ============================================================
# PATHS — Local
# ============================================================
PROJECT_ROOT = "/opt/airflow"
DATA_DIR = f"{PROJECT_ROOT}/data"
BRONZE_PATH = f"{DATA_DIR}/bronze/weather_readings"
SILVER_PATH = f"{DATA_DIR}/silver/weather_readings"
GOLD_PATH = f"{DATA_DIR}/gold/weather_features"

# ============================================================
# GCS CONFIG — 3 separate buckets (one per layer)
# ============================================================
import os
GCS_BUCKET_BRONZE = os.getenv("GCS_BUCKET_BRONZE", "climate-intelligence-485704-climate-bronze")
GCS_BUCKET_SILVER = os.getenv("GCS_BUCKET_SILVER", "climate-intelligence-485704-climate-silver")
GCS_BUCKET_GOLD   = os.getenv("GCS_BUCKET_GOLD",   "climate-intelligence-485704-climate-gold")
GCS_BRONZE_PREFIX = "weather_readings"
GCS_SILVER_PREFIX = "weather_readings"
GCS_GOLD_PREFIX   = "weather_features"

# Database config
DB_CONFIG = dict(host="postgres", port=5432, database="airflow", user="airflow", password="airflow")


# ============================================================
# GCS UPLOAD HELPER
# ============================================================

def upload_folder_to_gcs(local_path, bucket_name, gcs_prefix=""):
    """Upload an entire local folder (parquet files) to a GCS bucket.

    Structure on GCS:
      gs://climate-intelligence-485704-climate-bronze/weather_readings/reading_date=2026-03-15/part-00000.parquet
      gs://climate-intelligence-485704-climate-silver/weather_readings/reading_date=2026-03-15/part-00000.parquet
      gs://climate-intelligence-485704-climate-gold/weather_features/reading_date=2026-03-15/part-00000.parquet
    """
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    uploaded = 0
    skipped = 0

    for root, dirs, files in os.walk(local_path):
        for filename in files:
            local_file = os.path.join(root, filename)
            relative_path = os.path.relpath(local_file, local_path)
            gcs_path = f"{gcs_prefix}/{relative_path}".replace("\\", "/") if gcs_prefix else relative_path.replace("\\", "/")

            blob = bucket.blob(gcs_path)

            # Only upload if file is newer than GCS version
            if blob.exists():
                blob.reload()
                local_mtime = datetime.fromtimestamp(os.path.getmtime(local_file))
                gcs_mtime = blob.updated.replace(tzinfo=None)
                if local_mtime <= gcs_mtime:
                    skipped += 1
                    continue

            blob.upload_from_filename(local_file)
            uploaded += 1

    log.info(f"GCS upload to gs://{bucket_name}/{gcs_prefix}: {uploaded} uploaded, {skipped} unchanged")
    return uploaded


# ============================================================
# TASK 1: VERIFY BRONZE DATA EXISTS
# ============================================================

def verify_bronze_data(**context):
    """Check that Bronze layer has parquet data."""
    log.info(f"Checking Bronze path: {BRONZE_PATH}")

    if not os.path.exists(BRONZE_PATH):
        raise FileNotFoundError(
            f"Bronze path not found: {BRONZE_PATH}\n"
            f"Make sure:\n"
            f"  1. Kafka producer has been run\n"
            f"  2. Spark streaming has written to Bronze\n"
            f"  3. 'data/' folder is mounted in docker-compose.yml"
        )

    parquet_files = []
    for root, dirs, files in os.walk(BRONZE_PATH):
        for f in files:
            if f.endswith(".parquet"):
                parquet_files.append(os.path.join(root, f))

    if len(parquet_files) == 0:
        raise FileNotFoundError(f"No parquet files in {BRONZE_PATH}.")

    log.info(f"Found {len(parquet_files)} parquet files in Bronze layer")
    return len(parquet_files)


# ============================================================
# TASK 2: BRONZE → SILVER (Cleaning)
# ============================================================

def run_bronze_to_silver(**context):
    """Bronze → Silver: Clean, validate, deduplicate."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    log.info("Starting Bronze → Silver transformation...")

    spark = SparkSession.builder \
        .appName("ClimateETL-BronzeToSilver") \
        .master("local[*]") \
        .config("spark.driver.memory", "1g") \
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        log.info(f"Reading from: {BRONZE_PATH}")
        bronze_df = spark.read.parquet(BRONZE_PATH)
        bronze_count = bronze_df.count()
        log.info(f"Bronze records: {bronze_count}")

        if bronze_count == 0:
            raise ValueError("Bronze layer is empty!")

        silver_df = bronze_df

        # 1. Deduplicate by city + timestamp
        if "city" in silver_df.columns and "timestamp" in silver_df.columns:
            silver_df = silver_df.dropDuplicates(["city", "timestamp"])
        elif "city" in silver_df.columns and "reading_timestamp" in silver_df.columns:
            silver_df = silver_df.dropDuplicates(["city", "reading_timestamp"])

        # 2. Drop null critical fields
        critical_cols = ["city", "temperature_fahrenheit"]
        existing_critical = [c for c in critical_cols if c in silver_df.columns]
        if existing_critical:
            silver_df = silver_df.dropna(subset=existing_critical)

        # 3. Range validation
        if "temperature_fahrenheit" in silver_df.columns:
            silver_df = silver_df.filter(
                (F.col("temperature_fahrenheit") >= -80) &
                (F.col("temperature_fahrenheit") <= 140)
            )
        if "humidity_percent" in silver_df.columns:
            silver_df = silver_df.withColumn(
                "humidity_percent",
                F.when(F.col("humidity_percent") < 0, 0)
                 .when(F.col("humidity_percent") > 100, 100)
                 .otherwise(F.col("humidity_percent"))
            )

        # 4. Processing metadata
        silver_df = silver_df.withColumn("processed_at", F.current_timestamp())
        silver_df = silver_df.withColumn("data_quality_flag", F.lit("PASSED"))

        # 5. Partition column
        if "timestamp" in silver_df.columns:
            silver_df = silver_df.withColumn("reading_date", F.to_date("timestamp"))
        elif "reading_timestamp" in silver_df.columns:
            silver_df = silver_df.withColumn("reading_date", F.to_date("reading_timestamp"))
        else:
            silver_df = silver_df.withColumn("reading_date", F.current_date())

        silver_count = silver_df.count()
        log.info(f"Silver records: {silver_count} (dropped {bronze_count - silver_count})")

        silver_df.write \
            .mode("overwrite") \
            .partitionBy("reading_date") \
            .parquet(SILVER_PATH)

        log.info(f"Bronze → Silver complete: {silver_count} records")

    finally:
        spark.stop()


# ============================================================
# TASK 2B: UPLOAD BRONZE + SILVER TO GCS
# ============================================================

def upload_bronze_silver_to_gcs(**context):
    """Upload Bronze and Silver parquet to their separate GCS buckets."""
    log.info("Uploading Bronze + Silver to GCS...")
    bronze_count = upload_folder_to_gcs(BRONZE_PATH, GCS_BUCKET_BRONZE, GCS_BRONZE_PREFIX)
    silver_count = upload_folder_to_gcs(SILVER_PATH, GCS_BUCKET_SILVER, GCS_SILVER_PREFIX)
    log.info(f"GCS upload complete: Bronze={bronze_count}, Silver={silver_count}")


# ============================================================
# TASK 3: SILVER → GOLD (Feature Engineering)
# ============================================================

def run_silver_to_gold(**context):
    """Silver → Gold: Feature engineering + derived columns."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    log.info("Starting Silver → Gold transformation...")

    spark = SparkSession.builder \
        .appName("ClimateETL-SilverToGold") \
        .master("local[*]") \
        .config("spark.driver.memory", "1g") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        log.info(f"Reading from: {SILVER_PATH}")
        silver_df = spark.read.parquet(SILVER_PATH)
        silver_count = silver_df.count()
        log.info(f"Silver records: {silver_count}")

        gold_df = silver_df

        # 1. Temperature Celsius
        if "temperature_celsius" not in gold_df.columns and "temperature_fahrenheit" in gold_df.columns:
            gold_df = gold_df.withColumn(
                "temperature_celsius",
                F.round((F.col("temperature_fahrenheit") - 32) * 5 / 9, 2)
            )

        # 2. Heat Index (Rothfusz formula)
        if "temperature_fahrenheit" in gold_df.columns and "humidity_percent" in gold_df.columns:
            gold_df = gold_df.withColumn(
                "heat_index",
                F.when(F.col("temperature_fahrenheit") >= 80,
                    F.round(-42.379 + 2.04901523 * F.col("temperature_fahrenheit")
                    + 10.14333127 * F.col("humidity_percent")
                    - 0.22475541 * F.col("temperature_fahrenheit") * F.col("humidity_percent")
                    - 0.00683783 * F.col("temperature_fahrenheit") ** 2
                    - 0.05481717 * F.col("humidity_percent") ** 2
                    + 0.00122874 * F.col("temperature_fahrenheit") ** 2 * F.col("humidity_percent")
                    + 0.00085282 * F.col("temperature_fahrenheit") * F.col("humidity_percent") ** 2
                    - 0.00000199 * F.col("temperature_fahrenheit") ** 2 * F.col("humidity_percent") ** 2, 2)
                ).otherwise(F.col("temperature_fahrenheit"))
            )

        # 3. Wind Chill
        if "temperature_fahrenheit" in gold_df.columns and "wind_speed_mph" in gold_df.columns:
            gold_df = gold_df.withColumn(
                "wind_chill",
                F.when(
                    (F.col("temperature_fahrenheit") <= 50) & (F.col("wind_speed_mph") > 3),
                    F.round(35.74 + 0.6215 * F.col("temperature_fahrenheit")
                    - 35.75 * F.pow(F.col("wind_speed_mph"), 0.16)
                    + 0.4275 * F.col("temperature_fahrenheit") * F.pow(F.col("wind_speed_mph"), 0.16), 2)
                ).otherwise(F.col("temperature_fahrenheit"))
            )

        # 4. City-level statistics (anomaly detection)
        if "city" in gold_df.columns and "temperature_fahrenheit" in gold_df.columns:
            city_window = Window.partitionBy("city")
            gold_df = gold_df.withColumn("city_avg_temp", F.round(F.avg("temperature_fahrenheit").over(city_window), 2))
            gold_df = gold_df.withColumn("city_min_temp", F.round(F.min("temperature_fahrenheit").over(city_window), 2))
            gold_df = gold_df.withColumn("city_max_temp", F.round(F.max("temperature_fahrenheit").over(city_window), 2))
            gold_df = gold_df.withColumn("city_stddev_temp", F.round(F.stddev("temperature_fahrenheit").over(city_window), 2))
            gold_df = gold_df.withColumn(
                "temperature_anomaly",
                F.round(F.col("temperature_fahrenheit") - F.col("city_avg_temp"), 2)
            )
            gold_df = gold_df.withColumn(
                "temp_anomaly_score",
                F.when(F.col("city_stddev_temp") > 0,
                    F.round(F.abs(F.col("temperature_anomaly")) / F.col("city_stddev_temp"), 2)
                ).otherwise(F.lit(0.0))
            )

        # 5. Time features
        ts_col = None
        for candidate in ["timestamp", "reading_timestamp"]:
            if candidate in gold_df.columns:
                ts_col = candidate
                break
        if ts_col:
            gold_df = gold_df.withColumn("hour_of_day", F.hour(F.col(ts_col)))
            gold_df = gold_df.withColumn("day_of_week", F.dayofweek(F.col(ts_col)))
            gold_df = gold_df.withColumn("month", F.month(F.col(ts_col)))
            gold_df = gold_df.withColumn("is_daytime",
                F.when((F.hour(F.col(ts_col)) >= 6) & (F.hour(F.col(ts_col)) < 20), 1).otherwise(0))

        # 6. Visibility in km
        if "visibility_miles" in gold_df.columns and "visibility_km" not in gold_df.columns:
            gold_df = gold_df.withColumn(
                "visibility_km",
                F.round(F.col("visibility_miles") * 1.60934, 2)
            )
        elif "visibility_km" not in gold_df.columns:
            gold_df = gold_df.withColumn("visibility_km", F.lit(None).cast("double"))

        # 7. Extreme weather flags
        gold_df = gold_df.withColumn(
            "is_extreme_weather",
            F.when(
                (F.col("temperature_fahrenheit") > 100) |
                (F.col("temperature_fahrenheit") < 10) |
                (F.col("wind_speed_mph") > 50) |
                (F.col("temp_anomaly_score") > 2.5),
                F.lit(1)
            ).otherwise(F.lit(0))
        )
        gold_df = gold_df.withColumn("is_heatwave",
            F.when(F.col("temperature_fahrenheit") > 100, 1).otherwise(0))
        gold_df = gold_df.withColumn("is_extreme_cold",
            F.when(F.col("temperature_fahrenheit") < 10, 1).otherwise(0))
        gold_df = gold_df.withColumn("is_high_wind",
            F.when(F.col("wind_speed_mph") > 50, 1).otherwise(0))
        if "precipitation_mm" in gold_df.columns:
            gold_df = gold_df.withColumn("is_heavy_precipitation",
                F.when(F.col("precipitation_mm") > 10, 1).otherwise(0))
        else:
            gold_df = gold_df.withColumn("is_heavy_precipitation", F.lit(0))

        # Fill nulls in numeric columns
        numeric_cols = [f.name for f in gold_df.schema.fields
                        if str(f.dataType) in ("DoubleType()", "FloatType()", "IntegerType()", "LongType()")]
        for c in numeric_cols:
            gold_df = gold_df.fillna({c: 0})

        gold_count = gold_df.count()
        gold_cols = len(gold_df.columns)
        log.info(f"Gold: {gold_count} records, {gold_cols} columns")

        gold_df.write \
            .mode("overwrite") \
            .partitionBy("reading_date") \
            .parquet(GOLD_PATH)

        log.info(f"Silver → Gold complete: {gold_count} records, {gold_cols} features")

    finally:
        spark.stop()


# ============================================================
# TASK 3B: UPLOAD GOLD TO GCS
# ============================================================

def upload_gold_to_gcs(**context):
    """Upload Gold parquet to its GCS bucket."""
    log.info("Uploading Gold to GCS...")
    gold_count = upload_folder_to_gcs(GOLD_PATH, GCS_BUCKET_GOLD, GCS_GOLD_PREFIX)
    log.info(f"GCS Gold upload complete: {gold_count} files")


# ============================================================
# TASK 4: GOLD → WAREHOUSE
# ============================================================

def run_warehouse_load(**context):
    """Load Gold Parquet into PostgreSQL Star Schema."""
    import psycopg2
    from psycopg2.extras import execute_values
    import pandas as pd
    import numpy as np

    log.info("Starting Gold → Warehouse load...")

    gold_df = pd.read_parquet(GOLD_PATH)
    log.info(f"Gold records to load: {len(gold_df)}")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # ── Ensure schema exists ──
    cursor.execute("CREATE SCHEMA IF NOT EXISTS climate_warehouse")
    conn.commit()

    # ── Create tables if they don't exist ──
    cursor.execute("""
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

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_weather_type (
            weather_type_key SERIAL PRIMARY KEY,
            condition VARCHAR(50) NOT NULL,
            category VARCHAR(50),
            severity VARCHAR(20) DEFAULT 'Normal',
            description TEXT,
            UNIQUE(condition)
        )
    """)

    cursor.execute("""
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
        cursor.execute(idx_sql)
    conn.commit()

    # ── Populate dim_time if empty ──
    cursor.execute("SELECT COUNT(*) FROM climate_warehouse.dim_time")
    if cursor.fetchone()[0] == 0:
        log.info("Populating dim_time...")
        cursor.execute("""
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
        log.info("dim_time populated")

    # ── Populate dim_weather_type ──
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
        cursor.execute("""
            INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
            VALUES (%s, %s, %s, %s) ON CONFLICT (condition) DO NOTHING
        """, (cond, cat, sev, desc))

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
            cursor.execute("""
                INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
                VALUES (%s, %s, %s, %s) ON CONFLICT (condition) DO NOTHING
            """, (cond_str, cat, "Normal", f"{cond_str} conditions"))
    conn.commit()

    # ── Load dim_location from data ──
    if "city" in gold_df.columns:
        loc_cols = [c for c in ["city", "country", "continent", "state", "latitude", "longitude", "region"]
                    if c in gold_df.columns]
        cities = gold_df.drop_duplicates(subset=["city"])[loc_cols].copy()

        for _, row in cities.iterrows():
            cursor.execute("""
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
            """, (row.get("city",""), row.get("country","US"), row.get("continent"),
                  row.get("state"), row.get("latitude"), row.get("longitude"), row.get("region")))

    conn.commit()

    # ── Build lookup maps ──
    cursor.execute("SELECT location_key, city, country FROM climate_warehouse.dim_location")
    loc_map = {}
    for row in cursor.fetchall():
        loc_map[(row[1], row[2])] = row[0]
        loc_map[row[1]] = row[0]

    cursor.execute("SELECT weather_type_key, condition FROM climate_warehouse.dim_weather_type")
    wt_map = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT time_key, full_timestamp FROM climate_warehouse.dim_time")
    time_map = {row[1]: row[0] for row in cursor.fetchall()}

    ts_col = None
    for candidate in ["timestamp", "reading_timestamp"]:
        if candidate in gold_df.columns:
            ts_col = candidate
            break

    # ── Clear and reload ──
    cursor.execute("TRUNCATE climate_warehouse.fact_weather_readings RESTART IDENTITY")
    conn.commit()

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

    loaded = 0
    skipped = 0
    batch = []
    batch_size = 200

    for _, row in gold_df.iterrows():
        city = row.get("city", "")
        country = row.get("country", "US")
        loc_key = loc_map.get((city, country)) or loc_map.get(city)
        if not loc_key:
            skipped += 1
            continue

        time_key = None
        if ts_col and pd.notna(row.get(ts_col)):
            try:
                ts = pd.Timestamp(row[ts_col])
                rounded = ts.floor("h").to_pydatetime().replace(tzinfo=None)
                time_key = time_map.get(rounded)
            except Exception:
                time_key = None

        wt_key = None
        weather_cond = str(row.get("weather_condition", "")).strip()
        if weather_cond:
            wt_key = wt_map.get(weather_cond, wt_map.get("Unknown"))

        vis_km = safe_float(row.get("visibility_km"))
        if vis_km is None or vis_km == 0:
            vis_miles = safe_float(row.get("visibility_miles"))
            if vis_miles is not None:
                vis_km = round(vis_miles * 1.60934, 2)

        batch.append((
            loc_key, time_key, wt_key,
            safe_float(row.get("temperature_fahrenheit")),
            safe_float(row.get("temperature_celsius")),
            safe_float(row.get("humidity_percent")),
            safe_float(row.get("pressure_hpa")),
            safe_float(row.get("wind_speed_mph")),
            safe_int(row.get("wind_direction_degrees")),
            safe_float(row.get("precipitation_mm")),
            vis_km,
            safe_int(row.get("cloud_cover_percent")),
            None,  # uv_index
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
            str(row.get("data_quality_flag", "PASSED")),
        ))
        loaded += 1

        if len(batch) >= batch_size:
            execute_values(cursor, """
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

    if batch:
        execute_values(cursor, """
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
    conn.close()
    log.info(f"Warehouse loaded: {loaded} records, {skipped} skipped")


# ============================================================
# TASK 5: DATA QUALITY CHECKS
# ============================================================

def run_data_quality_check(**context):
    """Run data quality checks on the warehouse."""
    import psycopg2

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    log.info("=" * 60)
    log.info("DATA QUALITY CHECK REPORT")
    log.info("=" * 60)

    checks = {
        "Total fact records": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings",
            "min_expected": 1,
        },
        "Unique cities": {
            "sql": "SELECT COUNT(DISTINCT city) FROM climate_warehouse.dim_location",
            "min_expected": 1,
        },
        "Unique countries": {
            "sql": "SELECT COUNT(DISTINCT country) FROM climate_warehouse.dim_location",
            "min_expected": 1,
        },
        "Extreme weather count": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather = 1",
            "min_expected": 0,
        },
        "Null temperatures": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE temperature_fahrenheit IS NULL",
            "max_expected": 0,
        },
        "Temperature range check": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE temperature_fahrenheit < -80 OR temperature_fahrenheit > 140",
            "max_expected": 0,
        },
        "Null time_key (should be low)": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE time_key IS NULL",
            "max_expected": 50,
        },
        "Null location_key": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE location_key IS NULL",
            "max_expected": 0,
        },
        "Records with source tag": {
            "sql": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE source = 'openweathermap'",
            "min_expected": 1,
        },
    }

    all_passed = True
    for name, check in checks.items():
        cursor.execute(check["sql"])
        result = cursor.fetchone()[0]
        passed = True
        if "min_expected" in check and result < check["min_expected"]:
            passed = False
        if "max_expected" in check and result > check["max_expected"]:
            passed = False
        status = "PASS" if passed else "FAIL"
        log.info(f"  [{status}] {name}: {result}")
        if not passed:
            all_passed = False

    conn.close()

    if not all_passed:
        raise Exception("Data quality checks failed!")

    log.info("All data quality checks passed!")


# ============================================================
# DAG DEFINITION — Now with GCS upload tasks
# ============================================================

with DAG(
    dag_id="climate_intelligence_pipeline",
    default_args=default_args,
    description="End-to-end: Bronze → Silver → GCS → Gold → GCS → Warehouse → Quality Check",
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["climate", "pipeline", "production", "gcs"],
    doc_md="""
    ## Climate Intelligence Pipeline (80 Global Cities + GCS)

    **Flow:**
    Bronze → Silver → GCS(bronze+silver) → Gold → GCS(gold) → Warehouse → Quality Check

    **GCS Buckets:**
    - gs://climate-intelligence-485704-climate-bronze
    - gs://climate-intelligence-485704-climate-silver
    - gs://climate-intelligence-485704-climate-gold
    """,
) as dag:

    task_verify = PythonOperator(
        task_id="verify_bronze_data",
        python_callable=verify_bronze_data,
    )
    task_silver = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=run_bronze_to_silver,
        execution_timeout=timedelta(minutes=15),
    )
    task_gcs_bronze_silver = PythonOperator(
        task_id="upload_bronze_silver_to_gcs",
        python_callable=upload_bronze_silver_to_gcs,
        execution_timeout=timedelta(minutes=10),
    )
    task_gold = PythonOperator(
        task_id="silver_to_gold",
        python_callable=run_silver_to_gold,
        execution_timeout=timedelta(minutes=15),
    )
    task_gcs_gold = PythonOperator(
        task_id="upload_gold_to_gcs",
        python_callable=upload_gold_to_gcs,
        execution_timeout=timedelta(minutes=10),
    )
    task_warehouse = PythonOperator(
        task_id="load_warehouse",
        python_callable=run_warehouse_load,
        execution_timeout=timedelta(minutes=10),
    )
    task_quality = PythonOperator(
        task_id="data_quality_check",
        python_callable=run_data_quality_check,
    )

    # Pipeline flow with GCS uploads
    task_verify >> task_silver >> task_gcs_bronze_silver >> task_gold >> task_gcs_gold >> task_warehouse >> task_quality