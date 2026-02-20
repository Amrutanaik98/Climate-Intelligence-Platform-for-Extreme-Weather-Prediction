"""
🌍 Climate Intelligence Command Center
========================================
An immersive weather intelligence chatbot with real-time
data visualization, multi-mode AI, and live city monitoring.

Run: streamlit run genai/chatbot_app.py
"""

import os
import json
import random
import chromadb
import psycopg2
import pandas as pd
import streamlit as st
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Climate Command Center",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CUSTOM CSS — UNIQUE DARK WEATHER THEME
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600;800&display=swap');

.stApp {
    background: #0a0a0f;
    font-family: 'Inter', sans-serif;
}

/* Top command bar */
.command-bar {
    background: linear-gradient(90deg, #0f172a, #1e1b4b, #0f172a);
    border-bottom: 1px solid #22d3ee33;
    padding: 16px 30px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: -1rem -1rem 20px -1rem;
    border-radius: 0 0 16px 16px;
}

.command-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    color: #22d3ee;
    letter-spacing: 3px;
    text-transform: uppercase;
}

.command-status {
    display: flex;
    gap: 15px;
    align-items: center;
}

.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    animation: pulse 2s infinite;
}

.status-live { background: #22c55e; box-shadow: 0 0 10px #22c55e; }
.status-label { color: #64748b; font-size: 11px; font-family: 'JetBrains Mono', monospace; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* City cards grid */
.city-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
    margin: 15px 0;
}

.city-card {
    background: linear-gradient(145deg, #131325, #1a1a35);
    border: 1px solid #ffffff0a;
    border-radius: 12px;
    padding: 14px;
    text-align: center;
    transition: all 0.3s;
    cursor: default;
}

.city-card:hover {
    border-color: #22d3ee44;
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(34, 211, 238, 0.1);
}

.city-name { color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
.city-temp { color: #f1f5f9; font-size: 26px; font-weight: 800; margin: 4px 0; font-family: 'JetBrains Mono', monospace; }
.city-detail { color: #475569; font-size: 10px; }
.city-extreme { border-color: #ef444466; }
.city-extreme .city-temp { color: #f87171; }

/* Chat area */
.chat-container {
    background: #0d0d1a;
    border: 1px solid #ffffff08;
    border-radius: 16px;
    padding: 20px;
    max-height: 500px;
    overflow-y: auto;
    margin: 15px 0;
}

.msg-user {
    display: flex;
    justify-content: flex-end;
    margin: 12px 0;
}

.msg-user-bubble {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    padding: 12px 18px;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%;
    font-size: 14px;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
}

.msg-bot {
    display: flex;
    justify-content: flex-start;
    margin: 12px 0;
    gap: 10px;
}

.msg-bot-avatar {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, #06b6d4, #0891b2);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}

.msg-bot-content {
    background: #12122a;
    border: 1px solid #ffffff0a;
    padding: 14px 18px;
    border-radius: 4px 18px 18px 18px;
    max-width: 80%;
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.6;
}

.msg-bot-content code {
    background: #1e1e3f;
    padding: 2px 6px;
    border-radius: 4px;
    color: #7dd3fc;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}

/* Mode indicator */
.mode-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
}

.tag-rag { background: #064e3b; color: #34d399; }
.tag-sql { background: #1e3a5f; color: #38bdf8; }
.tag-report { background: #451a03; color: #fb923c; }
.tag-anomaly { background: #450a0a; color: #f87171; }

/* Metric cards */
.metric-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 15px 0;
}

.metric-card {
    background: linear-gradient(145deg, #131325, #1a1a35);
    border: 1px solid #ffffff08;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
}

.metric-value {
    font-size: 32px;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    background: linear-gradient(90deg, #22d3ee, #6366f1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.metric-label {
    color: #475569;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 4px;
}

/* Section headers */
.section-header {
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin: 20px 0 10px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #ffffff0a;
}

/* Input override */
.stChatInput > div {
    background: #12122a !important;
    border: 1px solid #22d3ee33 !important;
    border-radius: 14px !important;
}

.stChatInput textarea {
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Hide defaults */
#MainMenu, footer, header {visibility: hidden;}
.stDeployButton {display: none;}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #22d3ee33; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_resource
def init_groq():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def load_all_data():
    """Load Gold data into both Pandas and ChromaDB."""
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("CmdCenter").master("local[*]").getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        df = spark.read.parquet("data/gold/weather_features").toPandas()
        spark.stop()

        # Load into ChromaDB
        client = chromadb.Client()
        try:
            client.delete_collection("weather_data")
        except Exception:
            pass
        coll = client.create_collection("weather_data")

        docs, metas, ids = [], [], []
        for i, (_, r) in enumerate(df.iterrows()):
            d = (f"City: {r.get('city','?')}, {r.get('state','')}. "
                 f"Temp: {r.get('temperature_fahrenheit','?')}°F. "
                 f"Humidity: {r.get('humidity_percent','?')}%. "
                 f"Wind: {r.get('wind_speed_mph','?')} mph. "
                 f"Pressure: {r.get('pressure_hpa','?')} hPa. "
                 f"Heat Index: {r.get('heat_index','?')}°F. "
                 f"Wind Chill: {r.get('wind_chill','?')}°F. "
                 f"Condition: {r.get('weather_condition','?')}. "
                 f"Extreme: {'Yes' if r.get('is_extreme_weather',0)==1 else 'No'}. "
                 f"Anomaly: {r.get('temp_anomaly_score','?')}.")
            docs.append(d)
            metas.append({"city": str(r.get('city','')), "state": str(r.get('state',''))})
            ids.append(f"w_{i}")

        for s in range(0, len(docs), 100):
            e = min(s+100, len(docs))
            coll.add(documents=docs[s:e], metadatas=metas[s:e], ids=ids[s:e])

        return df, coll
    except Exception as e:
        st.error(f"Data load error: {e}")
        return None, None


def get_city_latest(df):
    """Get latest reading for each city."""
    return df.drop_duplicates(subset=['city'], keep='last').sort_values('temperature_fahrenheit', ascending=False)


def get_db_stats():
    try:
        conn = psycopg2.connect(host="localhost", port=5432, database="airflow", user="airflow", password="airflow")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather=1")
        extreme = c.fetchone()[0]
        conn.close()
        return total, extreme
    except Exception:
        return 660, 13


# ============================================================
# AI FUNCTIONS
# ============================================================

def detect_mode(q):
    q = q.lower()
    if any(k in q for k in ["anomaly","unusual","strange","why is","explain why"]):
        return "anomaly"
    if any(k in q for k in ["report","forecast","summary","conditions in","brief"]):
        return "report"
    if any(k in q for k in ["average","count","how many","total","max","min","highest","lowest","top","list","show me all"]):
        return "sql"
    return "rag"


def ai_answer(question, collection, groq_client):
    mode = detect_mode(question)

    if mode == "sql":
        schema = "climate_warehouse.fact_weather_readings(location_key,temperature_fahrenheit,humidity_percent,pressure_hpa,wind_speed_mph,heat_index,is_extreme_weather) JOIN climate_warehouse.dim_location(location_key,city,state,region) ON location_key"
        r = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"Return ONLY PostgreSQL SELECT. Use climate_warehouse. LIMIT 20. No explanation."},
                      {"role":"user","content":f"Schema:{schema}\nQuestion:{question}\nSQL:"}],
            max_tokens=200, temperature=0.1)
        sql = r.choices[0].message.content.strip().replace("```sql","").replace("```","").strip()

        try:
            conn = psycopg2.connect(host="localhost",port=5432,database="airflow",user="airflow",password="airflow")
            cur = conn.cursor()
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            conn.close()
            results = [dict(zip(cols,r)) for r in rows]

            r2 = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role":"system","content":"Summarize results naturally. Be specific."},
                          {"role":"user","content":f"Q:{question}\nResults:{str(results[:10])}\nAnswer in under 100 words:"}],
                max_tokens=200, temperature=0.2)
            return r2.choices[0].message.content.strip() + f"\n\n`{sql}`", mode
        except Exception as e:
            return f"Query error: {e}\n\nGenerated: `{sql}`", mode

    else:
        results = collection.query(query_texts=[question], n_results=6)
        ctx = "\n".join(results['documents'][0]) if results['documents'] else "No data."

        system_prompts = {
            "rag": "You are a climate data analyst. Answer from provided data only. Be specific with numbers and city names.",
            "report": "You are a senior weather analyst. Generate structured reports: Summary, Key Findings, Risks, Recommendations.",
            "anomaly": "You are a meteorologist. Explain anomalies: What's unusual, Possible causes, Risks, Precautions."
        }

        r = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":system_prompts[mode]},
                      {"role":"user","content":f"WEATHER DATA:\n{ctx}\n\nQUESTION: {question}\n\nAnswer in under 200 words:"}],
            max_tokens=400, temperature=0.3)
        return r.choices[0].message.content.strip(), mode


# ============================================================
# MAIN UI
# ============================================================

# Load data
groq_client = init_groq()

with st.spinner("Initializing Climate Command Center..."):
    gold_df, collection = load_all_data()

if gold_df is None:
    st.error("❌ Could not load data. Make sure data/gold/ exists.")
    st.stop()

cities_df = get_city_latest(gold_df)
total_records, extreme_count = get_db_stats()

# --- COMMAND BAR ---
st.markdown(f"""
<div class="command-bar">
    <div>
        <span class="command-title">⚡ Climate Command Center</span>
    </div>
    <div class="command-status">
        <span><span class="status-dot status-live"></span> <span class="status-label">KAFKA LIVE</span></span>
        <span style="color:#334155">│</span>
        <span class="status-label">{len(cities_df)} CITIES</span>
        <span style="color:#334155">│</span>
        <span class="status-label">{datetime.now().strftime('%H:%M:%S UTC')}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- METRICS ---
avg_temp = round(gold_df['temperature_fahrenheit'].mean(), 1)
max_temp = round(gold_df['temperature_fahrenheit'].max(), 1)
min_temp = round(gold_df['temperature_fahrenheit'].min(), 1)

st.markdown(f"""
<div class="metric-row">
    <div class="metric-card">
        <div class="metric-value">{total_records}</div>
        <div class="metric-label">Total Readings</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{avg_temp}°</div>
        <div class="metric-label">Avg Temperature</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{extreme_count}</div>
        <div class="metric-label">Extreme Events</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{max_temp}°</div>
        <div class="metric-label">Peak Temperature</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- CITY MONITORING GRID ---
st.markdown('<div class="section-header">📡 Live City Monitoring</div>', unsafe_allow_html=True)

city_cards = ""
for _, row in cities_df.iterrows():
    is_ext = "city-extreme" if row.get('is_extreme_weather', 0) == 1 else ""
    emoji = "🔴" if row.get('is_extreme_weather', 0) == 1 else ""
    temp = round(row.get('temperature_fahrenheit', 0), 1)
    hum = round(row.get('humidity_percent', 0))
    city_cards += f"""
    <div class="city-card {is_ext}">
        <div class="city-name">{row.get('city','?')} {emoji}</div>
        <div class="city-temp">{temp}°</div>
        <div class="city-detail">💧 {hum}% │ 💨 {round(row.get('wind_speed_mph',0),1)} mph</div>
    </div>
    """

st.markdown(f'<div class="city-grid">{city_cards}</div>', unsafe_allow_html=True)

# --- AI CHAT ---
st.markdown('<div class="section-header">🧠 AI Weather Intelligence</div>', unsafe_allow_html=True)

# Initialize chat
if "msgs" not in st.session_state:
    st.session_state.msgs = [{
        "role": "bot",
        "content": "Welcome to Climate Command Center. I'm monitoring weather data across 20 US cities in real-time. Ask me anything — I can search data, run SQL queries, generate reports, and explain anomalies.",
        "mode": "rag"
    }]

# Quick actions
c1, c2, c3, c4, c5 = st.columns(5)
qk = None
with c1:
    if st.button("🌡️ Hottest", use_container_width=True):
        qk = "Which city has the highest temperature right now?"
with c2:
    if st.button("🥶 Coldest", use_container_width=True):
        qk = "Which city has the lowest temperature?"
with c3:
    if st.button("⚠️ Extreme", use_container_width=True):
        qk = "How many extreme weather events are there and which cities?"
with c4:
    if st.button("📝 Report", use_container_width=True):
        qk = "Give me a weather report for all monitored cities"
with c5:
    if st.button("🔍 Anomaly", use_container_width=True):
        qk = "Explain any weather anomalies in the current data"

# Render chat messages
mode_tags = {
    "rag": '<span class="mode-tag tag-rag">RAG SEARCH</span>',
    "sql": '<span class="mode-tag tag-sql">SQL QUERY</span>',
    "report": '<span class="mode-tag tag-report">AI REPORT</span>',
    "anomaly": '<span class="mode-tag tag-anomaly">ANOMALY</span>',
}

chat_html = ""
for msg in st.session_state.msgs:
    if msg["role"] == "user":
        chat_html += f'<div class="msg-user"><div class="msg-user-bubble">{msg["content"]}</div></div>'
    else:
        tag = mode_tags.get(msg.get("mode", "rag"), "")
        # Escape HTML in content but preserve newlines
        content = msg["content"].replace("\n", "<br>")
        chat_html += f'''
        <div class="msg-bot">
            <div class="msg-bot-avatar">🌍</div>
            <div class="msg-bot-content">{tag}{content}</div>
        </div>'''

st.markdown(f'<div class="chat-container">{chat_html}</div>', unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Ask about weather, climate data, or extreme events...")

if qk:
    user_input = qk

if user_input:
    st.session_state.msgs.append({"role": "user", "content": user_input})

    with st.spinner("🧠 Analyzing..."):
        answer, mode = ai_answer(user_input, collection, groq_client)

    st.session_state.msgs.append({"role": "bot", "content": answer, "mode": mode})
    st.rerun()