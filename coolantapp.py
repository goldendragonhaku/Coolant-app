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

st.set_page_config(page_title="Coolant Pro v34", layout="wide")

# --- 1. SIDEBAR: SELECTION, BACKUP & EXCEL ---
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
    
    st.markdown("---")
    # NEW: EXCEL EXPORT BUTTON
    st.subheader("📊 Reports")
    if customer:
        df_export = pd.read_sql_query(f"SELECT date, m_id as 'Machine', coolant as 'Coolant', vol as 'Sump Vol', brix as 'Brix', ri as 'RI', conc as 'Actual %', ph as 'pH', notes as 'Observations' FROM logs WHERE customer='{customer}' ORDER BY date DESC", conn)
        
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Coolant Report')
                workbook  = writer.book
                worksheet = writer.sheets['Coolant Report']
                
                # Format Definitions
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
                red_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                ylw_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
                
                # Apply conditional formatting (Col G is Conc, Col H is pH)
                worksheet.conditional_format('G2:G500', {'type': 'cell', 'criteria': '<', 'value': t_conc, 'format': ylw_fmt})
                worksheet.conditional_format('H2:H500', {'type': 'cell', 'criteria': '<', 'value': t_ph, 'format': red_fmt})
                worksheet.set_column('A:I', 15) # Adjust column width
            
            st.download_button(
                label="📥 Export Shop Report (.xlsx)",
                data=output.getvalue(),
                file_name=f"{customer}_Report_{date.today()}.xlsx",
                mime="application/vnd.ms-excel"
            )
    
    st.markdown("---")
    st.subheader("💾 Database Backup")
    with open('coolant_pro_v30.db', 'rb') as f:
        st.download_button("Download Raw .DB File", f, file_name=f"coolant_backup_{date.today()}.db")

st.title("🧪 Coolant Pro v34")

# --- 2. MAIN INTERFACE (DATA ENTRY) ---
col_main, col_chart = st.columns([1, 1])

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        log_date = st.date_input("Service Date", value=date.today())
        
        # Machine Dropdown
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
        m_id = st.text_input("Machine ID Entry", value="" if m_choice == "+ New Machine" else m_choice)

        # Auto-Recall for Volume/RI
        last_vol, last_ri = 100.0, 1.0
        if m_choice != "+ New Machine":
            c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
            last_record = c.fetchone()
            if last_record: last_vol, last_ri = last_record[0], last_record[1]

        multi_coolant = st.toggle("Machine-specific coolant?")
        active_coolant = st.text_input("Coolant Name", value=shop_coolant) if multi_coolant else shop_coolant
        
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
                    st.warning(f"💡 Add **{round(((t_conc - actual_conc) / 100) * vol, 2)} Gal** conc.")
            with r2:
                st.metric("pH", ph, delta=round(ph - t_ph, 2))
                if 0 < ph < t_ph:
                    st.error(f"🚨 Add **{round((vol / 100) * 16, 1)} oz** pH Boost")

# --- 3. TREND CHART ---
with col_chart:
    st.subheader(f"📈 Trend: {m_id if m_id else 'Select Machine'}")
    if m_id and customer:
        history = pd.read_sql_query(f"SELECT date, conc FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not history.empty:
            history['date'] = pd.to_datetime(history['date'])
            chart = alt.Chart(history).mark_line(point=True).encode(
                x='date:T', y=alt.Y('conc:Q', title='Concentration %'), tooltip=['date', 'conc']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else: st.info("Historical trend will appear after saving.")

# --- 4. OBSERVATIONS & BUTTONS ---
st.markdown("---")
if "notes" not in st.session_state: st.session_state.notes = ""
notes_area = st.text_area("Observations", value=st.session_state.notes)

q_cols = st.columns(5)
if q_cols[0].button("Added pH Boost"): st.session_state.notes += "Added pH Boost. "; st.rerun()
if q_cols[1].button("Added Fungicide"): st.session_state.notes += "Added Fungicide. "; st.rerun()
if q_cols[2].button("Added Defoamer"): st.session_state.notes += "Added Defoamer. "; st.rerun()
if q_cols[3].button("Added Biocide"): st.session_state.notes += "Added Biocide. "; st.rerun()
if q_cols[4].button("Recommend DCR"): st.session_state.notes += "Recommend DCR. "; st.rerun()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True, type="primary"):
    if customer and m_id:
        c.execute("INSERT INTO logs (customer, coolant, m_id, vol, ri, brix, conc, ph, notes, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.notes, str(log_date)))
        conn.commit()
        st.success(f"Saved {m_id}!")
        st.session_state.notes = ""
        st.rerun()

# --- 5. RECENT HISTORY TABLE ---
st.markdown("### 🕒 Recent Entries")
if customer:
    recent_df = pd.read_sql_query(f"SELECT date, m_id, conc, ph, notes FROM logs WHERE customer='{customer}' ORDER BY date DESC, id DESC LIMIT 5", conn)
    if not recent_df.empty: st.table(recent_df)
