import streamlit as st
import subprocess
import os
import time
import shutil
import datetime
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path.cwd()
PROJECT_NAME = "prod"
WORK_DIR = BASE_DIR / PROJECT_NAME

# Repositories to clone
REPOS = [
    {"name": "datasource", "url": "https://github.com/ibm-live-project-interns/datasource.git"},
    {"name": "ingestor", "url": "https://github.com/ibm-live-project-interns/ingestor.git"},
    {"name": "ai-core", "url": "https://github.com/ibm-live-project-interns/ai-core.git"},
    {"name": "ui", "url": "https://github.com/ibm-live-project-interns/ui.git"}
]

# --- HELPER FUNCTIONS ---

def get_timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

def is_mock_file(file_path):
    try:
        if not file_path.exists(): return False
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return "FAILSAFE MODE" in content
    except:
        return False

def check_docker_engine():
    """Verifies Docker Engine is actually reachable."""
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_status(work_dir):
    """Checks the health of the environment."""
    status = {
        "docker": False,
        "repos": {},
        "containers": {},
        "alerts": [] 
    }

    # 1. Docker Engine Check
    status["docker"] = check_docker_engine()
    if not status["docker"]:
        status["alerts"].append("CRITICAL: Docker Daemon not reachable.")

    # 2. Repo Check
    for repo in REPOS:
        name = repo["name"]
        repo_path = work_dir / "services" / name
        dockerfile = repo_path / "Dockerfile"
        
        repo_state = {"status": "Unknown", "msg": ""}
        
        if not repo_path.exists():
             repo_state = {"status": "Missing", "msg": "Folder not found"}
             status["alerts"].append(f"**{name}**: Folder missing entirely.")
        elif not (repo_path / ".git").exists():
             repo_state = {"status": "Corrupt", "msg": "Invalid Git Repo"}
             status["alerts"].append(f"**{name}**: Corrupt folder detected.")
        
        if is_mock_file(dockerfile):
            repo_state = {"status": "Mock", "msg": "Failsafe Mode"}
            reason = "Clone failed" if not (repo_path / ".git").exists() else "Missing Dockerfile"
            status["alerts"].append(f"**{name}**: Running Mock ({reason})")
        elif dockerfile.exists():
             repo_state = {"status": "Valid", "msg": "Codebase Active"}
        else:
            repo_state = {"status": "Corrupt", "msg": "No Dockerfile"}
            status["alerts"].append(f"**{name}**: No Dockerfile found.")
            
        status["repos"][name] = repo_state

    # 3. Container Check
    if status["docker"] and (work_dir / "docker-compose.yml").exists():
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "-a"], 
                cwd=work_dir, capture_output=True, text=True, encoding='utf-8', errors='replace'
            )
            output = result.stdout
            
            # Check App Services
            for repo in REPOS:
                name = repo["name"]
                if name in output and "Up" in output:
                    status["containers"][name] = "Running"
                elif name in output:
                    status["containers"][name] = "Stopped"
                else:
                    status["containers"][name] = "Not Created"
            
            # Check Infrastructure
            infra_map = {
                "postgres": "database",
                "kafka": "kafka",
                "zookeeper": "zookeeper"
            }
            for docker_name, ui_key in infra_map.items():
                if docker_name in output and "Up" in output:
                     status["containers"][ui_key] = "Running"
                else:
                     status["containers"][ui_key] = "Not Created"
        except:
            pass
    return status

def stream_command(cmd, cwd, log_container):
    """Runs a shell command and streams output."""
    if not cwd.exists():
        return False
    try:
        process = subprocess.Popen(
            cmd, cwd=str(cwd), shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding='utf-8', errors='replace'
        )
        full_log = ""
        for line in iter(process.stdout.readline, ''):
            full_log += line
            if log_container:
                log_container.code(full_log, language="bash")
        process.stdout.close()
        return process.wait() == 0
    except Exception as e:
        if log_container: log_container.error(f"Error: {e}")
        return False

