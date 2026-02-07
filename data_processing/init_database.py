import psycopg2
from psycopg2 import sql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PostgreSQL connection settings
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "airflow",
    "password": "airflow",
    "database": "airflow"
}

def create_tables():
    """Create PostgreSQL tables for weather data"""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        logger.info("✅ Connected to PostgreSQL")
        
        # Create raw_events table
        create_raw_events = """
        CREATE TABLE IF NOT EXISTS raw_events (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            location VARCHAR(100) NOT NULL,
            temperature FLOAT NOT NULL,
            humidity FLOAT NOT NULL,
            wind_speed FLOAT NOT NULL,
            pressure FLOAT NOT NULL,
            precipitation FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create processed_data table
        create_processed_data = """
        CREATE TABLE IF NOT EXISTS processed_data (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            location VARCHAR(100) NOT NULL,
            temperature FLOAT NOT NULL,
            humidity FLOAT NOT NULL,
            wind_speed FLOAT NOT NULL,
            pressure FLOAT NOT NULL,
            precipitation FLOAT NOT NULL,
            heat_index FLOAT,
            extreme_event INTEGER,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_raw_events)
        cursor.execute(create_processed_data)
        conn.commit()
        
        logger.info("✅ Tables created successfully")
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()
