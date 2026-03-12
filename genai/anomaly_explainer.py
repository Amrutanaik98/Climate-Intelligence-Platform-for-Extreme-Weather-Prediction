"""
Anomaly Explanation Engine
===========================
When ML models detect weather anomalies, this engine
uses an LLM to explain WHY in plain English.

Run: python genai/anomaly_explainer.py
"""

import os
import logging
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnomalyExplainer")


class AnomalyExplainer:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
        logger.info("✅ Anomaly Explainer initialized")

    def explain_anomaly(self, weather_data: dict) -> str:
        prompt = f"""You are a meteorologist analyzing weather anomalies.

ANOMALOUS WEATHER READING:
- City: {weather_data.get('city', 'Unknown')}, {weather_data.get('state', '')}
- Country: {weather_data.get('country', '')}
- Continent: {weather_data.get('continent', '')}
- Current Temperature: {weather_data.get('temperature_fahrenheit', 'N/A')}°F
- City Average Temperature: {weather_data.get('city_avg_temp', 'N/A')}°F
- Temperature Anomaly: {weather_data.get('temperature_anomaly', 'N/A')}°F from average
- Anomaly Score: {weather_data.get('temp_anomaly_score', 'N/A')} standard deviations
- Humidity: {weather_data.get('humidity_percent', 'N/A')}%
- Pressure: {weather_data.get('pressure_hpa', 'N/A')} hPa
- Wind Speed: {weather_data.get('wind_speed_mph', 'N/A')} mph
- Heat Index: {weather_data.get('heat_index', 'N/A')}°F
- Season: {weather_data.get('season', 'N/A')}
- Extreme Weather Flags: Heatwave={weather_data.get('is_heatwave', 0)}, 
  Extreme Cold={weather_data.get('is_extreme_cold', 0)}, 
  High Wind={weather_data.get('is_high_wind', 0)}

EXPLAIN:
1. Why is this reading anomalous compared to the city average?
2. What weather pattern could cause this?
3. What are the potential risks?
4. What precautions should be taken?
Keep it under 150 words.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert meteorologist."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Explanation failed: {e}"


def main():
    print("=" * 60)
    print("🔍 ANOMALY EXPLANATION ENGINE")
    print("=" * 60)

    df = pd.read_parquet("data/gold/weather_features")
    logger.info(f"Loaded {len(df)} records, {df['city'].nunique()} cities")

    explainer = AnomalyExplainer()

    # Find records with highest anomaly scores
    anomalies = df.nlargest(3, 'temp_anomaly_score')

    for i, (_, row) in enumerate(anomalies.iterrows(), 1):
        data = row.to_dict()
        city = data.get('city', 'Unknown')
        state = data.get('state', '')
        country = data.get('country', '')
        print(f"\n🌡️ Anomaly #{i}: {city}, {state} ({country})")
        print(f"   Temperature: {data['temperature_fahrenheit']}°F "
              f"(avg: {data['city_avg_temp']}°F, anomaly: {data['temperature_anomaly']}°F)")
        print(f"   Anomaly Score: {data['temp_anomaly_score']}")
        print("-" * 40)
        explanation = explainer.explain_anomaly(data)
        print(explanation)

    print("\n✅ Anomaly explanations complete!")


if __name__ == "__main__":
    main()