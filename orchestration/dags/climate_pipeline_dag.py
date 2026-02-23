"""
Climate Intelligence Platform - Main Pipeline DAG (v2 Fixed)
=============================================================
Orchestrates the entire data pipeline:
1. Ingest weather data (Kafka producer)
2. Bronze → Silver (cleaning)
3. Silver → Gold (feature engineering)
4. Gold → Warehouse (load star schema)
5. Data quality checks

Schedule: Daily at 6:00 AM UTC

IMPORTANT: This DAG runs processing INSIDE the Airflow worker container.
Make sure your docker-compose.yml mounts the project folders correctly.
See volume mount instructions below.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
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
# PATHS — Adjust if your mount points differ
# ============================================================
PROJECT_ROOT = "/opt/airflow"
DATA_DIR = f"{PROJECT_ROOT}/data"
BRONZE_PATH = f"{DATA_DIR}/bronze/weather_readings"
SILVER_PATH = f"{DATA_DIR}/silver/weather_readings"
GOLD_PATH = f"{DATA_DIR}/gold/weather_features"

# Database config — use 'postgres' hostname (Docker service name), NOT 'localhost'
DB_CONFIG = dict(host="postgres", port=5432, database="airflow", user="airflow", password="airflow")


# ============================================================
# TASK 1: VERIFY DATA EXISTS
# ============================================================

def verify_bronze_data(**context):
    """Check that Bronze layer has data before processing."""
    import os

    log.info(f"Checking Bronze path: {BRONZE_PATH}")

    if not os.path.exists(BRONZE_PATH):
        raise FileNotFoundError(
            f"Bronze path not found: {BRONZE_PATH}\n"
            f"Make sure:\n"
            f"  1. Kafka producer has been run\n"
            f"  2. Spark streaming has written to Bronze\n"
            f"  3. 'data/' folder is mounted in docker-compose.yml"
        )

    # Count parquet files
    parquet_files = []
    for root, dirs, files in os.walk(BRONZE_PATH):
        for f in files:
            if f.endswith(".parquet"):
                parquet_files.append(os.path.join(root, f))

    if len(parquet_files) == 0:
        raise FileNotFoundError(f"No parquet files found in {BRONZE_PATH}. Run the Kafka producer + Spark streaming first.")

    log.info(f"✅ Found {len(parquet_files)} parquet files in Bronze layer")
    return len(parquet_files)


# ============================================================
# TASK 2: BRONZE → SILVER (Inline — no subprocess needed)
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
        # Read Bronze
        log.info(f"Reading from: {BRONZE_PATH}")
        bronze_df = spark.read.parquet(BRONZE_PATH)
        bronze_count = bronze_df.count()
        log.info(f"Bronze records: {bronze_count}")

        if bronze_count == 0:
            raise ValueError("Bronze layer is empty!")

        # --- CLEANING ---
        silver_df = bronze_df

        # 1. Deduplicate (by city + timestamp)
        if "city" in silver_df.columns and "timestamp" in silver_df.columns:
            silver_df = silver_df.dropDuplicates(["city", "timestamp"])
        elif "city" in silver_df.columns:
            silver_df = silver_df.dropDuplicates(["city", "reading_timestamp"])

        # 2. Drop rows with null critical fields
        critical_cols = ["city", "temperature_fahrenheit"]
        existing_critical = [c for c in critical_cols if c in silver_df.columns]
        if existing_critical:
            silver_df = silver_df.dropna(subset=existing_critical)

        # 3. Range validation — cap extreme outliers
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

        # 4. Add processing metadata
        silver_df = silver_df.withColumn("processed_at", F.current_timestamp())
        silver_df = silver_df.withColumn("data_quality_flag", F.lit("PASSED"))

        # 5. Add reading_date partition column
        if "timestamp" in silver_df.columns:
            silver_df = silver_df.withColumn("reading_date", F.to_date("timestamp"))
        elif "reading_timestamp" in silver_df.columns:
            silver_df = silver_df.withColumn("reading_date", F.to_date("reading_timestamp"))
        else:
            silver_df = silver_df.withColumn("reading_date", F.current_date())

        silver_count = silver_df.count()
        log.info(f"Silver records: {silver_count} (dropped {bronze_count - silver_count})")

        # Write Silver
        log.info(f"Writing to: {SILVER_PATH}")
        silver_df.write \
            .mode("overwrite") \
            .partitionBy("reading_date") \
            .parquet(SILVER_PATH)

        log.info(f"✅ Bronze → Silver complete: {silver_count} records")

    finally:
        spark.stop()


# ============================================================
# TASK 3: SILVER → GOLD (Feature Engineering)
# ============================================================

def run_silver_to_gold(**context):
    """Silver → Gold: Feature engineering (49 columns)."""
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

        # --- FEATURE ENGINEERING ---

        # 1. Temperature Celsius (if not present)
        if "temperature_celsius" not in gold_df.columns and "temperature_fahrenheit" in gold_df.columns:
            gold_df = gold_df.withColumn(
                "temperature_celsius",
                F.round((F.col("temperature_fahrenheit") - 32) * 5 / 9, 2)
            )

        # 2. Heat Index (simplified Rothfusz formula)
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

            # Temperature anomaly
            gold_df = gold_df.withColumn(
                "temperature_anomaly",
                F.round(F.col("temperature_fahrenheit") - F.col("city_avg_temp"), 2)
            )

            # Anomaly score (z-score)
            gold_df = gold_df.withColumn(
                "temp_anomaly_score",
                F.when(F.col("city_stddev_temp") > 0,
                    F.round(F.abs(F.col("temperature_anomaly")) / F.col("city_stddev_temp"), 2)
                ).otherwise(F.lit(0.0))
            )

        # 5. Time features
        ts_col = "timestamp" if "timestamp" in gold_df.columns else "reading_timestamp" if "reading_timestamp" in gold_df.columns else None
        if ts_col:
            gold_df = gold_df.withColumn("hour_of_day", F.hour(F.col(ts_col)))
            gold_df = gold_df.withColumn("day_of_week", F.dayofweek(F.col(ts_col)))
            gold_df = gold_df.withColumn("month", F.month(F.col(ts_col)))
            gold_df = gold_df.withColumn("is_daytime",
                F.when((F.hour(F.col(ts_col)) >= 6) & (F.hour(F.col(ts_col)) < 20), 1).otherwise(0))

        # 6. Extreme weather flag
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

        # Fill nulls in numeric columns
        numeric_cols = [f.name for f in gold_df.schema.fields if str(f.dataType) in ("DoubleType()", "FloatType()", "IntegerType()", "LongType()")]
        for c in numeric_cols:
            gold_df = gold_df.fillna({c: 0})

        gold_count = gold_df.count()
        gold_cols = len(gold_df.columns)
        log.info(f"Gold: {gold_count} records, {gold_cols} columns")

        # Write Gold
        log.info(f"Writing to: {GOLD_PATH}")
        gold_df.write \
            .mode("overwrite") \
            .partitionBy("reading_date") \
            .parquet(GOLD_PATH)

        log.info(f"✅ Silver → Gold complete: {gold_count} records, {gold_cols} features")

    finally:
        spark.stop()


# ============================================================
# TASK 4: GOLD → WAREHOUSE
# ============================================================

def run_warehouse_load(**context):
    """Load Gold Parquet into PostgreSQL Star Schema."""
    import psycopg2
    import pandas as pd

    log.info("Starting Gold → Warehouse load...")

    # Read gold data with pandas (fast, no Spark needed for warehouse load)
    gold_df = pd.read_parquet(GOLD_PATH)
    log.info(f"Gold records to load: {len(gold_df)}")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Ensure schema exists
    cursor.execute("CREATE SCHEMA IF NOT EXISTS climate_warehouse")

    # ── Create dimension tables ──
    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_time (
            time_key SERIAL PRIMARY KEY,
            reading_timestamp TIMESTAMP,
            hour INT, day_of_week INT, month INT, year INT,
            is_daytime INT,
            UNIQUE(reading_timestamp)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS climate_warehouse.dim_weather_type (
            weather_type_key SERIAL PRIMARY KEY,
            weather_condition VARCHAR(100),
            weather_group VARCHAR(50),
            UNIQUE(weather_condition)
        )
    """)

    # ── Create fact table ──
    cursor.execute("""
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

    # ── Load dimensions ──
    # Locations
    if "city" in gold_df.columns:
        cities = gold_df.drop_duplicates(subset=["city"])[["city", "state", "latitude", "longitude"]].copy()
        # Assign regions
        region_map = {
            "New York": "Northeast", "Boston": "Northeast",
            "Miami": "Southeast", "Atlanta": "Southeast", "New Orleans": "Southeast",
            "Houston": "South", "Dallas": "South", "Nashville": "South",
            "Chicago": "Midwest", "Detroit": "Midwest", "Minneapolis": "Midwest",
            "Denver": "West", "Phoenix": "West", "Las Vegas": "West",
            "Los Angeles": "West", "San Francisco": "West", "Seattle": "Northwest",
            "Portland": "Northwest", "Honolulu": "Pacific", "Anchorage": "Alaska",
        }
        for _, row in cities.iterrows():
            region = region_map.get(row["city"], "Other")
            cursor.execute("""
                INSERT INTO climate_warehouse.dim_location (city, state, latitude, longitude, region)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (city, state) DO NOTHING
            """, (row["city"], row.get("state"), row.get("latitude"), row.get("longitude"), region))

    # Weather types
    if "weather_condition" in gold_df.columns:
        conditions = gold_df["weather_condition"].dropna().unique()
        group_map = {"Clear": "Clear", "Clouds": "Cloudy", "Rain": "Precipitation",
                     "Drizzle": "Precipitation", "Snow": "Precipitation", "Mist": "Fog",
                     "Fog": "Fog", "Haze": "Fog", "Thunderstorm": "Severe"}
        for cond in conditions:
            group = group_map.get(str(cond), "Other")
            cursor.execute("""
                INSERT INTO climate_warehouse.dim_weather_type (weather_condition, weather_group)
                VALUES (%s, %s)
                ON CONFLICT (weather_condition) DO NOTHING
            """, (str(cond), group))

    conn.commit()

    # ── Build lookup maps ──
    cursor.execute("SELECT location_key, city FROM climate_warehouse.dim_location")
    loc_map = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT weather_type_key, weather_condition FROM climate_warehouse.dim_weather_type")
    wt_map = {row[1]: row[0] for row in cursor.fetchall()}

    # ── Clear and reload fact table ──
    cursor.execute("TRUNCATE climate_warehouse.fact_weather_readings RESTART IDENTITY")

    loaded = 0
    for _, row in gold_df.iterrows():
        city = row.get("city", "")
        loc_key = loc_map.get(city)
        wt_key = wt_map.get(str(row.get("weather_condition", "")))
        if not loc_key:
            continue

        cursor.execute("""
            INSERT INTO climate_warehouse.fact_weather_readings
            (location_key, weather_type_key, temperature_fahrenheit, temperature_celsius,
             humidity_percent, pressure_hpa, wind_speed_mph, wind_direction_degrees,
             precipitation_mm, visibility_miles, cloud_cover_percent, heat_index,
             wind_chill, temperature_anomaly, temp_anomaly_score, is_extreme_weather,
             data_quality_score)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            loc_key, wt_key,
            row.get("temperature_fahrenheit"), row.get("temperature_celsius"),
            row.get("humidity_percent"), row.get("pressure_hpa"),
            row.get("wind_speed_mph"), row.get("wind_direction_degrees"),
            row.get("precipitation_mm"), row.get("visibility_miles"),
            row.get("cloud_cover_percent"), row.get("heat_index"),
            row.get("wind_chill"), row.get("temperature_anomaly"),
            row.get("temp_anomaly_score"), row.get("is_extreme_weather"),
            row.get("data_quality_score", 1.0)
        ))
        loaded += 1

    conn.commit()
    conn.close()
    log.info(f"✅ Warehouse loaded: {loaded} fact records")


