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

# --- THE "FORCE" CSS ---
st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE = "#00529B"
QC_GREEN = "#78BE20"
SOFT_GRAY = "#F0F2F6"

st.markdown(f"""
    <style>
    /* 1. FORCE MAIN BACKGROUND */
    .stApp {{
        background-color: {SOFT_GRAY} !important;
    }}

    /* 2. FORCE SIDEBAR THEME */
    section[data-testid="stSidebar"] {{
        background-color: white !important;
        border-right: 6px solid {QC_BLUE} !important;
    }}
    
    /* 3. FORCE SIDEBAR TEXT COLORS */
    section[data-testid="stSidebar"] .stMarkdown h1, 
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown p {{
        color: {QC_BLUE} !important;
    }}

    /* 4. BRANDED TITLES */
    .main-title {{ 
        color: {QC_BLUE} !important; 
        font-weight: 800; 
        font-size: 50px; 
        margin-bottom: -10px; 
    }}

    /* 5. BRANDED BUTTONS */
    div.stButton > button:first-child {{
        background-color: {QC_BLUE} !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        font-weight: bold !important;
    }}
    div.stButton > button:first-child:hover {{
        background-color: {QC_GREEN} !important;
        transition: 0.3s !important;
    }}

    /* 6. METRIC COLORS */
    [data-testid="stMetricValue"] {{
        color: {QC_BLUE} !important;
        font-weight: bold !important;
    }}
    
    /* 7. CARD EFFECT FOR INPUT BLOCKS */
    div[data-testid="stVerticalBlock"] > div {{
        background-color: transparent;
    }}
    </style>
""", unsafe_allow_html=True)

# --- MASTER STATE ---
if "master_notes" not in st.session_state: st.session_state.master_notes = ""
def update_master_from_box(): st.session_state.master_notes = st.session_state.notes_widget
def add_quick_note(text): 
    st.session_state.master_notes += f"{text}. "
    if "notes_widget" in st.session_state:
        st.session_state.notes_widget = st.session_state.master_notes
def clear_notes(): 
    st.session_state.master_notes = ""
    if "notes_widget" in st.session_state: st.session_state.notes_widget = ""

# --- 1. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-weight:bold; color:{QC_GREEN} !important;'>FIELD ANALYTICS</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Active Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Customer Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Base Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Product Name", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

# --- 2. MAIN HEADER ---
st.markdown(f"<p class='main-title'>QualiServ <span style='color:{QC_GREEN}'>Pro</span></p>", unsafe_allow_html=True)

col_main, col_chart = st.columns([1, 1], gap="medium")

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Data")
        log_date = st.date_input("Service Date", value=date.today())
        
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_id = st.text_input("Machine ID", value="") # Changed to text for speed

        c1, c2 = st.columns(2)
        brix = c1.number_input("Brix Reading", min_value=0.0, step=0.1)
        ph = c2.number_input("pH Reading", min_value=0.0, step=0.1)
        
        ri = st.number_input("RI Factor", value=1.0)
        vol = st.number_input("Sump Volume", value=100.0)

        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown(f"### <span style='color:{QC_BLUE}'>Recommendations</span>", unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            r1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
            r2.metric("pH", ph, delta=round(ph - t_ph, 2))
            
            if actual_conc < t_conc:
                st.warning(f"**Add {round(((t_conc - actual_conc)/100)*vol, 2)} Gal** Concentrate")
            if 0 < ph < t_ph:
                st.error(f"**Add {round((vol/100)*16, 1)} oz** pH Boost 95")

with col_chart:
    st.subheader("📈 Trend")
    # Placeholder for trend logic

# --- 3. OBSERVATIONS ---
st.markdown("---")
st.text_area("Field Observations", value=st.session_state.master_notes, key="notes_widget", on_change=update_master_from_box)

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
        st.success("Log Saved.")
        clear_notes(); st.rerun()