def generate_dynamic_compose(repos):
    services_block = ""
    for repo in repos:
        name = repo["name"]
        
        # SMART DEPENDENCIES: Only wait for what you need
        depends_on = []
        if name == "datasource":
            depends_on = ["postgres"]
        elif name in ["ingestor", "ai-core"]:
            depends_on = ["kafka"]
        # UI has 0 dependencies to start fast
            
        depends_block = ""
        if depends_on:
            depends_block = "    depends_on:\n" + "\n".join([f"      - {dep}" for dep in depends_on])

        services_block += f"""
  {name}:
    build:
      context: ./services/{name}
      args:
        SERVICE_NAME: {name}
    env_file: .env
    networks: [org-network]
{depends_block}
"""
    return f"""networks:
  org-network:
    driver: bridge
volumes:
  postgres_data:
  kafka_data:
  zookeeper_data:
  app_logs:
services:
  # --- INFRASTRUCTURE ---
  postgres:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    networks: [org-network]
    environment:
      POSTGRES_USER: ${{POSTGRES_USER}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
      POSTGRES_DB: my_org_db
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - zookeeper_data:/var/lib/zookeeper/data
      - zookeeper_data:/var/lib/zookeeper/log
    networks: [org-network]

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    volumes:
      - kafka_data:/var/lib/kafka/data
    depends_on:
      - zookeeper
    networks: [org-network]

  # --- MICROSERVICES ---
{services_block}
"""

# --- MAIN APP ---

