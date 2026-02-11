"""
Spark Structured Streaming: Kafka → Bronze Layer
=================================================
This job runs CONTINUOUSLY. It reads every new message from
Kafka topic 'raw-weather-data' and writes it as Parquet files
to the Bronze layer.

Bronze layer = EXACT copy of what came from Kafka. No cleaning,
no transformations. If the raw data has nulls or duplicates,
Bronze has them too. This is intentional — we never lose the original.

WHY Parquet instead of CSV?
- Parquet is COLUMNAR: if you only need temperature, it reads
  only the temperature column (CSV reads the entire row)
- Parquet is COMPRESSED: 1GB CSV = ~200MB Parquet
- Parquet stores DATA TYPES: temperature is always a float,
  not a string that looks like a float
- Parquet supports PARTITIONING: data split by date for fast queries
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, current_timestamp, to_date,
    year, month, dayofmonth, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, TimestampType
)


# ============================================================
# STEP 1: Define the schema of our Kafka messages
#
# This MUST match what your Kafka producer sends.
# If the producer sends {"temperature": 75.3, "city": "NYC"},
# the schema must have temperature as Double and city as String.
# ============================================================

WEATHER_SCHEMA = StructType([
    StructField("message_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("ingestion_timestamp", StringType(), True),
    StructField("source", StringType(), True),
    StructField("location", StructType([
        StructField("city", StringType(), True),
        StructField("state", StringType(), True),
        StructField("country", StringType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
    ]), True),
    StructField("temperature_fahrenheit", DoubleType(), True),
    StructField("temperature_celsius", DoubleType(), True),
    StructField("humidity_percent", DoubleType(), True),
    StructField("pressure_hpa", DoubleType(), True),
    StructField("wind_speed_mph", DoubleType(), True),
    StructField("wind_direction_degrees", IntegerType(), True),
    StructField("precipitation_mm", DoubleType(), True),
    StructField("visibility_km", DoubleType(), True),
    StructField("cloud_cover_percent", IntegerType(), True),
    StructField("weather_condition", StringType(), True),
    StructField("uv_index", DoubleType(), True),
])


def create_spark_session():
    """
    Create a SparkSession with Kafka integration.
    
    The .config() calls load the required JAR files that let
    Spark talk to Kafka. Without these, Spark doesn't know
    how to read from Kafka.
    """
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Bronze")
        .master("local[*]")  # Use all available CPU cores
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
        )
        .config("spark.sql.streaming.checkpointLocation", "data/checkpoints/bronze")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def start_bronze_stream():
    """
    Main function: Read from Kafka → Write to Bronze layer as Parquet.
    """
    print("=" * 60)
    print("🏗️  BRONZE LAYER - Spark Structured Streaming")
    print("   Reading from Kafka → Writing to data/bronze/")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # --------------------------------------------------------
    # STEP 2: Read from Kafka
    #
    # Kafka messages have a KEY and VALUE.
    # The VALUE is our weather JSON (as bytes).
    # We need to:
    #   1. Read the raw bytes from Kafka
    #   2. Convert bytes to string
    #   3. Parse the JSON string into columns
    # --------------------------------------------------------

    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "raw-weather-data")
        .option("startingOffsets", "earliest")  # Read all existing messages too
        .option("failOnDataLoss", "false")
        .load()
    )

    print("✅ Connected to Kafka topic: raw-weather-data")

    # --------------------------------------------------------
    # STEP 3: Parse Kafka messages
    #
    # Kafka gives us columns: key, value, topic, partition, offset, timestamp
    # We only care about 'value' (our weather JSON)
    #
    # .cast("string") → converts bytes to readable string
    # from_json() → parses JSON string into structured columns
    # .select("data.*") → flattens the nested structure
    # --------------------------------------------------------

    parsed_df = (
        kafka_df
        # Convert Kafka value from bytes to string
        .selectExpr("CAST(value AS STRING) as json_string")
        # Parse JSON string using our schema
        .select(from_json(col("json_string"), WEATHER_SCHEMA).alias("data"))
        # Flatten: extract all fields from nested 'data' struct
        .select("data.*")
        # Flatten the nested 'location' struct
        .select(
            col("message_id"),
            col("timestamp"),
            col("ingestion_timestamp"),
            col("source"),
            col("location.city").alias("city"),
            col("location.state").alias("state"),
            col("location.country").alias("country"),
            col("location.latitude").alias("latitude"),
            col("location.longitude").alias("longitude"),
            col("temperature_fahrenheit"),
            col("temperature_celsius"),
            col("humidity_percent"),
            col("pressure_hpa"),
            col("wind_speed_mph"),
            col("wind_direction_degrees"),
            col("precipitation_mm"),
            col("visibility_km"),
            col("cloud_cover_percent"),
            col("weather_condition"),
            col("uv_index"),
        )
        # Add processing metadata
        .withColumn("bronze_loaded_at", current_timestamp())
        .withColumn("ingestion_date", to_date(col("timestamp")))
    )

    # --------------------------------------------------------
    # STEP 4: Write to Bronze Layer as Parquet
    #
    # .partitionBy("ingestion_date")
    #   → Creates folder structure: bronze/ingestion_date=2025-07-15/
    #   → When you query "give me July 15 data", Spark only reads
    #     that ONE folder, not the entire dataset. This is HUGE
    #     for performance when you have months of data.
    #
    # .trigger(processingTime="30 seconds")
    #   → Process new messages every 30 seconds
    #   → In production, you might use "10 seconds" or even continuous
    #
    # .outputMode("append")
    #   → Only write NEW data (don't rewrite existing data)
    #
    # checkpointLocation
    #   → Spark saves its progress here. If it crashes and restarts,
    #     it knows EXACTLY where it left off in Kafka (no duplicate
    #     or lost data). This is called "exactly-once processing."
    # --------------------------------------------------------

    query = (
        parsed_df.writeStream
        .format("parquet")
        .option("path", "data/bronze/weather_readings")
        .option("checkpointLocation", "data/checkpoints/bronze")
        .partitionBy("ingestion_date")
        .outputMode("append")
        .trigger(processingTime="30 seconds")
        .start()
    )

    print("✅ Streaming started! Writing Parquet to data/bronze/")
    print("   Partitioned by: ingestion_date")
    print("   Trigger: every 30 seconds")
    print("   Press Ctrl+C to stop\n")

    # Keep running until stopped
    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n🛑 Streaming stopped by user")
        query.stop()
        spark.stop()


if __name__ == "__main__":
    start_bronze_stream()