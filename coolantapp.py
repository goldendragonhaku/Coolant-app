import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- 1. DATABASE & THEME ---
conn = sqlite3.connect('qualiserv_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              vol REAL, ri REAL, brix REAL, conc REAL, ph REAL, notes TEXT, date TEXT)''')
conn.commit()

st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE, QC_DARK_BLUE, QC_GREEN = "#00529B", "#002D54", "#78BE20"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {QC_DARK_BLUE} !important; color: white !important; }}
    section[data-testid="stSidebar"] {{ background-color: {QC_BLUE} !important; border-right: 2px solid {QC_GREEN} !important; }}
    h1, h2, h3, p, span, label, .stMarkdown {{ color: white !important; }}
    .green-text {{ color: {QC_GREEN} !important; font-weight: bold; }}
    input, div[data-baseweb="select"], div[data-baseweb="input"], textarea {{ background-color: #ffffff !important; color: #000000 !important; border-radius: 5px !important; }}
    div.stButton > button {{ background-color: {QC_GREEN} !important; color: {QC_DARK_BLUE} !important; font-weight: bold !important; border: none !important; width: 100% !important; }}
    [data-testid="stMetricValue"] {{ color: {QC_GREEN} !important; font-size: 32px !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. THE NOTES ENGINE ---
if "notes_content" not in st.session_state:
    st.session_state.notes_content = ""

def add_note_fragment(fragment):
    # Capture what is currently in the box before adding the fragment
    if "temp_notes_box" in st.session_state:
        st.session_state.notes_content = st.session_state.temp_notes_box
    st.session_state.notes_content += f"{fragment}. "
    st.rerun()

# --- 3. SIDEBAR & INPUTS ---
with st.sidebar:
    st.markdown(f"<h1>QualiServ</h1>", unsafe_allow_html=True)
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    shops = [r[0] for r in c.fetchall() if r[0]]
    shop_choice = st.selectbox("Shop", ["+ New"] + shops)
    customer = st.text_input("Customer", value="" if shop_choice == "+ New" else shop_choice)
    
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)
col_in, col_gr = st.columns([1, 1], gap="large")

with col_in:
    st.markdown("### <span class='green-text'>Machine Data</span>", unsafe_allow_html=True)
    m_id = st.text_input("Machine ID")
    
    # Simple direct logic for brix/ph
    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Volume", value=100.0)
    ri = c2.number_input("RI Factor", value=1.0)
    
    c3, c4 = st.columns(2)
    brix = c3.number_input("Brix", min_value=0.0)
    ph = c4.number_input("pH", min_value=0.0)
    
    actual_conc = round(brix * ri, 2)
    if brix > 0:
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
        m2.metric("pH", ph, delta=round(ph - t_ph, 2))

# --- 4. THE NOTES SECTION (FIXED) ---
st.markdown("---")
st.markdown("### <span class='green-text'>Observations</span>", unsafe_allow_html=True)

# We use 'value' to show the state, but 'key' allows us to capture what's being typed
current_notes = st.text_area("Notes", value=st.session_state.notes_content, key="temp_notes_box", height=150)

# Quick Add Buttons
q1, q2, q3, q4, q5, q6 = st.columns(6)
if q1.button("pH Boost"): add_note_fragment("Added pH Boost")
if q2.button("Fungicide"): add_note_fragment("Added Fungicide")
if q3.button("Defoamer"): add_note_fragment("Added Defoamer")
if q4.button("Biocide"): add_note_fragment("Added Biocide")
if q5.button("DCR"): add_note_fragment("Recommend DCR")
if q6.button("🗑️"): 
    st.session_state.notes_content = ""
    st.rerun()

# --- 5. SAVE ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    # Ensure we capture the latest typed text even if no button was clicked
    final_notes = st.session_state.temp_notes_box
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?)",
                  (customer, m_id, vol, ri, brix, actual_conc, ph, final_notes, str(date.today())))
        conn.commit()
        st.session_state.notes_content = "" # Reset
        st.success("Successfully Logged.")
        st.rerun()