def main():
    st.set_page_config(page_title="DevOps Orchestrator", page_icon="🚀", layout="wide")
    
    if 'logs' not in st.session_state: st.session_state.logs = "Waiting for start..."
    if 'last_update' not in st.session_state: st.session_state.last_update = "Never"

    st.title("🚀 DevOps Orchestrator")
    
    # Tabs
    tab_dash, tab_logs = st.tabs(["🎛️ Controls & Status", "📜 Execution Logs"])
    
    # Calculate status once
    current_status = get_status(WORK_DIR)

    # --- TAB 1: DASHBOARD ---
    with tab_dash:
        
        # --- COMMAND CENTER ---
        with st.container(border=True):
            # 1. Header & Refresh
            c_head, c_ref = st.columns([5, 1])
            with c_head:
                st.subheader("🎛️ Control Panel")
            with c_ref:
                if st.button("🔄 Refresh", use_container_width=True, help=f"Last updated: {st.session_state.last_update}"):
                    st.session_state.last_update = get_timestamp()
                    st.rerun()

            # 2. Configuration (Branches)
            branch_map = {}
            with st.expander("⚙️ Repository Configuration (Branches)", expanded=False):
                # Dynamic columns based on repo count (clamped to 4 per row if needed)
                cols = st.columns(len(REPOS))
                for idx, repo in enumerate(REPOS):
                    with cols[idx]:
                        branch_map[repo['name']] = st.text_input(
                            f"{repo['name']}", 
                            value="main",
                            key=f"branch_{repo['name']}",
                            help=f"Target branch for {repo['name']}"
                        )

            # 3. Actions
            st.markdown("---")
            c_start, c_stop, c_nuke = st.columns(3)
            
            with c_start:
                if st.button("▶ Initialize & Start", type="primary", use_container_width=True):
                    with st.spinner("Orchestrating..."):
                        run_bootstrap(branch_map)
            
            with c_stop:
                if st.button("⏹ Stop Services", use_container_width=True):
                    stop_services()
                    
            with c_nuke:
                if st.button("💀 Hard Reset", type="secondary", use_container_width=True, help="⚠️ WARNING: Deletes 'prod' folder and rebuilds everything."):
                    nuke_and_rebuild(branch_map)

        st.markdown("") # Spacer

        # Alerts (Minimalist)
        if not current_status['docker']:
            st.error("Docker Engine is OFF. Please start Docker Desktop.", icon="🛑")
        elif current_status["alerts"]:
            st.warning(f"{len(current_status['alerts'])} Issue(s) Detected. Check Logs tab.", icon="⚠️")

        # Infrastructure
        st.subheader("Infrastructure")
        ic1, ic2, ic3 = st.columns(3)
        
        # Helper to style cards
        def status_card(col, title, status_text, is_healthy):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    if is_healthy: st.success(status_text)
                    else: st.error(status_text)

        status_card(ic1, "🐳 Docker Engine", "Active" if current_status['docker'] else "Offline", current_status['docker'])
        
        db_ok = "Running" in current_status["containers"].get("database", "")
        status_card(ic2, "🐘 Database", "Healthy" if db_ok else "Not Ready", db_ok)
        
        k_ok = "Running" in current_status["containers"].get("kafka", "")
        status_card(ic3, "🕸️ Kafka Cluster", "Healthy" if k_ok else "Not Ready", k_ok)

        st.markdown("### Microservices")
        cols = st.columns(4) # More compact grid
        for idx, repo in enumerate(REPOS):
            name = repo['name']
            col = cols[idx % 4]
            
            with col:
                with st.container(border=True):
                    st.markdown(f"**{name.title()}**")
                    
                    # Status logic
                    repo_d = current_status["repos"].get(name, {})
                    cont_s = current_status["containers"].get(name, "Not Created")
                    
                    if repo_d.get("status") == "Mock":
                        st.warning("⚠️ Mock Mode")
                    elif repo_d.get("status") == "Valid":
                        st.success("✅ Code Ready")
                    else:
                        st.error(f"❌ {repo_d.get('status', 'Error')}")
                        
                    if "Running" in cont_s:
                        st.caption("🟢 Container Up")
                    else:
                        st.caption(f"🔴 {cont_s}")

    # --- TAB 2: LOGS ---
    with tab_logs:
        st.markdown("### 📜 System Logs & Trace")
        
        # Detailed Alerts Section
        if current_status["alerts"]:
            with st.container(border=True):
                st.markdown("#### 🚨 Active Alerts")
                for alert in current_status["alerts"]:
                    st.error(alert, icon="⚠️")
        
        # Log Terminal
        st.text_area("Execution Output", value=st.session_state.logs, height=600, disabled=True)

# --- LOGIC ---

def nuke_and_rebuild(branch_map):
    st.session_state.logs += "\n💥 NUKING ENVIRONMENT..."
    try:
        if WORK_DIR.exists():
            # -v flag destroys volumes (fixes Zookeeper data corruption)
            subprocess.run("docker compose down -v", shell=True, cwd=WORK_DIR)
            
            def on_rm_error(func, path, exc_info):
                os.chmod(path, 0o777)
                os.remove(path)
            shutil.rmtree(WORK_DIR, onerror=on_rm_error)
            
        st.success("Wiped (including volumes). Re-initializing...")
        time.sleep(1)
        run_bootstrap(branch_map)
    except Exception as e:
        st.error(f"Reset Failed: {e}")

