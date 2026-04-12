"""
🌍 Climate Intelligence Command Center v5 (FAST + STUNNING UI)
Optimized loading: samples data for ChromaDB, caches aggressively.
Beautiful glassmorphism dark theme with smooth animations.

Run: streamlit run genai/chatbot_app.py
"""

import os
import chromadb
import psycopg2
import pandas as pd
import streamlit as st
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Climate Command Center", page_icon="🌍", layout="wide")

# ============================================================
# CSS — Glassmorphism Dark Theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* === RESET & GLOBAL === */
.stApp {
    background: #030308;
    background-image:
        radial-gradient(ellipse at 20% 50%, #0c1445 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, #1a0a2e 0%, transparent 50%),
        radial-gradient(ellipse at 50% 80%, #0a1628 0%, transparent 50%);
    color: #e2e8f0;
}
* { font-family: 'Inter', sans-serif; }

/* === ANIMATIONS === */
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
@keyframes slideUp { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes borderGlow {
    0%,100% { border-color: rgba(34,211,238,0.15); box-shadow: 0 0 15px rgba(34,211,238,0.05); }
    50% { border-color: rgba(34,211,238,0.35); box-shadow: 0 0 30px rgba(34,211,238,0.1); }
}
@keyframes shimmer {
    0% { background-position: -200% center; }
    100% { background-position: 200% center; }
}
@keyframes float {
    0%,100% { transform: translateY(0px); }
    50% { transform: translateY(-4px); }
}

/* === GLASS CARD BASE === */
.glass {
    background: linear-gradient(135deg, rgba(15,15,35,0.8), rgba(20,20,50,0.6));
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
}

/* === TOP BAR === */
.top-bar {
    background: linear-gradient(135deg, rgba(12,12,30,0.9), rgba(20,20,55,0.8));
    backdrop-filter: blur(30px);
    border: 1px solid rgba(34,211,238,0.12);
    padding: 18px 32px;
    border-radius: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    animation: borderGlow 6s ease-in-out infinite, slideUp 0.6s ease-out;
    position: relative;
    overflow: hidden;
}
.top-bar::before {
    content: '';
    position: absolute;
    top: 0; left: -100%; width: 200%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(34,211,238,0.03), transparent);
    animation: shimmer 8s ease-in-out infinite;
}
.top-title {
    font-family: 'JetBrains Mono';
    font-size: 15px;
    font-weight: 700;
    background: linear-gradient(135deg, #22d3ee, #818cf8, #c084fc);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 5px;
    text-transform: uppercase;
    animation: shimmer 4s linear infinite;
}
.top-status {
    color: #64748b;
    font-size: 11px;
    font-family: 'JetBrains Mono';
    display: flex;
    align-items: center;
    gap: 14px;
}
.live-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 12px #22c55e, 0 0 24px rgba(34,197,94,0.3);
    animation: pulse 2s ease-in-out infinite;
    margin-right: 5px;
}
.status-chip {
    background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(129,140,248,0.12));
    color: #a5b4fc;
    padding: 6px 16px;
    border-radius: 12px;
    font-size: 11px;
    font-family: 'JetBrains Mono';
    font-weight: 500;
    border: 1px solid rgba(99,102,241,0.2);
}
.stat-pill {
    background: rgba(255,255,255,0.04);
    padding: 4px 12px;
    border-radius: 8px;
    font-size: 11px;
    color: #94a3b8;
    border: 1px solid rgba(255,255,255,0.05);
}
.stat-num {
    color: #22d3ee;
    font-weight: 700;
}

/* === METRIC CARDS === */
.metric-card {
    background: linear-gradient(160deg, rgba(13,13,28,0.9), rgba(20,20,52,0.7));
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 26px 18px;
    text-align: center;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    animation: slideUp 0.5s ease-out backwards;
    position: relative;
    overflow: hidden;
}
.metric-card::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 20px;
    padding: 1px;
    background: linear-gradient(135deg, transparent, rgba(34,211,238,0.1), transparent);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity: 0;
    transition: opacity 0.4s;
}
.metric-card:hover {
    transform: translateY(-4px);
    border-color: rgba(34,211,238,0.2);
    box-shadow: 0 12px 40px rgba(34,211,238,0.08);
}
.metric-card:hover::after { opacity: 1; }
.metric-icon { font-size: 28px; margin-bottom: 8px; filter: drop-shadow(0 0 8px rgba(34,211,238,0.3)); }
.metric-value {
    font-size: 36px;
    font-weight: 900;
    font-family: 'JetBrains Mono';
    background: linear-gradient(135deg, #22d3ee, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.1;
    letter-spacing: -1px;
}
.metric-label {
    color: #475569;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-top: 6px;
    font-weight: 700;
}

/* === SECTION HEADERS === */
.section-hdr {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin: 32px 0 16px 0;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    display: flex;
    align-items: center;
    gap: 10px;
    animation: fadeIn 0.6s ease-out;
}

/* === CITY CARDS === */
.city-card {
    background: linear-gradient(160deg, rgba(13,13,28,0.85), rgba(20,20,52,0.65));
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 16px;
    padding: 18px 12px;
    text-align: center;
    margin-bottom: 10px;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    animation: slideUp 0.4s ease-out backwards;
}
.city-card:hover {
    border-color: rgba(34,211,238,0.2);
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(34,211,238,0.06);
}
.city-card.extreme {
    border-color: rgba(239,68,68,0.35);
    box-shadow: 0 0 30px rgba(239,68,68,0.08);
    animation: slideUp 0.4s ease-out backwards, borderGlow 3s ease-in-out infinite;
}
.city-card.extreme .city-temp { text-shadow: 0 0 20px rgba(239,68,68,0.3); }
.city-name {
    color: #94a3b8;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
}
.city-flag {
    color: #64748b;
    font-size: 8px;
    font-weight: 500;
}
.city-temp {
    font-size: 32px;
    font-weight: 900;
    font-family: 'JetBrains Mono';
    margin: 8px 0 6px 0;
    line-height: 1;
    letter-spacing: -1px;
}
.city-cond {
    color: #64748b;
    font-size: 10px;
    font-weight: 600;
    margin-bottom: 6px;
}
.city-details {
    color: #475569;
    font-size: 9px;
    font-family: 'JetBrains Mono';
    display: flex;
    justify-content: center;
    gap: 8px;
}

/* === CHAT === */
.chat-container {
    background: rgba(8,8,20,0.7);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 20px;
    padding: 24px;
    margin-top: 10px;
    max-height: 520px;
    overflow-y: auto;
}
.chat-container::-webkit-scrollbar { width: 4px; }
.chat-container::-webkit-scrollbar-track { background: transparent; }
.chat-container::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.3); border-radius: 4px; }

