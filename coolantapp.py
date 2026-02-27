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

st.set_page_config(page_title="Coolant Pro v37", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if "notes" not in st.session_state:
    st.session_state.notes = ""

def sync_notes():
    st.session_state.notes = st.session_state.notes_widget

def handle_note_click(text):
    st.session_state.notes += f"{text}. "
    if "notes_widget" in st.session_state:
        del st.session_state["notes_widget"]

# --- 1. SIDEBAR ---
with st.sidebar:
    st.header("🏢 Shop Selection")
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Select Existing Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    st.subheader("🎯 Shop Targets")
    shop_cool_name = st.text_input("Primary Shop Coolant", value="Coolant A")
    t_conc = st.number_input("Target Conc %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH Target", value=8.8, step=0.1)
    
    # Excel Export with Fixes
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

st.title("🧪 Coolant Pro Analytics v37")

# --- 2. MAIN INTERFACE ---
col_main, col_chart = st.columns([1, 1])

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        log_date = st.date_input("Service Date", value=date.today())
        
        # Machine Selection
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
        m_id = st.text_input("Machine ID Entry", value="" if m_choice == "+ New Machine" else m_choice)

        # Multi-Coolant Logic (RESTORED)
        multi_coolant = st.toggle("Use machine-specific coolant?")
        active_coolant = st.text_input("Specific Coolant Name", placeholder="e.g. Special Alloy Fluid") if multi_coolant else shop_cool_name
        
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

        # Analysis Calculation
        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown("### 📊 Recommendations")
            r1, r2 = st.columns(2)
            with r1:
                st.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
                if actual_conc < t_conc:
                    re_gal = round(((t_conc - actual_conc) / 100) * vol, 2)
                    st.warning(f"💡 Add **{re_gal} Gal** concentrate.")
            with r2:
                st.metric("pH", ph, delta=round(ph - t_ph, 2))
                if 0 < ph < t_ph:
                    re_oz = round((vol / 100) * 16, 1)
                    st.error(f"🚨 Add **{re_oz} oz** pH Boost 95.")

# --- 3. TREND CHART ---
with col_chart:
    st.subheader(f"📈 Trend: {m_id if m_id else ''}")
    if m_id and customer:
        history = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not history.empty:
            history['date'] = pd.to_datetime(history['date'])
            chart = alt.Chart(history).mark_line(point=True).encode(
                x='date:T', y=alt.Y('conc:Q', title='Conc %'), tooltip=['date', 'conc']
            ).properties(height=350)
            st.altair_chart(chart, use_container_width=True)

# --- 4. OBSERVATIONS & BUTTONS (SYNCED) ---
st.markdown("---")
st.subheader("📝 Field Observations")

st.text_area("Notes", value=st.session_state.notes, key="notes_widget", on_change=sync_notes)

q_cols = st.columns(5)
if q_cols[0].button("Added pH Boost"): handle_note_click("Added pH Boost")
if q_cols[1].button("Added Fungicide"): handle_note_click("Added Fungicide")
if q_cols[2].button("Added Defoamer"): handle_note_click("Added Defoamer")
if q_cols[3].button("Added Biocide"): handle_note_click("Added Biocide")
if q_cols[4].button("Recommend DCR"): handle_note_click("Recommend DCR")

# --- 5. SAVE ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True, type="primary"):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.notes, str(log_date)))
        conn.commit()
        st.success(f"Saved {m_id}!")
        st.session_state.notes = "" # Reset
        if "notes_widget" in st.session_state: del st.session_state["notes_widget"]
        st.rerun()
