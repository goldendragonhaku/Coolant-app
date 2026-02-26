import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v6.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, customer TEXT, coolant_product TEXT, 
              machine_id TEXT, material TEXT, sump_volume REAL,
              ri_factor REAL, brix REAL, concentration REAL, 
              ph REAL, additives TEXT, amount TEXT, 
              comments TEXT, date TEXT)''')
conn.commit()

# --- EXCEL EXPORT ENGINE ---
def to_excel(df, min_c, max_c, min_p):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Tab 1: Current Status
        summary = df.sort_values('date').groupby('machine_id').tail(1)
        summary.to_excel(writer, index=False, sheet_name='Current_Status')
        
        workbook  = writer.book
        worksheet = writer.sheets['Current_Status']
        
        # Color Formats
        red_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        ylw_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
        
        # Apply formatting to Concentration (Col I) and pH (Col J)
        worksheet.conditional_format('I2:I200', {'type': 'cell', 'criteria': 'not between', 
                                                 'minimum': min_c, 'maximum': max_c, 'format': ylw_fmt})
        worksheet.conditional_format('J2:J200', {'type': 'cell', 'criteria': '<', 
                                                 'value': min_p, 'format': red_fmt})

        # Tab 2: Full History
        df.sort_values(['machine_id', 'date'], ascending=[True, False]).to_excel(writer, index=False, sheet_name='Full_History')
    return output.getvalue()

# --- APP UI ---
st.set_page_config(page_title="Coolant Pro v6", layout="wide")

with st.sidebar:
    st.header("🎯 Target Thresholds")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        min_conc = st.number_input("Min Conc %", value=5.0)
        min_ph = st.number_input("Min pH", value=8.8)
    with col_t2:
        max_conc = st.number_input("Max Conc %", value=9.0)
        max_ph = st.number_input("Max pH", value=9.4)
    
    st.divider()
    st.header("📝 New Service Entry")
    cust = st.text_input("Customer Name")
    coolant = st.text_input("Coolant Product")
    m_id = st.text_input("Machine ID")
    sump_vol = st.number_input("Sump Volume (Gals)", value=100.0)
    ri = st.number_input("RI Factor", value=1.0)
    brx = st.number_input("Brix Reading", value=0.0)
    ph_in = st.number_input("Measured pH", value=9.0, step=0.1)
    
    calc_conc = round(brx * ri, 2)

    # --- CHEMICAL CALCULATIONS ---
    st.subheader("🛠️ Recommended Actions")
    rec_actions = []
    if calc_conc < min_conc:
        recharge = round(((min_conc - calc_conc) / 100) * sump_vol, 2)
        rec_actions.append(f"Add {recharge} Gals Concentrate")
        st.warning(f"⚠️ {rec_actions[-1]}")
    
    if ph_in < min_ph:
        boost = round((sump_vol / 100) * 16, 1)
        rec_actions.append(f"Add {boost} oz pH Boost 95")
        st.error(f"🔴 {rec_actions[-1]}")
        
        if cust and m_id:
            prev = pd.read_sql_query(f"SELECT ph FROM logs WHERE customer='{cust}' AND machine_id='{m_id}' ORDER BY date DESC LIMIT 1", conn)
            if not prev.empty and prev['ph'].iloc[0] < min_ph:
                rec_actions.append("Add 1oz Biocide (Persistent Low pH)")
                st.error("⚠️ ADD BIOCIDE")

    st.divider()
    adds = st.text_input("Additives Added")
    amt = st.text_input("Qty Added")
    comm = st.text_area("Observations")
    dt = st.date_input("Date", datetime.now())

    if st.button("💾 Save Visit"):
        c.execute('''INSERT INTO logs VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                  (cust, coolant, m_id, "N/A", sump_vol, ri, brx, calc_conc, ph_in, adds, amt, comm, str(dt)))
        conn.commit()
        st.success("Saved Successfully")

# --- MAIN TABS ---
st.title("🛡️ Coolant Health Management System")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Trends", "📋 Shop Summary", "📧 Email & Excel Export", "🌎 Global Master List"])

# FETCH CURRENT CUSTOMER DATA
df_cust = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{cust}' ORDER BY date ASC", conn) if cust else pd.DataFrame()

with tab1:
    if not df_cust.empty:
        m_sel = st.selectbox("Machine", df_cust['machine_id'].unique())
        m_df = df_cust[df_cust['machine_id'] == m_sel]
        fig = px.line(m_df, x='date', y=['concentration', 'ph'], markers=True, title=f"History for {m_sel}")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(m_df.sort_values('date', ascending=False))
    else:
        st.info("Enter a Customer Name in the sidebar to view trends.")

with tab2:
    if not df_cust.empty:
        summary = df_cust.sort_values('date').groupby('machine_id').tail(1)
        def style_h(row):
            styles = [''] * len(row)
            if row['concentration'] < min_conc or row['concentration'] > max_conc:
                styles[row.index.get_loc('concentration')] = 'background-color: #ffff99'
            if row['ph'] < min_ph: styles[row.index.get_loc('ph')] = 'background-color: #ffcccc'
            return styles
        st.table(summary[['machine_id', 'concentration', 'ph', 'date', 'comments']].style.apply(style_h, axis=1))

with tab3:
    if not df_cust.empty:
        col_ex, col_em = st.columns(2)
        with col_ex:
            st.subheader("📁 Excel Report")
            excel_file = to_excel(df_cust, min_conc, max_conc, min_ph)
            st.download_button("Download Formatted Excel", data=excel_file, 
                               file_name=f"{cust}_Report_{datetime.now().strftime('%Y%m%d')}.xlsx")
        
        with col_em:
            st.subheader("📧 Email Draft")
            email_body = f"Subject: Service Report - {cust} - {m_id}\n\nConc: {calc_conc}% | pH: {ph_in}\n\nActions:\n" + "\n".join(rec_actions)
            st.text_area("Copy Text:", email_body, height=200)

with tab4:
    st.subheader("🌎 Global Inventory (All Clients)")
    all_logs = pd.read_sql_query("SELECT * FROM logs ORDER BY date DESC", conn)
    if not all_logs.empty:
        search = st.text_input("Search Customers/Machines")
        master = all_logs.groupby(['customer', 'machine_id']).head(1)
        if search: master = master[master['customer'].str.contains(search, case=False) | master['machine_id'].str.contains(search, case=False)]
        st.dataframe(master[['customer', 'machine_id', 'concentration', 'ph', 'date']])
