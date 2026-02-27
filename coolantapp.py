import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect('qualiserv_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              vol REAL, ri REAL, brix REAL, conc REAL, ph REAL, notes TEXT, date TEXT)''')
conn.commit()

# --- 2. FORCED DARK THEME CSS ---
st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE = "#00529B"
QC_DARK_BLUE = "#002D54"
QC_GREEN = "#78BE20"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {QC_DARK_BLUE} !important; color: white !important; }}
    section[data-testid="stSidebar"] {{ background-color: {QC_BLUE} !important; border-right: 2px solid {QC_GREEN} !important; }}
    h1, h2, h3, p, span, label, .stMarkdown {{ color: white !important; }}
    .green-text {{ color: {QC_GREEN} !important; font-weight: bold; }}
    input, div[data-baseweb="select"], div[data-baseweb="input"] {{ background-color: #ffffff !important; color: #000000 !important; border-radius: 5px !important; }}
    div.stButton > button {{ background-color: {QC_GREEN} !important; color: {QC_DARK_BLUE} !important; font-weight: bold !important; border: none !important; width: 100% !important; }}
    [data-testid="stMetricValue"] {{ color: {QC_GREEN} !important; font-size: 32px !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. UPDATED LOGIC (The Fix for the API Exception) ---
if "master_notes" not in st.session_state: 
    st.session_state.master_notes = ""

def sync_from_widget():
    """Sync manual typing to master memory."""
    if "notes_widget" in st.session_state:
        st.session_state.master_notes = st.session_state.notes_widget

def add_quick_note(text):
    """Update master memory and rerun to refresh the widget."""
    st.session_state.master_notes += f"{text}. "
    st.rerun()

def clear_notes():
    st.session_state.master_notes = ""
    st.rerun()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1 style='text-align: center;'>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown("---")
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Active Shop", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Base Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Base Product", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

# --- 5. MAIN DASHBOARD ---
st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)
col_main, col_chart = st.columns([1, 1], gap="large")

with col_main:
    st.markdown(f"### <span class='green-text'>Machine Entry</span>")
    log_date = st.date_input("Date", value=date.today())
    m_id = st.text_input("Machine ID")
    
    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Vol", value=100.0)
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

# --- 6. OBSERVATIONS (The Corrected Widget) ---
st.markdown("---")
# The 'value' is tied to master_notes, 'on_change' handles manual typing
st.text_area("Observations", 
             value=st.session_state.master_notes, 
             key="notes_widget", 
             on_change=sync_from_widget, 
             height=120)

btns = st.columns(6)
if btns[0].button("pH Boost"): add_quick_note("Added pH Boost")
if btns[1].button("Fungicide"): add_quick_note("Added Fungicide")
if btns[2].button("Defoamer"): add_quick_note("Added Defoamer")
if btns[3].button("Biocide"): add_quick_note("Added Biocide")
if btns[4].button("DCR"): add_quick_note("Recommend DCR")
if btns[5].button("🗑️ CLEAR"): clear_notes()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, shop_cool_name, m_id, vol, ri, brix, actual_conc, ph, st.session_state.master_notes, str(log_date)))
        conn.commit()
        st.session_state.master_notes = ""
        st.success("Saved!")
        st.rerun()
