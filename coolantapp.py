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

st.set_page_config(page_title="Coolant Pro v41", layout="wide")

# --- MASTER STATE & NOTE LOGIC ---
if "master_notes" not in st.session_state:
    st.session_state.master_notes = ""

def update_master_from_box():
    st.session_state.master_notes = st.session_state.notes_widget

def add_quick_note(text):
    st.session_state.master_notes += f"{text}. "
    st.session_state.notes_widget = st.session_state.master_notes

def clear_notes():
    st.session_state.master_notes = ""
    if "notes_widget" in st.session_state:
        st.session_state.notes_widget = ""

# --- 1. SIDEBAR: SHOP & COOLANT SELECTION ---
with st.sidebar:
    st.header("🏢 Shop Selection")
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Existing Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    st.subheader("🎯 Shop Targets")
    
    # NEW: Shop-wide Coolant Dropdown
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    
    cool_choice = st.selectbox("Primary Shop Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Coolant Name Entry", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target Conc %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH Target", value=8.8, step=0.1)
    
    # Export Report
    if customer:
        df_export = pd.read_sql_query(f"SELECT date, m_id, coolant, vol, brix, ri, conc, ph, notes FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Report')
                workbook, worksheet = writer.book, writer.sheets['Report']
                ylw = workbook.add_format({'bg_color': '#FFEB9C'})
                red = workbook.add_format({'bg_color': '#FFC7CE'})
                worksheet.conditional_format('G2:G1000', {'type': 'cell', 'criteria': '<', 'value': t_conc, 'format': ylw})
                worksheet.conditional_format('H2:H1000', {'type': 'cell', 'criteria': '<', 'value': t_ph, 'format': red})
            st.download_button("📥 Export .xlsx", output.getvalue(), f"{customer.replace(' ','_')}_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.title("🧪 Coolant Pro Analytics v41")

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

        # NEW: Machine-Specific Coolant Logic
        multi_coolant = st.toggle("Use machine-specific coolant?")
        if multi_coolant:
            m_cool_choice = st.selectbox("Machine Coolant", ["+ New Coolant"] + all_coolants)
            active_coolant = st.text_input("Spec Coolant Entry", value="" if m_cool_choice == "+ New Coolant" else m_cool_choice)
        else:
            active_coolant = shop_cool_name
        
        # Recall Data
        last_vol, last_ri = 100.0, 1.0
        if m_choice != "+ New Machine":
            c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
            last_record = c.fetchone()
            if last_record: last_vol, last_ri = last_record[0], last_record[1]

        c1, c2 = st.columns(2)
        vol = c1.number_input("Sump Volume (Gals)", value=last_vol)
        ri = c2.number_input("RI Factor", value=last_ri)
        
        c3, c4 = st.columns(2)
        brix = c3.number_input("Brix Reading", min_value=0.0, format="%.1f")
        ph = c4.number_input("Current pH", min_value=0.0, format="%.1f")

        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown("### 📊 Recommendations")
            r1, r2 = st.columns(2)
            with r1:
                st.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
                if actual_conc < t_conc:
                    st.warning(f"💡 Add **{round(((t_conc - actual_conc)/100)*vol, 2)} Gal** conc.")
            with r2:
                st.metric("pH", ph, delta=round(ph - t_ph, 2))
                if 0 < ph < t_ph:
                    st.error(f"🚨 Add **{round((vol/100)*16, 1)} oz** pH Boost 95")

with col_chart:
    st.subheader(f"📈 Trend: {m_id if m_id else ''}")
    if m_id and customer:
        history = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not history.empty:
            history['date'] = pd.to_datetime(history['date'])
            chart = alt.Chart(history).mark_line(point=True).encode(x='date:T', y='conc:Q').properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 3. OBSERVATIONS ---
st.markdown("---")
st.subheader("📝 Field Observations")
st.text_area("Notes", value=st.session_state.master_notes, key="notes_widget", on_change=update_master_from_box, height=120)

q_cols = st.columns([1, 1, 1, 1, 1, 1])
if q_cols[0].button("Added pH Boost"): add_quick_note("Added pH Boost")
if q_cols[1].button("Added Fungicide"): add_quick_note("Added Fungicide")
if q_cols[2].button("Added Defoamer"): add_quick_note("Added Defoamer")
if q_cols[3].button("Added Biocide"): add_quick_note("Added Biocide")
if q_cols[4].button("Recommend DCR"): add_quick_note("Recommend DCR")
if q_cols[5].button("🗑️ CLEAR ALL"): clear_notes()

# --- 4. SAVE ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True, type="primary"):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.master_notes, str(log_date)))
        conn.commit()
        st.success(f"Saved {m_id}!")
        clear_notes()
        st.rerun()
