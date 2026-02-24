"""
🌍 Climate Intelligence Dashboard
===================================
Full visual dashboard consuming the FastAPI backend.

Run (in a NEW terminal, keep API running):
  streamlit run dashboard/app.py

Requires: FastAPI running on http://localhost:8000
"""

import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Climate Intelligence", page_icon="🌍", layout="wide")

API_URL = "http://localhost:8000"

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@300;400;500;600;700;800&display=swap');

.stApp { background: #06060e; color: #e2e8f0; }
* { font-family: 'Inter', sans-serif; }

@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }
@keyframes glow { 0%,100% { box-shadow:0 0 8px #22d3ee33; } 50% { box-shadow:0 0 20px #22d3ee55; } }
@keyframes slideUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }

.top-bar {
    background: linear-gradient(90deg, #0c0c1d, #141432, #0c0c1d);
    border: 1px solid #22d3ee22; padding:16px 28px;
    border-radius:16px; display:flex;
    justify-content:space-between; align-items:center;
    margin-bottom:20px; animation: glow 4s ease-in-out infinite;
}
.top-title {
    font-family:'JetBrains Mono'; font-size:15px; font-weight:700;
    background: linear-gradient(90deg, #22d3ee, #818cf8);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    letter-spacing:4px; text-transform:uppercase;
}
.top-status { color:#64748b; font-size:11px; font-family:'JetBrains Mono'; }
.live-dot {
    display:inline-block; width:8px; height:8px; border-radius:50%;
    background:#22c55e; box-shadow:0 0 12px #22c55e;
    animation: pulse 2s ease-in-out infinite; margin-right:4px;
}
.status-chip {
    background:#6366f122; color:#a5b4fc; padding:5px 14px;
    border-radius:10px; font-size:11px; font-family:'JetBrains Mono';
    border:1px solid #6366f133;
}

.metric-card {
    background: linear-gradient(160deg, #0d0d1a, #141430);
    border:1px solid #ffffff08; border-radius:16px;
    padding:22px 16px; text-align:center;
    transition: all 0.3s ease; animation: slideUp 0.5s ease-out;
}
.metric-card:hover { border-color:#22d3ee33; transform:translateY(-2px); }
.metric-icon { font-size:24px; margin-bottom:6px; }
.metric-value {
    font-size:32px; font-weight:800; font-family:'JetBrains Mono';
    background: linear-gradient(135deg, #22d3ee, #818cf8);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.metric-label { color:#475569; font-size:10px; text-transform:uppercase; letter-spacing:2px; margin-top:4px; }

.section-hdr {
    color:#94a3b8; font-size:11px; font-weight:700;
    letter-spacing:3px; text-transform:uppercase;
    margin:28px 0 14px 0; padding-bottom:8px;
    border-bottom:1px solid #ffffff08;
}

.city-card {
    background: linear-gradient(160deg, #0d0d1a, #141430);
    border:1px solid #ffffff08; border-radius:14px;
    padding:16px; text-align:center; margin-bottom:10px;
    transition: all 0.3s ease;
}
.city-card:hover { border-color:#22d3ee22; }
.city-card.extreme { border-color:#ef444455; box-shadow:0 0 20px #ef444418; }
.city-name { color:#94a3b8; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:1.5px; }
.city-temp { font-size:28px; font-weight:800; font-family:'JetBrains Mono'; margin:6px 0 4px; }
.city-details { color:#475569; font-size:10px; font-family:'JetBrains Mono'; }

.risk-high { color:#ef4444; font-weight:700; }
.risk-moderate { color:#f59e0b; font-weight:700; }
.risk-low { color:#22c55e; font-weight:700; }

.chat-msg-user {
    background: linear-gradient(135deg, #6366f1, #7c3aed);
    color:white; padding:12px 18px; border-radius:18px 18px 6px 18px;
    margin:10px 0; display:inline-block; max-width:72%;
    font-size:14px; float:right; clear:both;
    box-shadow:0 4px 16px #6366f133;
}
.chat-msg-bot {
    background: linear-gradient(160deg, #0f0f24, #151535);
    border:1px solid #ffffff0a; color:#cbd5e1;
    padding:14px 18px; border-radius:6px 18px 18px 18px;
    margin:10px 0; display:inline-block; max-width:82%;
    font-size:14px; float:left; clear:both; line-height:1.7;
}
.chat-clear { clear:both; }

.tag {
    display:inline-block; padding:3px 10px; border-radius:8px;
    font-size:9px; font-weight:700; letter-spacing:1.5px;
    text-transform:uppercase; margin-bottom:8px; font-family:'JetBrains Mono';
}
.tag-rag { background:#064e3b; color:#34d399; }
.tag-sql { background:#1e3a5f; color:#38bdf8; }
.tag-report { background:#451a03; color:#fb923c; }
.tag-anomaly { background:#450a0a; color:#f87171; }

div.stButton > button {
    background: linear-gradient(160deg, #0d0d1a, #141430) !important;
    border:1px solid #ffffff10 !important; color:#94a3b8 !important;
    border-radius:12px !important; font-size:12px !important;
    font-weight:600 !important; transition: all 0.3s ease !important;
}
div.stButton > button:hover {
    border-color:#22d3ee44 !important; color:#22d3ee !important;
    box-shadow:0 0 16px #22d3ee18 !important;
}

#MainMenu, footer, header { visibility:hidden; }
.stDeployButton { display:none; }
div[data-testid="stStatusWidget"] { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# API HELPERS
# ============================================================

@st.cache_data(ttl=30)
def api_get(endpoint):
    """Call the FastAPI backend."""
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return None


def api_post_chat(question, mode="auto"):
    """Send a chat question to the API."""
    try:
        r = requests.post(f"{API_URL}/api/chat", json={"question": question, "mode": mode}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"answer": f"API error: {e}", "mode": "error"}


# ============================================================
# CHECK API CONNECTION
# ============================================================

health = api_get("/")
if health is None:
    st.error("❌ Cannot connect to FastAPI backend. Make sure it's running:\n\n`python api/main.py`")
    st.stop()


# ============================================================
# LOAD DATA FROM API
# ============================================================

stats = api_get("/api/stats")
cities_data = api_get("/api/cities")
predictions_data = api_get("/api/predictions")
regions_data = api_get("/api/regions")
extreme_data = api_get("/api/extreme")

now = datetime.now().strftime("%b %d, %Y • %I:%M %p")


# ============================================================
# TOP BAR
# ============================================================

st.markdown(f"""
<div class="top-bar">
    <span class="top-title">🌍 Climate Intelligence Dashboard</span>
    <span class="top-status">
        <span class="live-dot"></span> LIVE &nbsp;│&nbsp;
        {stats['total_cities']} CITIES &nbsp;│&nbsp;
        <span class="status-chip">🕐 {now}</span> &nbsp;
        <span class="status-chip">⚡ API Connected</span>
    </span>
</div>
""", unsafe_allow_html=True)


# ============================================================
# METRICS ROW
# ============================================================

m1, m2, m3, m4, m5 = st.columns(5)
metrics = [
    (m1, "📊", stats["total_readings"], "Total Readings"),
    (m2, "🌡️", f"{stats['avg_temperature']}°F", "Avg Temperature"),
    (m3, "🔥", f"{stats['max_temperature']}°F", "Peak Temp"),
    (m4, "🥶", f"{stats['min_temperature']}°F", "Lowest Temp"),
    (m5, "⚠️", stats["extreme_events"], "Extreme Events"),
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


# ============================================================
# TABS — Main Navigation
# ============================================================

tab_map, tab_cities, tab_predictions, tab_regions, tab_chat = st.tabs([
    "🗺️ Weather Map", "🏙️ City Monitor", "🤖 ML Predictions", "📊 Regional Analysis", "🧠 AI Chat"
])


# ── TAB 1: WEATHER MAP ──
with tab_map:
    st.markdown('<div class="section-hdr">🗺️ &nbsp;US Weather Map — All Monitored Cities</div>', unsafe_allow_html=True)

    cities = cities_data["cities"]
    map_df = pd.DataFrame(cities)

    # Add lat/lon from API weather endpoint for each city
    lat_lon = {
        "New York": (40.71, -74.01), "Los Angeles": (34.05, -118.24),
        "Chicago": (41.88, -87.63), "Houston": (29.76, -95.37),
        "Phoenix": (33.45, -112.07), "Miami": (25.76, -80.19),
        "Seattle": (47.61, -122.33), "Denver": (39.74, -104.99),
        "Atlanta": (33.75, -84.39), "Boston": (42.36, -71.06),
        "Dallas": (32.78, -96.80), "San Francisco": (37.77, -122.42),
        "Las Vegas": (36.17, -115.14), "Portland": (45.52, -122.68),
        "Minneapolis": (44.98, -93.27), "Detroit": (42.33, -83.05),
        "Nashville": (36.16, -86.78), "New Orleans": (29.95, -90.07),
        "Honolulu": (21.31, -157.86), "Anchorage": (61.22, -149.90),
    }

    map_df["lat"] = map_df["city"].map(lambda c: lat_lon.get(c, (0, 0))[0])
    map_df["lon"] = map_df["city"].map(lambda c: lat_lon.get(c, (0, 0))[1])

    # Plotly map
    fig_map = px.scatter_geo(
        map_df, lat="lat", lon="lon",
        color="temperature_f",
        size=map_df["temperature_f"].apply(lambda x: max(abs(x), 10)),
        hover_name="city",
        hover_data={"temperature_f": True, "humidity": True, "wind_speed": True,
                     "weather_condition": True, "is_extreme": True, "lat": False, "lon": False},
        color_continuous_scale="RdYlBu_r",
        scope="usa",
        title="",
        labels={"temperature_f": "Temp (°F)"},
    )
    fig_map.update_layout(
        geo=dict(bgcolor="#06060e", lakecolor="#0a0a1a", landcolor="#12122a",
                 subunitcolor="#1e1e3a", countrycolor="#1e1e3a"),
        paper_bgcolor="#06060e", plot_bgcolor="#06060e",
        font=dict(color="#94a3b8"),
        margin=dict(l=0, r=0, t=10, b=0),
        height=500,
        coloraxis_colorbar=dict(title="°F", tickfont=dict(color="#94a3b8")),
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # Temperature bar chart
    st.markdown('<div class="section-hdr">📊 &nbsp;Temperature Comparison</div>', unsafe_allow_html=True)
    bar_df = map_df.sort_values("temperature_f", ascending=True)

    fig_bar = go.Figure()
    colors = ["#ef4444" if row["is_extreme"] else "#22d3ee" for _, row in bar_df.iterrows()]
    fig_bar.add_trace(go.Bar(
        x=bar_df["temperature_f"], y=bar_df["city"],
        orientation="h", marker_color=colors,
        text=bar_df["temperature_f"].apply(lambda x: f"{x}°F"),
        textposition="outside", textfont=dict(color="#94a3b8", size=11),
    ))
    fig_bar.update_layout(
        paper_bgcolor="#06060e", plot_bgcolor="#0a0a16",
        font=dict(color="#94a3b8"), height=550,
        xaxis=dict(title="Temperature (°F)", gridcolor="#ffffff08"),
        yaxis=dict(gridcolor="#ffffff08"),
        margin=dict(l=0, r=60, t=10, b=40),
    )
    st.plotly_chart(fig_bar, use_container_width=True)


# ── TAB 2: CITY MONITOR ──
with tab_cities:
    st.markdown('<div class="section-hdr">📡 &nbsp;Live City Monitoring</div>', unsafe_allow_html=True)

    cities = cities_data["cities"]
    for i in range(0, len(cities), 5):
        cols = st.columns(5)
        for j, col in enumerate(cols):
            if i + j < len(cities):
                c = cities[i + j]
                ext = c["is_extreme"]
                cls = "extreme" if ext else ""
                tc = "#f87171" if ext else "#e2e8f0"
                badge = ' <span style="color:#ef4444;">⚠</span>' if ext else ""
                with col:
                    st.markdown(f"""
                    <div class="city-card {cls}">
                        <div class="city-name">{c['city']}{badge}</div>
                        <div class="city-temp" style="color:{tc};">{c['temperature_f']}°</div>
                        <div class="city-details">
                            💧{c['humidity']}% │ 💨{c['wind_speed']}mph │ {c['weather_condition']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # City detail selector
    st.markdown('<div class="section-hdr">🔍 &nbsp;City Deep Dive</div>', unsafe_allow_html=True)
    city_names = [c["city"] for c in cities]
    selected_city = st.selectbox("Select a city", city_names)

    if selected_city:
        detail = api_get(f"/api/weather/{selected_city}")
        if detail:
            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown("**🌡️ Temperature**")
                st.metric("Fahrenheit", f"{detail['temperature']['fahrenheit']}°F")
                st.metric("Celsius", f"{detail['temperature']['celsius']}°C")
                st.metric("Heat Index", f"{detail['temperature']['heat_index']}°F")
                st.metric("Wind Chill", f"{detail['temperature']['wind_chill']}°F")
            with d2:
                st.markdown("**🌤️ Conditions**")
                st.metric("Weather", detail['conditions']['weather'])
                st.metric("Humidity", f"{detail['conditions']['humidity_percent']}%")
                st.metric("Pressure", f"{detail['conditions']['pressure_hpa']} hPa")
                st.metric("Wind", f"{detail['conditions']['wind_speed_mph']} mph")
            with d3:
                st.markdown("**📊 Analysis**")
                st.metric("Extreme Weather", "🔴 YES" if detail['analysis']['is_extreme_weather'] else "🟢 No")
                st.metric("Anomaly Score", detail['analysis']['anomaly_score'])
                st.metric("Temp Anomaly", f"{detail['analysis']['temperature_anomaly']}°F")
                st.metric("City Avg", f"{detail['analysis']['city_avg_temp']}°F")

            # Forecast
            forecast = api_get(f"/api/forecast/{selected_city}")
            if forecast:
                st.markdown(f'<div class="section-hdr">📈 &nbsp;24-Hour Forecast — {selected_city}</div>', unsafe_allow_html=True)
                fc_df = pd.DataFrame(forecast["forecast_24h"])
                fig_fc = go.Figure()
                fig_fc.add_trace(go.Scatter(
                    x=fc_df["hour"], y=fc_df["predicted_temp_f"],
                    mode="lines+markers", name="Predicted Temp",
                    line=dict(color="#22d3ee", width=3),
                    marker=dict(size=6, color="#22d3ee"),
                    fill="tozeroy", fillcolor="rgba(34,211,238,0.1)",
                ))
                fig_fc.add_hline(y=forecast["current_temp_f"], line_dash="dash",
                                line_color="#818cf8", annotation_text=f"Current: {forecast['current_temp_f']}°F")
                fig_fc.update_layout(
                    paper_bgcolor="#06060e", plot_bgcolor="#0a0a16",
                    font=dict(color="#94a3b8"), height=350,
                    xaxis=dict(title="Hours Ahead", gridcolor="#ffffff08"),
                    yaxis=dict(title="Temperature (°F)", gridcolor="#ffffff08"),
                    margin=dict(l=0, r=0, t=10, b=40),
                )
                st.plotly_chart(fig_fc, use_container_width=True)


# ── TAB 3: ML PREDICTIONS ──
with tab_predictions:
    st.markdown('<div class="section-hdr">🤖 &nbsp;ML Extreme Weather Predictions</div>', unsafe_allow_html=True)

    preds = predictions_data["predictions"]
    summary = predictions_data["summary"]

    # Risk summary
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🔴</div>
            <div class="metric-value">{summary['high_risk']}</div>
            <div class="metric-label">High Risk Cities</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🟡</div>
            <div class="metric-value">{summary['moderate_risk']}</div>
            <div class="metric-label">Moderate Risk</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon">🟢</div>
            <div class="metric-value">{summary['low_risk']}</div>
            <div class="metric-label">Low Risk</div>
        </div>
        """, unsafe_allow_html=True)

    # Predictions table
    st.markdown('<div class="section-hdr">📋 &nbsp;City Risk Assessment</div>', unsafe_allow_html=True)
    pred_df = pd.DataFrame(preds)
    pred_df["Risk"] = pred_df["risk_level"]
    display_df = pred_df[["city", "temperature_f", "humidity", "wind_speed", "heat_index", "anomaly_score", "Risk"]].copy()
    display_df.columns = ["City", "Temp (°F)", "Humidity %", "Wind (mph)", "Heat Index", "Anomaly", "Risk Level"]
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)

    # Anomaly scatter
    st.markdown('<div class="section-hdr">📊 &nbsp;Temperature vs Anomaly Score</div>', unsafe_allow_html=True)
    fig_scatter = px.scatter(
        pred_df, x="temperature_f", y="anomaly_score",
        size="wind_speed", color="risk_level",
        hover_name="city",
        color_discrete_map={"🔴 HIGH": "#ef4444", "🟡 MODERATE": "#f59e0b", "🟢 LOW": "#22c55e"},
        labels={"temperature_f": "Temperature (°F)", "anomaly_score": "Anomaly Score"},
    )
    fig_scatter.update_layout(
        paper_bgcolor="#06060e", plot_bgcolor="#0a0a16",
        font=dict(color="#94a3b8"), height=400,
        xaxis=dict(gridcolor="#ffffff08"), yaxis=dict(gridcolor="#ffffff08"),
        margin=dict(l=0, r=0, t=10, b=40),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Extreme events detail
    if extreme_data and extreme_data["count"] > 0:
        st.markdown('<div class="section-hdr">🚨 &nbsp;Active Extreme Weather Alerts</div>', unsafe_allow_html=True)
        for event in extreme_data["extreme_events"]:
            reasons = ", ".join(event["reasons"]) if event["reasons"] else "Multiple factors"
            st.warning(f"**{event['city']}, {event['state']}** — {event['temperature_f']}°F | Anomaly: {event['anomaly_score']} | {reasons}")


# ── TAB 4: REGIONAL ANALYSIS ──
with tab_regions:
    st.markdown('<div class="section-hdr">📊 &nbsp;Weather by US Region</div>', unsafe_allow_html=True)

    if regions_data:
        regions = regions_data["regions"]
        region_list = []
        for name, data in regions.items():
            region_list.append({
                "Region": name,
                "Avg Temp": data["avg_temp"],
                "Max Temp": data["max_temp"],
                "Min Temp": data["min_temp"],
                "Avg Humidity": data["avg_humidity"],
                "Avg Wind": data["avg_wind"],
                "Cities": data["city_count"],
                "Extreme": data["extreme_count"],
            })
        region_df = pd.DataFrame(region_list).sort_values("Avg Temp", ascending=False)

        # Region temperature chart
        fig_region = go.Figure()
        fig_region.add_trace(go.Bar(
            x=region_df["Region"], y=region_df["Avg Temp"],
            name="Avg Temp", marker_color="#22d3ee",
            text=region_df["Avg Temp"].apply(lambda x: f"{x}°F"),
            textposition="outside", textfont=dict(color="#94a3b8"),
        ))
        fig_region.add_trace(go.Bar(
            x=region_df["Region"], y=region_df["Max Temp"],
            name="Max Temp", marker_color="#ef4444", opacity=0.5,
        ))
        fig_region.add_trace(go.Bar(
            x=region_df["Region"], y=region_df["Min Temp"],
            name="Min Temp", marker_color="#38bdf8", opacity=0.5,
        ))
        fig_region.update_layout(
            barmode="group",
            paper_bgcolor="#06060e", plot_bgcolor="#0a0a16",
            font=dict(color="#94a3b8"), height=400,
            xaxis=dict(gridcolor="#ffffff08"), yaxis=dict(title="Temperature (°F)", gridcolor="#ffffff08"),
            legend=dict(font=dict(color="#94a3b8")),
            margin=dict(l=0, r=0, t=10, b=40),
        )
        st.plotly_chart(fig_region, use_container_width=True)

        # Region table
        st.markdown('<div class="section-hdr">📋 &nbsp;Regional Summary</div>', unsafe_allow_html=True)
        st.dataframe(region_df, use_container_width=True, hide_index=True)

        # Humidity vs Wind by region
        st.markdown('<div class="section-hdr">💧 &nbsp;Humidity vs Wind Speed by Region</div>', unsafe_allow_html=True)
        fig_hw = px.scatter(
            region_df, x="Avg Humidity", y="Avg Wind", size="Cities",
            color="Region", text="Region",
            labels={"Avg Humidity": "Avg Humidity (%)", "Avg Wind": "Avg Wind (mph)"},
        )
        fig_hw.update_layout(
            paper_bgcolor="#06060e", plot_bgcolor="#0a0a16",
            font=dict(color="#94a3b8"), height=400,
            xaxis=dict(gridcolor="#ffffff08"), yaxis=dict(gridcolor="#ffffff08"),
            margin=dict(l=0, r=0, t=10, b=40),
        )
        st.plotly_chart(fig_hw, use_container_width=True)


# ── TAB 5: AI CHAT ──
with tab_chat:
    st.markdown('<div class="section-hdr">🧠 &nbsp;AI Weather Intelligence</div>', unsafe_allow_html=True)

    if "msgs" not in st.session_state:
        st.session_state.msgs = [{
            "role": "bot",
            "text": "Welcome! 👋 I'm connected to the Climate Intelligence API monitoring 20 US cities.\n\n"
                    "I support 4 modes:\n"
                    "• **RAG** — Ask anything about weather data\n"
                    "• **SQL** — Quantitative queries\n"
                    "• **Report** — Structured reports\n"
                    "• **Anomaly** — Unusual pattern analysis\n\n"
                    "Try the quick buttons or type your question!",
            "mode": "rag"
        }]

    # Quick buttons
    c1, c2, c3, c4, c5 = st.columns(5)
    qk = None
    with c1:
        if st.button("🔥 Hottest", use_container_width=True): qk = "Which city has the highest temperature?"
    with c2:
        if st.button("🥶 Coldest", use_container_width=True): qk = "Which city has the lowest temperature?"
    with c3:
        if st.button("⚠️ Extreme", use_container_width=True): qk = "How many extreme weather events?"
    with c4:
        if st.button("📋 Report", use_container_width=True): qk = "Generate a weather report for all cities"
    with c5:
        if st.button("🔍 Anomalies", use_container_width=True): qk = "Explain any weather anomalies"

    # Tags
    tag_html = {
        "rag": '<span class="tag tag-rag">RAG</span>',
        "sql": '<span class="tag tag-sql">SQL</span>',
        "report": '<span class="tag tag-report">REPORT</span>',
        "anomaly": '<span class="tag tag-anomaly">ANOMALY</span>',
    }

    # Render messages
    for msg in st.session_state.msgs:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-msg-user">{msg["text"]}</div><div class="chat-clear"></div>', unsafe_allow_html=True)
        else:
            tag = tag_html.get(msg.get("mode", "rag"), "")
            text = msg["text"].replace("\n", "<br>")
            st.markdown(f'<div class="chat-msg-bot">{tag}<br>{text}</div><div class="chat-clear"></div>', unsafe_allow_html=True)

    # Input
    user_in = st.chat_input("Ask about weather, climate, or extreme events...")
    if qk: user_in = qk

    if user_in:
        st.session_state.msgs.append({"role": "user", "text": user_in})
        with st.spinner("🧠 Analyzing..."):
            response = api_post_chat(user_in)
        st.session_state.msgs.append({
            "role": "bot",
            "text": response.get("answer", "No response"),
            "mode": response.get("mode", "rag")
        })
        st.rerun()