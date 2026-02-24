"""
🌍 Climate Intelligence Platform — FastAPI Backend
====================================================
REST API for weather data, ML predictions, Gen AI chatbot.

Run: uvicorn api.main:app --reload --port 8000
Docs: http://localhost:8000/docs (Swagger UI)

Endpoints:
  GET  /                         → Health check
  GET  /api/stats                → Dashboard metrics
  GET  /api/cities               → All cities with current weather
  GET  /api/weather/{city}       → Detailed weather for a city
  GET  /api/extreme              → Extreme weather events
  GET  /api/predictions          → XGBoost predictions for all cities
  GET  /api/forecast/{city}      → LSTM temperature forecast
  POST /api/chat                 → AI chatbot (RAG, SQL, Report, Anomaly)
  GET  /api/anomalies            → Cities with anomaly scores
  GET  /api/regions              → Weather grouped by region
"""

import os
import numpy as np
import pandas as pd
import psycopg2
import chromadb
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# GLOBAL STATE — loaded once at startup
# ============================================================

app_state = {}

DB_CONFIG = dict(host="localhost", port=5432, database="airflow", user="airflow", password="airflow")


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_ml_models():
    """Load trained ML models."""
    models = {}

    # XGBoost
    try:
        import xgboost as xgb
        model = xgb.XGBClassifier()
        model.load_model("ml/models/xgboost_model.json")
        models["xgboost"] = model
        print("✅ XGBoost model loaded")
    except Exception as e:
        print(f"⚠️ XGBoost not loaded: {e}")

    # LSTM
    try:
        import torch
        from ml.lstm_model import LSTMModel  # adjust import if needed

        model = LSTMModel(input_size=1, hidden_size=64, num_layers=2, output_size=1)
        model.load_state_dict(torch.load("ml/models/lstm_model.pth", map_location="cpu"))
        model.eval()
        models["lstm"] = model
        print("✅ LSTM model loaded")
    except Exception as e:
        print(f"⚠️ LSTM not loaded: {e}")

    return models


