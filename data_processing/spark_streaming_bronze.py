"""
Spark Structured Streaming: Kafka → Bronze Layer
==================================================
Reads Avro messages from Kafka (matching the global producer),
deserializes them, writes as Parquet to Bronze.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, to_date, udf
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
import io
import fastavro
import json


# Schema matching the producer's flat Avro output
BRONZE_SCHEMA = StructType([
    StructField("city", StringType(), True),
    StructField("country", StringType(), True),
    StructField("continent", StringType(), True),
    StructField("region", StringType(), True),
    StructField("state", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("temperature_fahrenheit", DoubleType(), True),
    StructField("temperature_celsius", DoubleType(), True),
    StructField("humidity_percent", DoubleType(), True),
    StructField("pressure_hpa", DoubleType(), True),
    StructField("wind_speed_mph", DoubleType(), True),
    StructField("wind_direction_degrees", DoubleType(), True),
    StructField("weather_condition", StringType(), True),
    StructField("weather_description", StringType(), True),
    StructField("cloud_cover_percent", DoubleType(), True),
    StructField("visibility_miles", DoubleType(), True),
    StructField("precipitation_mm", DoubleType(), True),
    StructField("timestamp", StringType(), True),
    StructField("ingestion_timestamp", StringType(), True),
])

# Avro schema — must EXACTLY match the producer's AVRO_SCHEMA
AVRO_SCHEMA = {
    "type": "record",
    "name": "WeatherReading",
    "namespace": "com.climate.weather",
    "fields": [
        {"name": "city", "type": "string"},
        {"name": "country", "type": "string"},
        {"name": "continent", "type": "string"},
        {"name": "region", "type": "string"},
        {"name": "state", "type": ["null", "string"], "default": None},
        {"name": "latitude", "type": "double"},
        {"name": "longitude", "type": "double"},
        {"name": "temperature_fahrenheit", "type": "double"},
        {"name": "temperature_celsius", "type": "double"},
        {"name": "humidity_percent", "type": "double"},
        {"name": "pressure_hpa", "type": "double"},
        {"name": "wind_speed_mph", "type": "double"},
        {"name": "wind_direction_degrees", "type": "double"},
        {"name": "weather_condition", "type": "string"},
        {"name": "weather_description", "type": "string"},
        {"name": "cloud_cover_percent", "type": "double"},
        {"name": "visibility_miles", "type": "double"},
        {"name": "precipitation_mm", "type": "double"},
        {"name": "timestamp", "type": "string"},
        {"name": "ingestion_timestamp", "type": "string"},
    ]
}

PARSED_SCHEMA = fastavro.parse_schema(AVRO_SCHEMA)


def create_spark_session():
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Bronze")
        .master("local[*]")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1")
        .config("spark.sql.streaming.checkpointLocation", "data/checkpoints/bronze")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def deserialize_avro_message(raw_bytes):
    """Deserialize Avro message from Kafka — NO 5-byte header (schemaless_writer)."""
    if raw_bytes is None:
        return None
    try:
        bytes_io = io.BytesIO(raw_bytes)
        record = fastavro.schemaless_reader(bytes_io, PARSED_SCHEMA)
        return json.dumps(record)
    except Exception as e:
        # If schemaless fails, try skipping 5-byte Confluent header
        try:
            bytes_io = io.BytesIO(raw_bytes[5:])
            record = fastavro.schemaless_reader(bytes_io, PARSED_SCHEMA)
            return json.dumps(record)
        except:
            return None


def start_bronze_stream():
    print("=" * 60)
    print("🏗️  BRONZE LAYER - Spark Structured Streaming")
    print("   Reading from Kafka → Writing to data/bronze/")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    from pyspark.sql.functions import from_json
    deserialize_udf = udf(deserialize_avro_message, StringType())

    # Read from Kafka
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "raw-weather-data")
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )

    print("✅ Connected to Kafka topic: raw-weather-data")

    # Deserialize Avro → JSON → Structured columns
    parsed_df = (
        kafka_df
        .withColumn("json_string", deserialize_udf(col("value")))
        .filter(col("json_string").isNotNull())
        .select(from_json(col("json_string"), BRONZE_SCHEMA).alias("data"))
        .select("data.*")
        .withColumn("bronze_loaded_at", current_timestamp())
        .withColumn("ingestion_date", to_date(col("timestamp")))
    )

    # Write to Bronze as Parquet
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
    print("   Trigger: every 30 seconds")
    print("   Press Ctrl+C to stop\n")

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n🛑 Streaming stopped by user")
        query.stop()
        spark.stop()


if __name__ == "__main__":
    start_bronze_stream()