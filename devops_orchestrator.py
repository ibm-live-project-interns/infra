import streamlit as st
import subprocess
import os
import time
import shutil
import datetime
from pathlib import Path

# --- CONFIGURATION ---
# Setup relative to the current script location
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
    """Checks if the Dockerfile is our generated mock."""
    try:
        if not file_path.exists(): return False
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return "FAILSAFE MODE" in content
    except:
        return False

def get_status(work_dir):
    """Checks the health of the environment and generates alerts."""
    status = {
        "docker": False,
        "repos": {},
        "containers": {},
        "alerts": [] # Store validation errors here
    }

    # 1. Docker Engine Check
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status["docker"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        status["docker"] = False

    # 2. Repository Folder Check
    for repo in REPOS:
        name = repo["name"]
        repo_path = work_dir / "services" / name
        dockerfile = repo_path / "Dockerfile"
        
        if not repo_path.exists():
             status["repos"][name] = "❌ Missing"
             status["alerts"].append(f"**{name}**: Folder missing entirely.")
        elif not (repo_path / ".git").exists():
             status["repos"][name] = "⚠️ Not a Git Repo"
             # We don't alert here if it has a Dockerfile, might be local code
        
        if is_mock_file(dockerfile):
            status["repos"][name] = "⚠️ Mock Active"
            if not (repo_path / ".git").exists():
                reason = "Repository clone failed or missing."
            else:
                reason = "Repository exists but missing valid 'Dockerfile'."
            status["alerts"].append(f"**{name}**: Running Mock. Reason: {reason}")
            
        elif dockerfile.exists():
             status["repos"][name] = "✅ Valid Code"
        else:
            status["repos"][name] = "❓ Corrupt"
            status["alerts"].append(f"**{name}**: Repository corrupt (No Dockerfile found).")

    # 3. Container Status Check
    if (work_dir / "docker-compose.yml").exists():
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "-a"], 
                cwd=work_dir, capture_output=True, text=True
            )
            output = result.stdout
            
            for repo in REPOS:
                name = repo["name"]
                if name in output and "Up" in output:
                    status["containers"][name] = "🟢 Running"
                elif name in output:
                    status["containers"][name] = "🔴 Stopped"
                else:
                    status["containers"][name] = "⚪ Not Created"
            
            if "postgres" in output and "Up" in output:
                 status["containers"]["database"] = "🟢 Running"
            else:
                 status["containers"]["database"] = "⚪ Not Created"
                 
        except Exception:
            pass
            
    return status

def stream_command(cmd, cwd, log_container):
    """Runs a shell command and streams output."""
    if not cwd.exists():
        log_container.error(f"❌ Path not found: {cwd}")
        return False

    try:
        # Merge stderr into stdout to capture errors
        process = subprocess.Popen(
            cmd, cwd=str(cwd), shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding='utf-8'
        )
        full_log = ""
        for line in iter(process.stdout.readline, ''):
            full_log += line
            log_container.code(full_log, language="bash")
        process.stdout.close()
        return process.wait() == 0
    except Exception as e:
        log_container.error(f"❌ Error: {e}")
        return False

def generate_dynamic_compose(repos):
    """Generates a docker-compose.yml string based on the config list."""
    services_block = ""
    for repo in repos:
        name = repo["name"]
        services_block += f"""
  {name}:
    build:
      context: ./services/{name}
      args:
        SERVICE_NAME: {name}
    env_file: .env
    networks: [org-network]
"""
    # Postgres is always included as core infra
    return f"""version: '3.8'
networks:
  org-network:
    driver: bridge
volumes:
  postgres_data:
  app_logs:
services:
  postgres:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    networks: [org-network]
    environment:
      POSTGRES_USER: ${{POSTGRES_USER}}
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
      POSTGRES_DB: my_org_db
    volumes: ["postgres_data:/var/lib/postgresql/data"]
{services_block}
"""

# --- MAIN APP UI ---

def main():
    st.set_page_config(page_title="DevOps Orchestrator", page_icon="🚀", layout="wide")
    
    st.title("🚀 DevOps Orchestrator")
    
    # Header Info
    col_info_1, col_info_2 = st.columns([3, 1])
    with col_info_1:
        st.markdown(f"**Target Environment:** `{WORK_DIR}`")
    with col_info_2:
        if 'last_updated' not in st.session_state:
            st.session_state.last_updated = get_timestamp()
        st.markdown(f"**Last Updated:** `{st.session_state.last_updated}`")

    if 'logs' not in st.session_state:
        st.session_state.logs = "Ready to initialize..."

    # --- STATUS DASHBOARD ---
    st.subheader("📊 Service Monitor")
    current_status = get_status(WORK_DIR)
    
    # Alert Banner for Mocks or Issues
    if current_status["alerts"]:
        for alert in current_status["alerts"]:
            st.warning(alert, icon="⚠️")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🐳 Engine")
        if current_status["docker"]: st.success("Docker Active")
        else: st.error("Docker Stopped")

    with c2:
        st.markdown("### 📦 Codebase")
        for name, state in current_status["repos"].items():
            color = "green" if "Valid" in state else "orange" if "Mock" in state else "red"
            st.markdown(f"**{name}**: :{color}[{state}]")

    with c3:
        st.markdown("### 🚢 Runtime")
        for name, state in current_status["containers"].items():
            st.write(f"**{name}:** {state}")
            
    st.divider()

    # --- ACTIONS ---
    c_act, c_log = st.columns([1, 2])

    with c_act:
        st.subheader("Controls")
        if st.button("▶ Initialize & Start", type="primary", use_container_width=True):
            run_bootstrap()
            
        if st.button("⏹ Stop Services", type="secondary", use_container_width=True):
            stop_services()
            
        if st.button("🔄 Refresh View", use_container_width=True):
            st.session_state.last_updated = get_timestamp()
            st.rerun()

    with c_log:
        st.subheader("📜 Live Logs")
        log_box = st.empty()
        log_box.code(st.session_state.logs, language="bash")

