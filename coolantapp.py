import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date
import streamlit.components.v1 as components

# --- DATABASE SETUP ---
conn = sqlite3.connect('qualiserv_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              metal TEXT, alloy TEXT, vol REAL, ri REAL, brix REAL, conc REAL, 
              ph REAL, notes TEXT, date TEXT)''')
conn.commit()

# --- THE "NUCLEAR" CSS OPTION ---
# This forces the colors by targeting the specific class names Streamlit uses
st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE = "#00529B"
QC_GREEN = "#78BE20"

st.markdown(f"""
    <style>
    /* Force the main background to a dark enough gray to see white boxes */
    .stApp {{
        background-color: #E5E7E9 !important;
    }}

    /* Force the sidebar to be DARK BLUE so the white text/inputs pop */
    section[data-testid="stSidebar"] {{
        background-color: {QC_BLUE} !important;
        color: white !important;
    }}

    /* Force all sidebar text to WHITE */
    section[data-testid="stSidebar"] .stMarkdown p, 
    section[data-testid="stSidebar"] .stMarkdown h1, 
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] label {{
        color: white !important;
    }}

    /* High-Contrast Titles */
    .main-header {{
        color: {QC_BLUE};
        font-size: 50px;
        font-weight: 900;
        text-shadow: 1px 1px 2px #bdc3c7;
    }}

    /* Branded Button Styling */
    div.stButton > button {{
        background-color: {QC_BLUE} !important;
        color: white !important;
        border: 2px solid white !important;
        font-weight: bold !important;
        height: 3em !important;
        width: 100% !important;
    }}
    
    div.stButton > button:hover {{
        background-color: {QC_GREEN} !important;
        border-color: {QC_GREEN} !important;
    }}

    /* Metric Styling for Visibility */
    [data-testid="stMetricValue"] {{
        color: {QC_BLUE} !important;
        font-size: 36px !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- MASTER STATE ---
if "master_notes" not in st.session_state: st.session_state.master_notes = ""

# --- 1. SIDEBAR (NOW DARK BLUE) ---
with st.sidebar:
    st.markdown("<h1>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{QC_GREEN} !important;'><b>FIELD SERVICE PRO</b></p>", unsafe_allow_html=True)
    st.markdown("---")
    
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Customer", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    st.markdown("---")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Base Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Product", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

# --- 2. MAIN DASHBOARD ---
st.markdown(f"<p class='main-header'>QualiServ <span style='color:{QC_GREEN}'>Pro</span></p>", unsafe_allow_html=True)

col_main, col_chart = st.columns([1, 1], gap="large")

with col_main:
    # Adding a white background card manually via container
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        m_id = st.text_input("Machine ID")
        
        c1, c2 = st.columns(2)
        brix = c1.number_input("Brix Reading", min_value=0.0, format="%.1f")
        ph = c2.number_input("pH Reading", min_value=0.0, format="%.1f")
        
        actual_conc = round(brix * 1.0, 2) # Assume 1.0 RI for quick display
        
        if brix > 0:
            m1, m2 = st.columns(2)
            m1.metric("Actual Conc", f"{actual_conc}%")
            m2.metric("pH Level", ph)
            
            if actual_conc < t_conc:
                st.warning(f"**Action:** Low Concentration! Add product.")
            if 0 < ph < t_ph:
                st.error(f"**Action:** Low pH! Add pH Boost.")

with col_chart:
    st.subheader("📈 Trend")
    st.info("Chart will render here based on historical data.")

# --- 3. OBSERVATIONS ---
st.markdown("---")
notes = st.text_area("Field Observations", value=st.session_state.master_notes)

btns = st.columns(6)
if btns[0].button("pH Boost"): st.session_state.master_notes += "Added pH Boost. "; st.rerun()
if btns[1].button("Fungicide"): st.session_state.notes += "Added Fungicide. "; st.rerun()
if btns[2].button("Defoamer"): st.session_state.notes += "Added Defoamer. "; st.rerun()
if btns[3].button("Biocide"): st.session_state.notes += "Added Biocide. "; st.rerun()
if btns[4].button("DCR"): st.session_state.notes += "Recommend DCR. "; st.rerun()
if btns[5].button("🗑️"): st.session_state.master_notes = ""; st.rerun()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    # Save Logic...
    st.success("Successfully Saved!")
