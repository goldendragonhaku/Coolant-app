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

# --- BRANDING & CSS ---
st.set_page_config(page_title="QualiServ Pro", layout="wide")

# QualiChem Brand Colors
QC_BLUE = "#00529B"
QC_GREEN = "#78BE20"

st.markdown(f"""
    <style>
    /* Main Header */
    .main-title {{ color: {QC_BLUE}; font-weight: bold; font-size: 42px; }}
    
    /* Buttons */
    div.stButton > button:first-child {{
        background-color: {QC_BLUE};
        color: white;
        border-radius: 8px;
        border: none;
    }}
    div.stButton > button:first-child:hover {{
        background-color: {QC_GREEN};
        color: white;
    }}
    
    /* Metric Styling */
    [data-testid="stMetricValue"] {{ color: {QC_BLUE}; }}
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {{ background-color: #f0f2f6; border-right: 3px solid {QC_BLUE}; }}
    </style>
""", unsafe_allow_html=True)

# --- MASTER STATE ---
if "master_notes" not in st.session_state: st.session_state.master_notes = ""

def update_master_from_box(): st.session_state.master_notes = st.session_state.notes_widget
def add_quick_note(text): 
    st.session_state.master_notes += f"{text}. "
    st.session_state.notes_widget = st.session_state.master_notes
def clear_notes(): 
    st.session_state.master_notes = ""
    if "notes_widget" in st.session_state: st.session_state.notes_widget = ""

# --- 1. SIDEBAR: QUALISERV SHOP SELECT ---
with st.sidebar:
    st.markdown(f"<h1 style='color:{QC_BLUE}'>QualiServ</h1>", unsafe_allow_html=True)
    st.header("🏢 Shop Selection")
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Existing Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    st.subheader("🎯 Target Specs")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Primary Shop Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Coolant Name Entry", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target Conc %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH Target", value=8.8, step=0.1)
    
    # Branded Export
    if customer:
        df_export = pd.read_sql_query(f"SELECT date, m_id, coolant, conc, ph, notes FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='QualiServ Report')
                workbook, worksheet = writer.book, writer.sheets['QualiServ Report']
                # Header formatting
                header_fmt = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': QC_BLUE})
                for col_num, value in enumerate(df_export.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
            st.download_button("📥 Export Branded .xlsx", output.getvalue(), f"QualiServ_{customer.replace(' ','_')}.xlsx")

st.markdown(f"<p class='main-title'>QualiServ <span style='color:{QC_GREEN}'>Pro</span></p>", unsafe_allow_html=True)

# --- 2. MAIN INTERFACE ---
col_main, col_chart = st.columns([1, 1])

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        log_date = st.date_input("Service Date", value=date.today())
        
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
        m_id = st.text_input("Machine ID", value="" if m_choice == "+ New Machine" else m_choice)

        multi_coolant = st.toggle("Machine-specific coolant?")
        if multi_coolant:
            m_cool_choice = st.selectbox("Specific Coolant", ["+ New Coolant"] + all_coolants)
            active_coolant = st.text_input("Spec Entry", value="" if m_cool_choice == "+ New Coolant" else m_cool_choice)
        else:
            active_coolant = shop_cool_name
        
        # Sump & Readings
        c1, c2 = st.columns(2)
        vol = c1.number_input("Sump Volume", value=100.0)
        ri = c2.number_input("RI Factor", value=1.0)
        c3, c4 = st.columns(2)
        brix = c3.number_input("Brix", min_value=0.0, format="%.1f")
        ph = c4.number_input("pH", min_value=0.0, format="%.1f")

        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown(f"### <span style='color:{QC_BLUE}'>Analysis</span>", unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            with r1:
                st.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
                if actual_conc < t_conc: st.warning(f"💡 Add **{round(((t_conc - actual_conc)/100)*vol, 2)} Gal**")
            with r2:
                st.metric("pH", ph, delta=round(ph - t_ph, 2))
                if 0 < ph < t_ph: st.error(f"🚨 Add **{round((vol/100)*16, 1)} oz** pH Boost 95")

with col_chart:
    st.subheader("📈 Trend")
    if m_id and customer:
        history = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not history.empty:
            history['date'] = pd.to_datetime(history['date'])
            chart = alt.Chart(history).mark_line(color=QC_BLUE, point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 3. OBSERVATIONS ---
st.markdown("---")
st.text_area("Notes", value=st.session_state.master_notes, key="notes_widget", on_change=update_master_from_box, height=120)

q_cols = st.columns([1, 1, 1, 1, 1, 1])
if q_cols[0].button("pH Boost"): add_quick_note("Added pH Boost")
if q_cols[1].button("Fungicide"): add_quick_note("Added Fungicide")
if q_cols[2].button("Defoamer"): add_quick_note("Added Defoamer")
if q_cols[3].button("Biocide"): add_quick_note("Added Biocide")
if q_cols[4].button("DCR"): add_quick_note("Recommend DCR")
if q_cols[5].button("🗑️ CLEAR"): clear_notes()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.master_notes, str(log_date)))
        conn.commit()
        st.success(f"Saved {m_id} to {customer}")
        clear_notes(); st.rerun()
