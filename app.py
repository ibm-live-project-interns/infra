import streamlit as st
import time
from core.config import REPOS, WORK_DIR
from core.utils import get_timestamp
from orchestrator import DevOpsManager

# --- SETUP ---
st.set_page_config(page_title="DevOps Orchestrator", page_icon="🚀", layout="wide")

if 'logs' not in st.session_state: st.session_state.logs = "System Ready..."
if 'last_update' not in st.session_state: st.session_state.last_update = "Never"

def log_to_ui(msg):
    st.session_state.logs += f"\n{msg}"

manager = DevOpsManager(log_callback=log_to_ui)

# --- UI LAYOUT ---
col_t, col_s = st.columns([3, 1])
col_t.title("🚀 DevOps Orchestrator")
col_s.markdown(f"<div style='text-align:right; color:gray; padding-top:20px'>Updated: {st.session_state.last_update}</div>", unsafe_allow_html=True)

tab_dash, tab_logs = st.tabs(["🎛️ Dashboard", "📜 Logs"])

# Fetch Status
status = manager.check_health()

with tab_dash:
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        c1.subheader("Control Panel")
        if c2.button("🔄 Refresh", use_container_width=True):
            st.session_state.last_update = get_timestamp()
            st.rerun()

        branch_map = {}
        with st.expander("⚙️ Repository Config", expanded=False):
            cols = st.columns(len(REPOS))
            for idx, repo in enumerate(REPOS):
                with cols[idx]:
                    branch_map[repo['name']] = st.text_input(f"{repo['name']}", value="main")

        st.markdown("---")
        b1, b2, b3 = st.columns(3)
        
        if b1.button("▶ Initialize & Start", type="primary", use_container_width=True):
            st.session_state.logs = f"--- STARTED {get_timestamp()} ---\n"
            with st.spinner("Running Orchestrator..."):
                if manager.bootstrap_environment(branch_map):
                    st.toast("Success!", icon="✅")
                else:
                    st.error("Failed. Check Logs.")
            time.sleep(1)
            st.rerun()

        if b2.button("⏹ Stop", use_container_width=True):
            manager.stop()
            st.toast("Stopped", icon="🛑")
            time.sleep(1)
            st.rerun()
            
        if b3.button("💀 Hard Reset", type="secondary", use_container_width=True):
            manager.nuke()
            st.warning("Environment Wiped")
            time.sleep(1)
            st.rerun()

    if status["alerts"]:
        st.warning(f"{len(status['alerts'])} Active Alerts. Check Logs.", icon="⚠️")

    # --- INFRASTRUCTURE SECTION ---
    st.subheader("Infrastructure & Management")
    
    # Helper for cards
    def card(col, title, raw_status, link=None):
        is_healthy = "running" in str(raw_status).lower()
        display_val = raw_status if raw_status else "Not Created"
        
        with col:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                if is_healthy: 
                    st.success(display_val)
                    if link:
                        st.markdown(f"🔗 [Open GUI]({link})")
                elif "exited" in str(display_val).lower(): 
                    st.error(display_val)
                else: 
                    st.warning(display_val)

    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    
    card(ic1, "🐳 Docker", "Active" if status['docker'] else "Offline")
    card(ic2, "🐘 Postgres", status['containers'].get('database', 'Not Created'))
    card(ic3, "🕸️ Kafka", status['containers'].get('kafka', 'Not Created'))
    
    # GUI Cards
    card(ic4, "🐘 PgAdmin", status['containers'].get('pgadmin', 'Not Created'), "http://localhost:5050")
    card(ic5, "🕸️ Kafka UI", status['containers'].get('kafka-ui', 'Not Created'), "http://localhost:8090")

    # --- MICROSERVICES SECTION ---
    st.subheader("Microservices")
    cols = st.columns(4)
    for idx, repo in enumerate(REPOS):
        name = repo['name']
        with cols[idx % 4]:
            with st.container(border=True):
                st.markdown(f"**{name.title()}**")
                
                r_stat = status['repos'][name]['status']
                if r_stat == "Valid": st.success("✅ Code Ready")
                elif r_stat == "Mock": st.warning("⚠️ Mock Mode")
                else: st.error(f"❌ {r_stat}")
                
                c_stat = status['containers'].get(name, "Not Created")
                if "running" in str(c_stat).lower(): st.caption(f"🟢 {c_stat}")
                else: st.caption(f"🔴 {c_stat}")

with tab_logs:
    st.text_area("Live Output", value=st.session_state.logs, height=600, disabled=True)