def run_bootstrap(branch_map):
    st.session_state.last_update = get_timestamp()
    logs = f"--- STARTED AT {get_timestamp()} ---\n"
    
    def log(msg):
        nonlocal logs
        logs += f"{msg}\n"
        st.session_state.logs = logs

    if not check_docker_engine():
        log("❌ CRITICAL: Docker Daemon is not running.")
        return

    try:
        # Directory
        if not WORK_DIR.exists():
            log(f"📂 Creating: {WORK_DIR}")
            WORK_DIR.mkdir(parents=True, exist_ok=True)
            (WORK_DIR / "services").mkdir(exist_ok=True)
            (WORK_DIR / "_failsafe").mkdir(exist_ok=True)

        # Compose
        compose_file = WORK_DIR / "docker-compose.yml"
        log("📄 Generating docker-compose.yml...")
        with open(compose_file, "w", encoding="utf-8") as f:
            f.write(generate_dynamic_compose(REPOS))

        # Mock
        mock_file = WORK_DIR / "_failsafe" / "Dockerfile.mock"
        mock_content = """FROM alpine:latest
ARG SERVICE_NAME
RUN echo "⚠️ FAILSAFE MODE: Service [$SERVICE_NAME] is running as a placeholder."
CMD ["sh", "-c", "while true; do echo 💤 [$SERVICE_NAME] Sleeping (Failsafe Mode)...; sleep 30; done"]
"""
        mock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(mock_file, "w", encoding="utf-8") as f:
            f.write(mock_content)

        # Repos
        for repo in REPOS:
            name = repo["name"]
            url = repo["url"]
            path = WORK_DIR / "services" / name
            dockerfile = path / "Dockerfile"
            target_branch = branch_map.get(name, "main")
            
            if not path.exists(): path.mkdir(parents=True, exist_ok=True)

            if path.exists() and any(path.iterdir()) and not (path / ".git").exists():
                log(f"⚠️ {name} corrupt. Wiping.")
                shutil.rmtree(path)
                path.mkdir(parents=True, exist_ok=True)

            if not (path / ".git").exists():
                log(f"⬇️ Cloning {name} ({target_branch})...")
                # FIX: Explicit encoding
                subprocess.run(f'git clone -b {target_branch} {url} "{path}"', shell=True, cwd=WORK_DIR, encoding='utf-8', errors='replace')
            else:
                if is_mock_file(dockerfile):
                    log(f"🔄 Swapping Mock -> Real ({name})...")
                    try: os.remove(dockerfile)
                    except: pass
                log(f"🔄 Updating {name} to '{target_branch}'...")
                # FIX: Explicit encoding
                subprocess.run("git fetch origin", shell=True, cwd=path, encoding='utf-8', errors='replace')
                subprocess.run(f"git checkout {target_branch}", shell=True, cwd=path, encoding='utf-8', errors='replace')
                stream_command(f"git pull origin {target_branch}", path, None)

            if not dockerfile.exists():
                log(f"⚠️ {name} missing Dockerfile. Using Mock.")
                shutil.copy(mock_file, dockerfile)
            elif is_mock_file(dockerfile):
                log(f"ℹ️ {name} using Mock.")
            else:
                log(f"✅ {name} Valid.")

        # Env
        if not (WORK_DIR / ".env").exists():
            with open(WORK_DIR / ".env", "w", encoding="utf-8") as f:
                f.write("ENV=dev\nPOSTGRES_USER=admin\nPOSTGRES_PASSWORD=secret")

        # Docker
        log("🐳 Starting Docker Compose...")
        # FIX: Explicit encoding and errors='replace' to avoid crash on special characters
        res = subprocess.run("docker compose up -d --build --remove-orphans", shell=True, cwd=WORK_DIR, capture_output=True, text=True, encoding='utf-8', errors='replace')
        log(res.stdout)
        if res.returncode == 0:
            log("✅ ENVIRONMENT UP!")
            st.toast("System Online", icon="✅")
        else:
            log("❌ DOCKER FAIL")
            log(res.stderr)
            st.error("Docker Failed. See Logs.")

    except Exception as e:
        log(f"❌ ERROR: {e}")
        st.error(f"System Error: {e}")
    
    time.sleep(1)
    st.rerun()

def stop_services():
    st.session_state.last_update = get_timestamp()
    if (WORK_DIR / "docker-compose.yml").exists():
        subprocess.run("docker compose down", shell=True, cwd=WORK_DIR)
        st.toast("Stopped", icon="🛑")
        st.session_state.logs += f"\n[{get_timestamp()}] Services Stopped."
        time.sleep(1)
        st.rerun()

if __name__ == "__main__":
    main()