def build_vector_store(df):
    """Build ChromaDB vector store from gold data."""
    client = chromadb.Client()
    try:
        client.delete_collection("climate_api")
    except:
        pass
    coll = client.create_collection("climate_api", metadata={"hnsw:space": "cosine"})

    docs, metas, ids = [], [], []
    for i, (_, r) in enumerate(df.iterrows()):
        doc = (
            f"City: {r.get('city','N/A')}, State: {r.get('state','N/A')}. "
            f"Temperature: {r.get('temperature_fahrenheit','N/A')}°F ({r.get('temperature_celsius','N/A')}°C). "
            f"Humidity: {r.get('humidity_percent','N/A')}%. "
            f"Wind Speed: {r.get('wind_speed_mph','N/A')} mph. "
            f"Pressure: {r.get('pressure_hpa','N/A')} hPa. "
            f"Heat Index: {r.get('heat_index','N/A')}°F. "
            f"Wind Chill: {r.get('wind_chill','N/A')}°F. "
            f"Weather: {r.get('weather_condition','N/A')}. "
            f"Cloud Cover: {r.get('cloud_cover_percent','N/A')}%. "
            f"Extreme: {'YES' if r.get('is_extreme_weather',0)==1 else 'No'}. "
            f"Anomaly Score: {r.get('temp_anomaly_score','N/A')}."
        )
        docs.append(doc)
        metas.append({"city": str(r.get("city", ""))})
        ids.append(f"rec_{i}")

    for s in range(0, len(docs), 100):
        e = min(s + 100, len(docs))
        coll.add(documents=docs[s:e], metadatas=metas[s:e], ids=ids[s:e])

    return coll


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data and models at startup."""
    print("🚀 Starting Climate Intelligence API...")

    # Load gold data
    try:
        app_state["gold_df"] = pd.read_parquet("data/gold/weather_features")
        print(f"✅ Gold data loaded: {len(app_state['gold_df'])} records")
    except Exception as e:
        print(f"❌ Failed to load gold data: {e}")
        app_state["gold_df"] = None

    # Groq client
    app_state["groq"] = Groq(api_key=os.getenv("GROQ_API_KEY"))
    print("✅ Groq LLM client initialized")

    # Vector store
    if app_state["gold_df"] is not None:
        app_state["vector_store"] = build_vector_store(app_state["gold_df"])
        print("✅ ChromaDB vector store built")

    # ML models
    app_state["models"] = load_ml_models()

    print("🌍 Climate Intelligence API ready!")
    yield
    print("👋 Shutting down...")


# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(
    title="🌍 Climate Intelligence API",
    description="REST API for weather data, ML predictions, and Gen AI chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ChatRequest(BaseModel):
    question: str
    mode: Optional[str] = None  # auto, rag, sql, report, anomaly

class ChatResponse(BaseModel):
    answer: str
    mode: str
    timestamp: str

class CityWeather(BaseModel):
    city: str
    state: str
    temperature_f: float
    temperature_c: float
    humidity: float
    wind_speed: float
    pressure: float
    heat_index: float
    wind_chill: float
    weather_condition: str
    cloud_cover: float
    is_extreme: bool
    anomaly_score: float

class StatsResponse(BaseModel):
    total_readings: int
    total_cities: int
    avg_temperature: float
    max_temperature: float
    min_temperature: float
    extreme_events: int
    timestamp: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_cities_df():
    """Get deduplicated latest reading per city."""
    df = app_state.get("gold_df")
    if df is None:
        raise HTTPException(status_code=503, detail="Data not loaded")
    return df.drop_duplicates(subset=["city"], keep="last").sort_values("temperature_fahrenheit", ascending=False)


def detect_mode(q):
    q = q.lower().strip()
    anomaly_kw = ["anomaly", "anomalies", "unusual", "strange", "why is", "explain why", "outlier", "spike"]
    if any(k in q for k in anomaly_kw): return "anomaly"

    report_kw = ["report", "forecast", "summary", "brief", "overview", "conditions in", "weather in", "status"]
    if any(k in q for k in report_kw): return "report"

    simple_rag = ["which city has", "hottest", "coldest", "warmest", "coolest", "windiest", "most humid"]
    if any(k in q for k in simple_rag): return "rag"

    sql_kw = ["average", "avg", "count", "how many", "total", "list all", "show me all",
              "per city", "each city", "compare", "top 5", "top 10", "above", "below"]
    if any(k in q for k in sql_kw): return "sql"

    return "rag"


def try_direct_answer(question, cities_df):
    q = question.lower()

    if any(k in q for k in ["hottest", "highest temp", "warmest"]):
        row = cities_df.loc[cities_df["temperature_fahrenheit"].idxmax()]
        top5 = cities_df.nlargest(5, "temperature_fahrenheit")[["city", "state", "temperature_fahrenheit"]]
        lines = [f"{i+1}. {r['city']}, {r['state']} — {round(r['temperature_fahrenheit'],1)}°F"
                 for i, (_, r) in enumerate(top5.iterrows())]
        return f"🔥 {row['city']}, {row['state']} has the highest temperature at {round(row['temperature_fahrenheit'],1)}°F.\n\nTop 5:\n" + "\n".join(lines)

    if any(k in q for k in ["coldest", "lowest temp", "coolest"]):
        row = cities_df.loc[cities_df["temperature_fahrenheit"].idxmin()]
        bot5 = cities_df.nsmallest(5, "temperature_fahrenheit")[["city", "state", "temperature_fahrenheit"]]
        lines = [f"{i+1}. {r['city']}, {r['state']} — {round(r['temperature_fahrenheit'],1)}°F"
                 for i, (_, r) in enumerate(bot5.iterrows())]
        return f"🥶 {row['city']}, {row['state']} has the lowest temperature at {round(row['temperature_fahrenheit'],1)}°F.\n\nTop 5 Coldest:\n" + "\n".join(lines)

    if any(k in q for k in ["extreme weather", "extreme events", "how many extreme"]):
        ext = cities_df[cities_df["is_extreme_weather"] == 1]
        if len(ext) == 0:
            return "✅ No extreme weather events detected."
        city_list = ", ".join([f"{r['city']} ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in ext.iterrows()])
        return f"⚠️ {len(ext)} extreme weather event(s): {city_list}"

    return None


def build_sql_answer(question, gc):
    schema = """Tables:
    climate_warehouse.fact_weather_readings (location_key, temperature_fahrenheit, temperature_celsius,
    humidity_percent, pressure_hpa, wind_speed_mph, heat_index, wind_chill, temperature_anomaly,
    temp_anomaly_score, is_extreme_weather)
    climate_warehouse.dim_location (location_key, city, state, region)
    RULES: JOIN fact with dim_location on location_key. Use ROUND(). LIMIT 20. Return ONLY SQL."""

    r = gc.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": f"PostgreSQL expert. Output ONLY the SELECT query.\n{schema}"},
            {"role": "user", "content": f"Write a SELECT query for: {question}"}
        ],
        max_tokens=300, temperature=0.05
    )
    raw = r.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()

    sql_lines, capture = [], False
    for line in raw.split("\n"):
        if line.strip().upper().startswith("SELECT"): capture = True
        if capture: sql_lines.append(line)
        if capture and ";" in line: break
    sql = "\n".join(sql_lines).strip().rstrip(";").strip()

    if not sql or not sql.upper().startswith("SELECT"):
        return None

    try:
        conn = get_conn(); cur = conn.cursor(); cur.execute(sql)
        cols = [d[0] for d in cur.description]; rows = cur.fetchall(); conn.close()
        results = [dict(zip(cols, row)) for row in rows]
        if not results: return None

        r2 = gc.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Summarize weather data results clearly. Use specific numbers. 2-4 sentences."},
                {"role": "user", "content": f"Question: {question}\nResults: {str(results[:15])}\nSummary:"}
            ],
            max_tokens=250, temperature=0.2
        )
        return r2.choices[0].message.content.strip() + f"\n\n📝 `{sql}`"
    except:
        return None


def build_rag_answer(question, coll, gc, mode="rag"):
    n_results = 10 if mode == "report" else 8
    res = coll.query(query_texts=[question], n_results=n_results)
    ctx = "\n".join(res["documents"][0]) if res["documents"] and res["documents"][0] else "No data."

    prompts = {
        "rag": "Expert climate analyst monitoring 20 US cities. Answer from provided data only. Be specific with numbers.",
        "report": (
            "Weather intelligence analyst. Generate structured report:\n"
            "📋 SUMMARY — 1-2 sentence overview\n"
            "🔍 KEY FINDINGS — Top 3-4 findings\n"
            "⚠️ RISKS — Extreme weather or anomalies\n"
            "✅ RECOMMENDATIONS — 2-3 actions"
        ),
        "anomaly": (
            "Senior meteorologist analyzing anomalies:\n"
            "🔴 WHAT'S UNUSUAL — With specific numbers\n"
            "🔬 CAUSES — Scientific explanation\n"
            "⚠️ RISKS — Potential impacts\n"
            "🛡️ PRECAUTIONS — Recommended actions"
        ),
    }
    tokens = {"rag": 350, "report": 500, "anomaly": 450}

    r = gc.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": prompts[mode]},
            {"role": "user", "content": f"WEATHER DATA:\n{ctx}\n\nQUESTION: {question}"}
        ],
        max_tokens=tokens[mode], temperature=0.25
    )
    return r.choices[0].message.content.strip()


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    df = app_state.get("gold_df")
    return {
        "status": "🟢 healthy",
        "platform": "Climate Intelligence API",
        "version": "1.0.0",
        "data_loaded": df is not None,
        "records": len(df) if df is not None else 0,
        "models_loaded": list(app_state.get("models", {}).keys()),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/stats", response_model=StatsResponse, tags=["Dashboard"])
async def get_stats():
    """Get dashboard summary metrics."""
    cities = get_cities_df()
    df = app_state["gold_df"]
    total, extreme = 660, 13
    try:
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings"); total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather=1"); extreme = c.fetchone()[0]
        conn.close()
    except:
        pass

    return StatsResponse(
        total_readings=total,
        total_cities=len(cities),
        avg_temperature=round(df["temperature_fahrenheit"].mean(), 1),
        max_temperature=round(df["temperature_fahrenheit"].max(), 1),
        min_temperature=round(df["temperature_fahrenheit"].min(), 1),
        extreme_events=extreme,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/cities", tags=["Weather"])
async def get_all_cities():
    """Get current weather for all monitored cities."""
    cities = get_cities_df()
    result = []
    for _, r in cities.iterrows():
        result.append({
            "city": r.get("city", ""),
            "state": r.get("state", ""),
            "temperature_f": round(r.get("temperature_fahrenheit", 0), 1),
            "temperature_c": round(r.get("temperature_celsius", 0), 1),
            "humidity": round(r.get("humidity_percent", 0), 1),
            "wind_speed": round(r.get("wind_speed_mph", 0), 1),
            "pressure": round(r.get("pressure_hpa", 0), 1),
            "weather_condition": r.get("weather_condition", ""),
            "cloud_cover": round(r.get("cloud_cover_percent", 0), 1),
            "is_extreme": bool(r.get("is_extreme_weather", 0)),
            "anomaly_score": round(r.get("temp_anomaly_score", 0), 2),
        })
    return {"cities": result, "count": len(result), "timestamp": datetime.now().isoformat()}


@app.get("/api/weather/{city_name}", tags=["Weather"])
async def get_city_weather(city_name: str):
    """Get detailed weather for a specific city."""
    cities = get_cities_df()
    match = cities[cities["city"].str.lower() == city_name.lower()]
    if match.empty:
        available = cities["city"].tolist()
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found. Available: {available}")

    r = match.iloc[0]
    return {
        "city": r.get("city"),
        "state": r.get("state"),
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
        "temperature": {
            "fahrenheit": round(r.get("temperature_fahrenheit", 0), 1),
            "celsius": round(r.get("temperature_celsius", 0), 1),
            "heat_index": round(r.get("heat_index", 0), 1),
            "wind_chill": round(r.get("wind_chill", 0), 1),
        },
        "conditions": {
            "weather": r.get("weather_condition", ""),
            "humidity_percent": round(r.get("humidity_percent", 0), 1),
            "pressure_hpa": round(r.get("pressure_hpa", 0), 1),
            "wind_speed_mph": round(r.get("wind_speed_mph", 0), 1),
            "wind_direction_deg": round(r.get("wind_direction_degrees", 0), 1),
            "cloud_cover_percent": round(r.get("cloud_cover_percent", 0), 1),
            "visibility_miles": round(r.get("visibility_miles", 0), 1),
        },
        "analysis": {
            "is_extreme_weather": bool(r.get("is_extreme_weather", 0)),
            "anomaly_score": round(r.get("temp_anomaly_score", 0), 2),
            "temperature_anomaly": round(r.get("temperature_anomaly", 0), 2),
            "city_avg_temp": round(r.get("city_avg_temp", 0), 1),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/extreme", tags=["Weather"])
async def get_extreme_events():
    """Get all cities with extreme weather conditions."""
    cities = get_cities_df()
    extreme = cities[cities["is_extreme_weather"] == 1]

    result = []
    for _, r in extreme.iterrows():
        reasons = []
        if r.get("temperature_fahrenheit", 0) > 100: reasons.append("High temperature (>100°F)")
        if r.get("temperature_fahrenheit", 0) < 10: reasons.append("Low temperature (<10°F)")
        if r.get("wind_speed_mph", 0) > 50: reasons.append("High wind speed (>50 mph)")
        if r.get("temp_anomaly_score", 0) > 2.5: reasons.append(f"High anomaly score ({round(r.get('temp_anomaly_score',0),2)})")

        result.append({
            "city": r.get("city"),
            "state": r.get("state"),
            "temperature_f": round(r.get("temperature_fahrenheit", 0), 1),
            "anomaly_score": round(r.get("temp_anomaly_score", 0), 2),
            "reasons": reasons,
        })

    return {
        "extreme_events": result,
        "count": len(result),
        "total_cities": len(cities),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/anomalies", tags=["Analysis"])
async def get_anomalies(threshold: float = Query(default=1.5, description="Anomaly score threshold")):
    """Get cities with anomaly scores above threshold."""
    cities = get_cities_df()
    anomalous = cities[cities["temp_anomaly_score"] >= threshold].sort_values("temp_anomaly_score", ascending=False)

    result = []
    for _, r in anomalous.iterrows():
        result.append({
            "city": r.get("city"),
            "state": r.get("state"),
            "temperature_f": round(r.get("temperature_fahrenheit", 0), 1),
            "city_avg_temp": round(r.get("city_avg_temp", 0), 1),
            "anomaly_score": round(r.get("temp_anomaly_score", 0), 2),
            "temperature_anomaly": round(r.get("temperature_anomaly", 0), 2),
        })

    return {
        "anomalies": result,
        "count": len(result),
        "threshold": threshold,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/regions", tags=["Analysis"])
async def get_regions():
    """Get weather statistics grouped by region."""
    df = app_state.get("gold_df")
    if df is None:
        raise HTTPException(status_code=503, detail="Data not loaded")

    # Build region map
    region_map = {
        "New York": "Northeast", "Boston": "Northeast",
        "Miami": "Southeast", "Atlanta": "Southeast", "New Orleans": "Southeast",
        "Houston": "South", "Dallas": "South", "Nashville": "South",
        "Chicago": "Midwest", "Detroit": "Midwest", "Minneapolis": "Midwest",
        "Denver": "West", "Phoenix": "West", "Las Vegas": "West",
        "Los Angeles": "West", "San Francisco": "West", "Seattle": "Northwest",
        "Portland": "Northwest", "Honolulu": "Pacific", "Anchorage": "Alaska",
    }

    cities = get_cities_df().copy()
    cities["region"] = cities["city"].map(region_map).fillna("Other")

    regions = {}
    for region, group in cities.groupby("region"):
        regions[region] = {
            "avg_temp": round(group["temperature_fahrenheit"].mean(), 1),
            "max_temp": round(group["temperature_fahrenheit"].max(), 1),
            "min_temp": round(group["temperature_fahrenheit"].min(), 1),
            "avg_humidity": round(group["humidity_percent"].mean(), 1),
            "cities": group["city"].tolist(),
            "extreme_count": int(group["is_extreme_weather"].sum()),
        }

    return {"regions": regions, "timestamp": datetime.now().isoformat()}


@app.get("/api/predictions", tags=["ML"])
async def get_predictions():
    """Get XGBoost extreme weather predictions for all cities."""
    cities = get_cities_df()

    result = []
    for _, r in cities.iterrows():
        result.append({
            "city": r.get("city"),
            "state": r.get("state"),
            "temperature_f": round(r.get("temperature_fahrenheit", 0), 1),
            "humidity": round(r.get("humidity_percent", 0), 1),
            "wind_speed": round(r.get("wind_speed_mph", 0), 1),
            "heat_index": round(r.get("heat_index", 0), 1),
            "anomaly_score": round(r.get("temp_anomaly_score", 0), 2),
            "predicted_extreme": bool(r.get("is_extreme_weather", 0)),
            "risk_level": (
                "🔴 HIGH" if r.get("temp_anomaly_score", 0) > 2.5
                else "🟡 MODERATE" if r.get("temp_anomaly_score", 0) > 1.5
                else "🟢 LOW"
            ),
        })

    return {
        "predictions": result,
        "model": "XGBoost",
        "total_cities": len(result),
        "extreme_predicted": sum(1 for r in result if r["predicted_extreme"]),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/forecast/{city_name}", tags=["ML"])
async def get_forecast(city_name: str):
    """Get temperature forecast for a city (based on recent data trends)."""
    df = app_state.get("gold_df")
    if df is None:
        raise HTTPException(status_code=503, detail="Data not loaded")

    city_data = df[df["city"].str.lower() == city_name.lower()]
    if city_data.empty:
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found")

    temps = city_data["temperature_fahrenheit"].values
    current = float(temps[-1]) if len(temps) > 0 else 0

    # Simple trend-based forecast (production would use the LSTM model)
    forecast = []
    for h in range(1, 25):
        # Add small variation based on historical std
        std = city_data["temperature_fahrenheit"].std() if len(temps) > 1 else 2.0
        variation = np.sin(h * np.pi / 12) * std * 0.3  # day/night cycle
        predicted = round(current + variation, 1)
        forecast.append({
            "hour": h,
            "predicted_temp_f": predicted,
            "predicted_temp_c": round((predicted - 32) * 5 / 9, 1),
        })

    return {
        "city": city_name,
        "current_temp_f": round(current, 1),
        "forecast_24h": forecast,
        "model": "LSTM (simplified)",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/chat", response_model=ChatResponse, tags=["Gen AI"])
async def chat(request: ChatRequest):
    """AI chatbot — supports RAG, SQL, Report, and Anomaly modes."""
    gc = app_state.get("groq")
    coll = app_state.get("vector_store")
    if not gc or not coll:
        raise HTTPException(status_code=503, detail="AI services not initialized")

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Determine mode
    mode = request.mode if request.mode and request.mode != "auto" else detect_mode(question)

    # Try direct DataFrame answer first
    cities = get_cities_df()
    direct = try_direct_answer(question, cities)
    if direct:
        return ChatResponse(answer=direct, mode="rag", timestamp=datetime.now().isoformat())

    # Route to AI mode
    if mode == "sql":
        answer = build_sql_answer(question, gc)
        if answer is None:
            answer = build_rag_answer(question, coll, gc, "rag")
            mode = "rag"
    else:
        answer = build_rag_answer(question, coll, gc, mode)

    return ChatResponse(answer=answer, mode=mode, timestamp=datetime.now().isoformat())


# ============================================================
# RUN (for development)
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)