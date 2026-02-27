import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime, date

# --- DATABASE SETUP ---
conn = sqlite3.connect('qualiserv_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              metal TEXT, alloy TEXT, vol REAL, ri REAL, brix REAL, conc REAL, 
              ph REAL, notes TEXT, date TEXT)''')
conn.commit()

# --- BRANDING & CSS ---
st.set_page_config(page_title="QualiServ Pro", layout="wide")

QC_BLUE = "#00529B"
QC_GREEN = "#78BE20"

st.markdown(f"""
    <style>
    /* Main App Background - Light Gray for Depth */
    .stApp {{ 
        background-color: #F4F7F9; 
    }}
    
    /* Sidebar - Solid White with Blue Border */
    [data-testid="stSidebar"] {{
        background-color: #FFFFFF !important;
        border-right: 5px solid {QC_BLUE};
    }}
    
    /* Title Styling */
    .main-title {{ 
        color: {QC_BLUE}; 
        font-weight: 800; 
        font-size: 48px; 
        margin-bottom: 0px; 
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}

    /* Card Effect for Containers */
    div[data-testid="stVerticalBlock"] > div:has(div.stExpander) {{
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}

    /* Branded Buttons */
    div.stButton > button:first-child {{
        background-color: {QC_BLUE};
        color: white;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: bold;
        border: none;
    }}
    div.stButton > button:first-child:hover {{
        background-color: {QC_GREEN};
        color: white;
    }}

    /* Inputs */
    .stTextInput input, .stNumberInput input {{
        border-radius: 8px !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- MASTER STATE ---
if "master_notes" not in st.session_state: st.session_state.master_notes = ""
def update_master_from_box(): st.session_state.master_notes = st.session_state.notes_widget
def add_quick_note(text): 
    st.session_state.master_notes += f"{text}. "
    if "notes_widget" in st.session_state:
        st.session_state.notes_widget = st.session_state.master_notes
def clear_notes(): 
    st.session_state.master_notes = ""
    if "notes_widget" in st.session_state: st.session_state.notes_widget = ""

# --- 1. SIDEBAR ---
with st.sidebar:
    st.markdown(f"<h1 style='color:{QC_BLUE}; margin-bottom:0;'>QualiServ</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{QC_GREEN}; font-weight:bold;'>FIELD SERVICE ANALYTICS</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    shop_choice = st.selectbox("Active Shop", ["+ New Shop"] + existing_shops)
    customer = st.text_input("Confirm Shop Name", value="" if shop_choice == "+ New Shop" else shop_choice)
        
    st.markdown("---")
    c.execute("SELECT DISTINCT coolant FROM logs ORDER BY coolant ASC")
    all_coolants = [row[0] for row in c.fetchall() if row[0]]
    cool_choice = st.selectbox("Primary Coolant", ["+ New Coolant"] + all_coolants)
    shop_cool_name = st.text_input("Coolant Entry", value="" if cool_choice == "+ New Coolant" else cool_choice)
    
    t_conc = st.number_input("Target Conc %", value=8.0)
    t_ph = st.number_input("Min pH Target", value=8.8)
    
    if customer:
        df_export = pd.read_sql_query(f"SELECT date, m_id, conc, ph, notes FROM logs WHERE customer='{customer}'", conn)
        if not df_export.empty:
            st.markdown("---")
            st.download_button("📥 Download Excel Report", "dummy_data", file_name="report.xlsx") # Simplified for brevity

st.markdown(f"<p class='main-title'>QualiServ <span style='color:{QC_GREEN}'>Pro</span></p>", unsafe_allow_html=True)

# --- 2. MAIN DASHBOARD ---
col_main, col_chart = st.columns([1, 1], gap="large")

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        log_date = st.date_input("Date", value=date.today())
        
        c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
        existing_machines = [row[0] for row in c.fetchall() if row[0]]
        m_id = st.selectbox("Machine ID", ["+ New Machine"] + existing_machines)
        
        c1, c2 = st.columns(2)
        brix = c1.number_input("Brix Reading", min_value=0.0, step=0.1)
        ph = c2.number_input("pH Reading", min_value=0.0, step=0.1)
        
        ri = st.number_input("RI Factor", value=1.0)
        vol = st.number_input("Sump Volume (Gal)", value=100.0)

        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown("---")
            res1, res2 = st.columns(2)
            res1.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
            res2.metric("pH", ph, delta=round(ph - t_ph, 2))
            
            if actual_conc < t_conc:
                st.warning(f"Add {round(((t_conc - actual_conc)/100)*vol, 2)} Gal Concentrate")
            if 0 < ph < t_ph:
                st.error(f"Add {round((vol/100)*16, 1)} oz pH Boost 95")

with col_chart:
    st.subheader("📈 Concentration Trend")
    # Trend Chart Logic here...

# --- 3. OBSERVATIONS ---
st.markdown("---")
st.text_area("Observations", value=st.session_state.master_notes, key="notes_widget", on_change=update_master_from_box)

btns = st.columns(6)
if btns[0].button("pH Boost"): add_quick_note("Added pH Boost")
if btns[1].button("Fungicide"): add_quick_note("Added Fungicide")
if btns[2].button("Defoamer"): add_quick_note("Added Defoamer")
if btns[3].button("Biocide"): add_quick_note("Added Biocide")
if btns[4].button("DCR"): add_quick_note("Recommend DCR")
if btns[5].button("🗑️ CLEAR"): clear_notes()

if st.button("💾 SAVE MACHINE LOG", use_container_width=True):
    # Save Logic here...
    st.rerun()
