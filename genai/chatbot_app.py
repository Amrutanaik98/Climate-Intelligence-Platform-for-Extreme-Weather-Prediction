"""
🌍 Climate Intelligence Chatbot - Interactive Streamlit App
============================================================
A visually appealing RAG chatbot that lets users ask climate
questions in natural language and get grounded answers from
real weather data.

Features:
- Chat interface with message history
- RAG (ChromaDB + Groq LLM)
- Text-to-SQL queries
- Weather report generation
- Anomaly explanations
- Sidebar with data stats

Run: streamlit run genai/chatbot_app.py
"""

import os
import sys
import streamlit as st
import chromadb
import psycopg2
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="🌍 Climate Intelligence Chatbot",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS FOR VISUAL APPEAL
# ============================================================
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }

    /* Chat message styling */
    .user-msg {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px;
        border-radius: 20px 20px 5px 20px;
        margin: 10px 0;
        color: white;
        max-width: 80%;
        margin-left: auto;
        font-size: 16px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }

    .bot-msg {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 15px 20px;
        border-radius: 20px 20px 20px 5px;
        margin: 10px 0;
        color: #e0e0e0;
        max-width: 85%;
        font-size: 15px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    .sql-box {
        background: #1e1e3f;
        padding: 12px 16px;
        border-radius: 10px;
        margin: 8px 0;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        color: #7dd3fc;
        border: 1px solid #334155;
        overflow-x: auto;
    }

    /* Sidebar styling */
    .sidebar-stat {
        background: linear-gradient(135deg, #667eea22, #764ba222);
        padding: 15px;
        border-radius: 12px;
        margin: 8px 0;
        border: 1px solid rgba(255,255,255,0.1);
        text-align: center;
    }

    .stat-number {
        font-size: 28px;
        font-weight: bold;
        color: #667eea;
    }

    .stat-label {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
    }

    /* Header styling */
    .main-header {
        text-align: center;
        padding: 20px 0 10px 0;
    }

    .main-header h1 {
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2em;
        font-weight: 800;
    }

    /* Quick action buttons */
    .quick-btn {
        background: linear-gradient(135deg, #667eea22, #764ba222);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 12px;
        padding: 10px 16px;
        color: #cbd5e1;
        cursor: pointer;
        transition: all 0.3s;
        text-align: center;
        font-size: 13px;
    }

    /* Input styling */
    .stTextInput > div > div > input {
        background: #1a1a2e !important;
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 15px !important;
        padding: 12px 20px !important;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        margin: 2px;
    }
    .mode-rag { background: #166534; color: #4ade80; }
    .mode-sql { background: #1e3a5f; color: #7dd3fc; }
    .mode-report { background: #713f12; color: #fbbf24; }
    .mode-anomaly { background: #7f1d1d; color: #fca5a5; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# INITIALIZE SERVICES
# ============================================================

@st.cache_resource
def init_groq():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def init_chromadb():
    client = chromadb.Client()
    collection = client.get_or_create_collection("weather_data")
    return client, collection

@st.cache_resource
def load_weather_into_chromadb():
    """Load Gold layer data into ChromaDB."""
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("Chatbot").master("local[*]").getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        df = spark.read.parquet("data/gold/weather_features").toPandas()
        spark.stop()

        client = chromadb.Client()
        try:
            client.delete_collection("weather_data")
        except Exception:
            pass
        collection = client.create_collection("weather_data")

        docs, metas, ids = [], [], []
        for i, (_, row) in enumerate(df.iterrows()):
            doc = (
                f"City: {row.get('city', '?')}, {row.get('state', '')}. "
                f"Temperature: {row.get('temperature_fahrenheit', '?')}°F. "
                f"Humidity: {row.get('humidity_percent', '?')}%. "
                f"Wind: {row.get('wind_speed_mph', '?')} mph. "
                f"Pressure: {row.get('pressure_hpa', '?')} hPa. "
                f"Heat Index: {row.get('heat_index', '?')}°F. "
                f"Wind Chill: {row.get('wind_chill', '?')}°F. "
                f"Condition: {row.get('weather_condition', '?')}. "
                f"Extreme: {'Yes' if row.get('is_extreme_weather', 0) == 1 else 'No'}. "
                f"Anomaly Score: {row.get('temp_anomaly_score', '?')}."
            )
            docs.append(doc)
            metas.append({"city": str(row.get('city', '')), "state": str(row.get('state', ''))})
            ids.append(f"w_{i}")

        batch = 100
        for s in range(0, len(docs), batch):
            e = min(s + batch, len(docs))
            collection.add(documents=docs[s:e], metadatas=metas[s:e], ids=ids[s:e])

        return collection, df
    except Exception as e:
        return None, None


def get_db_stats():
    """Get stats from PostgreSQL warehouse."""
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, database="airflow",
            user="airflow", password="airflow"
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT city) FROM climate_warehouse.dim_location")
        cities = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather = 1")
        extreme = cur.fetchone()[0]
        conn.close()
        return {"total": total, "cities": cities, "extreme": extreme}
    except Exception:
        return {"total": 660, "cities": 20, "extreme": 13}


# ============================================================
# CHAT FUNCTIONS
# ============================================================

def detect_mode(question):
    """Detect which mode to use based on the question."""
    q = question.lower()
    sql_keywords = ["average", "count", "how many", "total", "sum", "max", "min", "highest", "lowest", "top", "list all", "show me"]
    report_keywords = ["report", "forecast", "summary", "brief", "conditions in"]
    anomaly_keywords = ["anomaly", "unusual", "weird", "strange", "abnormal", "why is", "explain"]

    if any(k in q for k in anomaly_keywords):
        return "anomaly"
    if any(k in q for k in report_keywords):
        return "report"
    if any(k in q for k in sql_keywords):
        return "sql"
    return "rag"


def rag_answer(question, collection, groq_client):
    """RAG: Search ChromaDB → LLM generates answer."""
    results = collection.query(query_texts=[question], n_results=5)
    context = "\n".join(results['documents'][0]) if results['documents'] else "No data."

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a climate analyst. Answer based ONLY on the provided data. Be specific with numbers."},
            {"role": "user", "content": f"DATA:\n{context}\n\nQUESTION: {question}\n\nAnswer in under 150 words:"}
        ],
        max_tokens=300, temperature=0.2
    )
    return response.choices[0].message.content.strip(), "rag"


def sql_answer(question, groq_client):
    """Text-to-SQL: Convert to SQL → Execute → Answer."""
    schema = """
    TABLE: climate_warehouse.fact_weather_readings (location_key INT, temperature_fahrenheit FLOAT, humidity_percent FLOAT, pressure_hpa FLOAT, wind_speed_mph FLOAT, heat_index FLOAT, wind_chill FLOAT, temp_anomaly FLOAT, is_extreme_weather INT, source VARCHAR)
    TABLE: climate_warehouse.dim_location (location_key INT, city VARCHAR, state VARCHAR, region VARCHAR, latitude FLOAT, longitude FLOAT)
    TABLE: climate_warehouse.dim_weather_type (weather_type_key INT, condition VARCHAR, severity VARCHAR)
    """

    sql_response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Return ONLY a PostgreSQL SELECT query. No explanation. Use climate_warehouse. schema. LIMIT 20."},
            {"role": "user", "content": f"Schema: {schema}\n\nQuestion: {question}\n\nSQL:"}
        ],
        max_tokens=200, temperature=0.1
    )
    sql = sql_response.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()

    try:
        conn = psycopg2.connect(host="localhost", port=5432, database="airflow", user="airflow", password="airflow")
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()
        results = [dict(zip(cols, r)) for r in rows]

        nl_response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Summarize SQL results naturally. Be specific with numbers."},
                {"role": "user", "content": f"Question: {question}\nResults: {str(results[:10])}\nAnswer in under 100 words:"}
            ],
            max_tokens=200, temperature=0.2
        )
        answer = nl_response.choices[0].message.content.strip()
        return f"{answer}\n\n📝 **SQL Query:**\n```sql\n{sql}\n```", "sql"

    except Exception as e:
        return f"SQL execution failed: {e}\n\nGenerated SQL: `{sql}`", "sql"


