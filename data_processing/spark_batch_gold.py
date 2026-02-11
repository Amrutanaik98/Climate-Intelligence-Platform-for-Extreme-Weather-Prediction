"""
Spark Batch Job: Silver → Gold Layer
=====================================
Reads cleaned data from Silver, engineers features,
creates aggregations, and writes ML-ready data to Gold.

FEATURE ENGINEERING:
1. Heat Index calculation
2. Wind Chill calculation
3. Temperature anomaly score (how far from historical average)
4. Rolling statistics (24h averages, min, max)
5. Extreme weather flags
6. Time-based features (hour of day, day of week, season)
"""

from pyspark.sql import SparkSession
from pyspark.sql import Window
from pyspark.sql.functions import (
    col, when, lit, avg, min as spark_min, max as spark_max,
    stddev, count, current_timestamp, to_date,
    hour as spark_hour, dayofweek, month, quarter,
    lag, round as spark_round, udf, abs as spark_abs
)
from pyspark.sql.types import DoubleType, StringType
import os
import math


def create_spark_session():
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Gold")
        .master("local[*]")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def read_silver(spark):
    """Read cleaned data from Silver layer."""
    silver_path = "data/silver/weather_readings"

    if not os.path.exists(silver_path):
        print("❌ No Silver data found! Run silver job first.")
        return None

    df = spark.read.parquet(silver_path)
    # Only use valid records for Gold layer
    df = df.filter(col("quality_flag") == "VALID")
    print(f"📥 Read {df.count()} valid records from Silver layer")
    return df


def calculate_heat_index(df):
    """
    Calculate Heat Index — "feels like" temperature.
    
    WHY: Temperature alone doesn't tell you how dangerous the heat is.
    90°F with 20% humidity feels fine, but 90°F with 90% humidity can
    kill you. Heat index combines both into one danger metric.
    
    Formula: Rothfusz regression equation (used by NOAA)
    Only valid when temp >= 80°F and humidity >= 40%
    """
    df_hi = df.withColumn(
        "heat_index",
        when(
            (col("temperature_fahrenheit") >= 80) &
            (col("humidity_percent") >= 40) &
            (col("humidity_percent") > 0),
            spark_round(
                -42.379
                + 2.04901523 * col("temperature_fahrenheit")
                + 10.14333127 * col("humidity_percent")
                - 0.22475541 * col("temperature_fahrenheit") * col("humidity_percent")
                - 0.00683783 * col("temperature_fahrenheit") * col("temperature_fahrenheit")
                - 0.05481717 * col("humidity_percent") * col("humidity_percent")
                + 0.00122874 * col("temperature_fahrenheit") * col("temperature_fahrenheit") * col("humidity_percent")
                + 0.00085282 * col("temperature_fahrenheit") * col("humidity_percent") * col("humidity_percent")
                - 0.00000199 * col("temperature_fahrenheit") * col("temperature_fahrenheit") * col("humidity_percent") * col("humidity_percent"),
                1
            )
        ).otherwise(col("temperature_fahrenheit"))
    )

    print("✅ Calculated Heat Index")
    return df_hi


def calculate_wind_chill(df):
    """
    Calculate Wind Chill — "feels like" in cold weather.
    
    WHY: 30°F with no wind is bearable. 30°F with 30mph wind
    feels like 15°F and can cause frostbite in 30 minutes.
    
    Only valid when temp <= 50°F and wind > 3 mph.
    """
    df_wc = df.withColumn(
        "wind_chill",
        when(
            (col("temperature_fahrenheit") <= 50) &
            (col("wind_speed_mph") > 3) &
            (col("wind_speed_mph") > 0),
            spark_round(
                35.74
                + 0.6215 * col("temperature_fahrenheit")
                - 35.75 * (col("wind_speed_mph") ** 0.16)
                + 0.4275 * col("temperature_fahrenheit") * (col("wind_speed_mph") ** 0.16),
                1
            )
        ).otherwise(col("temperature_fahrenheit"))
    )

    print("✅ Calculated Wind Chill")
    return df_wc


def add_extreme_weather_flags(df):
    """
    Flag extreme weather conditions.
    
    WHY: These binary flags become TARGET VARIABLES for our ML model.
    The model will learn to PREDICT these flags based on weather patterns.
    
    Thresholds based on NOAA definitions:
    - Heatwave: Heat index >= 105°F for extended period
    - Extreme cold: Wind chill <= 0°F
    - High wind: Wind speed >= 40 mph
    - Heavy rain: Precipitation >= 7.6 mm/hr (0.3 inches)
    """
    df_flags = (
        df
        .withColumn(
            "is_heatwave",
            when(col("heat_index") >= 105, lit(1)).otherwise(lit(0))
        )
        .withColumn(
            "is_extreme_cold",
            when(col("wind_chill") <= 0, lit(1)).otherwise(lit(0))
        )
        .withColumn(
            "is_high_wind",
            when(col("wind_speed_mph") >= 40, lit(1)).otherwise(lit(0))
        )
        .withColumn(
            "is_heavy_precipitation",
            when(col("precipitation_mm") >= 7.6, lit(1)).otherwise(lit(0))
        )
        # Combined extreme flag (ANY extreme condition)
        .withColumn(
            "is_extreme_weather",
            when(
                (col("is_heatwave") == 1) |
                (col("is_extreme_cold") == 1) |
                (col("is_high_wind") == 1) |
                (col("is_heavy_precipitation") == 1),
                lit(1)
            ).otherwise(lit(0))
        )
    )

    extreme_count = df_flags.filter(col("is_extreme_weather") == 1).count()
    total = df_flags.count()
    print(f"🌪️  Extreme weather flags: {extreme_count}/{total} records ({round(extreme_count/max(total,1)*100, 1)}%)")

    return df_flags


