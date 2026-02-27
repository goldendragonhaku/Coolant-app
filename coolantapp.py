import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- 1. DATABASE & THEME ---
DB_NAME = 'qualiserv_pro.db'
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              vol REAL, ri REAL, brix REAL, conc REAL, ph REAL, notes TEXT, date TEXT)''')
conn.commit()

st.set_page_config(page_title="QualiServ Pro v62", layout="wide")

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

# --- 2. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1>QualiServ</h1>", unsafe_allow_html=True)
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    shops = [r[0] for r in c.fetchall() if r[0]]
    shop_choice = st.selectbox("Select Shop", ["+ New Shop"] + shops)
    customer = st.text_input("Active Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    st.markdown("---")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    coolants = [r[0] for r in c.fetchall() if r[0]]
    cool_choice = st.selectbox("Base Shop Product", ["+ New"] + coolants)
    shop_coolant = st.text_input("Product Name", value="" if cool_choice == "+ New" else cool_choice)
    
    if customer:
        st.subheader("📊 Reports")
        df_exp = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        if not df_exp.empty:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                df_exp.to_excel(writer, index=False)
            st.download_button("📥 Export Shop Excel", out.getvalue(), f"{customer}_Report.xlsx")

    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)

# --- 3. THE RECALL ENGINE ---
# We use this function to update the internal state keys for the number inputs
def recall_machine_specs():
    target_m = st.session_state.m_choice_widget
    if target_m != "+ New Machine":
        c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY date DESC LIMIT 1", (target_m, customer))
        result = c.fetchone()
        if result:
            st.session_state.vol_input = result[0]
            st.session_state.ri_input = result[1]
    else:
        st.session_state.vol_input = 100.0
        st.session_state.ri_input = 1.0

# Initialize state keys if they don't exist
if "vol_input" not in st.session_state: st.session_state.vol_input = 100.0
if "ri_input" not in st.session_state: st.session_state.ri_input = 1.0

# --- 4. MAIN DASHBOARD ---
col_in, col_chart = st.columns([1, 1], gap="large")

with col_in:
    st.markdown("### <span class='green-text'>Machine Entry</span>", unsafe_allow_html=True)
    service_date = st.date_input("Service Date", value=date.today())
    
    # Machine Selector with Callback
    c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
    machines = [r[0] for r in c.fetchall() if r[0]]
    m_choice = st.selectbox("Select Machine", ["+ New Machine"] + machines, key="m_choice_widget", on_change=recall_machine_specs)
    m_id = st.text_input("Confirm ID", value="" if m_choice == "+ New Machine" else m_choice)

    m_cool_toggle = st.toggle("Machine-specific product?")
    active_coolant = st.text_input("Product Override", value=shop_coolant) if m_cool_toggle else shop_coolant

    # Number inputs tied to the session state keys we update in the recall function
    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Vol (Gal)", key="vol_input")
    ri = c2.number_input("RI Factor", key="ri_input")
    
    c3, c4 = st.columns(2)
    brix = c3.number_input("Brix Reading", min_value=0.0)
    ph = c4.number_input("pH Reading", min_value=0.0)

    actual_conc = round(brix * ri, 2)
    if brix > 0:
        st.markdown("---")
        m1, m2 = st.columns(2)
        m1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
        m2.metric("pH", ph, delta=round(ph - t_ph, 2))

with col_chart:
    st.markdown("### <span class='green-text'>Trend History</span>", unsafe_allow_html=True)
    if m_id and customer:
        hist = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}'", conn)
        if not hist.empty:
            hist['date'] = pd.to_datetime(hist['date'])
            chart = alt.Chart(hist).mark_line(color=QC_GREEN, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 5. OBSERVATIONS ---
st.markdown("---")
st.markdown(f"### <span class='green-text'>Observations</span>", unsafe_allow_html=True)
user_notes = st.text_area("Field Notes", height=120, label_visibility="collapsed")

if st.button("💾 SAVE LOG", use_container_width=True):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, user_notes, str(service_date)))
        conn.commit()
        st.success(f"Saved {m_id}!")
        st.rerun()
