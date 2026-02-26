import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- DATABASE SETUP & MIGRATION ---
conn = sqlite3.connect('coolant_pro_v3.db', check_same_thread=False)
c = conn.cursor()

# Create table with all new fields
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, 
              customer TEXT, 
              coolant_product TEXT,
              machine_id TEXT, 
              material TEXT, 
              sump_volume REAL,
              ri_factor REAL, 
              brix REAL, 
              concentration REAL, 
              ph REAL, 
              additives TEXT, 
              amount TEXT, 
              comments TEXT, 
              date TEXT)''')
conn.commit()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Coolant Pro Tracker v3", layout="wide")

# --- SIDEBAR: INPUT & TARGETS ---
with st.sidebar:
    st.header("🎯 Target Thresholds")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        min_target = st.number_input("Min %", value=5.0)
    with col_t2:
        max_target = st.number_input("Max %", value=9.0)
    
    st.divider()
    st.header("📝 New Service Entry")
    cust = st.text_input("Customer Name")
    coolant = st.text_input("Coolant Product (e.g. TRIM E206)")
    m_id = st.text_input("Machine/Sump ID")
    mat = st.selectbox("Material", ["Aluminum", "Steel", "Cast Iron", "Stainless", "Mixed"])
    sump_vol = st.number_input("Sump Volume (Gals/Ltrs)", value=50.0)
    
    st.divider()
    ri = st.number_input("RI Factor", value=1.0, step=0.1)
    brx = st.number_input("Brix Reading", min_value=0.0, step=0.1)
    ph_val = st.number_input("Measured pH", min_value=0.0, max_value=14.0, value=9.0, step=0.1)
    
    # MATH SECTION
    calc_conc = round(brx * ri, 2)
    
    # RECHARGE CALCULATOR LOGIC
    st.subheader("🧮 Recharge Calculator")
    if calc_conc < min_target:
        needed_diff = min_target - calc_conc
        # Amount of concentrate to add = (Target Diff / 100) * Sump Volume
        recharge_amt = round((needed_diff / 100) * sump_vol, 2)
        st.warning(f"Add **{recharge_amt}** units of concentrate to reach {min_target}%")
    else:
        st.success("Concentration is within or above spec.")
    
    st.divider()
    adds = st.text_input("Additives Used")
    amt = st.text_input("Volume/Amount Added")
    comm = st.text_area("Observations")
    dt = st.date_input("Service Date", datetime.now())

    if st.button("💾 Save Service Log"):
        if cust and m_id:
            c.execute('''INSERT INTO logs 
                         (customer, coolant_product, machine_id, material, sump_volume, 
                          ri_factor, brix, concentration, ph, additives, amount, comments, date) 
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                      (cust, coolant, m_id, mat, sump_vol, ri, brx, calc_conc, ph_val, adds, amt, comm, str(dt)))
            conn.commit()
            st.success(f"Logged {m_id} for {cust}")
        else:
            st.error("Customer and Machine ID are required.")

# --- MAIN DASHBOARD ---
st.title("🧪 Industrial Coolant Management")

if cust:
    tab1, tab2, tab3 = st.tabs(["📊 Trends", "🏢 Shop Health Dashboard", "📥 Export"])

    df = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{cust}' ORDER BY date ASC", conn)

    with tab1:
        if not df.empty:
            m_list = df['machine_id'].unique()
            selected_m = st.selectbox("Select Machine", m_list)
            m_df = df[df['machine_id'] == selected_m]
            
            # Show Product info
            current_product = m_df['coolant_product'].iloc[-1]
            st.info(f"Currently tracking: **{current_product}** in {selected_m}")

            fig = px.line(m_df, x='date', y='concentration', title=f"Concentration Trend: {selected_m}", markers=True)
            fig.add_hrect(y0=min_target, y1=max_target, fillcolor="green", opacity=0.1, line_width=0)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(m_df.sort_values('date', ascending=False))
        else:
            st.info("No data found for this customer.")

    with tab2:
        st.subheader(f"Current Status: {cust}")
        if not df.empty:
            # Get latest for each machine
            summary = df.sort_values('date').groupby('machine_id').tail(1)
            
            def color_cells(val):
                color = '#ffff99' if (val < min_target or val > max_target) else ''
                return f'background-color: {color}'

            st.table(summary[['machine_id', 'coolant_product', 'concentration', 'ph', 'date', 'comments']].style.applymap(color_cells, subset=['concentration']))

    with tab3:
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(f"📥 Download {cust} Master Report", data=csv, file_name=f"{cust}_Coolant_Report.csv")
else:
    st.info("👈 Enter a Customer Name in the sidebar to begin.")