.chat-msg-user {
    background: linear-gradient(135deg, #6366f1, #7c3aed, #9333ea);
    color: white;
    padding: 14px 20px;
    border-radius: 20px 20px 6px 20px;
    margin: 12px 0;
    display: inline-block;
    max-width: 70%;
    font-size: 14px;
    float: right;
    clear: both;
    box-shadow: 0 6px 24px rgba(99,102,241,0.25);
    animation: slideUp 0.3s ease-out;
    font-weight: 500;
    line-height: 1.6;
}
.chat-msg-bot {
    background: linear-gradient(160deg, rgba(15,15,38,0.9), rgba(22,22,55,0.7));
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.06);
    color: #cbd5e1;
    padding: 16px 20px;
    border-radius: 6px 20px 20px 20px;
    margin: 12px 0;
    display: inline-block;
    max-width: 80%;
    font-size: 14px;
    float: left;
    clear: both;
    line-height: 1.8;
    animation: slideUp 0.3s ease-out;
}
.chat-clear { clear: both; }

/* === MODE TAGS === */
.tag {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 10px;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 10px;
    font-family: 'JetBrains Mono';
}
.tag-rag {
    background: linear-gradient(135deg, rgba(6,78,59,0.6), rgba(6,78,59,0.3));
    color: #34d399;
    border: 1px solid rgba(52,211,153,0.2);
}
.tag-sql {
    background: linear-gradient(135deg, rgba(30,58,95,0.6), rgba(30,58,95,0.3));
    color: #38bdf8;
    border: 1px solid rgba(56,189,248,0.2);
}
.tag-report {
    background: linear-gradient(135deg, rgba(69,26,3,0.6), rgba(69,26,3,0.3));
    color: #fb923c;
    border: 1px solid rgba(251,146,60,0.2);
}
.tag-anomaly {
    background: linear-gradient(135deg, rgba(69,10,10,0.6), rgba(69,10,10,0.3));
    color: #f87171;
    border: 1px solid rgba(248,113,113,0.2);
}

