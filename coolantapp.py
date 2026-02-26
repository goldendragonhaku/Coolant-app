import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v9.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, customer TEXT, coolant_product TEXT, 
              machine_id TEXT, mat_category TEXT, specific_alloy TEXT, sump_volume REAL,
              ri_factor REAL, brix REAL, concentration REAL, 
              ph REAL, additives TEXT, amount TEXT, 
              comments TEXT, date TEXT)''')
conn.commit()

# --- EXCEL EXPORT ENGINE ---
def to_excel(df, min_c, max_c, min_p):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        summary = df.sort_values('date').groupby('machine_id').tail(1)
        summary.to_excel(writer, index=False, sheet_name='Current_Status')
        workbook, worksheet = writer.book, writer.sheets['Current_Status']
        red_fmt = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        ylw_fmt = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
        worksheet.conditional_format('J2:J200', {'type': 'cell', 'criteria': 'not between', 'minimum': min_c, 'maximum': max_c, 'format': ylw_fmt})
        worksheet.conditional_format('K2:K200', {'type': 'cell', 'criteria': '<', 'value': min_p, 'format': red_fmt})
        df.sort_values(['machine_id', 'date'], ascending=[True, False]).to_excel(writer, index=False, sheet_name='Full_History')
    return output.getvalue()

# --- APP UI ---
st.set_page_config(page_title="Coolant Pro v9", layout="wide")

with st.sidebar:
    st.header("🏢 Customer Profile")
    # Get unique customers for autocomplete
    all_custs = pd.read_sql_query("SELECT DISTINCT customer FROM logs", conn)['customer'].tolist()
    cust = st.selectbox("Customer Name (Select or Type)", [""] + all_custs)
    
    # If user wants to add a brand new customer not in list
    new_cust = st.text_input("OR Add New Customer Name")
    final_cust = new_cust if new_cust else cust
    
    mat_cat = st.selectbox("Primary Metal", ["Aluminum Alloys", "Carbon Steels", "Stainless Steels", "Cast Iron", "Yellow Metals", "Titanium/Inconel", "Tool Steels"])
    alloy = st.text_input("Primary Alloy", placeholder="e.g., 6061-T6")
    
    st.divider()
    st.header("⚙️ Machine Service Entry")
    
    # --- SMART RECALL LOGIC ---
    known_machines = []
    default_vol = 100.0
    default_ri = 1.0
    default_product = ""

    if final_cust:
        hist = pd.read_sql_query(f"SELECT DISTINCT machine_id FROM logs WHERE customer='{final_cust}'", conn)
        known_machines = hist['machine_id'].tolist()

    m_selection = st.selectbox("Select Existing Machine", ["+ Add New Machine"] + known_machines)
    
    if m_selection == "+ Add New Machine":
        m_id = st.text_input("Enter New Machine ID")
    else:
        m_id = m_selection
        # Pre-fill defaults from last visit
        last_visit = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{final_cust}' AND machine_id='{m_id}' ORDER BY date DESC LIMIT 1", conn)
        if not last_visit.empty:
            default_vol = float(last_visit['sump_volume'].iloc[0])
            default_ri = float(last_visit['ri_factor'].iloc[0])
            default_product = last_visit['coolant_product'].iloc[0]

    coolant = st.text_input("Coolant Product", value=default_product)
    sump_vol = st.number_input("Sump Volume (Gals)", value=default_vol)
    ri = st.number_input("RI Factor", value=default_ri)
    
    st.divider()
    brx = st.number_input("Brix Reading", value=0.0)
    ph_in = st.number_input("Measured pH", value=9.0, step=0.1)
    calc_conc = round(brx * ri, 2)

    # Thresholds (Internal hidden or visible)
    min_conc, max_conc, min_ph = 5.0, 9.0, 8.8
    
    # Additive Logic
    rec_actions = []
    if calc_conc < min_conc:
        recharge = round(((min_conc - calc_conc) / 100) * sump_vol, 2)
        rec_actions.append(f"Add {recharge} Gals Concentrate")
    if ph_in < min_ph:
        boost = round((sump_vol / 100) * 16, 1)
        rec_actions.append(f"Add {boost} oz pH Boost 95")

    st.divider()
    adds = st.text_input("Additives Added")
    amt = st.text_input("Qty Added")
    comm = st.text_area("Observations")
    dt = st.date_input("Service Date", datetime.now())

    if st.button("💾 Save Machine Log"):
        if final_cust and m_id:
            c.execute('''INSERT INTO logs VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                      (final_cust, coolant, m_id, mat_cat, alloy, sump_vol, ri, brx, calc_conc, ph_in, adds, amt, comm, str(dt)))
            conn.commit()
            st.success(f"Log saved for {m_id}")
            st.rerun() # Refresh to update lists

# --- DASHBOARD LOGIC (Simplified for clarity) ---
st.title("🛡️ Coolant Health Management System")
tab1, tab2, tab3 = st.tabs(["📊 Trends", "📋 Shop Summary", "📧 Reporting"])

df_cust = pd.read_sql_query(f"SELECT * FROM logs WHERE customer='{final_cust}' ORDER BY date ASC", conn) if final_cust else pd.DataFrame()

with tab1:
    if not df_cust.empty:
        m_sel = st.selectbox("Select Machine to View", df_cust['machine_id'].unique())
        m_df = df_cust[df_cust['machine_id'] == m_sel]
        st.plotly_chart(px.line(m_df, x='date', y=['concentration', 'ph'], markers=True), use_container_width=True)
        st.dataframe(m_df.sort_values('date', ascending=False))

with tab2:
    if not df_cust.empty:
        summary = df_cust.sort_values('date').groupby('machine_id').tail(1)
        st.table(summary[['machine_id', 'concentration', 'ph', 'date', 'comments']])

with tab3:
    if not df_cust.empty:
        excel_file = to_excel(df_cust, min_conc, max_conc, min_ph)
        st.download_button("Download Excel Report", data=excel_file, file_name=f"{final_cust}_Report.xlsx")
        st.text_area("Email Draft", f"Service Report for {final_cust}\nMachine: {m_id}\nConc: {calc_conc}%\npH: {ph_in}\nActions: {', '.join(rec_actions)}")
