"""
Text-to-SQL Query Engine
==========================
Converts natural language questions to SQL queries,
executes them against the PostgreSQL warehouse,
and returns natural language answers.

Run: python genai/text_to_sql.py
"""

import os
import logging
import psycopg2
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TextToSQL")


class TextToSQLEngine:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
        self.db_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "airflow"),
            "user": os.getenv("POSTGRES_USER", "airflow"),
            "password": os.getenv("POSTGRES_PASSWORD", "airflow"),
        }
        logger.info("✅ Text-to-SQL Engine initialized")

    def _get_schema_info(self) -> str:
        return """
DATABASE SCHEMA (PostgreSQL):

TABLE: climate_warehouse.fact_weather_readings
  - reading_key (INT, PRIMARY KEY)
  - location_key (INT, FK to dim_location)
  - weather_type_key (INT, FK to dim_weather_type)
  - temperature_fahrenheit (FLOAT)
  - temperature_celsius (FLOAT)
  - humidity_percent (FLOAT)
  - pressure_hpa (FLOAT)
  - wind_speed_mph (FLOAT)
  - wind_direction_degrees (FLOAT)
  - precipitation_mm (FLOAT)
  - visibility_miles (FLOAT)
  - cloud_cover_percent (FLOAT)
  - heat_index (FLOAT)
  - wind_chill (FLOAT)
  - temperature_anomaly (FLOAT)
  - temp_anomaly_score (FLOAT)
  - is_extreme_weather (INT, 0 or 1)
  - data_quality_score (FLOAT)
  - loaded_at (TIMESTAMP)

TABLE: climate_warehouse.dim_location
  - location_key (INT, PRIMARY KEY)
  - city (VARCHAR)
  - state (VARCHAR)
  - latitude (FLOAT)
  - longitude (FLOAT)
  - region (VARCHAR)

TABLE: climate_warehouse.dim_weather_type
  - weather_type_key (INT, PRIMARY KEY)
  - weather_condition (VARCHAR)
  - weather_group (VARCHAR)
"""

    def question_to_sql(self, question: str) -> str:
        schema = self._get_schema_info()

        prompt = f"""You are a SQL expert. Convert the user's question to a PostgreSQL query.

{schema}

RULES:
1. Only generate SELECT queries (never INSERT, UPDATE, DELETE, DROP)
2. Always use the schema prefix: climate_warehouse.
3. Use JOINs when needed to get city names from dim_location
4. Use ROUND() for decimal values
5. Limit results to 20 rows maximum
6. Return ONLY the SQL query, nothing else (no explanation, no markdown)

USER QUESTION: {question}

SQL QUERY:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Return only SQL, no explanation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.1,
            )
            sql = response.choices[0].message.content.strip()
            sql = sql.replace("```sql", "").replace("```", "").strip()
            return sql
        except Exception as e:
            return f"Error: {e}"

    def execute_sql(self, sql: str) -> list:
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def results_to_natural_language(self, question: str, sql: str, results: list) -> str:
        results_str = str(results[:10])

        prompt = f"""The user asked: "{question}"

We ran this SQL query: {sql}

And got these results: {results_str}

Please provide a natural language answer to the user's question based on these results.
Be specific with numbers and city names. Keep it under 100 words."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Summarize SQL results in natural language."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {e}"

    def ask(self, question: str) -> dict:
        logger.info(f"❓ Question: {question}")

        sql = self.question_to_sql(question)
        logger.info(f"📝 SQL: {sql}")

        results = self.execute_sql(sql)
        logger.info(f"📊 Results: {len(results)} rows")

        if results and "error" in results[0]:
            return {
                "question": question,
                "sql": sql,
                "results": results,
                "answer": f"SQL error: {results[0]['error']}. Try rephrasing your question.",
            }

        answer = self.results_to_natural_language(question, sql, results)

        return {
            "question": question,
            "sql": sql,
            "results": results,
            "answer": answer,
        }


def main():
    print("=" * 60)
    print("🔤 TEXT-TO-SQL QUERY ENGINE")
    print("=" * 60)

    engine = TextToSQLEngine()

    questions = [
        "What is the average temperature for each city?",
        "Which cities have extreme weather conditions?",
        "What is the hottest city in the dataset?",
        "How many weather readings do we have in total?",
        "Show me cities with humidity above 80%",
        "What is the average wind speed by region?",
    ]

    for q in questions:
        print(f"\n❓ {q}")
        result = engine.ask(q)
        print(f"📝 SQL: {result['sql']}")
        print(f"🤖 Answer: {result['answer']}")
        print("-" * 40)

    print("\n✅ Text-to-SQL demo complete!")


if __name__ == "__main__":
    main()