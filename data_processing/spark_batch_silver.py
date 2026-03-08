"""
Spark Batch Job: Bronze → Silver Layer (Fixed for Global Producer)
===================================================================
Reads raw Parquet from Bronze, cleans and validates,
writes cleaned Parquet to Silver.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, current_timestamp, to_date,
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
    bronze_path = "data/bronze/weather_readings"
    if not os.path.exists(bronze_path):
        print("❌ No Bronze data found! Run streaming job first.")
        return None

    df = spark.read.parquet(bronze_path)
    row_count = df.count()
    if row_count == 0:
        print("❌ Bronze layer is empty! Let streaming run longer.")
        return None
    print(f"📥 Read {row_count} records from Bronze layer")
    print(f"   Columns: {df.columns}")
    return df


def remove_duplicates(df):
    before = df.count()
    # Deduplicate by city + timestamp (no message_id in new schema)
    df_deduped = df.dropDuplicates(["city", "timestamp"])
    after = df_deduped.count()
    print(f"🔄 Deduplication: {before} → {after} ({before - after} removed)")
    return df_deduped


def validate_ranges(df):
    df_validated = df.withColumn(
        "quality_flag",
        when(
            (col("temperature_fahrenheit") < -60) | (col("temperature_fahrenheit") > 140),
            lit("SUSPECT_TEMPERATURE")
        ).when(
            (col("humidity_percent") < 0) | (col("humidity_percent") > 100),
            lit("SUSPECT_HUMIDITY")
        ).when(
            (col("wind_speed_mph") < 0) | (col("wind_speed_mph") > 250),
            lit("SUSPECT_WIND")
        ).when(
            (col("pressure_hpa") < 870) | (col("pressure_hpa") > 1084),
            lit("SUSPECT_PRESSURE")
        ).otherwise(lit("VALID"))
    )

    valid = df_validated.filter(col("quality_flag") == "VALID").count()
    suspect = df_validated.filter(col("quality_flag") != "VALID").count()
    print(f"✅ Validation: {valid} valid, {suspect} suspect records")
    return df_validated


def handle_nulls(df):
    before = df.count()
    df_cleaned = df.dropna(subset=["city", "timestamp", "temperature_fahrenheit"])
    df_cleaned = df_cleaned.fillna({
        "humidity_percent": -1.0,
        "wind_speed_mph": -1.0,
        "wind_direction_degrees": -1.0,
        "precipitation_mm": 0.0,
        "visibility_miles": -1.0,
        "cloud_cover_percent": -1.0,
        "weather_condition": "Unknown",
        "weather_description": "unknown",
        "state": "Unknown",
        "country": "Unknown",
        "continent": "Unknown",
        "region": "Unknown",
    })
    after = df_cleaned.count()
    print(f"🧹 Null handling: dropped {before - after} records")
    return df_cleaned


def add_derived_columns(df):
    df_enriched = df

    # Calculate celsius if missing
    if "temperature_celsius" in df.columns:
        df_enriched = df_enriched.withColumn(
            "temperature_celsius",
            when(
                col("temperature_celsius").isNull() & col("temperature_fahrenheit").isNotNull(),
                (col("temperature_fahrenheit") - 32) * 5 / 9
            ).otherwise(col("temperature_celsius"))
        )

    # Add time components
    df_enriched = (
        df_enriched
        .withColumn("reading_date", to_date(col("timestamp")))
        .withColumn("reading_year", year(col("timestamp")))
        .withColumn("reading_month", month(col("timestamp")))
        .withColumn("reading_day", dayofmonth(col("timestamp")))
        .withColumn("silver_loaded_at", current_timestamp())
    )
    return df_enriched


def write_silver(df):
    output_path = "data/silver/weather_readings"
    df.write.mode("overwrite").partitionBy("reading_date").parquet(output_path)
    print(f"💾 Wrote {df.count()} records to Silver: {output_path}")


def main():
    print("=" * 60)
    print("🥈 SILVER LAYER - Bronze → Silver Processing")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    df = read_bronze(spark)
    if df is None:
        spark.stop()
        return

    df = remove_duplicates(df)
    df = validate_ranges(df)
    df = handle_nulls(df)
    df = add_derived_columns(df)
    write_silver(df)

    # Summary
    print("\n" + "=" * 60)
    print("📊 SILVER LAYER SUMMARY")
    print("=" * 60)
    print(f"Total records: {df.count()}")
    print(f"Unique cities: {df.select('city').distinct().count()}")
    print(f"Quality flags:")
    df.groupBy("quality_flag").count().show()
    print("Sample data:")
    df.select("city", "country", "continent", "temperature_fahrenheit",
              "humidity_percent", "wind_speed_mph", "quality_flag").show(10, truncate=False)
    print("\n✅ Bronze → Silver complete!")
    spark.stop()


if __name__ == "__main__":
    main()