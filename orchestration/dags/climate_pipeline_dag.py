"""
Climate Intelligence Platform - Main Pipeline DAG
==================================================
Orchestrates the entire data pipeline:
1. Ingest weather data (Kafka producer)
2. Bronze → Silver (cleaning)
3. Silver → Gold (feature engineering)
4. Gold → Warehouse (load star schema)
5. Data quality checks

Schedule: Daily at 6:00 AM UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator


# ============================================================
# DAG CONFIGURATION
# ============================================================

default_args = {
    "owner": "climate-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2025, 1, 1),
}


# ============================================================
# TASK FUNCTIONS
# ============================================================

def run_bronze_to_silver():
    """Execute Bronze → Silver Spark job."""
    import subprocess
    result = subprocess.run(
        ["python", "/opt/airflow/data_processing/spark_batch_silver.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise Exception("Bronze → Silver job failed!")


def run_silver_to_gold():
    """Execute Silver → Gold Spark job."""
    import subprocess
    result = subprocess.run(
        ["python", "/opt/airflow/data_processing/spark_batch_gold.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise Exception("Silver → Gold job failed!")


def run_warehouse_load():
    """Load Gold data into PostgreSQL warehouse."""
    import subprocess
    result = subprocess.run(
        ["python", "/opt/airflow/dags/load_warehouse.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise Exception("Warehouse load failed!")


def run_data_quality_check():
    """Run data quality checks on the warehouse."""
    import psycopg2

    conn = psycopg2.connect(
        host="postgres", port=5432,
        database="airflow", user="airflow", password="airflow"
    )
    cursor = conn.cursor()

    checks = {
        "Total fact records": "SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings",
        "Unique cities": "SELECT COUNT(DISTINCT city) FROM climate_warehouse.dim_location",
        "Records today": """
            SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings
            WHERE loaded_at::date = CURRENT_DATE
        """,
        "Extreme weather count": """
            SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings
            WHERE is_extreme_weather = 1
        """,
        "Null temperatures": """
            SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings
            WHERE temperature_fahrenheit IS NULL
        """,
    }

    print("=" * 60)
    print("📊 DATA QUALITY CHECK REPORT")
    print("=" * 60)

    all_passed = True
    for check_name, sql in checks.items():
        cursor.execute(sql)
        result = cursor.fetchone()[0]
        status = "✅" if result is not None else "❌"
        print(f"  {status} {check_name}: {result}")

        # Fail if null temperatures exceed 10%
        if check_name == "Null temperatures" and result > 0:
            cursor.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
            total = cursor.fetchone()[0]
            if total > 0 and (result / total) > 0.1:
                print(f"  ⚠️ WARNING: {result}/{total} null temperatures ({round(result/total*100, 1)}%)")
                all_passed = False

    conn.close()

    if not all_passed:
        raise Exception("Data quality check failed!")

    print("\n✅ All data quality checks passed!")


# ============================================================
# DAG DEFINITION
# ============================================================

with DAG(
    dag_id="climate_intelligence_pipeline",
    default_args=default_args,
    description="End-to-end climate data pipeline: Ingest → Process → Warehouse",
    schedule_interval="0 6 * * *",  # Daily at 6:00 AM UTC
    catchup=False,
    tags=["climate", "pipeline", "production"],
) as dag:

    # Task 1: Run producer to ingest data
    task_ingest = BashOperator(
        task_id="ingest_weather_data",
        bash_command="echo 'Weather data ingestion triggered (producer running continuously)'",
    )

    # Task 2: Bronze → Silver
    task_silver = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=run_bronze_to_silver,
    )

    # Task 3: Silver → Gold
    task_gold = PythonOperator(
        task_id="silver_to_gold",
        python_callable=run_silver_to_gold,
    )

    # Task 4: Gold → Warehouse
    task_warehouse = PythonOperator(
        task_id="load_warehouse",
        python_callable=run_warehouse_load,
    )

    # Task 5: Data Quality Check
    task_quality = PythonOperator(
        task_id="data_quality_check",
        python_callable=run_data_quality_check,
    )

    # ============================================================
    # TASK DEPENDENCIES (the arrows in the DAG)
    # ============================================================
    task_ingest >> task_silver >> task_gold >> task_warehouse >> task_quality