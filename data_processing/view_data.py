import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "airflow",
    "password": "airflow",
    "database": "airflow"
}

def view_processed_data(limit=20):
    """Query and display processed data"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Query processed data
        query = f"""
        SELECT 
            location,
            temperature,
            humidity,
            wind_speed,
            heat_index,
            extreme_event,
            processed_at
        FROM processed_data
        ORDER BY processed_at DESC
        LIMIT {limit}
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            print("\n" + "="*100)
            print("📊 PROCESSED WEATHER DATA (Last {} Records)".format(limit))
            print("="*100)
            print(f"{'Location':<20} {'Temp':<10} {'Humidity':<10} {'Wind':<10} {'Heat Idx':<10} {'Extreme':<10} {'Time':<30}")
            print("-"*100)
            
            for row in rows:
                location, temp, humidity, wind, heat_idx, extreme, processed_at = row
                print(f"{location:<20} {temp:<10.1f} {humidity:<10.1f} {wind:<10.1f} {heat_idx:<10.1f} {extreme:<10} {str(processed_at):<30}")
            
            print("="*100)
            print(f"✅ Total records shown: {len(rows)}")
            print("="*100 + "\n")
        else:
            print("❌ No data found in database")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    view_processed_data(limit=20)
