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

# --- 2. THE NOTES ENGINE (THE FIX) ---
if "master_notes" not in st.session_state:
    st.session_state.master_notes = ""

def handle_quick_note(text_to_add):
    # 1. Capture what is CURRENTLY typed in the box before it reruns
    if "notes_widget" in st.session_state:
        st.session_state.master_notes = st.session_state.notes_widget
    
    # 2. Append the new note
    st.session_state.master_notes += f"{text_to_add}. "
    
    # 3. MANUALLY update the widget's internal state so it shows up instantly
    st.session_state.notes_widget = st.session_state.master_notes

def clear_notes():
    st.session_state.master_notes = ""
    st.session_state.notes_widget = ""

# --- 3. SIDEBAR (Full Logic Restored) ---
with st.sidebar:
    st.markdown(f"<h1>QualiServ</h1>", unsafe_allow_html=True)
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    shops = [r[0] for r in c.fetchall() if r[0]]
    shop_choice = st.selectbox("Shop", ["+ New Shop"] + shops)
    customer = st.text_input("Active Customer", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    st.markdown("---")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    coolants = [r[0] for r in c.fetchall() if r[0]]
    cool_choice = st.selectbox("Shop Product", ["+ New"] + coolants)
    shop_coolant = st.text_input("Product Name", value="" if cool_choice == "+ New" else cool_choice)
    
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)

# --- 4. DATA ENTRY & RECALL ---
col_in, col_gr = st.columns([1, 1], gap="large")

with col_in:
    st.markdown("### <span class='green-text'>Machine Data</span>", unsafe_allow_html=True)
    
    c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
    machines = [r[0] for r in c.fetchall() if r[0]]
    m_choice = st.selectbox("Machine ID", ["+ New Machine"] + machines)
    m_id = st.text_input("Confirm ID", value="" if m_choice == "+ New Machine" else m_choice)

    # Auto-Recall History
    last_vol, last_ri = 100.0, 1.0
    if m_choice != "+ New Machine":
        c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
        res = c.fetchone()
        if res: last_vol, last_ri = res[0], res[1]

    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Volume", value=last_vol)
    ri = c2.number_input("RI Factor", value=last_ri)
    
    c3, c4 = st.columns(2)
    brix = c3.number_input("Brix Reading", min_value=0.0)
    ph = c4.number_input("pH Reading", min_value=0.0)
    
    actual_conc = round(brix * ri, 2)
    if brix > 0:
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
        m2.metric("pH", ph, delta=round(ph - t_ph, 2))

with col_gr:
    st.markdown("### <span class='green-text'>Trend Analytics</span>", unsafe_allow_html=True)
    if m_id and customer:
        hist = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}'", conn)
        if not hist.empty:
            hist['date'] = pd.to_datetime(hist['date'])
            chart = alt.Chart(hist).mark_line(color=QC_GREEN, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 5. OBSERVATIONS (THE INSTANT SYNC BOX) ---
st.markdown("---")
st.markdown("### <span class='green-text'>Field Observations</span>", unsafe_allow_html=True)

# Using 'key' to allow handle_quick_note to push data directly into the widget
st.text_area("Observations Log", value=st.session_state.master_notes, key="notes_widget", height=150)

q_cols = st.columns(6)
if q_cols[0].button("pH Boost"): handle_quick_note("Added pH Boost")
if q_cols[1].button("Fungicide"): handle_quick_note("Added Fungicide")
if q_cols[2].button("Defoamer"): handle_quick_note("Added Defoamer")
if q_cols[3].button("Biocide"): handle_quick_note("Added Biocide")
if q_cols[4].button("DCR"): handle_quick_note("Recommend DCR")
if q_cols[5].button("🗑️ CLEAR"): clear_notes()

# --- 6. SAVE ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    # Final capture of whatever is in the box
    final_notes = st.session_state.notes_widget if "notes_widget" in st.session_state else st.session_state.master_notes
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, shop_coolant, m_id, vol, ri, brix, actual_conc, ph, final_notes, str(date.today())))
        conn.commit()
        clear_notes()
        st.success("Log Entry Recorded.")
        st.rerun()