def add_time_features(df):
    """
    Add time-based features.
    
    WHY: Weather patterns depend heavily on TIME.
    - Temperature peaks at 3pm, lowest at 6am
    - Weekday vs weekend affects urban heat islands
    - Season is the biggest predictor of weather
    
    These features help the ML model learn cyclical patterns.
    """
    df_time = (
        df
        .withColumn("hour_of_day", spark_hour(col("timestamp")))
        .withColumn("day_of_week", dayofweek(col("timestamp")))
        .withColumn("month_of_year", month(col("timestamp")))
        .withColumn("quarter", quarter(col("timestamp")))
        .withColumn(
            "season",
            when(col("month_of_year").isin(12, 1, 2), lit("Winter"))
            .when(col("month_of_year").isin(3, 4, 5), lit("Spring"))
            .when(col("month_of_year").isin(6, 7, 8), lit("Summer"))
            .otherwise(lit("Fall"))
        )
        .withColumn(
            "is_daytime",
            when(
                (col("hour_of_day") >= 6) & (col("hour_of_day") <= 18),
                lit(1)
            ).otherwise(lit(0))
        )
    )

    print("✅ Added time-based features")
    return df_time


def add_city_statistics(df):
    """
    Add per-city rolling statistics.
    
    WHY: Knowing that NYC is currently 80°F means nothing without context.
    If NYC's average this month is 75°F, then 80°F is slightly warm.
    If NYC's average this month is 60°F, then 80°F is a major anomaly.
    
    The temperature ANOMALY (deviation from average) is often more
    predictive than the absolute temperature.
    """
    # Window: all records for the same city
    city_window = Window.partitionBy("city")

    df_stats = (
        df
        .withColumn("city_avg_temp", spark_round(avg("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_min_temp", spark_round(spark_min("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_max_temp", spark_round(spark_max("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_stddev_temp", spark_round(stddev("temperature_fahrenheit").over(city_window), 2))
        .withColumn("city_avg_humidity", spark_round(avg("humidity_percent").over(city_window), 1))
        # Temperature anomaly: how far from the city average?
        .withColumn(
            "temp_anomaly",
            spark_round(col("temperature_fahrenheit") - col("city_avg_temp"), 1)
        )
        # Anomaly score: how many standard deviations from average?
        .withColumn(
            "temp_anomaly_score",
            when(
                col("city_stddev_temp") > 0,
                spark_round(
                    spark_abs(col("temperature_fahrenheit") - col("city_avg_temp")) / col("city_stddev_temp"),
                    2
                )
            ).otherwise(lit(0.0))
        )
    )

    print("✅ Added per-city statistics and anomaly scores")
    return df_stats


def write_gold(df):
    """Write feature-engineered data to Gold layer."""
    output_path = "data/gold/weather_features"

    (
        df.write
        .mode("overwrite")
        .partitionBy("reading_date")
        .parquet(output_path)
    )

    count = df.count()
    print(f"💾 Wrote {count} records to Gold layer: {output_path}")


def print_gold_summary(df):
    """Print summary of Gold layer data."""
    print("\n" + "=" * 60)
    print("📊 GOLD LAYER - FEATURE ENGINEERING SUMMARY")
    print("=" * 60)
    print(f"Total records: {df.count()}")
    print(f"Total features: {len(df.columns)}")
    print(f"\nAll columns ({len(df.columns)}):")
    for i, col_name in enumerate(sorted(df.columns), 1):
        print(f"  {i:2d}. {col_name}")

    print(f"\n🌡️  Temperature stats by city:")
    df.groupBy("city").agg(
        spark_round(avg("temperature_fahrenheit"), 1).alias("avg_temp"),
        spark_round(avg("heat_index"), 1).alias("avg_heat_index"),
        spark_round(avg("temp_anomaly_score"), 2).alias("avg_anomaly_score"),
        count("*").alias("record_count"),
    ).orderBy("city").show(25, truncate=False)

    print(f"🌪️  Extreme weather distribution:")
    df.groupBy("is_extreme_weather").count().show()

    print(f"\n📅 Season distribution:")
    df.groupBy("season").count().orderBy("season").show()


def main():
    print("=" * 60)
    print("🥇 GOLD LAYER - Silver → Gold Feature Engineering")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Step 1: Read Silver
    df = read_silver(spark)
    if df is None:
        return

    # Step 2: Calculate Heat Index
    df = calculate_heat_index(df)

    # Step 3: Calculate Wind Chill
    df = calculate_wind_chill(df)

    # Step 4: Add extreme weather flags
    df = add_extreme_weather_flags(df)

    # Step 5: Add time-based features
    df = add_time_features(df)

    # Step 6: Add city statistics and anomaly scores
    df = add_city_statistics(df)

    # Step 7: Add final metadata
    df = df.withColumn("gold_loaded_at", current_timestamp())

    # Step 8: Write to Gold
    write_gold(df)

    # Step 9: Print summary
    print_gold_summary(df)

    print("\n✅ Silver → Gold processing complete!")
    print(f"   Total features available for ML: {len(df.columns)}")
    spark.stop()


if __name__ == "__main__":
    main()