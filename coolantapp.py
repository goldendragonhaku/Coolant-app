import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v5.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, customer TEXT, coolant_product TEXT, 
              machine_id TEXT, material TEXT, sump_volume REAL,
              ri_factor REAL, brix REAL, concentration REAL, 
              ph REAL, additives TEXT, amount TEXT, 
              comments TEXT, date TEXT)''')
conn.commit()

st.set_page_config(page_title="Coolant Pro v5", layout="wide")

# --- SIDEBAR: TARGETS & INPUT ---
with st.sidebar:
    st.header("🎯 Target Thresholds")
    col1, col2 = st.columns(2)
    with col1:
        min_conc = st.number_input("Min Conc %", value=5.0)
        min_ph = st.number_input("Min pH", value=8.8)
    with col2:
        max_conc = st.number_input("Max Conc %", value=9.0)
        max_ph = st.number_input("Max pH", value=9.4)
    
    st.divider()
    st.header("📝 Service Entry")
    cust = st.text_input("Customer")
    coolant = st.text_input("Coolant Product")
    m_id = st.text_input("Machine ID")
    sump_vol = st.number_input("Sump Volume (Gals)", value=100.0)
    
    st.divider()
    ri = st.number_input("RI Factor", value=1.0)
    brx = st.number_input("Brix Reading", value=0.0)
    ph_in = st.number_input("Measured pH", value=9.0, step=0.1)
    
    calc_conc = round(brx * ri, 2)

    # --- ADDITIVE CALCULATIONS ---
    st.subheader("🛠️ Recommended Actions")
    rec_actions = []
    
    # 1. Concentration Recharge
    if calc_conc < min_conc:
        recharge = round(((min_conc - calc_conc) / 100) * sump_vol, 2)
        rec_actions.append(f"Add {recharge} Gals of Concentrate")
        st.warning(f"⚠️ {rec_actions[-1]}")
    
    # 2. pH Boost 95 Logic
    if ph_in < min_ph:
        boost_dose = round((sump_vol / 100) * 16, 1)
        rec_actions.append(f"Add {boost_dose} oz of pH Boost 95")
        st.error(f"🔴 LOW pH: {rec_actions[-1]}")
        
        # 3. Biocide "Visit History" Logic
        if cust and m_id:
            prev_log = pd.read_sql_query(
                f"SELECT ph FROM logs WHERE customer='{cust}' AND machine_id='{m_id}' ORDER BY date DESC LIMIT 1", conn)
            if not prev_log.empty and prev_log['ph'].iloc[0] < min_ph:
                rec_actions.append("Add 1oz dose of Biocide (Persistent low pH)")
                st.error("⚠️ BIOCIDE REQUIRED")
    
    elif ph_in > max_ph:
        st.warning("🟡 HIGH pH: Monitor for skin irritation.")
    else:
        st.success("✅ Fluid is Optimal")

    adds = st.text_input("Additives Actually Added")
    amt = st.text_input("Qty Added")
    comm = st.text_area("Notes")
    dt = st.date_input("Date", datetime.now())

    if st.button("💾 Save Visit"):
        c.execute('''INSERT INTO logs VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                  (cust, coolant, m_id, "N/A", sump_vol, ri, brx, calc_conc, ph_in, adds, amt, comm, str(dt)))
        conn.commit()
        st.success("Data Saved!")

# --- DASHBOARD ---
st.title("🛡️ Coolant Health & Reporting")

if cust:
    tab1, tab2, tab3 = st.tabs(["📊 Trends", "📋 Shop Summary", "📧 Email Report"])
    
    df = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{cust}' ORDER BY date ASC", conn)
    
    with tab1:
        if not df.empty:
            m_id_sel = st.selectbox("Select Machine", df['machine_id'].unique())
            m_df = df[df['machine_id'] == m_id_sel]
            fig = px.line(m_df, x='date', y=['concentration', 'ph'], markers=True, title=f"History: {m_id_sel}")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(m_df.sort_values('date', ascending=False))

    with tab2:
        if not df.empty:
            summary = df.sort_values('date').groupby('machine_id').tail(1)
            def style_health(row):
                styles = [''] * len(row)
                if row['concentration'] < min_conc or row['concentration'] > max_conc:
                    styles[row.index.get_loc('concentration')] = 'background-color: #ffff99'
                if row['ph'] < min_ph:
                    styles[row.index.get_loc('ph')] = 'background-color: #ffcccc'
                elif row['ph'] > max_ph:
                    styles[row.index.get_loc('ph')] = 'background-color: #ffff99'
                return styles
            st.table(summary[['machine_id', 'concentration', 'ph', 'date', 'comments']].style.apply(style_health, axis=1))

    with tab3:
        st.subheader("Draft Service Email")
        status_text = "OPTIMAL" if (min_conc <= calc_conc <= max_conc and ph_in >= min_ph) else "ATTENTION REQUIRED"
        
        email_body = f"""
Subject: Coolant Service Report - {cust} - {m_id} ({dt})

Hello,

I have completed the coolant service for {m_id}. 

SERVICE SUMMARY:
- Machine: {m_id}
- Coolant: {coolant}
- Concentration: {calc_conc}% (Target: {min_conc}-{max_conc}%)
- pH Level: {ph_in} (Target: {min_ph}+)
- Status: {status_text}

RECOMMENDED ACTIONS:
{chr(10).join(['• ' + a for a in rec_actions]) if rec_actions else '• No immediate action required.'}

NOTES:
{comm if comm else 'No additional notes.'}

Best regards,
Coolant Maintenance Team
        """
        st.text_area("Copy and Paste into Email:", email_body, height=350)
