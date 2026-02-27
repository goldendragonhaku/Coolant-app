import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v30.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              metal TEXT, alloy TEXT, vol REAL, ri REAL, brix REAL, conc REAL, 
              ph REAL, notes TEXT, date TEXT)''')
conn.commit()

st.set_page_config(page_title="Coolant Pro v36", layout="wide")

# Initialize Session State for Notes
if "notes" not in st.session_state:
    st.session_state.notes = ""

# Callback function to sync manual typing to state
def sync_notes():
    st.session_state.notes = st.session_state.notes_widget

# --- 1. SIDEBAR ---
with st.sidebar:
    st.header("🏢 Shop Selection")
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Existing Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    st.subheader("🎯 Shop Targets")
    shop_coolant = st.text_input("Primary Coolant", value="Coolant A")
    t_conc = st.number_input("Target Conc %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH Target", value=8.8, step=0.1)
    
    # Export logic
    if customer:
        df_export = pd.read_sql_query(f"SELECT date, m_id, coolant, vol, brix, ri, conc, ph, notes FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Report')
                # ... (conditional formatting logic from v35 goes here)
            st.download_button("📥 Export .xlsx", output.getvalue(), f"{customer}_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.title("🧪 Coolant Pro v36")

# --- 2. MAIN INTERFACE ---
col_main, col_chart = st.columns([1, 1])

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        log_date = st.date_input("Service Date", value=date.today())
        
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
        m_id = st.text_input("Machine ID Entry", value="" if m_choice == "+ New Machine" else m_choice)

        last_vol, last_ri = 100.0, 1.0
        if m_choice != "+ New Machine":
            c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
            last_record = c.fetchone()
            if last_record: last_vol, last_ri = last_record[0], last_record[1]

        vol = st.number_input("Sump Volume (Gals)", value=last_vol)
        ri = st.number_input("RI Factor", value=last_ri)
        brix = st.number_input("Brix Reading", min_value=0.0, format="%.1f")
        ph = st.number_input("Current pH", min_value=0.0, format="%.1f")

# --- 3. TREND CHART (Logic from v35) ---
with col_chart:
    st.subheader("📈 Trend Visualization")
    # ... (Altair Chart code here)

# --- 4. THE FIX: OBSERVATIONS & BUTTONS ---
st.markdown("---")
st.subheader("📝 Field Observations")

# We use 'key' to bind the widget and 'on_change' to update the state immediately
st.text_area("Observations", 
             value=st.session_state.notes, 
             key="notes_widget", 
             on_change=sync_notes)

st.write("Quick Add:")
q_cols = st.columns(5)
def handle_click(text):
    st.session_state.notes += f"{text}. "
    # We clear the widget key so it pulls the updated state value on rerun
    if "notes_widget" in st.session_state:
        del st.session_state["notes_widget"]

if q_cols[0].button("Added pH Boost"): handle_click("Added pH Boost")
if q_cols[1].button("Added Fungicide"): handle_click("Added Fungicide")
if q_cols[2].button("Added Defoamer"): handle_click("Added Defoamer")
if q_cols[3].button("Added Biocide"): handle_click("Added Biocide")
if q_cols[4].button("Recommend DCR"): handle_click("Recommend DCR")

# --- 5. SAVE ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True, type="primary"):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, shop_coolant, m_id, vol, ri, brix, (brix*ri), ph, st.session_state.notes, str(log_date)))
        conn.commit()
        st.success(f"Saved {m_id}")
        st.session_state.notes = "" # Reset session state
        if "notes_widget" in st.session_state:
            del st.session_state["notes_widget"] # Reset widget
        st.rerun()
