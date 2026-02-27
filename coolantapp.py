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

# --- 2. THEMED CSS (FORCED CONTRAST) ---
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
    [data-testid="stTable"] {{ background-color: white !important; color: black !important; border-radius: 10px; overflow: hidden; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE FOR NOTES ---
if "master_notes" not in st.session_state: 
    st.session_state.master_notes = ""

def sync_notes():
    """Captures manual typing into master memory"""
    if "notes_widget" in st.session_state:
        st.session_state.master_notes = st.session_state.notes_widget

def add_quick_note(text):
    """Appends button text to master memory and triggers refresh"""
    st.session_state.master_notes += f"{text}. "
    st.rerun()

def clear_notes():
    st.session_state.master_notes = ""
    st.rerun()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1 style='text-align: center;'>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Shop Dropdown
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Active Shop", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    # Global Coolant History
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Base Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Base Product", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH", value=8.8, step=0.1)

# --- 5. MAIN DASHBOARD ---
st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)
col_main, col_chart = st.columns([1, 1], gap="large")

with col_main:
    st.markdown(f"### <span class='green-text'>Machine Data Entry</span>", unsafe_allow_html=True)
    log_date = st.date_input("Service Date", value=date.today())
    
    # Machine Dropdown
    c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
    existing_machines = [row[0] for row in c.fetchall() if row[0]]
    m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
    m_id = st.text_input("Machine ID Entry", value="" if m_choice == "+ New Machine" else m_choice)

    # --- RESTORED: MULTI-COOLANT TOGGLE ---
    multi_coolant = st.toggle("Machine-specific coolant?")
    if multi_coolant:
        m_cool_choice = st.selectbox("Machine Coolant", ["+ New"] + all_coolants)
        active_coolant = st.text_input("Override Product", value="" if m_cool_choice == "+ New" else m_cool_choice)
    else:
        active_coolant = shop_cool_name

    # Historical Recall
    last_vol, last_ri = 100.0, 1.0
    if m_choice != "+ New Machine":
        c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
        last_rec = c.fetchone()
        if last_rec: last_vol, last_ri = last_rec[0], last_rec[1]

    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Volume", value=last_vol)
    ri = c2.number_input("RI Factor", value=last_ri)
    
    c3, c4 = st.columns(2)
    brix = c3.number_input("Brix Reading", min_value=0.0, format="%.1f")
    ph = c4.number_input("pH Reading", min_value=0.0, format="%.1f")

    actual_conc = round(brix * ri, 2)
    if brix > 0:
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
        m2.metric("pH", ph, delta=round(ph - t_ph, 2))
        
        if actual_conc < t_conc:
            st.warning(f"💡 Add **{round(((t_conc - actual_conc)/100)*vol, 2)} Gal** Concentrate")
        if 0 < ph < t_ph:
            st.error(f"🚨 Add **{round((vol/100)*16, 1)} oz** pH Boost 95")

with col_chart:
    st.subheader("📈 Historical Trend")
    if m_id and customer:
        hist_df = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not hist_df.empty:
            hist_df['date'] = pd.to_datetime(hist_df['date'])
            chart = alt.Chart(hist_df).mark_line(color=QC_GREEN, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 6. OBSERVATIONS (FIXED SYNC) ---
st.markdown("---")
st.text_area("Observations", value=st.session_state.master_notes, key="notes_widget", on_change=sync_notes, height=120)

btns = st.columns(6)
if btns[0].button("pH Boost"): add_quick_note("Added pH Boost")
if btns[1].button("Fungicide"): add_quick_note("Added Fungicide")
if btns[2].button("Defoamer"): add_quick_note("Added Defoamer")
if btns[3].button("Biocide"): add_quick_note("Added Biocide")
if btns[4].button("DCR"): add_quick_note("Recommend DCR")
if btns[5].button("🗑️"): clear_notes()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.master_notes, str(log_date)))
        conn.commit()
        st.session_state.master_notes = ""
        st.success(f"Saved {m_id}!")
        st.rerun()
