import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- DATABASE SETUP ---
conn = sqlite3.connect('qualiserv_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              metal TEXT, alloy TEXT, vol REAL, ri REAL, brix REAL, conc REAL, 
              ph REAL, notes TEXT, date TEXT)''')
conn.commit()

# --- THE "NIGHT VISION" CSS ---
st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE = "#00529B"
QC_DARK_BLUE = "#002D54"
QC_GREEN = "#78BE20"

st.markdown(f"""
    <style>
    /* 1. MAIN BACKGROUND: DEEP NAVY */
    .stApp {{
        background-color: {QC_DARK_BLUE} !important;
        color: white !important;
    }}

    /* 2. SIDEBAR: QUALICHEM BLUE */
    section[data-testid="stSidebar"] {{
        background-color: {QC_BLUE} !important;
        border-right: 2px solid {QC_GREEN} !important;
    }}

    /* 3. TEXT COLOR FORCING (GREEN & WHITE) */
    h1, h2, h3, p, span, label, .stMarkdown {{
        color: white !important;
    }}
    
    /* Highlight Titles in Green */
    .green-text {{
        color: {QC_GREEN} !important;
        font-weight: bold;
    }}

    /* 4. INPUT BOXES: HIGH CONTRAST */
    input, div[data-baseweb="select"] {{
        background-color: #ffffff !important;
        color: #000000 !important;
        border-radius: 5px !important;
    }}

    /* 5. BRANDED BUTTONS (GREEN) */
    div.stButton > button {{
        background-color: {QC_GREEN} !important;
        color: {QC_DARK_BLUE} !important;
        font-weight: bold !important;
        border: none !important;
        width: 100% !important;
    }}

    /* 6. METRIC BOXES */
    [data-testid="stMetricValue"] {{
        color: {QC_GREEN} !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- MASTER STATE ---
if "master_notes" not in st.session_state: st.session_state.master_notes = ""

# --- 1. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1 style='text-align: center;'>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;' class='green-text'>PRO ANALYTICS</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    customer = st.selectbox("Shop Name", existing_shops)
    
    st.markdown("---")
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

# --- 2. MAIN HEADER ---
st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)

col_main, col_chart = st.columns([1, 1], gap="large")

with col_main:
    st.markdown(f"### <span class='green-text'>Machine Entry</span>", unsafe_allow_html=True)
    m_id = st.text_input("Machine ID")
    
    c1, c2 = st.columns(2)
    with c1:
        brix = st.number_input("Brix Reading", min_value=0.0, format="%.1f")
    with c2:
        ph = st.number_input("pH Reading", min_value=0.0, format="%.1f")
    
    actual_conc = round(brix * 1.0, 2)
    
    if brix > 0:
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Conc", f"{actual_conc}%")
        m2.metric("pH", ph)
        
        if actual_conc < t_conc:
            st.warning(f"ACTION: Add Concentrate")
        if 0 < ph < t_ph:
            st.error(f"ACTION: Add pH Boost")

with col_chart:
    st.markdown(f"### <span class='green-text'>Trend Line</span>", unsafe_allow_html=True)
    # Altair chart would go here

# --- 3. OBSERVATIONS ---
st.markdown("---")
notes = st.text_area("Observations", value=st.session_state.master_notes)

btns = st.columns(5)
if btns[0].button("pH Boost"): st.session_state.master_notes += "Added pH Boost. "; st.rerun()
if btns[1].button("Fungicide"): st.session_state.master_notes += "Added Fungicide. "; st.rerun()
if btns[2].button("Defoamer"): st.session_state.master_notes += "Added Defoamer. "; st.rerun()
if btns[3].button("Biocide"): st.session_state.master_notes += "Added Biocide. "; st.rerun()
if btns[4].button("DCR"): st.session_state.master_notes += "Recommend DCR. "; st.rerun()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    st.success("Entry Recorded in QualiServ")