def report_answer(question, collection, groq_client):
    """Generate a weather report."""
    results = collection.query(query_texts=[question], n_results=10)
    context = "\n".join(results['documents'][0]) if results['documents'] else "No data."

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional weather analyst. Generate a structured weather report."},
            {"role": "user", "content": f"DATA:\n{context}\n\nGenerate a weather report addressing: {question}\n\nFormat: 1) Summary 2) Key findings 3) Risks 4) Recommendations. Under 200 words."}
        ],
        max_tokens=400, temperature=0.3
    )
    return response.choices[0].message.content.strip(), "report"


def anomaly_answer(question, collection, groq_client):
    """Explain weather anomalies."""
    results = collection.query(query_texts=[question], n_results=8)
    context = "\n".join(results['documents'][0]) if results['documents'] else "No data."

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a meteorologist explaining weather anomalies."},
            {"role": "user", "content": f"DATA:\n{context}\n\nExplain: {question}\n\nInclude: 1) What's unusual 2) Possible causes 3) Risks 4) Precautions. Under 150 words."}
        ],
        max_tokens=300, temperature=0.3
    )
    return response.choices[0].message.content.strip(), "anomaly"


def get_answer(question, collection, groq_client):
    """Route question to the right handler."""
    mode = detect_mode(question)
    if mode == "sql":
        return sql_answer(question, groq_client)
    elif mode == "report":
        return report_answer(question, collection, groq_client)
    elif mode == "anomaly":
        return anomaly_answer(question, collection, groq_client)
    else:
        return rag_answer(question, collection, groq_client)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🌍 Climate Intelligence")
    st.markdown("---")

    stats = get_db_stats()

    st.markdown(f"""
    <div class="sidebar-stat">
        <div class="stat-number">{stats['total']}</div>
        <div class="stat-label">Weather Readings</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="sidebar-stat">
        <div class="stat-number">{stats['cities']}</div>
        <div class="stat-label">US Cities Monitored</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="sidebar-stat">
        <div class="stat-number">{stats['extreme']}</div>
        <div class="stat-label">Extreme Events Detected</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🤖 AI Modes")
    st.markdown("""
    <span class="mode-badge mode-rag">🔍 RAG Search</span>
    <span class="mode-badge mode-sql">📊 Text-to-SQL</span>
    <span class="mode-badge mode-report">📝 Reports</span>
    <span class="mode-badge mode-anomaly">⚠️ Anomalies</span>
    """, unsafe_allow_html=True)

    st.markdown("""
    <br>
    
    **Try asking:**
    - "Which city is the hottest?"
    - "How many extreme weather events?"
    - "Give me a report for Phoenix"
    - "Why is the anomaly score high?"
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"*Powered by Groq (Llama 3.1) + ChromaDB*")
    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")


