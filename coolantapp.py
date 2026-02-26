import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v2.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, customer TEXT, machine_id TEXT, material TEXT, 
              ri_factor REAL, brix REAL, concentration REAL, 
              ph REAL, additives TEXT, amount TEXT, 
              comments TEXT, date TEXT)''')
conn.commit()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Coolant Pro Tracker", layout="wide")

# --- SIDEBAR: INPUT & TARGETS ---
with st.sidebar:
    st.header("🎯 Target Thresholds")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        min_target = st.number_input("Min Concentration %", value=5.0)
    with col_t2:
        max_target = st.number_input("Max Concentration %", value=9.0)
    
    st.divider()
    st.header("📝 New Service Entry")
    cust = st.text_input("Customer Name", placeholder="e.g., Precision Aero")
    m_id = st.text_input("Machine/Sump ID", placeholder="e.g., CNC-01")
    mat = st.selectbox("Material Processed", ["Aluminum", "Steel", "Cast Iron", "Stainless", "Yellow Metals"])
    
    ri = st.number_input("RI Factor (Multiplier)", value=1.0, step=0.1)
    brx = st.number_input("Brix Reading", min_value=0.0, step=0.1)
    ph_val = st.number_input("Measured pH", min_value=0.0, max_value=14.0, value=9.0, step=0.1)
    
    calc_conc = round(brx * ri, 2)
    
    # Real-time Logic Alert
    if calc_conc < min_target or calc_conc > max_target:
        st.warning(f"OUT OF RANGE: {calc_conc}%")
    else:
        st.success(f"IN RANGE: {calc_conc}%")
    
    adds = st.text_input("Additives Used")
    amt = st.text_input("Volume/Amount")
    comm = st.text_area("Observations")
    dt = st.date_input("Service Date", datetime.now())

    if st.button("Save Service Log"):
        if cust and m_id:
            c.execute('''INSERT INTO logs (customer, machine_id, material, ri_factor, brix, concentration, ph, additives, amount, comments, date) 
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (cust, m_id, mat, ri, brx, calc_conc, ph_val, adds, amt, comm, str(dt)))
            conn.commit()
            st.success(f"Saved {m_id} for {cust}")
        else:
            st.error("Please enter Customer and Machine ID")

# --- MAIN DASHBOARD ---
st.title("🛡️ Coolant Performance System")

if cust:
    tab1, tab2, tab3 = st.tabs(["📊 Trends & History", "🏢 Shop Health Dashboard", "📥 Export Report"])

    # FETCH DATA
    df = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{cust}' ORDER BY date ASC", conn)

    with tab1:
        if not df.empty:
            selected_m = st.selectbox("Filter by Machine", df['machine_id'].unique())
            m_df = df[df['machine_id'] == selected_m]
            
            # Trend Chart with Target Bands
            fig = px.line(m_df, x='date', y='concentration', title=f"Concentration Trend: {selected_m}", markers=True)
            fig.add_hrect(y0=min_target, y1=max_target, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Target Zone")
            st.plotly_chart(fig, use_container_width=True)
            
            st.write("### Full History")
            st.dataframe(m_df.sort_values('date', ascending=False))
        else:
            st.info("No data yet for this customer.")

    with tab2:
        st.subheader("Current Status of All Machines")
        if not df.empty:
            summary = df.sort_values('date').groupby('machine_id').tail(1)
            
            def highlight_status(val):
                color = '#ffff99' if (val < min_target or val > max_target) else ''
                return f'background-color: {color}'

            st.table(summary[['machine_id', 'concentration', 'ph', 'date', 'comments']].style.applymap(highlight_status, subset=['concentration']))
    
    with tab3:
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📩 Download Full Customer Report (CSV)", data=csv, file_name=f"{cust}_Master_Report.csv")

else:
    st.info("Enter a Customer Name in the sidebar to view data.")
