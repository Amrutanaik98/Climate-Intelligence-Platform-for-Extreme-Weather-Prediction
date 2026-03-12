"""
Weather Report Generator
=========================
Takes weather data + ML predictions and generates
natural language reports using Groq LLM.

Run: python genai/report_generator.py
"""

import os
import logging
import pandas as pd
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
        prompt = f"""You are a professional weather analyst for the Climate Intelligence Platform.
Based on the following weather data, generate a concise weather intelligence report.

WEATHER DATA:
- City: {weather_data.get('city', 'Unknown')}, {weather_data.get('state', '')}
- Country: {weather_data.get('country', '')}
- Continent: {weather_data.get('continent', '')}
- Temperature: {weather_data.get('temperature_fahrenheit', 'N/A')}°F ({weather_data.get('temperature_celsius', 'N/A')}°C)
- Humidity: {weather_data.get('humidity_percent', 'N/A')}%
- Wind Speed: {weather_data.get('wind_speed_mph', 'N/A')} mph
- Pressure: {weather_data.get('pressure_hpa', 'N/A')} hPa
- Heat Index: {weather_data.get('heat_index', 'N/A')}°F
- Wind Chill: {weather_data.get('wind_chill', 'N/A')}°F
- Weather Condition: {weather_data.get('weather_condition', 'N/A')}
- Extreme Weather Flag: {'YES' if weather_data.get('is_extreme_weather', 0) == 1 else 'NO'}
- Temperature Anomaly Score: {weather_data.get('temp_anomaly_score', 'N/A')}
- Temperature Anomaly: {weather_data.get('temperature_anomaly', 'N/A')}°F
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
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Report generation failed: {e}"

    def generate_batch_report(self, weather_records: list) -> str:
        cities_summary = "\n".join([
            f"- {r.get('city', '?')}, {r.get('country', '?')}: "
            f"{r.get('temperature_fahrenheit', '?')}°F, "
            f"Humidity {r.get('humidity_percent', '?')}%, "
            f"{'⚠️ EXTREME' if r.get('is_extreme_weather', 0) == 1 else 'Normal'}"
            for r in weather_records[:30]
        ])

        prompt = f"""You are a weather analyst. Generate a brief global weather summary 
based on these {len(weather_records)} city readings across 6 continents:

{cities_summary}

INSTRUCTIONS:
1. Identify the hottest and coldest cities globally
2. Note any extreme weather conditions
3. Provide continental/regional patterns
4. Keep it under 200 words
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a global weather intelligence analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Batch report failed: {e}"


def main():
    print("=" * 60)
    print("📝 WEATHER REPORT GENERATOR")
    print("=" * 60)

    df = pd.read_parquet("data/gold/weather_features")
    logger.info(f"Loaded {len(df)} records, {df['city'].nunique()} cities")

    generator = WeatherReportGenerator()

    # Generate report for one city
    phoenix = df[df['city'] == 'Phoenix']
    if len(phoenix) > 0:
        sample = phoenix.iloc[0].to_dict()
        print("\n📍 Single City Report (Phoenix):")
        print("-" * 40)
        report = generator.generate_report(sample)
        print(report)
    else:
        sample = df.iloc[0].to_dict()
        print(f"\n📍 Single City Report ({sample['city']}):")
        print("-" * 40)
        report = generator.generate_report(sample)
        print(report)

    # Generate batch report
    latest = df.drop_duplicates(subset=['city'], keep='last')
    records = latest.to_dict('records')
    print(f"\n\n🌎 Global Summary Report ({len(records)} cities):")
    print("-" * 40)
    batch_report = generator.generate_batch_report(records)
    print(batch_report)

    print("\n✅ Report generation complete!")


if __name__ == "__main__":
    main()