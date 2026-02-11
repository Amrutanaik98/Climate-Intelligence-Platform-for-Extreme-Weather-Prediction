"""
Spark Batch Job: Bronze → Silver Layer
=======================================
Reads raw Parquet from Bronze, cleans and validates,
writes cleaned Parquet to Silver.

CLEANING STEPS:
1. Remove exact duplicates (same message_id)
2. Handle nulls (fill with sensible defaults or drop)
3. Validate ranges (temperature between -60 and 140°F)
4. Fix data types
5. Standardize column names
6. Add data quality flags
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, count, isnan, isnull,
    current_timestamp, to_date, avg, stddev,
    year, month, dayofmonth
)
import os


def create_spark_session():
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Silver")
        .master("local[*]")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def read_bronze(spark):
    """Read raw data from Bronze layer."""
    bronze_path = "data/bronze/weather_readings"

    if not os.path.exists(bronze_path):
        print("❌ No Bronze data found! Run the streaming job first.")
        return None

    df = spark.read.parquet(bronze_path)
    row_count = df.count()
    print(f"📥 Read {row_count} records from Bronze layer")
    return df


def remove_duplicates(df):
    """
    Remove duplicate records based on message_id.
    
    WHY do duplicates happen?
    - Kafka producer retries: if ack was lost, producer resends
    - Spark streaming checkpoint issues
    - Multiple producers running accidentally
    
    We keep the FIRST occurrence and drop the rest.
    """
    before_count = df.count()
    df_deduped = df.dropDuplicates(["message_id"])
    after_count = df_deduped.count()
    removed = before_count - after_count
    print(f"🔄 Deduplication: {before_count} → {after_count} ({removed} duplicates removed)")
    return df_deduped


def validate_ranges(df):
    """
    Flag records with impossible values.
    
    Instead of DELETING bad records (we might lose real anomalies),
    we ADD a quality flag column. The ML model can decide whether
    to use flagged records or not.
    
    Valid ranges:
    - Temperature: -60°F to 140°F (Death Valley record is 134°F)
    - Humidity: 0% to 100%
    - Wind speed: 0 to 250 mph (strongest tornado ~300 mph)
    - Pressure: 870 to 1084 hPa (recorded extremes on Earth)
    """
    df_validated = df.withColumn(
        "quality_flag",
        when(
            (col("temperature_fahrenheit") < -60) |
            (col("temperature_fahrenheit") > 140),
            lit("SUSPECT_TEMPERATURE")
        ).when(
            (col("humidity_percent") < 0) |
            (col("humidity_percent") > 100),
            lit("SUSPECT_HUMIDITY")
        ).when(
            (col("wind_speed_mph") < 0) |
            (col("wind_speed_mph") > 250),
            lit("SUSPECT_WIND")
        ).when(
            (col("pressure_hpa") < 870) |
            (col("pressure_hpa") > 1084),
            lit("SUSPECT_PRESSURE")
        ).otherwise(
            lit("VALID")
        )
    )

    # Count quality flags
    valid_count = df_validated.filter(col("quality_flag") == "VALID").count()
    suspect_count = df_validated.filter(col("quality_flag") != "VALID").count()
    print(f"✅ Validation: {valid_count} valid, {suspect_count} suspect records")

    return df_validated


def handle_nulls(df):
    """
    Handle null/missing values.
    
    Strategy:
    - CRITICAL fields (city, timestamp, temperature): DROP if null
      (these are essential, can't do anything without them)
    - OPTIONAL fields (uv_index, visibility): FILL with defaults
      (nice to have but not required)
    
    WHY not fill temperature with average?
    Because a missing temperature is fundamentally different from
    an average temperature. Filling it could mislead the ML model.
    Better to drop it and be honest about missing data.
    """
    before_count = df.count()

    # Drop records missing critical fields
    df_cleaned = df.dropna(subset=["city", "timestamp", "temperature_fahrenheit"])

    # Fill optional fields with sensible defaults
    df_cleaned = df_cleaned.fillna({
        "humidity_percent": -1.0,        # -1 signals "not available"
        "wind_speed_mph": -1.0,
        "wind_direction_degrees": -1,
        "precipitation_mm": 0.0,         # No precipitation data = assume 0
        "visibility_km": -1.0,
        "cloud_cover_percent": -1,
        "weather_condition": "Unknown",
        "uv_index": -1.0,
        "state": "Unknown",
        "country": "US",
    })

    after_count = df_cleaned.count()
    dropped = before_count - after_count
    print(f"🧹 Null handling: dropped {dropped} records missing critical fields")

    return df_cleaned


def add_derived_columns(df):
    """
    Add useful derived columns that don't exist in raw data.
    
    These aren't feature engineering (that's Gold layer) —
    these are basic calculations that make the data more usable.
    """
    df_enriched = (
        df
        # If celsius is missing but fahrenheit exists, calculate it
        .withColumn(
            "temperature_celsius",
            when(
                col("temperature_celsius").isNull() & col("temperature_fahrenheit").isNotNull(),
                (col("temperature_fahrenheit") - 32) * 5 / 9
            ).otherwise(col("temperature_celsius"))
        )
        # Add time components for easier querying
        .withColumn("reading_date", to_date(col("timestamp")))
        .withColumn("reading_year", year(col("timestamp")))
        .withColumn("reading_month", month(col("timestamp")))
        .withColumn("reading_day", dayofmonth(col("timestamp")))
        # Add processing timestamp
        .withColumn("silver_loaded_at", current_timestamp())
    )

    return df_enriched


def write_silver(df):
    """Write cleaned data to Silver layer, partitioned by date and state."""
    output_path = "data/silver/weather_readings"

    (
        df.write
        .mode("overwrite")              # Overwrite previous Silver data
        .partitionBy("reading_date")    # Folder per date
        .parquet(output_path)
    )

    count = df.count()
    print(f"💾 Wrote {count} records to Silver layer: {output_path}")


def print_data_quality_report(df):
    """Print a summary of the cleaned data."""
    print("\n" + "=" * 60)
    print("📊 SILVER LAYER - DATA QUALITY REPORT")
    print("=" * 60)
    print(f"Total records: {df.count()}")
    print(f"Unique cities: {df.select('city').distinct().count()}")
    print(f"Date range: {df.select('reading_date').distinct().orderBy('reading_date').collect()}")
    print(f"\nQuality flags:")
    df.groupBy("quality_flag").count().show()
    print(f"\nSample data:")
    df.select(
        "city", "state", "temperature_fahrenheit",
        "humidity_percent", "wind_speed_mph", "quality_flag"
    ).show(10, truncate=False)


def main():
    print("=" * 60)
    print("🥈 SILVER LAYER - Bronze → Silver Processing")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Step 1: Read Bronze
    df = read_bronze(spark)
    if df is None:
        return

    # Step 2: Remove duplicates
    df = remove_duplicates(df)

    # Step 3: Validate ranges
    df = validate_ranges(df)

    # Step 4: Handle nulls
    df = handle_nulls(df)

    # Step 5: Add derived columns
    df = add_derived_columns(df)

    # Step 6: Write to Silver
    write_silver(df)

    # Step 7: Print quality report
    print_data_quality_report(df)

    print("\n✅ Bronze → Silver processing complete!")
    spark.stop()


if __name__ == "__main__":
    main()