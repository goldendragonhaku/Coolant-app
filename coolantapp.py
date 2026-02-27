import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- 1. DATABASE & THEME ---
DB_NAME = 'qualiserv_pro.db'

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

conn = get_connection()
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

# --- 2. SESSION STATE LOGIC ---
if "master_notes" not in st.session_state:
    st.session_state.master_notes = ""

def sync_notes():
    if "notes_widget" in st.session_state:
        st.session_state.master_notes = st.session_state.notes_widget

def add_quick_note(text):
    sync_notes()
    st.session_state.master_notes += f"{text}. "
    st.rerun()

# --- 3. SIDEBAR: DATA MANAGEMENT ---
with st.sidebar:
    st.markdown(f"<h1>QualiServ</h1>", unsafe_allow_html=True)
    
    # --- SHOP SELECT ---
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    shops = [r[0] for r in c.fetchall() if r[0]]
    shop_choice = st.selectbox("Shop Selection", ["+ New Shop"] + shops)
    customer = st.text_input("Active Shop", value="" if shop_choice == "+ New Shop" else shop_choice)
    
    st.markdown("---")
    
    # --- IMPORT / EXPORT TOOLS ---
    with st.expander("💾 DATA MANAGEMENT"):
        # Export DB
        with open(DB_NAME, 'rb') as f:
            st.download_button("Download Database (.db)", f, file_name="qualiserv_backup.db")
        
        # Import DB
        uploaded_db = st.file_uploader("Replace Database (.db)", type="db")
        if uploaded_db:
            with open(DB_NAME, "wb") as f:
                f.write(uploaded_db.getbuffer())
            st.success("Database Replaced. Refreshing...")
            st.rerun()

        st.markdown("---")
        
        # Import Excel
        uploaded_xl = st.file_uploader("Bulk Import Excel", type="xlsx")
        if uploaded_xl:
            import_df = pd.read_excel(uploaded_xl)
            import_df.to_sql('logs', conn, if_exists='append', index=False)
            st.success("Data Appended!")
            st.rerun()

    st.markdown("---")
    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

# --- 4. MAIN INTERFACE ---
st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)
col_in, col_chart = st.columns([1, 1], gap="large")

with col_in:
    st.markdown("### <span class='green-text'>Machine Data</span>", unsafe_allow_html=True)
    
    # ID Selector & Recall
    c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
    machines = [r[0] for r in c.fetchall() if r[0]]
    m_choice = st.selectbox("Select Machine", ["+ New Machine"] + machines)
    m_id = st.text_input("Confirm ID", value="" if m_choice == "+ New Machine" else m_choice)

    last_vol, last_ri = 100.0, 1.0
    if m_choice != "+ New Machine":
        c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
        recall = c.fetchone()
        if recall: last_vol, last_ri = recall[0], recall[1]

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
        if actual_conc < t_conc:
            st.warning(f"💡 Add {round(((t_conc - actual_conc)/100)*vol, 2)} Gal Concentrate")
        if 0 < ph < t_ph:
            st.error(f"🚨 Add {round((vol/100)*16, 1)} oz pH Boost 95")

with col_chart:
    st.markdown("### <span class='green-text'>Trend Analytics</span>", unsafe_allow_html=True)
    if m_id and customer:
        hist = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}'", conn)
        if not hist.empty:
            hist['date'] = pd.to_datetime(hist['date'])
            chart = alt.Chart(hist).mark_line(color=QC_GREEN, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 5. OBSERVATIONS (FIXED SYNC) ---
st.markdown("---")
st.text_area("Observations", value=st.session_state.master_notes, key="notes_widget", on_change=sync_notes, height=120)

btns = st.columns(6)
if btns[0].button("pH Boost"): add_quick_note("Added pH Boost")
if btns[1].button("Fungicide"): add_quick_note("Added Fungicide")
if btns[2].button("Defoamer"): add_quick_note("Added Defoamer")
if btns[3].button("Biocide"): add_quick_note("Added Biocide")
if btns[4].button("DCR"): add_quick_note("Recommend DCR")
if btns[5].button("🗑️"): 
    st.session_state.master_notes = ""
    st.rerun()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    sync_notes()
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?)",
                  (customer, m_id, vol, ri, brix, actual_conc, ph, st.session_state.master_notes, str(date.today())))
        conn.commit()
        st.session_state.master_notes = ""
        st.success("Entry Saved.")
        st.rerun()
