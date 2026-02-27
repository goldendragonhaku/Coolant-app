import streamlit as st
import pandas as pd
import sqlite3
import io
import altair as alt
from datetime import datetime

# --- DATABASE SETUP ---
conn = sqlite3.connect('coolant_pro_v30.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, coolant TEXT, m_id TEXT, 
              metal TEXT, alloy TEXT, vol REAL, ri REAL, brix REAL, conc REAL, 
              ph REAL, notes TEXT, date TEXT)''')
conn.commit()

st.set_page_config(page_title="Coolant Pro Analytics v32", layout="wide")

# --- 1. SIDEBAR: SHOP SELECTION ---
with st.sidebar:
    st.header("🏢 Shop Selection")
    
    # Get unique shops from DB
    c.execute("SELECT DISTINCT customer FROM logs ORDER BY customer ASC")
    existing_shops = [row[0] for row in c.fetchall() if row[0]]
    
    # Dropdown + Manual Entry Option
    shop_choice = st.selectbox("Select Existing Shop", ["+ New Shop"] + existing_shops)
    
    if shop_choice == "+ New Shop":
        customer = st.text_input("New Shop Name", placeholder="Type Name...")
    else:
        customer = shop_choice
        
    st.markdown("---")
    st.subheader("🎯 Shop Targets")
    shop_coolant = st.text_input("Primary Coolant", value="Coolant A")
    t_conc = st.number_input("Target Conc %", value=8.0, step=0.5)
    t_ph = st.number_input("Min pH Target", value=8.8, step=0.1)

st.title("🧪 Coolant Pro Analytics v32")

# --- 2. MAIN INTERFACE: MACHINE SELECTION ---
col_main, col_chart = st.columns([1, 1])

with col_main:
    with st.container(border=True):
        st.subheader("⚙️ Machine Entry")
        
        # Get unique machines for the selected shop
        existing_machines = []
        if customer:
            c.execute("SELECT DISTINCT m_id FROM logs WHERE customer=? ORDER BY m_id ASC", (customer,))
            existing_machines = [row[0] for row in c.fetchall() if row[0]]
        
        m_col1, m_col2 = st.columns([2, 1])
        with m_col1:
            m_choice = st.selectbox("Select Machine", ["+ New Machine"] + existing_machines)
        
        if m_choice == "+ New Machine":
            m_id = st.text_input("New Machine ID")
        else:
            m_id = m_choice

        # AUTO-RECALL LOGIC: If machine exists, pull the last used Volume and RI
        last_vol, last_ri = 100.0, 1.0
        if m_choice != "+ New Machine":
            c.execute("SELECT vol, ri FROM logs WHERE m_id=? AND customer=? ORDER BY id DESC LIMIT 1", (m_id, customer))
            last_record = c.fetchone()
            if last_record:
                last_vol, last_ri = last_record[0], last_record[1]

        multi_coolant = st.toggle("Machine-specific coolant?")
        active_coolant = st.text_input("Coolant Name", value=shop_coolant) if multi_coolant else shop_coolant
        
        c1, c2 = st.columns(2)
        vol = c1.number_input("Sump Volume (Gals)", value=last_vol)
        ri = c2.number_input("RI Factor", value=last_ri)
        
        c3, c4 = st.columns(2)
        brix = c3.number_input("Brix Reading", min_value=0.0, format="%.1f")
        ph = c4.number_input("Current pH", min_value=0.0, format="%.1f")

        # --- ANALYSIS BRAIN ---
        actual_conc = round(brix * ri, 2)
        if brix > 0:
            st.markdown("### 📊 Recommendations")
            res1, res2 = st.columns(2)
            with res1:
                st.metric("Conc", f"{actual_conc}%", delta=round(actual_conc - t_conc, 2))
                if actual_conc < t_conc:
                    recharge = round(((t_conc - actual_conc) / 100) * vol, 2)
                    st.warning(f"💡 Add **{recharge} Gal** concentrate")
            with res2:
                st.metric("pH", ph, delta=round(ph - t_ph, 2))
                if 0 < ph < t_ph:
                    boost = round((vol / 100) * 16, 1)
                    st.error(f"🚨 Add **{boost} oz** pH Boost 95")

# --- 3. TREND VISUALIZATION ---
with col_chart:
    st.subheader(f"📈 Trend: {m_id if m_id else 'Select Machine'}")
    if m_id and customer:
        history = pd.read_sql_query(f"SELECT date, conc, ph FROM logs WHERE customer='{customer}' AND m_id='{m_id}' ORDER BY date ASC", conn)
        if not history.empty:
            history['date'] = pd.to_datetime(history['date'])
            chart = alt.Chart(history).mark_line(point=True).encode(
                x='date:T',
                y=alt.Y('conc:Q', title='Conc %'),
                tooltip=['date', 'conc', 'ph']
            ).properties(height=300)
            target_line = alt.Chart(pd.DataFrame({'y': [t_conc]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
            st.altair_chart(chart + target_line, use_container_width=True)
        else:
            st.info("First entry for this machine.")

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
                  (customer, active_coolant, m_id, vol, ri, brix, actual_conc, ph, st.session_state.notes, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        st.success(f"Saved {m_id}!")
        st.session_state.notes = ""
        st.rerun()
    else:
        st.error("Missing Shop or Machine ID")

# --- 5. RECENT SESSION HISTORY ---
st.markdown("### 🕒 Recent Entries (Current Shop)")
if customer:
    recent_df = pd.read_sql_query(f"SELECT date, m_id, conc, ph, notes FROM logs WHERE customer='{customer}' ORDER BY id DESC LIMIT 5", conn)
    if not recent_df.empty:
        st.table(recent_df)
