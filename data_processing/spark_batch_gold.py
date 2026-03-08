"""
Spark Batch Job: Silver → Gold Layer (Fixed for Global Producer)
=================================================================
Feature engineering: heat index, wind chill, anomaly scores,
extreme weather flags, time features.
"""

from pyspark.sql import SparkSession
from pyspark.sql import Window
from pyspark.sql.functions import (
    col, when, lit, avg, min as spark_min, max as spark_max,
    stddev, count, current_timestamp, to_date,
    hour as spark_hour, dayofweek, month, quarter,
    round as spark_round, abs as spark_abs
)
import os


def create_spark_session():
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Gold")
        .master("local[*]")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def read_silver(spark):
    silver_path = "data/silver/weather_readings"
    if not os.path.exists(silver_path):
        print("❌ No Silver data found! Run silver job first.")
        return None
    df = spark.read.parquet(silver_path)
    df = df.filter(col("quality_flag") == "VALID")
    print(f"📥 Read {df.count()} valid records from Silver")
    return df


def calculate_heat_index(df):
    df = df.withColumn(
        "heat_index",
        when(
            (col("temperature_fahrenheit") >= 80) & (col("humidity_percent") >= 40),
            spark_round(
                -42.379
                + 2.04901523 * col("temperature_fahrenheit")
                + 10.14333127 * col("humidity_percent")
                - 0.22475541 * col("temperature_fahrenheit") * col("humidity_percent")
                - 0.00683783 * col("temperature_fahrenheit") ** 2
                - 0.05481717 * col("humidity_percent") ** 2
                + 0.00122874 * col("temperature_fahrenheit") ** 2 * col("humidity_percent")
                + 0.00085282 * col("temperature_fahrenheit") * col("humidity_percent") ** 2
                - 0.00000199 * col("temperature_fahrenheit") ** 2 * col("humidity_percent") ** 2,
                1
            )
        ).otherwise(col("temperature_fahrenheit"))
    )
    print("✅ Calculated Heat Index")
    return df


def calculate_wind_chill(df):
    df = df.withColumn(
        "wind_chill",
        when(
            (col("temperature_fahrenheit") <= 50) & (col("wind_speed_mph") > 3),
            spark_round(
                35.74 + 0.6215 * col("temperature_fahrenheit")
                - 35.75 * (col("wind_speed_mph") ** 0.16)
                + 0.4275 * col("temperature_fahrenheit") * (col("wind_speed_mph") ** 0.16),
                1
            )
        ).otherwise(col("temperature_fahrenheit"))
    )
    print("✅ Calculated Wind Chill")
    return df


def add_extreme_weather_flags(df):
    df = (
        df
        .withColumn("is_heatwave", when(col("heat_index") >= 105, lit(1)).otherwise(lit(0)))
        .withColumn("is_extreme_cold", when(col("wind_chill") <= 0, lit(1)).otherwise(lit(0)))
        .withColumn("is_high_wind", when(col("wind_speed_mph") >= 40, lit(1)).otherwise(lit(0)))
        .withColumn("is_heavy_precipitation", when(col("precipitation_mm") >= 7.6, lit(1)).otherwise(lit(0)))
        .withColumn(
            "is_extreme_weather",
            when(
                (col("is_heatwave") == 1) | (col("is_extreme_cold") == 1) |
                (col("is_high_wind") == 1) | (col("is_heavy_precipitation") == 1),
                lit(1)
            ).otherwise(lit(0))
        )
    )
    ext = df.filter(col("is_extreme_weather") == 1).count()
    total = df.count()
    print(f"🌪️  Extreme weather: {ext}/{total} ({round(ext/max(total,1)*100, 1)}%)")
    return df


def add_time_features(df):
    df = (
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
            when((col("hour_of_day") >= 6) & (col("hour_of_day") <= 18), lit(1)).otherwise(lit(0))
        )
    )
    print("✅ Added time features")
    return df


def add_city_statistics(df):
    city_window = Window.partitionBy("city")
    df = (
        df
        .withColumn("city_avg_temp", spark_round(avg("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_min_temp", spark_round(spark_min("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_max_temp", spark_round(spark_max("temperature_fahrenheit").over(city_window), 1))
        .withColumn("city_stddev_temp", spark_round(stddev("temperature_fahrenheit").over(city_window), 2))
        .withColumn("city_avg_humidity", spark_round(avg("humidity_percent").over(city_window), 1))
        .withColumn(
            "temperature_anomaly",
            spark_round(col("temperature_fahrenheit") - col("city_avg_temp"), 1)
        )
        .withColumn(
            "temp_anomaly_score",
            when(col("city_stddev_temp") > 0,
                 spark_round(spark_abs(col("temperature_fahrenheit") - col("city_avg_temp")) / col("city_stddev_temp"), 2)
            ).otherwise(lit(0.0))
        )
    )
    print("✅ Added city statistics and anomaly scores")
    return df


def write_gold(df):
    output_path = "data/gold/weather_features"
    df.write.mode("overwrite").partitionBy("reading_date").parquet(output_path)
    print(f"💾 Wrote {df.count()} records to Gold: {output_path}")


def main():
    print("=" * 60)
    print("🥇 GOLD LAYER - Silver → Gold Feature Engineering")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    df = read_silver(spark)
    if df is None:
        spark.stop()
        return

    df = calculate_heat_index(df)
    df = calculate_wind_chill(df)
    df = add_extreme_weather_flags(df)
    df = add_time_features(df)
    df = add_city_statistics(df)
    df = df.withColumn("gold_loaded_at", current_timestamp())
    write_gold(df)

    # Summary
    print("\n" + "=" * 60)
    print("📊 GOLD LAYER SUMMARY")
    print("=" * 60)
    print(f"Records: {df.count()}")
    print(f"Features: {len(df.columns)}")
    print(f"Cities: {df.select('city').distinct().count()}")
    print(f"\nTemperature by city:")
    df.groupBy("city").agg(
        spark_round(avg("temperature_fahrenheit"), 1).alias("avg_temp"),
        spark_round(avg("temp_anomaly_score"), 2).alias("avg_anomaly"),
        count("*").alias("records"),
    ).orderBy("avg_temp", ascending=False).show(20, truncate=False)

    print(f"Extreme weather distribution:")
    df.groupBy("is_extreme_weather").count().show()
    print(f"\n✅ Gold layer complete! {len(df.columns)} features ready for ML")
    spark.stop()


if __name__ == "__main__":
    main()