# --- ORCHESTRATION LOGIC ---

def run_bootstrap():
    log_ph = st.empty()
    logs = f"--- STARTED AT {get_timestamp()} ---\n"
    
    def log(msg):
        nonlocal logs
        logs += f"{msg}\n"
        log_ph.code(logs, language="bash")
        st.session_state.logs = logs

    # 1. Directory Setup
    if not WORK_DIR.exists():
        log(f"📂 Creating workspace: {WORK_DIR}")
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        (WORK_DIR / "services").mkdir(exist_ok=True)
        (WORK_DIR / "_failsafe").mkdir(exist_ok=True)

    # 2. Regenerate Docker Compose (Dynamic based on REPOS list)
    # We ALWAYS overwrite this to ensure config matches REPOS list
    compose_file = WORK_DIR / "docker-compose.yml"
    log("📄 Generating dynamic docker-compose.yml...")
    try:
        content = generate_dynamic_compose(REPOS)
        with open(compose_file, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        log(f"❌ Error writing compose file: {e}")
        return

    # 3. Generate Mock File
    mock_file = WORK_DIR / "_failsafe" / "Dockerfile.mock"
    mock_content = """FROM alpine:latest
ARG SERVICE_NAME
RUN echo "⚠️ FAILSAFE MODE: Service [$SERVICE_NAME] is running as a placeholder."
CMD ["sh", "-c", "while true; do echo 💤 [$SERVICE_NAME] Sleeping (Failsafe Mode)...; sleep 30; done"]
"""
    # Ensure failsafe dir exists (redundant safety check)
    mock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(mock_file, "w", encoding="utf-8") as f:
        f.write(mock_content)

    # 4. Repo Management (The "Swap" Logic)
    for repo in REPOS:
        name = repo["name"]
        url = repo["url"]
        path = WORK_DIR / "services" / name
        dockerfile = path / "Dockerfile"
        
        # Ensure service dir exists so we can put a mock there if needed
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        # A. Clone if missing .git
        if not (path / ".git").exists():
            log(f"⬇️ Cloning {name}...")
            # If dir exists but empty/mock, we might need to clone into it (or git init)
            # Simplest is: try clone. If fails (dir not empty), we rely on manual fix or git pull later.
            # Git clone to non-empty dir fails. 
            if any(path.iterdir()) and not (path / ".git").exists():
                 log(f"⚠️ Folder {name} exists but is not a git repo. Skipping clone.")
            else:
                 stream_command(f'git clone {url} "{path}"', WORK_DIR, log_ph)
        else:
            # B. If repo exists, try to update
            # SMART SWAP: If we are on Mock, delete it first so git pull doesn't conflict 
            if is_mock_file(dockerfile):
                log(f"🔄 Mock detected in {name}. Removing mock to allow update...")
                try:
                    os.remove(dockerfile) 
                except: pass
                
            log(f"🔄 Updating {name}...")
            stream_command("git pull", path, log_ph)

        # C. Final Validation & Injection
        if not dockerfile.exists():
            log(f"⚠️ No Dockerfile in {name}. Injecting Failsafe Mock.")
            shutil.copy(mock_file, dockerfile)
        elif is_mock_file(dockerfile):
            log(f"ℹ️ {name} is using Mock.")
        else:
            log(f"✅ {name} is valid.")

    # 5. Env File
    if not (WORK_DIR / ".env").exists():
        with open(WORK_DIR / ".env", "w", encoding="utf-8") as f:
            f.write("ENV=dev\nPOSTGRES_USER=admin\nPOSTGRES_PASSWORD=secret")

    # 6. Launch
    log("🐳 Building & Starting Containers...")
    success = stream_command("docker compose up -d --build --remove-orphans", WORK_DIR, log_ph)
    
    if success:
        log("✅ DONE! Environment is ready.")
        st.success("Services Updated & Running!")
        st.session_state.last_updated = get_timestamp()
        time.sleep(2)
        st.rerun()
    else:
        log("❌ Docker failed to start. Check logs above for details.")
        st.error("Infrastructure startup failed.")

def stop_services():
    log_ph = st.empty()
    if (WORK_DIR / "docker-compose.yml").exists():
        log_ph.code("Stopping...", language="bash")
        stream_command("docker compose down", WORK_DIR, log_ph)
        st.success("Services Stopped.")
        st.session_state.last_updated = get_timestamp()
        time.sleep(1)
        st.rerun()
    else:
        st.warning("Environment not found.")

if __name__ == "__main__":
    main()