/* === QUICK BUTTONS === */
div.stButton > button {
    background: linear-gradient(160deg, rgba(13,13,28,0.9), rgba(20,20,52,0.7)) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #94a3b8 !important;
    border-radius: 14px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.5px !important;
}
div.stButton > button:hover {
    border-color: rgba(34,211,238,0.3) !important;
    color: #22d3ee !important;
    box-shadow: 0 4px 20px rgba(34,211,238,0.12) !important;
    transform: translateY(-2px) !important;
}

/* === HIDE STREAMLIT DEFAULTS === */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
div[data-testid="stStatusWidget"] { visibility: hidden; }

/* === INPUT === */
div[data-testid="stChatInput"] textarea {
    background: rgba(10,10,24,0.8) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 16px !important;
    color: #e2e8f0 !important;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(34,211,238,0.3) !important;
    box-shadow: 0 0 20px rgba(34,211,238,0.08) !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE HELPER
# ============================================================

DB = dict(host="localhost", port=5432, database="airflow", user="airflow", password="airflow")

def get_conn():
    return psycopg2.connect(**DB)

def get_db_stats():
    try:
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather=1")
        extreme = c.fetchone()[0]
        conn.close()
        return total, extreme
    except Exception:
        return 0, 0


# ============================================================
# DATA LOADING — OPTIMIZED: sample for ChromaDB, full for direct answers
# ============================================================

@st.cache_resource
def init_groq():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def load_gold_data():
    """Load gold parquet + build ChromaDB vector store.
    OPTIMIZATION: Only load latest reading per city into ChromaDB (80 docs instead of 6000+).
    Full DataFrame kept for direct answers.
    """
    try:
        df = pd.read_parquet("data/gold/weather_features")

        # For ChromaDB: only latest reading per city (fast + no memory issues)
        latest = df.sort_values('timestamp' if 'timestamp' in df.columns else 'reading_date', ascending=False) \
                   .drop_duplicates(subset=['city'], keep='first')

        client = chromadb.Client()
        try: client.delete_collection("climate_data")
        except Exception: pass
        coll = client.create_collection("climate_data", metadata={"hnsw:space": "cosine"})

        docs, metas, ids = [], [], []
        for i, (_, r) in enumerate(latest.iterrows()):
            vis_val = r.get('visibility_km', r.get('visibility_miles', 'N/A'))
            vis_unit = "km" if 'visibility_km' in r.index and r.get('visibility_km') else "miles"

            doc = (
                f"City: {r.get('city','N/A')}, Country: {r.get('country','N/A')}, "
                f"Continent: {r.get('continent','N/A')}, Region: {r.get('region','N/A')}. "
                f"Temperature: {r.get('temperature_fahrenheit','N/A')}F ({r.get('temperature_celsius','N/A')}C). "
                f"Humidity: {r.get('humidity_percent','N/A')}%. "
                f"Wind: {r.get('wind_speed_mph','N/A')} mph. "
                f"Pressure: {r.get('pressure_hpa','N/A')} hPa. "
                f"Heat Index: {r.get('heat_index','N/A')}F. "
                f"Wind Chill: {r.get('wind_chill','N/A')}F. "
                f"Weather: {r.get('weather_condition','N/A')} - {r.get('weather_description','')}. "
                f"Clouds: {r.get('cloud_cover_percent','N/A')}%. "
                f"Visibility: {vis_val} {vis_unit}. "
                f"Rain: {r.get('precipitation_mm','N/A')} mm. "
                f"Extreme: {'YES' if r.get('is_extreme_weather',0)==1 else 'No'}. "
                f"Heatwave: {'YES' if r.get('is_heatwave',0)==1 else 'No'}. "
                f"Extreme Cold: {'YES' if r.get('is_extreme_cold',0)==1 else 'No'}. "
                f"High Wind: {'YES' if r.get('is_high_wind',0)==1 else 'No'}. "
                f"Anomaly Score: {r.get('temp_anomaly_score','N/A')}. "
                f"Temp Anomaly: {r.get('temperature_anomaly','N/A')}F."
            )
            docs.append(doc)
            metas.append({
                "city": str(r.get('city', '')),
                "country": str(r.get('country', '')),
                "continent": str(r.get('continent', '')),
                "temp": float(r.get('temperature_fahrenheit', 0)),
                "extreme": int(r.get('is_extreme_weather', 0)),
            })
            ids.append(f"rec_{i}")

        # Single batch — only ~80 docs now
        coll.add(documents=docs, metadatas=metas, ids=ids)

        return df, coll
    except Exception as e:
        st.error(f"Data load error: {e}")
        return None, None


# ============================================================
# AI ENGINE
# ============================================================

def detect_mode(q):
    q = q.lower().strip()
    anomaly_kw = ["anomaly", "anomalies", "unusual", "strange", "weird", "abnormal",
                  "why is", "explain why", "what's wrong", "outlier", "spike", "unexpected"]
    if any(k in q for k in anomaly_kw): return "anomaly"
    report_kw = ["report", "forecast", "summary", "brief", "overview", "conditions in",
                 "weather in", "what's the weather", "tell me about", "update for", "status"]
    if any(k in q for k in report_kw): return "report"
    simple_rag = ["which city has", "what city has", "hottest", "coldest",
                  "warmest", "coolest", "most humid", "windiest"]
    if any(k in q for k in simple_rag): return "rag"
    sql_kw = ["average", "avg", "count", "how many", "total", "sum",
              "list all", "show me all", "group by", "per city", "each city",
              "compare", "percentage", "rank", "top 5", "top 10", "top 3",
              "above", "below", "between", "greater", "less than",
              "per continent", "each continent", "per country", "by region"]
    if any(k in q for k in sql_kw): return "sql"
    return "rag"


def build_sql_answer(question, gc):
    schema_info = """
    Tables in schema climate_warehouse:
    1. fact_weather_readings: reading_key, location_key, time_key, weather_type_key,
       temperature_fahrenheit, temperature_celsius, humidity_percent, pressure_hpa,
       wind_speed_mph, wind_direction_degrees, precipitation_mm, visibility_km,
       cloud_cover_percent, uv_index, heat_index, wind_chill, temp_anomaly, temp_anomaly_score,
       is_extreme_weather, is_heatwave, is_extreme_cold, is_high_wind, is_heavy_precipitation, source, quality_flag
    2. dim_location: location_key, city, country, continent, state, latitude, longitude, region (80 cities, 6 continents)
    3. dim_time: time_key, full_timestamp, date, year, quarter, month, month_name, week_of_year, day_of_month, day_of_week, day_name, hour, is_weekend, season
    4. dim_weather_type: weather_type_key, condition, category, severity, description
    RULES: JOIN fact with dim_location using location_key. JOIN dim_time using time_key. JOIN dim_weather_type using weather_type_key. Use ROUND(). LIMIT 20. Return ONLY SQL.
    """
    r = gc.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": f"PostgreSQL expert. Output ONLY the SQL query.\n{schema_info}"},
            {"role": "user", "content": f"Write SELECT for: {question}"}
        ],
        max_tokens=400, temperature=0.05
    )
    raw = r.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()
    lines = raw.split("\n")
    capture = False
    sql_lines = []
    for line in lines:
        if line.strip().upper().startswith("SELECT"): capture = True
        if capture: sql_lines.append(line)
        if capture and ";" in line: break
    sql = "\n".join(sql_lines).strip().rstrip(";").strip()
    if not sql or not sql.upper().startswith("SELECT"): return None, "sql"
    try:
        conn = get_conn(); cur = conn.cursor(); cur.execute(sql)
        cols = [d[0] for d in cur.description]; rows = cur.fetchall(); conn.close()
        results = [dict(zip(cols, row)) for row in rows]
        if not results: return "No results found. Try rephrasing.", "sql"
        r2 = gc.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Summarize weather results with specific numbers. 2-4 sentences."},
                {"role": "user", "content": f"Question: {question}\nResults:\n{str(results[:15])}\nSummary:"}
            ],
            max_tokens=250, temperature=0.2
        )
        return r2.choices[0].message.content.strip() + f"\n\n📝 `{sql}`", "sql"
    except Exception:
        return None, "sql"


