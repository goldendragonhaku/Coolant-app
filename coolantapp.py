import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import date

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_web.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (customer TEXT, coolant TEXT, m_id TEXT, metal TEXT, alloy TEXT, 
              vol REAL, ri REAL, brix REAL, conc REAL, ph REAL, 
              notes TEXT, date TEXT)''')
conn.commit()

# --- APP CONFIG ---
st.set_page_config(page_title="Coolant Pro v28", layout="centered")

# --- 1. SHOP PROFILE & TARGETS ---
st.title("🧪 Coolant Pro Web")
with st.container(border=True):
    st.subheader("🏢 Shop Profile & Targets")
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Shop Name", placeholder="Customer Name")
        target_conc = st.number_input("Target Conc %", value=8.0)
    with col2:
        shop_coolant = st.text_input("Shop-Wide Coolant", value="Coolant A")
        target_ph = st.number_input("Min pH Target", value=8.8)

    metal_type = st.selectbox("Metal Category", ["Aluminum 6XXX", "Aluminum 7XXX", "Stainless", "Cast Iron", "Carbon Steel", "Yellow Metals"])
    alloy = st.text_input("Specific Alloy", placeholder="e.g. 6061-T6")

# --- 2. MACHINE READINGS ---
st.subheader("⚙️ Machine Data")
multi_coolant = st.toggle("Use machine-specific coolant for this unit?")

col3, col4 = st.columns(2)
with col3:
    m_id = st.text_input("Machine ID")
    active_coolant = st.text_input("Specific Coolant Name") if multi_coolant else shop_coolant
with col4:
    vol = st.number_input("Sump Volume (Gals)", value=100)
    ri = st.number_input("RI Factor", value=1.0)

col5, col6 = st.columns(2)
with col5:
    brix = st.number_input("Brix Reading", value=0.0, format="%.1f")
with col6:
    ph = st.number_input("Current pH", value=0.0, format="%.1f")

# --- 3. LIVE CALCULATIONS ---
st.markdown("### 📊 Analysis")
actual_conc = round(brix * ri, 2)

if brix > 0:
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.metric("Concentration", f"{actual_conc}%")
        if actual_conc < target_conc:
            recharge = round(((target_conc - actual_conc) / 100) * vol, 2)
            st.warning(f"Add {recharge} Gal of {active_coolant}")
    with res_col2:
        st.metric("pH Level", ph)
        if 0 < ph < target_ph:
            boost = round((vol / 100) * 16, 1)
            st.error(f"Add {boost} oz of pH Boost 95")
        elif ph >= target_ph:
            st.success("pH is Healthy")

# --- 4. OBSERVATIONS & QUICK NOTES ---
st.subheader("📝 Field Observations")
# Initialize notes in session state if not present
if "notes_content" not in st.session_state:
    st.session_state.notes_content = ""

notes = st.text_area("Notes", value=st.session_state.notes_content)

st.write("Tap to Add:")
q_notes = ["Added pH Boost", "Added fungicide", "Added Defoamer", "Recommend DCR"]
btn_cols = st.columns(4)
for i, qn in enumerate(q_notes):
    if btn_cols[i].button(qn):
        st.session_state.notes_content += f"{qn}. "
        st.rerun()

# --- 5. SAVE & EXCEL EXPORT ---
if st.button("💾 SAVE MACHINE LOG", use_container_width=True, type="primary"):
    if customer and m_id:
        c.execute("INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (customer, active_coolant, m_id, metal_type, alloy, vol, ri, brix, actual_conc, ph, st.session_state.notes_content, str(date.today())))
        conn.commit()
        st.success(f"Logged {m_id}!")
        st.session_state.notes_content = "" # Clear notes for next machine
    else:
        st.error("Missing Shop Name or Machine ID")

st.markdown("---")
if st.checkbox("Generate Excel Report"):
    df = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{customer}'", conn)
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='CoolantLog')
            workbook  = writer.book
            worksheet = writer.sheets['CoolantLog']
            
            # Formats
            red_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            ylw_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
            
            # Conditional Formatting (Col I is Conc, Col J is pH)
            worksheet.conditional_format('I2:I500', {'type': 'cell', 'criteria': '<', 'value': target_conc, 'format': ylw_fmt})
            worksheet.conditional_format('J2:J500', {'type': 'cell', 'criteria': '<', 'value': target_ph, 'format': red_fmt})
            
        st.download_button(label="📥 Download .xlsx Report", data=output.getvalue(), file_name=f"{customer}_Report.xlsx", mime="application/vnd.ms-excel")
