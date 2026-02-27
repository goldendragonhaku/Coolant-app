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

st.set_page_config(page_title="QualiServ Pro v60", layout="wide")

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
    .hint-text {{ color: #bdc3c7; font-size: 12px; font-style: italic; }}
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
    
    # Reports & DB Tools
    if customer:
        st.subheader("📊 Reports")
        df_exp = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        if not df_exp.empty:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='QualiServ')
            st.download_button("📥 Export Shop Excel", out.getvalue(), f"{customer}_Report.xlsx")

    with st.expander("💾 Database Tools"):
        with open(DB_NAME, 'rb') as f:
            st.download_button("Download DB", f, file_name="qualiserv_backup.db")
        up_db = st.file_uploader("Upload DB", type="db")
        if up_db:
            with open(DB_NAME, "wb") as f: f.write(up_db.getbuffer())
            st.rerun()

    t_conc = st.number_input("Target %", value=8.0)
    t_ph = st.number_input("Min pH", value=8.8)

st.markdown(f"<h1>QualiServ <span class='green-text'>Pro</span></h1>", unsafe_allow_html=True)

# --- 3. MAIN DASHBOARD ---
col_in, col_chart = st.columns([1, 1], gap="large")

with col_in:
    st.markdown("### <span class='green-text'>Machine Data Entry</span>", unsafe_allow_html=True)
    
    c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
    machines = [r[0] for r in c.fetchall() if r[0]]
    m_choice = st.selectbox("Select Machine", ["+ New Machine"] + machines)
    m_id = st.text_input("Machine ID", value="" if m_choice == "+ New Machine" else m_choice)

    # RECALL & LAST SERVICE INFO
    last_vol, last_ri, last_notes, last_date = 100.0, 1.0, "No previous notes.", "N/A"
    if m_choice != "+ New Machine":
        c.execute("SELECT vol, ri, notes, date FROM logs WHERE m_id=? AND customer=? ORDER BY date DESC LIMIT 1", (m_id, customer))
        recall = c.fetchone()
        if recall:
            last_vol, last_ri, last_notes, last_date = recall[0], recall[1], recall[2], recall[3]
            st.markdown(f"""
                <div style="background-color: rgba(255,255,255,0.1); padding: 10px; border-radius: 5px; border-left: 4px solid {QC_GREEN};">
                <span class='green-text'>Last Service:</span> {last_date}<br>
                <span class='green-text'>Prev Notes:</span> {last_notes}
                </div>
            """, unsafe_allow_html=True)

    m_cool_toggle = st.toggle("Machine-specific product?")
    active_coolant = st.text_input("Product Override", value=shop_coolant) if m_cool_toggle else shop_coolant

    c1, c2 = st.columns(2)
    vol = c1.number_input("Sump Vol", value=last_vol)
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

with col_chart:
    st.markdown("### <span class='green-text'>Trend History</span>", unsafe_allow_html=True)
    if m_id and customer:
        hist = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}'", conn)
        if not hist.empty:
            hist['date'] = pd.to_datetime(hist['date'])
            chart = alt.Chart(hist).mark_line(color=QC_GREEN, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 4. OBSERVATIONS (HINT RESTORED) ---
st.markdown("---")
st.markdown(f"### <span class='green-text'>Observations</span> <span class='hint-text'>(Press Cmd+Enter to finalize)</span>", unsafe_allow_html=True)
user_notes = st.text_area("Field Notes", height=120, label_visibility="collapsed", placeholder="Ex: Added 2 gallons, adjusted skim speed...")

if st.button("💾 SAVE LOG", use_container_width=True):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, user_notes, str(date.today())))
        conn.commit()
        st.success(f"Entry Saved for {m_id}")
        st.rerun()