def build_rag_answer(question, coll, gc, mode="rag"):
    n = 10 if mode == "report" else 8
    res = coll.query(query_texts=[question], n_results=n)
    ctx = "\n".join(res['documents'][0]) if res['documents'] and res['documents'][0] else "No data."
    prompts = {
        "rag": "Expert climate analyst monitoring 80 cities across 6 continents. Answer from provided data only. Be specific.",
        "report": "Global weather analyst. Report format: 📋 SUMMARY, 🔍 KEY FINDINGS (top 3-4), ⚠️ RISKS, 🌍 REGIONAL HIGHLIGHTS, ✅ RECOMMENDATIONS.",
        "anomaly": "Senior meteorologist. Format: 🔴 WHAT'S UNUSUAL, 🔬 LIKELY CAUSES, ⚠️ RISK ASSESSMENT, 🛡️ PRECAUTIONS. Focus on high anomaly scores.",
    }
    tokens = {"rag": 350, "report": 600, "anomaly": 450}
    r = gc.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": prompts[mode]}, {"role": "user", "content": f"DATA:\n{ctx}\n\nQUESTION: {question}"}],
        max_tokens=tokens[mode], temperature=0.25
    )
    return r.choices[0].message.content.strip(), mode


def try_direct_answer(question, gold_df):
    q = question.lower()
    cities = gold_df.drop_duplicates(subset=['city'], keep='last')
    def fmt(row):
        c = row.get('country', '')
        return f"{row['city']}, {c}" if c else row['city']

    if any(k in q for k in ["hottest", "highest temp", "warmest", "highest temperature"]):
        row = cities.loc[cities['temperature_fahrenheit'].idxmax()]
        top5 = cities.nlargest(5, 'temperature_fahrenheit')
        lines = "\n".join([f"  {i+1}. **{fmt(r)}** — {round(r['temperature_fahrenheit'],1)}°F" for i, (_, r) in enumerate(top5.iterrows())])
        return f"🔥 **{fmt(row)}** has the highest temperature at **{round(row['temperature_fahrenheit'],1)}°F**.\n\n**Top 5 Hottest:**\n{lines}", "rag"

    if any(k in q for k in ["coldest", "lowest temp", "coolest", "lowest temperature", "freezing"]):
        row = cities.loc[cities['temperature_fahrenheit'].idxmin()]
        bot5 = cities.nsmallest(5, 'temperature_fahrenheit')
        lines = "\n".join([f"  {i+1}. **{fmt(r)}** — {round(r['temperature_fahrenheit'],1)}°F" for i, (_, r) in enumerate(bot5.iterrows())])
        return f"🥶 **{fmt(row)}** has the lowest temperature at **{round(row['temperature_fahrenheit'],1)}°F**.\n\n**Top 5 Coldest:**\n{lines}", "rag"

    if any(k in q for k in ["most humid", "highest humidity"]):
        row = cities.loc[cities['humidity_percent'].idxmax()]
        return f"💧 **{fmt(row)}** — highest humidity at **{round(row['humidity_percent'],1)}%** ({round(row['temperature_fahrenheit'],1)}°F).", "rag"

    if any(k in q for k in ["windiest", "most windy", "highest wind", "strongest wind"]):
        row = cities.loc[cities['wind_speed_mph'].idxmax()]
        return f"💨 **{fmt(row)}** — highest wind at **{round(row['wind_speed_mph'],1)} mph** ({round(row['temperature_fahrenheit'],1)}°F).", "rag"

    if any(k in q for k in ["extreme weather", "extreme events", "how many extreme"]):
        ext = cities[cities['is_extreme_weather'] == 1]
        if len(ext) == 0: return "✅ No extreme weather events detected.", "rag"
        cl = ", ".join([f"**{fmt(r)}** ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in ext.iterrows()])
        return f"⚠️ **{len(ext)} extreme event(s):**\n\n{cl}", "rag"

    if any(k in q for k in ["heatwave", "heat wave"]):
        hw = cities[cities.get('is_heatwave', pd.Series([0]*len(cities))) == 1] if 'is_heatwave' in cities.columns else cities[cities['temperature_fahrenheit'] > 100]
        if len(hw) == 0: return "✅ No heatwave conditions detected.", "rag"
        cl = ", ".join([f"**{fmt(r)}** ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in hw.iterrows()])
        return f"🔥 **{len(hw)} heatwave(s)** (>100°F):\n\n{cl}", "rag"

    if any(k in q for k in ["extreme cold", "freezing cold"]):
        ec = cities[cities.get('is_extreme_cold', pd.Series([0]*len(cities))) == 1] if 'is_extreme_cold' in cities.columns else cities[cities['temperature_fahrenheit'] < 10]
        if len(ec) == 0: return "✅ No extreme cold detected.", "rag"
        cl = ", ".join([f"**{fmt(r)}** ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in ec.iterrows()])
        return f"🥶 **{len(ec)} extreme cold** (<10°F):\n\n{cl}", "rag"

    return None, None


def ai_answer(question, coll, gc):
    direct, mode = try_direct_answer(question, st.session_state.gold_df)
    if direct: return direct, mode
    mode = detect_mode(question)
    if mode == "sql":
        result, m = build_sql_answer(question, gc)
        if result is None: return build_rag_answer(question, coll, gc, "rag")
        return result, m
    return build_rag_answer(question, coll, gc, mode)


# ============================================================
# MAIN APP
# ============================================================

def render_app():
    gc = init_groq()

    with st.spinner("⚡ Initializing Climate Intelligence..."):
        gold_df, coll = load_gold_data()

    if gold_df is None:
        st.error("❌ Could not load data. Run the pipeline first.")
        st.stop()

    st.session_state.gold_df = gold_df

    cities = gold_df.drop_duplicates(subset=['city'], keep='last').sort_values('temperature_fahrenheit', ascending=False)
    total, extreme = get_db_stats()
    avg_t = round(gold_df['temperature_fahrenheit'].mean(), 1)
    max_t = round(gold_df['temperature_fahrenheit'].max(), 1)
    min_t = round(gold_df['temperature_fahrenheit'].min(), 1)
    now = datetime.now().strftime("%b %d, %Y • %I:%M %p")
    city_count = len(cities)
    continent_count = gold_df['continent'].nunique() if 'continent' in gold_df.columns else "?"
    country_count = gold_df['country'].nunique() if 'country' in gold_df.columns else "?"

    # ── TOP BAR ──
    st.markdown(f"""
    <div class="top-bar">
        <span class="top-title">🌍 Climate Command Center</span>
        <span class="top-status">
            <span class="live-dot"></span> LIVE
            <span class="stat-pill"><span class="stat-num">{city_count}</span> Cities</span>
            <span class="stat-pill"><span class="stat-num">{continent_count}</span> Continents</span>
            <span class="stat-pill"><span class="stat-num">{country_count}</span> Countries</span>
            <span class="status-chip">🕐 {now}</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── METRICS ──
    m1, m2, m3, m4, m5 = st.columns(5)
    for col, icon, val, label in [
        (m1, "📊", f"{total:,}", "Total Readings"),
        (m2, "🌡️", f"{avg_t}°F", "Avg Temperature"),
        (m3, "🔥", f"{max_t}°F", "Peak Temp"),
        (m4, "🥶", f"{min_t}°F", "Lowest Temp"),
        (m5, "⚠️", str(extreme), "Extreme Events"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-icon">{icon}</div>
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── CITY GRID ──
    st.markdown('<div class="section-hdr">📡 &nbsp;Global City Monitoring</div>', unsafe_allow_html=True)

    rows_of_cities = [cities.iloc[i:i+5] for i in range(0, len(cities), 5)]
    for row_chunk in rows_of_cities:
        cols = st.columns(5)
        for idx, (_, city) in enumerate(row_chunk.iterrows()):
            with cols[idx]:
                t = round(city.get('temperature_fahrenheit', 0), 1)
                h = round(city.get('humidity_percent', 0))
                w = round(city.get('wind_speed_mph', 0), 1)
                nm = city.get('city', '?')
                country = city.get('country', '')
                cond = city.get('weather_condition', '')
                ext = city.get('is_extreme_weather', 0) == 1
                cls = "extreme" if ext else ""
                tc = "#f87171" if ext else "#22d3ee"
                badge = ' <span style="color:#ef4444;font-size:12px;">⚠</span>' if ext else ""
                st.markdown(f"""
                <div class="city-card {cls}">
                    <div class="city-name">{nm}{badge}</div>
                    <div class="city-flag">{country}</div>
                    <div class="city-temp" style="color:{tc};">{t}°</div>
                    <div class="city-cond">{cond}</div>
                    <div class="city-details">
                        <span>💧{h}%</span>
                        <span>💨{w}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── AI CHAT ──
    st.markdown('<div class="section-hdr">🧠 &nbsp;AI Weather Intelligence</div>', unsafe_allow_html=True)

    if "msgs" not in st.session_state:
        st.session_state.msgs = [{
            "role": "bot",
            "text": (
                f"Welcome to Climate Command Center! 👋\n\n"
                f"Monitoring **{city_count} cities** across **{continent_count} continents** and **{country_count} countries**.\n\n"
                "**4 intelligence modes:**\n"
                "• **RAG** — Natural language questions\n"
                "• **SQL** — Data queries & rankings\n"
                "• **Report** — Structured intelligence\n"
                "• **Anomaly** — Pattern analysis\n\n"
                "Try the buttons below or type anything!"
            ),
            "mode": "rag"
        }]

    c1, c2, c3, c4, c5 = st.columns(5)
    qk = None
    with c1:
        if st.button("🔥 Hottest", use_container_width=True): qk = "Which city has the highest temperature right now?"
    with c2:
        if st.button("🥶 Coldest", use_container_width=True): qk = "Which city has the lowest temperature?"
    with c3:
        if st.button("⚠️ Extreme", use_container_width=True): qk = "How many extreme weather events and which cities?"
    with c4:
        if st.button("📋 Report", use_container_width=True): qk = "Generate a comprehensive weather report for all cities"
    with c5:
        if st.button("🔍 Anomalies", use_container_width=True): qk = "Detect and explain weather anomalies across all cities"

    tag_html = {
        "rag": '<span class="tag tag-rag">RAG</span>',
        "sql": '<span class="tag tag-sql">SQL</span>',
        "report": '<span class="tag tag-report">REPORT</span>',
        "anomaly": '<span class="tag tag-anomaly">ANOMALY</span>',
    }

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for msg in st.session_state.msgs:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-msg-user">{msg["text"]}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
        else:
            tag = tag_html.get(msg.get("mode", "rag"), "")
            text = msg["text"].replace("\n", "<br>")
            st.markdown(f'<div class="chat-msg-bot">{tag}<br>{text}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    user_in = st.chat_input("Ask about weather, climate, extreme events, or city conditions...")
    if qk: user_in = qk
    if user_in:
        st.session_state.msgs.append({"role": "user", "text": user_in})
        with st.spinner("🧠 Analyzing..."):
            ans, mode = ai_answer(user_in, coll, gc)
        st.session_state.msgs.append({"role": "bot", "text": ans, "mode": mode})
        st.rerun()


render_app()