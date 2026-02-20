"""
Weather Report Generator
=========================
Takes weather data + ML predictions and generates
natural language reports using Groq LLM.
"""

import os
import logging
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReportGenerator")


class WeatherReportGenerator:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
        logger.info("✅ Report Generator initialized with Groq")

    def generate_report(self, weather_data: dict) -> str:
        """
        Generate a natural language weather report from data.
        
        PROMPT ENGINEERING: We carefully structure the prompt to:
        1. Give the LLM a ROLE (weather analyst)
        2. Provide the DATA as context
        3. Specify the FORMAT we want
        4. Add CONSTRAINTS (be concise, factual)
        """
        prompt = f"""You are a professional weather analyst for the Climate Intelligence Platform.
Based on the following weather data, generate a concise weather intelligence report.

WEATHER DATA:
- City: {weather_data.get('city', 'Unknown')}, {weather_data.get('state', '')}
- Temperature: {weather_data.get('temperature_fahrenheit', 'N/A')}°F ({weather_data.get('temperature_celsius', 'N/A')}°C)
- Humidity: {weather_data.get('humidity_percent', 'N/A')}%
- Wind Speed: {weather_data.get('wind_speed_mph', 'N/A')} mph
- Pressure: {weather_data.get('pressure_hpa', 'N/A')} hPa
- Heat Index: {weather_data.get('heat_index', 'N/A')}°F
- Wind Chill: {weather_data.get('wind_chill', 'N/A')}°F
- Weather Condition: {weather_data.get('weather_condition', 'N/A')}
- Extreme Weather Flag: {'YES' if weather_data.get('is_extreme_weather', 0) == 1 else 'NO'}
- Temperature Anomaly Score: {weather_data.get('temp_anomaly_score', 'N/A')}
- Season: {weather_data.get('season', 'N/A')}

INSTRUCTIONS:
1. Start with a one-line summary of conditions
2. Mention any risks or warnings if extreme weather is detected
3. Compare to typical conditions for this location
4. Provide a brief recommendation
5. Keep it under 150 words
6. Use professional but accessible language
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional weather intelligence analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3,  # Low = more factual, less creative
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Report generation failed: {e}"

    def generate_batch_report(self, weather_records: list) -> str:
        """Generate a summary report for multiple cities."""
        cities_summary = "\n".join([
            f"- {r.get('city', '?')}, {r.get('state', '?')}: "
            f"{r.get('temperature_fahrenheit', '?')}°F, "
            f"Humidity {r.get('humidity_percent', '?')}%, "
            f"{'⚠️ EXTREME' if r.get('is_extreme_weather', 0) == 1 else 'Normal'}"
            for r in weather_records[:20]
        ])

        prompt = f"""You are a weather analyst. Generate a brief nationwide weather summary 
based on these {len(weather_records)} city readings:

{cities_summary}

INSTRUCTIONS:
1. Identify the hottest and coldest cities
2. Note any extreme weather conditions
3. Provide regional patterns
4. Keep it under 200 words
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a weather intelligence analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Batch report failed: {e}"


def main():
    """Test the report generator with Gold layer data."""
    print("=" * 60)
    print("📝 WEATHER REPORT GENERATOR")
    print("=" * 60)

    # Load Gold data
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("ReportGen").master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    df = spark.read.parquet("data/gold/weather_features").toPandas()
    spark.stop()

    generator = WeatherReportGenerator()

    # Generate report for one city
    sample = df[df['city'] == 'Phoenix'].iloc[0].to_dict()
    print("\n📍 Single City Report (Phoenix, AZ):")
    print("-" * 40)
    report = generator.generate_report(sample)
    print(report)

    # Generate batch report
    latest = df.drop_duplicates(subset=['city'], keep='last')
    records = latest.to_dict('records')
    print("\n\n🌎 Nationwide Summary Report:")
    print("-" * 40)
    batch_report = generator.generate_batch_report(records)
    print(batch_report)

    print("\n✅ Report generation complete!")


if __name__ == "__main__":
    main()