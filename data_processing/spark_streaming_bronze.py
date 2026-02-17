"""
Spark Structured Streaming: Kafka → Bronze Layer (FIXED)
=========================================================
Reads Avro-encoded messages from Kafka, deserializes them,
and writes as Parquet files to the Bronze layer.

FIX: The producer sends AVRO (binary), not JSON.
We use fastavro to deserialize the Avro bytes.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, to_date, udf, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType
)
import io
import fastavro
import json


# ============================================================
# SCHEMA: What the final Bronze columns look like
# ============================================================
BRONZE_SCHEMA = StructType([
    StructField("message_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("ingestion_timestamp", StringType(), True),
    StructField("source", StringType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("country", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
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
    return (
        SparkSession.builder
        .appName("ClimateIntelligence-Bronze")
        .master("local[*]")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1"
        )
        .config("spark.sql.streaming.checkpointLocation", "data/checkpoints/bronze")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def deserialize_avro_message(raw_bytes):
    """
    Deserialize a single Avro message from Kafka.
    
    WHY: The producer uses AvroSerializer which adds a 5-byte header
    (1 magic byte + 4 bytes schema ID) before the actual Avro data.
    We need to skip those 5 bytes, then use fastavro to read the rest.
    """
    if raw_bytes is None:
        return None

    try:
        # Skip the first 5 bytes (Confluent Avro wire format header)
        # Byte 0: Magic byte (0x00)
        # Bytes 1-4: Schema ID (4 bytes, big-endian int)
        # Bytes 5+: Actual Avro-encoded data
        avro_bytes = raw_bytes[5:]

        # Use fastavro to deserialize
        bytes_io = io.BytesIO(avro_bytes)
        record = fastavro.schemaless_reader(
            bytes_io,
            # The Avro schema (must match producer's schema)
            {
                "type": "record",
                "name": "WeatherReading",
                "namespace": "com.climate.platform",
                "fields": [
                    {"name": "message_id", "type": "string"},
                    {"name": "timestamp", "type": "string"},
                    {"name": "ingestion_timestamp", "type": "string"},
                    {"name": "source", "type": {"type": "enum", "name": "DataSource", "symbols": ["NOAA", "OPENWEATHERMAP", "NASA", "MOCK"]}},
                    {"name": "location", "type": {"type": "record", "name": "Location", "fields": [
                        {"name": "city", "type": "string"},
                        {"name": "state", "type": ["null", "string"], "default": None},
                        {"name": "country", "type": "string", "default": "US"},
                        {"name": "latitude", "type": "double"},
                        {"name": "longitude", "type": "double"}
                    ]}},
                    {"name": "temperature_fahrenheit", "type": ["null", "double"], "default": None},
                    {"name": "temperature_celsius", "type": ["null", "double"], "default": None},
                    {"name": "humidity_percent", "type": ["null", "double"], "default": None},
                    {"name": "pressure_hpa", "type": ["null", "double"], "default": None},
                    {"name": "wind_speed_mph", "type": ["null", "double"], "default": None},
                    {"name": "wind_direction_degrees", "type": ["null", "int"], "default": None},
                    {"name": "precipitation_mm", "type": ["null", "double"], "default": None},
                    {"name": "visibility_km", "type": ["null", "double"], "default": None},
                    {"name": "cloud_cover_percent", "type": ["null", "int"], "default": None},
                    {"name": "weather_condition", "type": ["null", "string"], "default": None},
                    {"name": "uv_index", "type": ["null", "double"], "default": None},
                ]
            }
        )

        # Flatten the location nested field and convert to JSON string
        location = record.get("location", {})
        flat = {
            "message_id": record.get("message_id"),
            "timestamp": record.get("timestamp"),
            "ingestion_timestamp": record.get("ingestion_timestamp"),
            "source": record.get("source"),
            "city": location.get("city"),
            "state": location.get("state"),
            "country": location.get("country", "US"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "temperature_fahrenheit": record.get("temperature_fahrenheit"),
            "temperature_celsius": record.get("temperature_celsius"),
            "humidity_percent": record.get("humidity_percent"),
            "pressure_hpa": record.get("pressure_hpa"),
            "wind_speed_mph": record.get("wind_speed_mph"),
            "wind_direction_degrees": record.get("wind_direction_degrees"),
            "precipitation_mm": record.get("precipitation_mm"),
            "visibility_km": record.get("visibility_km"),
            "cloud_cover_percent": record.get("cloud_cover_percent"),
            "weather_condition": record.get("weather_condition"),
            "uv_index": record.get("uv_index"),
        }
        return json.dumps(flat)

    except Exception as e:
        return None


def start_bronze_stream():
    print("=" * 60)
    print("🏗️  BRONZE LAYER - Spark Structured Streaming")
    print("   Reading from Kafka → Writing to data/bronze/")
    print("=" * 60)

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Register the Avro deserializer as a UDF
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

    # Step 1: Deserialize Avro bytes to JSON string using UDF
    # Step 2: Parse JSON string into structured columns
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
    print("   Partitioned by: ingestion_date")
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