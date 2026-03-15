"""
🌍 Climate Intelligence Command Center v3 (FIXED)
Schema-aligned, dynamic city count, visibility_km support.

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
# CSS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@300;400;500;600;700;800&display=swap');

/* === GLOBAL === */
.stApp { background: #06060e; color: #e2e8f0; }
* { font-family: 'Inter', sans-serif; }

/* === ANIMATIONS === */
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }
@keyframes slideUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
@keyframes glow { 0%,100% { box-shadow:0 0 8px #22d3ee33; } 50% { box-shadow:0 0 20px #22d3ee55; } }

/* === TOP BAR === */
.top-bar {
    background: linear-gradient(90deg, #0c0c1d, #141432, #0c0c1d);
    border: 1px solid #22d3ee22; padding:14px 28px;
    border-radius:16px; display:flex;
    justify-content:space-between; align-items:center;
    margin-bottom:20px; animation: glow 4s ease-in-out infinite;
}
.top-title {
    font-family:'JetBrains Mono'; font-size:14px; font-weight:700;
    background: linear-gradient(90deg, #22d3ee, #818cf8);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    letter-spacing:4px; text-transform:uppercase;
}
.top-status { color:#64748b; font-size:11px; font-family:'JetBrains Mono'; display:flex; align-items:center; gap:12px; }
.live-dot {
    display:inline-block; width:8px; height:8px; border-radius:50%;
    background:#22c55e; box-shadow:0 0 12px #22c55e;
    animation: pulse 2s ease-in-out infinite; margin-right:4px;
}
.status-chip {
    background: linear-gradient(135deg, #6366f122, #818cf822);
    color:#a5b4fc; padding:5px 14px; border-radius:10px;
    font-size:11px; font-family:'JetBrains Mono'; font-weight:500;
    border: 1px solid #6366f133;
}

/* === METRICS === */
.metric-card {
    background: linear-gradient(160deg, #0d0d1a, #141430);
    border: 1px solid #ffffff08; border-radius:16px;
    padding:22px 16px; text-align:center;
    transition: all 0.3s ease; animation: slideUp 0.5s ease-out;
}
.metric-card:hover { border-color: #22d3ee33; transform: translateY(-2px); }
.metric-icon { font-size:24px; margin-bottom:6px; }
.metric-value {
    font-size:32px; font-weight:800; font-family:'JetBrains Mono';
    background: linear-gradient(135deg, #22d3ee, #818cf8);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    line-height:1.2;
}
.metric-label {
    color:#475569; font-size:10px; text-transform:uppercase;
    letter-spacing:2px; margin-top:4px; font-weight:600;
}

/* === SECTION HEADERS === */
.section-hdr {
    color:#94a3b8; font-size:11px; font-weight:700;
    letter-spacing:3px; text-transform:uppercase;
    margin:28px 0 14px 0; padding-bottom:8px;
    border-bottom: 1px solid #ffffff08;
    display:flex; align-items:center; gap:8px;
}

/* === CITY CARDS === */
.city-card {
    background: linear-gradient(160deg, #0d0d1a, #141430);
    border: 1px solid #ffffff08; border-radius:14px;
    padding:16px; text-align:center; margin-bottom:10px;
    transition: all 0.3s ease;
}
.city-card:hover { border-color: #22d3ee22; transform: translateY(-1px); }
.city-card.extreme { border-color: #ef444455; box-shadow: 0 0 20px #ef444418; }
.city-name {
    color:#94a3b8; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:1.5px;
}
.city-temp {
    font-size:28px; font-weight:800; font-family:'JetBrains Mono';
    margin:6px 0 4px 0; line-height:1;
}
.city-details { color:#475569; font-size:10px; font-family:'JetBrains Mono'; }

/* === CHAT === */
.chat-container {
    background: #0a0a16; border: 1px solid #ffffff08;
    border-radius:16px; padding:20px; margin-top:8px;
    max-height:500px; overflow-y:auto;
}
.chat-msg-user {
    background: linear-gradient(135deg, #6366f1, #7c3aed);
    color:white; padding:12px 18px; border-radius:18px 18px 6px 18px;
    margin:10px 0; display:inline-block; max-width:72%;
    font-size:14px; float:right; clear:both;
    box-shadow: 0 4px 16px #6366f133;
    animation: slideUp 0.3s ease-out;
}
.chat-msg-bot {
    background: linear-gradient(160deg, #0f0f24, #151535);
    border: 1px solid #ffffff0a; color:#cbd5e1;
    padding:14px 18px; border-radius:6px 18px 18px 18px;
    margin:10px 0; display:inline-block; max-width:82%;
    font-size:14px; float:left; clear:both; line-height:1.7;
    animation: slideUp 0.3s ease-out;
}
.chat-clear { clear:both; }

/* === TAGS === */
.tag {
    display:inline-block; padding:3px 10px; border-radius:8px;
    font-size:9px; font-weight:700; letter-spacing:1.5px;
    text-transform:uppercase; margin-bottom:8px;
    font-family:'JetBrains Mono';
}
.tag-rag { background:#064e3b; color:#34d399; border:1px solid #16a34a33; }
.tag-sql { background:#1e3a5f; color:#38bdf8; border:1px solid #0ea5e933; }
.tag-report { background:#451a03; color:#fb923c; border:1px solid #ea580c33; }
.tag-anomaly { background:#450a0a; color:#f87171; border:1px solid #ef444433; }

/* === QUICK BUTTONS === */
div.stButton > button {
    background: linear-gradient(160deg, #0d0d1a, #141430) !important;
    border: 1px solid #ffffff10 !important; color: #94a3b8 !important;
    border-radius: 12px !important; font-size: 12px !important;
    font-weight: 600 !important; padding: 8px 12px !important;
    transition: all 0.3s ease !important;
}
div.stButton > button:hover {
    border-color: #22d3ee44 !important; color: #22d3ee !important;
    box-shadow: 0 0 16px #22d3ee18 !important;
    transform: translateY(-1px) !important;
}

/* === HIDE STREAMLIT DEFAULTS === */
#MainMenu, footer, header { visibility:hidden; }
.stDeployButton { display:none; }
div[data-testid="stStatusWidget"] { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE HELPER — FIXED: aligned with create_wh.sql schema
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
# DATA LOADING — Fast pandas + ChromaDB
# ============================================================

@st.cache_resource
def init_groq():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def load_gold_data():
    """Load gold parquet with pandas + build ChromaDB vector store."""
    try:
        df = pd.read_parquet("data/gold/weather_features")

        client = chromadb.Client()
        try: client.delete_collection("climate_data")
        except Exception: pass
        coll = client.create_collection("climate_data", metadata={"hnsw:space": "cosine"})

        docs, metas, ids = [], [], []
        for i, (_, r) in enumerate(df.iterrows()):
            # FIXED: use visibility_km (aligned with warehouse schema)
            vis_val = r.get('visibility_km', r.get('visibility_miles', 'N/A'))
            vis_unit = "km" if 'visibility_km' in r.index else "miles"

            doc = (
                f"City: {r.get('city','N/A')}, State: {r.get('state','N/A')}. "
                f"Temperature: {r.get('temperature_fahrenheit','N/A')}°F ({r.get('temperature_celsius','N/A')}°C). "
                f"Humidity: {r.get('humidity_percent','N/A')}%. "
                f"Wind Speed: {r.get('wind_speed_mph','N/A')} mph. "
                f"Pressure: {r.get('pressure_hpa','N/A')} hPa. "
                f"Heat Index: {r.get('heat_index','N/A')}°F. "
                f"Wind Chill: {r.get('wind_chill','N/A')}°F. "
                f"Weather Condition: {r.get('weather_condition','N/A')}. "
                f"Cloud Cover: {r.get('cloud_cover_percent','N/A')}%. "
                f"Visibility: {vis_val} {vis_unit}. "
                f"Extreme Weather: {'YES' if r.get('is_extreme_weather',0)==1 else 'No'}. "
                f"Heatwave: {'YES' if r.get('is_heatwave',0)==1 else 'No'}. "
                f"Extreme Cold: {'YES' if r.get('is_extreme_cold',0)==1 else 'No'}. "
                f"High Wind: {'YES' if r.get('is_high_wind',0)==1 else 'No'}. "
                f"Temperature Anomaly Score: {r.get('temp_anomaly_score','N/A')}. "
                f"Temperature Anomaly: {r.get('temperature_anomaly','N/A')}°F."
            )
            docs.append(doc)
            metas.append({
                "city": str(r.get('city', '')),
                "temp": float(r.get('temperature_fahrenheit', 0)),
                "extreme": int(r.get('is_extreme_weather', 0)),
            })
            ids.append(f"rec_{i}")

        for s in range(0, len(docs), 100):
            e = min(s + 100, len(docs))
            coll.add(documents=docs[s:e], metadatas=metas[s:e], ids=ids[s:e])

        return df, coll
    except Exception as e:
        st.error(f"Data load error: {e}")
        return None, None


# ============================================================
# SMART AI ENGINE
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
              "above", "below", "between", "greater", "less than"]
    if any(k in q for k in sql_kw): return "sql"

    return "rag"


def build_sql_answer(question, gc):
    # FIXED: schema info aligned with create_wh.sql
    schema_info = """
    Tables:
    1. climate_warehouse.fact_weather_readings
       Columns: reading_key, location_key, time_key, weather_type_key,
       temperature_fahrenheit, temperature_celsius, humidity_percent, pressure_hpa,
       wind_speed_mph, wind_direction_degrees, precipitation_mm, visibility_km,
       cloud_cover_percent, uv_index, heat_index, wind_chill,
       temp_anomaly, temp_anomaly_score,
       is_extreme_weather, is_heatwave, is_extreme_cold, is_high_wind,
       is_heavy_precipitation, source, quality_flag

    2. climate_warehouse.dim_location
       Columns: location_key, city, state, country, latitude, longitude, region

    3. climate_warehouse.dim_time
       Columns: time_key, full_timestamp, date, year, quarter, month, month_name,
       week_of_year, day_of_month, day_of_week, day_name, hour, is_weekend, season

    4. climate_warehouse.dim_weather_type
       Columns: weather_type_key, condition, category, severity, description

    RULES:
    - Always JOIN fact with dim_location using location_key.
    - JOIN with dim_time using time_key for time-based queries.
    - JOIN with dim_weather_type using weather_type_key for weather condition queries.
    - Use ROUND() for decimals. Add LIMIT 20.
    - Return ONLY a valid PostgreSQL SELECT statement. No explanations.
    """
    r = gc.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": f"You are a PostgreSQL expert. Output ONLY the SQL query, nothing else.\n{schema_info}"},
            {"role": "user", "content": f"Write a SELECT query for: {question}"}
        ],
        max_tokens=400, temperature=0.05
    )
    raw = r.choices[0].message.content.strip()

    # Extract SQL
    raw = raw.replace("```sql", "").replace("```", "").strip()
    lines = raw.split("\n")
    capture = False
    sql_lines = []
    for line in lines:
        if line.strip().upper().startswith("SELECT"):
            capture = True
        if capture:
            sql_lines.append(line)
        if capture and ";" in line:
            break
    sql = "\n".join(sql_lines).strip().rstrip(";").strip()

    if not sql or not sql.upper().startswith("SELECT"):
        return None, "sql"

    try:
        conn = get_conn(); cur = conn.cursor(); cur.execute(sql)
        cols = [d[0] for d in cur.description]; rows = cur.fetchall(); conn.close()
        results = [dict(zip(cols, row)) for row in rows]

        if not results:
            return "No results found for that query. Try rephrasing.", "sql"

        r2 = gc.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Summarize the weather query results clearly with specific numbers. Be concise (2-4 sentences)."},
                {"role": "user", "content": f"User asked: {question}\nResults:\n{str(results[:15])}\n\nSummary:"}
            ],
            max_tokens=250, temperature=0.2
        )
        return r2.choices[0].message.content.strip() + f"\n\n📝 `{sql}`", "sql"
    except Exception:
        return None, "sql"


def build_rag_answer(question, coll, gc, mode="rag"):
    n_results = 10 if mode == "report" else 8
    res = coll.query(query_texts=[question], n_results=n_results)
    ctx = "\n".join(res['documents'][0]) if res['documents'] and res['documents'][0] else "No data."

    prompts = {
        "rag": (
            "You are an expert climate analyst. "
            "Answer ONLY from the provided data. Be specific with numbers and city names. "
            "If data doesn't contain the answer, say so clearly."
        ),
        "report": (
            "You are a weather intelligence analyst. Generate a structured report:\n"
            "📋 **SUMMARY** — 1-2 sentence overview\n"
            "🔍 **KEY FINDINGS** — Top 3-4 findings with specific numbers\n"
            "⚠️ **RISKS & ALERTS** — Any extreme weather or anomalies\n"
            "✅ **RECOMMENDATIONS** — 2-3 actionable items\n"
            "Use specific temperatures, cities, and data values."
        ),
        "anomaly": (
            "You are a senior meteorologist analyzing anomalies:\n"
            "🔴 **WHAT'S UNUSUAL** — Identify anomalies with specific numbers\n"
            "🔬 **LIKELY CAUSES** — Scientific explanation\n"
            "⚠️ **RISK ASSESSMENT** — Potential impacts\n"
            "🛡️ **PRECAUTIONS** — Recommended actions\n"
            "Focus on high anomaly scores or extreme weather flags."
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
    return r.choices[0].message.content.strip(), mode


def try_direct_answer(question, gold_df):
    """Answer simple min/max/ranking questions directly from DataFrame."""
    q = question.lower()
    cities = gold_df.drop_duplicates(subset=['city'], keep='last')

    if any(k in q for k in ["hottest", "highest temp", "warmest", "highest temperature", "most hot"]):
        row = cities.loc[cities['temperature_fahrenheit'].idxmax()]
        top5 = cities.nlargest(5, 'temperature_fahrenheit')[['city', 'state', 'temperature_fahrenheit']]
        lines = "\n".join([f"  {i+1}. **{r['city']}, {r['state']}** — {round(r['temperature_fahrenheit'],1)}°F"
                          for i, (_, r) in enumerate(top5.iterrows())])
        return (f"🔥 **{row['city']}, {row['state']}** has the highest temperature at **{round(row['temperature_fahrenheit'],1)}°F**.\n\n"
                f"**Top 5 Hottest Cities:**\n{lines}"), "rag"

    if any(k in q for k in ["coldest", "lowest temp", "coolest", "lowest temperature", "most cold", "freezing"]):
        row = cities.loc[cities['temperature_fahrenheit'].idxmin()]
        bot5 = cities.nsmallest(5, 'temperature_fahrenheit')[['city', 'state', 'temperature_fahrenheit']]
        lines = "\n".join([f"  {i+1}. **{r['city']}, {r['state']}** — {round(r['temperature_fahrenheit'],1)}°F"
                          for i, (_, r) in enumerate(bot5.iterrows())])
        return (f"🥶 **{row['city']}, {row['state']}** has the lowest temperature at **{round(row['temperature_fahrenheit'],1)}°F**.\n\n"
                f"**Top 5 Coldest Cities:**\n{lines}"), "rag"

    if any(k in q for k in ["most humid", "highest humidity", "humid"]):
        row = cities.loc[cities['humidity_percent'].idxmax()]
        return (f"💧 **{row['city']}, {row['state']}** has the highest humidity at **{round(row['humidity_percent'],1)}%** "
                f"with a temperature of {round(row['temperature_fahrenheit'],1)}°F."), "rag"

    if any(k in q for k in ["windiest", "most windy", "highest wind", "strongest wind"]):
        row = cities.loc[cities['wind_speed_mph'].idxmax()]
        return (f"💨 **{row['city']}, {row['state']}** has the highest wind speed at **{round(row['wind_speed_mph'],1)} mph** "
                f"with a temperature of {round(row['temperature_fahrenheit'],1)}°F."), "rag"

    if any(k in q for k in ["extreme weather", "extreme events", "how many extreme"]):
        ext = cities[cities['is_extreme_weather'] == 1]
        count = len(ext)
        if count == 0:
            return "✅ No extreme weather events detected across all monitored cities.", "rag"
        city_list = ", ".join([f"**{r['city']}** ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in ext.iterrows()])
        return (f"⚠️ **{count} extreme weather event(s)** detected:\n\n{city_list}\n\n"
                f"These cities have conditions outside normal ranges based on anomaly scoring."), "rag"

    # FIXED: heatwave-specific query
    if any(k in q for k in ["heatwave", "heat wave"]):
        hw = cities[cities.get('is_heatwave', pd.Series([0]*len(cities))) == 1]
        if len(hw) == 0:
            return "✅ No heatwave conditions detected.", "rag"
        city_list = ", ".join([f"**{r['city']}** ({round(r['temperature_fahrenheit'],1)}°F)" for _, r in hw.iterrows()])
        return f"🔥 **{len(hw)} city/cities** with heatwave conditions (>100°F):\n\n{city_list}", "rag"

    return None, None


def ai_answer(question, coll, gc):
    direct, mode = try_direct_answer(question, st.session_state.gold_df)
    if direct:
        return direct, mode

    mode = detect_mode(question)
    if mode == "sql":
        result, m = build_sql_answer(question, gc)
        if result is None:
            return build_rag_answer(question, coll, gc, "rag")
        return result, m
    return build_rag_answer(question, coll, gc, mode)


# ============================================================
# MAIN APP
# ============================================================

def render_app():
    gc = init_groq()

    with st.spinner("⚡ Loading Climate Intelligence..."):
        gold_df, coll = load_gold_data()

    if gold_df is None:
        st.error("❌ Could not load data. Run the pipeline first:\n`python data_processing/spark_batch_gold.py`")
        st.stop()

    st.session_state.gold_df = gold_df

    cities = gold_df.drop_duplicates(subset=['city'], keep='last').sort_values('temperature_fahrenheit', ascending=False)
    total, extreme = get_db_stats()
    avg_t = round(gold_df['temperature_fahrenheit'].mean(), 1)
    max_t = round(gold_df['temperature_fahrenheit'].max(), 1)
    min_t = round(gold_df['temperature_fahrenheit'].min(), 1)
    now = datetime.now().strftime("%b %d, %Y • %I:%M %p")
    city_count = len(cities)  # FIXED: dynamic count

    # ── TOP BAR ──
    st.markdown(f"""
    <div class="top-bar">
        <span class="top-title">🌍 Climate Command Center</span>
        <span class="top-status">
            <span class="live-dot"></span> LIVE &nbsp;│&nbsp; {city_count} CITIES &nbsp;│&nbsp;
            <span class="status-chip">🕐 {now}</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── METRICS ──
    m1, m2, m3, m4, m5 = st.columns(5)
    metrics = [
        (m1, "📊", total, "Total Readings"),
        (m2, "🌡️", f"{avg_t}°F", "Avg Temperature"),
        (m3, "🔥", f"{max_t}°F", "Peak Temp"),
        (m4, "🥶", f"{min_t}°F", "Lowest Temp"),
        (m5, "⚠️", extreme, "Extreme Events"),
    ]
    for col, icon, val, label in metrics:
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-icon">{icon}</div>
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── CITY GRID ──
    st.markdown('<div class="section-hdr">📡 &nbsp;Live City Monitoring</div>', unsafe_allow_html=True)

    rows_of_cities = [cities.iloc[i:i+5] for i in range(0, len(cities), 5)]
    for row_chunk in rows_of_cities:
        cols = st.columns(5)
        for idx, (_, city) in enumerate(row_chunk.iterrows()):
            with cols[idx]:
                t = round(city.get('temperature_fahrenheit', 0), 1)
                h = round(city.get('humidity_percent', 0))
                w = round(city.get('wind_speed_mph', 0), 1)
                nm = city.get('city', '?')
                cond = city.get('weather_condition', '')
                ext = city.get('is_extreme_weather', 0) == 1
                cls = "extreme" if ext else ""
                tc = "#f87171" if ext else "#e2e8f0"
                badge = ' <span style="color:#ef4444;">⚠</span>' if ext else ""
                st.markdown(f"""
                <div class="city-card {cls}">
                    <div class="city-name">{nm}{badge}</div>
                    <div class="city-temp" style="color:{tc};">{t}°</div>
                    <div class="city-details">💧{h}% &nbsp;│&nbsp; 💨{w}mph &nbsp;│&nbsp; {cond}</div>
                </div>
                """, unsafe_allow_html=True)

    # ── AI CHAT ──
    st.markdown('<div class="section-hdr">🧠 &nbsp;AI Weather Intelligence</div>', unsafe_allow_html=True)

    # FIXED: dynamic city count in welcome message
    if "msgs" not in st.session_state:
        st.session_state.msgs = [{
            "role": "bot",
            "text": (
                f"Welcome to Climate Command Center! 👋 I'm monitoring **"
                f"{city_count} cities** in real-time.\n\n"
                "I support 4 intelligence modes:\n"
                "• **RAG** — Ask anything about current weather data\n"
                "• **SQL** — Quantitative queries (averages, counts, rankings)\n"
                "• **Report** — Structured weather intelligence reports\n"
                "• **Anomaly** — Explain unusual weather patterns\n\n"
                "Try the quick buttons or type your question!"
            ),
            "mode": "rag"
        }]

    # Quick buttons
    c1, c2, c3, c4, c5 = st.columns(5)
    qk = None
    with c1:
        if st.button("🔥 Hottest City", use_container_width=True): qk = "Which city has the highest temperature right now?"
    with c2:
        if st.button("🥶 Coldest City", use_container_width=True): qk = "Which city has the lowest temperature?"
    with c3:
        if st.button("⚠️ Extreme Events", use_container_width=True): qk = "How many extreme weather events are there and which cities are affected?"
    with c4:
        if st.button("📋 Full Report", use_container_width=True): qk = "Generate a comprehensive weather report for all monitored cities"
    with c5:
        if st.button("🔍 Anomalies", use_container_width=True): qk = "Detect and explain any weather anomalies across all cities"

    tag_html = {
        "rag":     '<span class="tag tag-rag">RAG</span>',
        "sql":     '<span class="tag tag-sql">SQL</span>',
        "report":  '<span class="tag tag-report">REPORT</span>',
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
    if qk:
        user_in = qk
    if user_in:
        st.session_state.msgs.append({"role": "user", "text": user_in})
        with st.spinner("🧠 Analyzing climate data..."):
            ans, mode = ai_answer(user_in, coll, gc)
        st.session_state.msgs.append({"role": "bot", "text": ans, "mode": mode})
        st.rerun()


# ============================================================
# RUN
# ============================================================
render_app()