# ============================================================
# TASK 5: DATA QUALITY CHECKS
# ============================================================

def run_data_quality_check(**context):
    """Run data quality checks on the warehouse."""
    import psycopg2

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    log.info("=" * 60)
    log.info("📊 DATA QUALITY CHECK REPORT")
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

        status = "✅" if passed else "❌"
        log.info(f"  {status} {name}: {result}")

        if not passed:
            all_passed = False

    conn.close()

    if not all_passed:
        raise Exception("❌ Data quality checks failed! Check logs above.")

    log.info("✅ All data quality checks passed!")


# ============================================================
# DAG DEFINITION
# ============================================================

with DAG(
    dag_id="climate_intelligence_pipeline",
    default_args=default_args,
    description="End-to-end climate data pipeline: Ingest → Process → Warehouse → Quality Check",
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["climate", "pipeline", "production"],
    doc_md="""
    ## Climate Intelligence Pipeline
    
    **Flow:** Bronze → Silver → Gold → PostgreSQL Warehouse → Quality Check
    
    **Prerequisites:**
    - Kafka producer running (`kafka_producer_openweather.py`)
    - Spark streaming writing Bronze (`spark_streaming_bronze.py`)
    - Docker volumes mounted correctly
    
    **Troubleshooting:**
    - Check Bronze data exists: `ls data/bronze/weather_readings/`
    - Check Spark logs in task output
    - Verify PostgreSQL is accessible from Airflow container
    """,
) as dag:

    # Task 1: Verify Bronze data exists
    task_verify = PythonOperator(
        task_id="verify_bronze_data",
        python_callable=verify_bronze_data,
    )

    # Task 2: Bronze → Silver
    task_silver = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=run_bronze_to_silver,
        execution_timeout=timedelta(minutes=15),
    )

    # Task 3: Silver → Gold
    task_gold = PythonOperator(
        task_id="silver_to_gold",
        python_callable=run_silver_to_gold,
        execution_timeout=timedelta(minutes=15),
    )

    # Task 4: Gold → Warehouse
    task_warehouse = PythonOperator(
        task_id="load_warehouse",
        python_callable=run_warehouse_load,
        execution_timeout=timedelta(minutes=10),
    )

    # Task 5: Data Quality Checks
    task_quality = PythonOperator(
        task_id="data_quality_check",
        python_callable=run_data_quality_check,
    )

    # Pipeline flow
    task_verify >> task_silver >> task_gold >> task_warehouse >> task_quality