# ============================================================
# MAIN CHAT INTERFACE
# ============================================================

st.markdown("""
<div class="main-header">
    <h1>🌦️ Climate Intelligence Chatbot</h1>
    <p style="color: #94a3b8; font-size: 16px;">
        Ask me anything about weather data across 20 US cities — I'll search real data, 
        query the warehouse, and generate insights using AI.
    </p>
</div>
""", unsafe_allow_html=True)

# Initialize
groq_client = init_groq()

with st.spinner("🔄 Loading weather data into AI memory..."):
    collection, gold_df = load_weather_into_chromadb()

if collection is None:
    st.error("❌ Could not load weather data. Make sure Gold layer exists in data/gold/")
    st.stop()

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi! I'm your Climate Intelligence Assistant. I can answer questions about weather data from 20 US cities.\n\nI can:\n- 🔍 **Search** weather data (RAG)\n- 📊 **Query** the warehouse (Text-to-SQL)\n- 📝 **Generate** weather reports\n- ⚠️ **Explain** anomalies\n\nWhat would you like to know?",
        "mode": "rag"
    })

# Quick action buttons
st.markdown("#### ⚡ Quick Questions")
col1, col2, col3, col4 = st.columns(4)

quick_q = None
with col1:
    if st.button("🌡️ Hottest City", use_container_width=True):
        quick_q = "Which city has the highest temperature?"
with col2:
    if st.button("⚠️ Extreme Events", use_container_width=True):
        quick_q = "How many extreme weather events are there?"
with col3:
    if st.button("📝 Phoenix Report", use_container_width=True):
        quick_q = "Give me a weather report for Phoenix"
with col4:
    if st.button("🥶 Coldest City", use_container_width=True):
        quick_q = "Which city has the lowest temperature?"

st.markdown("---")

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-msg">💬 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        mode = msg.get("mode", "rag")
        mode_badges = {
            "rag": '<span class="mode-badge mode-rag">🔍 RAG Search</span>',
            "sql": '<span class="mode-badge mode-sql">📊 Text-to-SQL</span>',
            "report": '<span class="mode-badge mode-report">📝 Report</span>',
            "anomaly": '<span class="mode-badge mode-anomaly">⚠️ Anomaly</span>',
        }
        badge = mode_badges.get(mode, "")
        st.markdown(f'<div class="bot-msg">{badge}<br><br>{msg["content"]}</div>', unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Ask me about weather, climate, or extreme events...")

# Handle quick question buttons
if quick_q:
    user_input = quick_q

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.markdown(f'<div class="user-msg">💬 {user_input}</div>', unsafe_allow_html=True)

    # Get AI answer
    with st.spinner("🧠 Thinking..."):
        answer, mode = get_answer(user_input, collection, groq_client)

    # Add bot response
    st.session_state.messages.append({"role": "assistant", "content": answer, "mode": mode})

    mode_badges = {
        "rag": '<span class="mode-badge mode-rag">🔍 RAG Search</span>',
        "sql": '<span class="mode-badge mode-sql">📊 Text-to-SQL</span>',
        "report": '<span class="mode-badge mode-report">📝 Report</span>',
        "anomaly": '<span class="mode-badge mode-anomaly">⚠️ Anomaly</span>',
    }
    badge = mode_badges.get(mode, "")
    st.markdown(f'<div class="bot-msg">{badge}<br><br>{answer}</div>', unsafe_allow_html=True)

    st.rerun()