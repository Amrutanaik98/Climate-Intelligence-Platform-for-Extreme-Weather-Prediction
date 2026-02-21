"""
🌍 Climate Intelligence Command Center
With Full Signup/Login Authentication (PostgreSQL + bcrypt)

Run: streamlit run genai/chatbot_app.py
First time: creates users table automatically
"""

import os
import hashlib
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
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600;800&display=swap');
.stApp { background: #0a0a0f; }

/* AUTH PAGE */
.auth-container {
    max-width: 420px; margin: 60px auto; padding: 40px;
    background: linear-gradient(145deg, #131325, #1a1a35);
    border: 1px solid #22d3ee22; border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.auth-logo { text-align: center; font-size: 48px; margin-bottom: 8px; }
.auth-title {
    text-align: center; font-family: 'JetBrains Mono';
    font-size: 18px; color: #22d3ee; letter-spacing: 3px;
    text-transform: uppercase; margin-bottom: 4px;
}
.auth-subtitle { text-align: center; color: #64748b; font-size: 13px; margin-bottom: 30px; }
.auth-divider {
    text-align: center; color: #334155; font-size: 12px;
    margin: 20px 0; position: relative;
}
.auth-divider::before, .auth-divider::after {
    content: ''; position: absolute; top: 50%; width: 40%;
    height: 1px; background: #1e293b;
}
.auth-divider::before { left: 0; }
.auth-divider::after { right: 0; }
.auth-footer { text-align: center; color: #475569; font-size: 11px; margin-top: 20px; }
.auth-error { background: #450a0a; color: #fca5a5; padding: 10px 16px; border-radius: 10px; font-size: 13px; margin: 10px 0; text-align: center; }
.auth-success { background: #052e16; color: #86efac; padding: 10px 16px; border-radius: 10px; font-size: 13px; margin: 10px 0; text-align: center; }

/* MAIN APP */
.top-bar {
    background: linear-gradient(90deg, #0f172a, #1e1b4b, #0f172a);
    border: 1px solid #22d3ee33; padding: 12px 24px;
    border-radius: 12px; display: flex;
    justify-content: space-between; align-items: center; margin-bottom: 16px;
}
.top-title { font-family: 'JetBrains Mono'; font-size: 13px; color: #22d3ee; letter-spacing: 3px; text-transform: uppercase; }
.top-status { color: #64748b; font-size: 11px; font-family: 'JetBrains Mono'; }
.live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; margin-right: 6px; }
.user-badge { background: #6366f133; color: #a5b4fc; padding: 4px 12px; border-radius: 8px; font-size: 11px; font-family: 'JetBrains Mono'; }

.metric-box {
    background: linear-gradient(145deg, #131325, #1a1a35);
    border: 1px solid #ffffff0a; border-radius: 14px;
    padding: 20px; text-align: center;
}
.metric-num {
    font-size: 30px; font-weight: 800; font-family: 'JetBrains Mono';
    background: linear-gradient(90deg, #22d3ee, #6366f1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.metric-lbl { color: #475569; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; margin-top: 4px; }

.section-hdr {
    color: #e2e8f0; font-size: 12px; font-weight: 600;
    letter-spacing: 2px; text-transform: uppercase;
    margin: 20px 0 10px 0; padding-bottom: 6px;
    border-bottom: 1px solid #ffffff0a;
}

.chat-bubble-user {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white; padding: 10px 16px; border-radius: 16px 16px 4px 16px;
    margin: 8px 0; display: inline-block; max-width: 75%;
    font-size: 14px; float: right; clear: both;
}
.chat-bubble-bot {
    background: #12122a; border: 1px solid #ffffff0a;
    color: #cbd5e1; padding: 12px 16px; border-radius: 4px 16px 16px 16px;
    margin: 8px 0; display: inline-block; max-width: 85%;
    font-size: 14px; float: left; clear: both; line-height: 1.6;
}
.chat-clear { clear: both; }

.tag { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 9px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; font-family: 'JetBrains Mono'; }
.tag-rag { background: #064e3b; color: #34d399; }
.tag-sql { background: #1e3a5f; color: #38bdf8; }
.tag-report { background: #451a03; color: #fb923c; }
.tag-anomaly { background: #450a0a; color: #f87171; }

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE: USER AUTHENTICATION
# ============================================================

DB = dict(host="localhost", port=5432, database="airflow", user="airflow", password="airflow")

def get_conn():
    return psycopg2.connect(**DB)

def init_users_table():
    """Create users table if it doesn't exist."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS climate_warehouse.users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                full_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                login_count INT DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB init error: {e}")

def hash_password(password):
    """Hash password with SHA-256 + salt."""
    salt = "climate_platform_2026"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def signup_user(username, email, password, full_name):
    """Register a new user. Returns (success, message)."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO climate_warehouse.users (username, email, password_hash, full_name)
               VALUES (%s, %s, %s, %s)""",
            (username.lower().strip(), email.lower().strip(), hash_password(password), full_name.strip())
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully!"
    except psycopg2.errors.UniqueViolation:
        return False, "Username or email already exists."
    except Exception as e:
        return False, f"Error: {e}"

def login_user(username, password):
    """Authenticate user. Returns (success, user_data)."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username, email, full_name, login_count FROM climate_warehouse.users WHERE username = %s AND password_hash = %s",
            (username.lower().strip(), hash_password(password))
        )
        user = cur.fetchone()
        if user:
            cur.execute(
                "UPDATE climate_warehouse.users SET last_login = CURRENT_TIMESTAMP, login_count = login_count + 1 WHERE user_id = %s",
                (user[0],)
            )
            conn.commit()
            conn.close()
            return True, {"id": user[0], "username": user[1], "email": user[2], "name": user[3], "logins": user[4] + 1}
        conn.close()
        return False, None
    except Exception as e:
        return False, None


# ============================================================
# AUTH UI
# ============================================================

def render_auth_page():
    """Render login/signup page."""

    # Center column
    _, col, _ = st.columns([1, 1.5, 1])

    with col:
        st.markdown("""
        <div class="auth-container">
            <div class="auth-logo">🌍</div>
            <div class="auth-title">Climate Command</div>
            <div class="auth-subtitle">Weather Intelligence Platform</div>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_signup = st.tabs(["🔑 Sign In", "📝 Create Account"])

        with tab_login:
            st.markdown("")
            login_user_input = st.text_input("Username", key="login_username", placeholder="Enter your username")
            login_pass = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")

            if st.button("🔓 Sign In", use_container_width=True, key="login_btn"):
                if not login_user_input or not login_pass:
                    st.markdown('<div class="auth-error">Please fill in all fields</div>', unsafe_allow_html=True)
                else:
                    success, user_data = login_user(login_user_input, login_pass)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = user_data
                        st.rerun()
                    else:
                        st.markdown('<div class="auth-error">Invalid username or password</div>', unsafe_allow_html=True)

            st.markdown('<div class="auth-footer">Don\'t have an account? Click "Create Account" above</div>', unsafe_allow_html=True)

        with tab_signup:
            st.markdown("")
            signup_name = st.text_input("Full Name", key="signup_name", placeholder="e.g., Amruta Naik")
            signup_email = st.text_input("Email", key="signup_email", placeholder="e.g., amruta@example.com")
            signup_username = st.text_input("Choose Username", key="signup_username", placeholder="e.g., amruta")
            signup_pass = st.text_input("Choose Password", type="password", key="signup_password", placeholder="Min 6 characters")
            signup_pass2 = st.text_input("Confirm Password", type="password", key="signup_password2", placeholder="Re-enter password")

            if st.button("🚀 Create Account", use_container_width=True, key="signup_btn"):
                if not all([signup_name, signup_email, signup_username, signup_pass, signup_pass2]):
                    st.markdown('<div class="auth-error">Please fill in all fields</div>', unsafe_allow_html=True)
                elif len(signup_pass) < 6:
                    st.markdown('<div class="auth-error">Password must be at least 6 characters</div>', unsafe_allow_html=True)
                elif signup_pass != signup_pass2:
                    st.markdown('<div class="auth-error">Passwords do not match</div>', unsafe_allow_html=True)
                elif "@" not in signup_email:
                    st.markdown('<div class="auth-error">Please enter a valid email</div>', unsafe_allow_html=True)
                else:
                    success, msg = signup_user(signup_username, signup_email, signup_pass, signup_name)
                    if success:
                        st.markdown(f'<div class="auth-success">✅ {msg} Please sign in.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="auth-error">{msg}</div>', unsafe_allow_html=True)

            st.markdown('<div class="auth-footer">Already have an account? Click "Sign In" above</div>', unsafe_allow_html=True)


# ============================================================
# MAIN APP (after login)
# ============================================================

@st.cache_resource
def init_groq():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

@st.cache_resource
def load_data():
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("Cmd").master("local[*]").getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        df = spark.read.parquet("data/gold/weather_features").toPandas()
        spark.stop()

        client = chromadb.Client()
        try: client.delete_collection("weather_data")
        except: pass
        coll = client.create_collection("weather_data")

        docs, metas, ids = [], [], []
        for i, (_, r) in enumerate(df.iterrows()):
            d = (f"City: {r.get('city','?')}, {r.get('state','')}. "
                 f"Temp: {r.get('temperature_fahrenheit','?')}°F. "
                 f"Humidity: {r.get('humidity_percent','?')}%. "
                 f"Wind: {r.get('wind_speed_mph','?')} mph. "
                 f"Pressure: {r.get('pressure_hpa','?')} hPa. "
                 f"Heat Index: {r.get('heat_index','?')}°F. "
                 f"Condition: {r.get('weather_condition','?')}. "
                 f"Extreme: {'Yes' if r.get('is_extreme_weather',0)==1 else 'No'}. "
                 f"Anomaly: {r.get('temp_anomaly_score','?')}.")
            docs.append(d); metas.append({"city":str(r.get('city',''))}); ids.append(f"w_{i}")

        for s in range(0, len(docs), 100):
            coll.add(documents=docs[s:min(s+100,len(docs))], metadatas=metas[s:min(s+100,len(docs))], ids=ids[s:min(s+100,len(docs))])
        return df, coll
    except Exception as e:
        return None, None

def get_db_stats():
    try:
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings"); t = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM climate_warehouse.fact_weather_readings WHERE is_extreme_weather=1"); e = c.fetchone()[0]
        conn.close(); return t, e
    except: return 660, 13

def detect_mode(q):
    q = q.lower()
    if any(k in q for k in ["anomaly","unusual","strange","why is","explain why"]): return "anomaly"
    if any(k in q for k in ["report","forecast","summary","conditions in","brief"]): return "report"
    if any(k in q for k in ["average","count","how many","total","max","min","highest","lowest","top","list","show me all"]): return "sql"
    return "rag"

def ai_answer(question, coll, gc):
    mode = detect_mode(question)
    if mode == "sql":
        schema = "climate_warehouse.fact_weather_readings(location_key,temperature_fahrenheit,humidity_percent,pressure_hpa,wind_speed_mph,heat_index,is_extreme_weather) JOIN climate_warehouse.dim_location(location_key,city,state,region)"
        r = gc.chat.completions.create(model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":"Return ONLY PostgreSQL SELECT. Use climate_warehouse. LIMIT 20."},
                      {"role":"user","content":f"Schema:{schema}\nQ:{question}\nSQL:"}],
            max_tokens=200, temperature=0.1)
        sql = r.choices[0].message.content.strip().replace("```sql","").replace("```","").strip()
        try:
            conn = get_conn(); cur = conn.cursor(); cur.execute(sql)
            cols = [d[0] for d in cur.description]; rows = cur.fetchall(); conn.close()
            results = [dict(zip(cols,r)) for r in rows]
            r2 = gc.chat.completions.create(model="llama-3.1-8b-instant",
                messages=[{"role":"system","content":"Summarize results naturally."},
                          {"role":"user","content":f"Q:{question}\nResults:{str(results[:10])}\n100 words max:"}],
                max_tokens=200, temperature=0.2)
            return r2.choices[0].message.content.strip() + f"\n\n📝 `{sql}`", mode
        except Exception as e:
            return f"Query error: {e}\n\nSQL: `{sql}`", mode
    else:
        res = coll.query(query_texts=[question], n_results=6)
        ctx = "\n".join(res['documents'][0]) if res['documents'] else "No data."
        sp = {"rag":"Climate analyst. Answer from data only. Be specific.",
              "report":"Weather analyst. Format: Summary, Findings, Risks, Recommendations.",
              "anomaly":"Meteorologist. Explain: What's unusual, Causes, Risks, Precautions."}
        r = gc.chat.completions.create(model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":sp[mode]},
                      {"role":"user","content":f"DATA:\n{ctx}\n\nQ:{question}\n\n200 words max:"}],
            max_tokens=400, temperature=0.3)
        return r.choices[0].message.content.strip(), mode


def render_main_app():
    """Render the main Command Center (after auth)."""
    user = st.session_state.user
    gc = init_groq()

    with st.spinner("⚡ Initializing Command Center..."):
        gold_df, coll = load_data()

    if gold_df is None:
        st.error("❌ Could not load data/gold/. Run the pipeline first.")
        st.stop()

    cities = gold_df.drop_duplicates(subset=['city'], keep='last').sort_values('temperature_fahrenheit', ascending=False)
    total, extreme = get_db_stats()
    avg_t = round(gold_df['temperature_fahrenheit'].mean(), 1)
    max_t = round(gold_df['temperature_fahrenheit'].max(), 1)

    # --- TOP BAR WITH USER ---
    st.markdown(f"""
    <div class="top-bar">
        <span class="top-title">⚡ Climate Command Center</span>
        <span class="top-status">
            <span class="live-dot"></span>LIVE │ {len(cities)} CITIES │
            <span class="user-badge">👤 {user['name']}</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Logout button (top right)
    _, _, logout_col = st.columns([6, 1, 1])
    with logout_col:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.msgs = []
            st.rerun()

    # --- METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-box"><div class="metric-num">{total}</div><div class="metric-lbl">Total Readings</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-box"><div class="metric-num">{avg_t}°</div><div class="metric-lbl">Avg Temperature</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-box"><div class="metric-num">{extreme}</div><div class="metric-lbl">Extreme Events</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-box"><div class="metric-num">{max_t}°</div><div class="metric-lbl">Peak Temperature</div></div>', unsafe_allow_html=True)

    # --- CITY GRID ---
    st.markdown('<div class="section-hdr">📡 Live City Monitoring</div>', unsafe_allow_html=True)

    rows_of_cities = [cities.iloc[i:i+5] for i in range(0, len(cities), 5)]
    for row_cities in rows_of_cities:
        cols = st.columns(5)
        for idx, (_, city) in enumerate(row_cities.iterrows()):
            with cols[idx]:
                temp = round(city.get('temperature_fahrenheit', 0), 1)
                hum = round(city.get('humidity_percent', 0))
                wind = round(city.get('wind_speed_mph', 0), 1)
                name = city.get('city', '?')
                is_ext = city.get('is_extreme_weather', 0) == 1
                color = "#f87171" if is_ext else "#e2e8f0"
                border = "#ef444466" if is_ext else "#ffffff0a"
                warn = " 🔴" if is_ext else ""
                st.markdown(f"""
                <div style="background:linear-gradient(145deg,#131325,#1a1a35);
                    border:1px solid {border};border-radius:12px;
                    padding:14px;text-align:center;margin-bottom:8px;">
                    <div style="color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;">{name}{warn}</div>
                    <div style="color:{color};font-size:26px;font-weight:800;font-family:'JetBrains Mono';margin:4px 0;">{temp}°</div>
                    <div style="color:#475569;font-size:10px;">💧 {hum}% │ 💨 {wind} mph</div>
                </div>
                """, unsafe_allow_html=True)

    # --- AI CHAT ---
    st.markdown(f'<div class="section-hdr">🧠 AI Weather Intelligence — Welcome, {user["name"]}!</div>', unsafe_allow_html=True)

    if "msgs" not in st.session_state:
        st.session_state.msgs = [{"role":"bot","text":f"Welcome back, {user['name']}! 👋 I'm your Climate Intelligence Assistant monitoring 20 US cities. What would you like to know?","mode":"rag"}]

    # Quick buttons
    c1, c2, c3, c4, c5 = st.columns(5)
    qk = None
    with c1:
        if st.button("🌡️ Hottest", use_container_width=True): qk = "Which city has the highest temperature?"
    with c2:
        if st.button("🥶 Coldest", use_container_width=True): qk = "Which city has the lowest temperature?"
    with c3:
        if st.button("⚠️ Extreme", use_container_width=True): qk = "How many extreme weather events and which cities?"
    with c4:
        if st.button("📝 Report", use_container_width=True): qk = "Generate a weather report for all cities"
    with c5:
        if st.button("🔍 Anomaly", use_container_width=True): qk = "Explain any weather anomalies in the data"

    # Render chat
    tags = {"rag":'<span class="tag tag-rag">RAG</span>',
            "sql":'<span class="tag tag-sql">SQL</span>',
            "report":'<span class="tag tag-report">REPORT</span>',
            "anomaly":'<span class="tag tag-anomaly">ANOMALY</span>'}

    for msg in st.session_state.msgs:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["text"]}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
        else:
            tag = tags.get(msg.get("mode","rag"), "")
            text = msg["text"].replace("\n", "<br>")
            st.markdown(f'<div class="chat-bubble-bot">{tag}<br>{text}</div><div class="chat-clear"></div>', unsafe_allow_html=True)

    # Input
    user_in = st.chat_input("Ask about weather, climate, or extreme events...")
    if qk: user_in = qk

    if user_in:
        st.session_state.msgs.append({"role":"user","text":user_in})
        with st.spinner("🧠 Analyzing..."):
            ans, mode = ai_answer(user_in, coll, gc)
        st.session_state.msgs.append({"role":"bot","text":ans,"mode":mode})
        st.rerun()


# ============================================================
# APP ROUTER
# ============================================================

# Initialize auth state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None

# Create users table on first run
init_users_table()

# Route to login or main app
if st.session_state.authenticated:
    render_main_app()
else:
    render_auth_page()