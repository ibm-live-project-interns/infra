import os
import shutil
from pathlib import Path
from core.config import REPOS, WORK_DIR, INIT_SQL, MOCK_DOCKERFILE
from core import docker_ops, git_ops, utils

class DevOpsManager:
    def __init__(self, log_callback=None):
        self.log = log_callback if log_callback else print

    def check_health(self):
        """Aggregates all status checks into one state object."""
        status = {
            "docker": docker_ops.check_engine(),
            "repos": {},
            "containers": {},
            "alerts": []
        }
        
        if not status["docker"]:
            status["alerts"].append("CRITICAL: Docker Daemon is down.")

        # Check Repos
        for repo in REPOS:
            name = repo["name"]
            path = WORK_DIR / "services" / name
            dockerfile = path / "Dockerfile"
            
            r_state = {"status": "Unknown", "msg": ""}
            if not path.exists():
                r_state = {"status": "Missing", "msg": "Not found"}
            elif utils.is_mock_file(dockerfile):
                r_state = {"status": "Mock", "msg": "Failsafe Mode"}
                status["alerts"].append(f"{name}: Running in Mock Mode")
            elif dockerfile.exists():
                r_state = {"status": "Valid", "msg": "Codebase Active"}
            else:
                r_state = {"status": "Corrupt", "msg": "No Dockerfile"}
                status["alerts"].append(f"{name}: Missing Dockerfile")
            
            status["repos"][name] = r_state

        # Check Containers
        if status["docker"]:
            raw_status = docker_ops.get_containers_status(WORK_DIR)
            
            # --- FIX: Explicitly map Infrastructure Services ---
            status["containers"]["database"] = raw_status.get("postgres", "Not Created")
            status["containers"]["kafka"] = raw_status.get("kafka", "Not Created")
            # MAPPING ADDED HERE:
            status["containers"]["pgadmin"] = raw_status.get("pgadmin", "Not Created")
            status["containers"]["kafka-ui"] = raw_status.get("kafka-ui", "Not Created")
            
            # Map App Services
            for repo in REPOS:
                status["containers"][repo["name"]] = raw_status.get(repo["name"], "Not Created")

        return status

    def bootstrap_environment(self, branch_map, use_local=False):
        self.log(f"🚀 Starting Bootstrap on {WORK_DIR} (Local Mode: {use_local})...")
        
        # 1. Scaffold Directories
        if not WORK_DIR.exists():
            self.log("📂 Creating directory structure...")
            WORK_DIR.mkdir(parents=True, exist_ok=True)
            (WORK_DIR / "services").mkdir(exist_ok=True)
            (WORK_DIR / "_failsafe").mkdir(exist_ok=True)
            (WORK_DIR / "postgres-init").mkdir(exist_ok=True)

        # 2. Write Static Files (Init SQL & Mock)
        with open(WORK_DIR / "postgres-init" / "init.sql", "w", encoding="utf-8") as f:
            f.write(INIT_SQL)
        
        mock_path = WORK_DIR / "_failsafe" / "Dockerfile.mock"
        with open(mock_path, "w", encoding="utf-8") as f:
            f.write(MOCK_DOCKERFILE)

        # 3. Generate Compose
        self.log("📄 Generating docker-compose.yml...")
        with open(WORK_DIR / "docker-compose.yml", "w", encoding="utf-8") as f:
            f.write(docker_ops.generate_compose_file(REPOS, use_local=use_local))

        # 4. Git Operations (Clone/Update)
        for repo in REPOS:
            name = repo["name"]
            branch = branch_map.get(name, "main")
            path = WORK_DIR / "services" / name
            
            # 4. Git Operations (Clone/Update) OR Local Link
            if use_local:
                 # Check if local folder exists in project root (../../name)
                 project_root = WORK_DIR.parent.parent
                 local_src = project_root / name
                 
                 if local_src.exists() and local_src.is_dir():
                     self.log(f"🔗 Linking Local Source: {name} -> {path}")
                     # Remove existing directory/link if present
                     if path.exists(follow_symlinks=False):
                         if path.is_symlink(): path.unlink()
                         else: shutil.rmtree(path)
                     
                     # Create Symlink
                     os.symlink(local_src, path)
                 else:
                     self.log(f"⚠️ Local source for {name} not found at {local_src}. Falling back to Git.")
                     git_ops.clone_or_update(name, repo["url"], path, branch, self.log)
            else:
                git_ops.clone_or_update(name, repo["url"], path, branch, self.log)
            
            # Inject Mock if needed
            dockerfile = path / "Dockerfile"
            if not dockerfile.exists():
                self.log(f"⚠️ {name} has no Dockerfile. Injecting Mock.")
                shutil.copy(mock_path, dockerfile)

        # 5. Env File
        if not (WORK_DIR / ".env").exists():
            with open(WORK_DIR / ".env", "w", encoding="utf-8") as f:
                f.write("ENV=dev\nPOSTGRES_USER=admin\nPOSTGRES_PASSWORD=secret\nPOSTGRES_DB=my_org_db")

        # 6. Docker Launch
        self.log("🐳 Starting Docker Compose (Streaming)...")
        success = utils.stream_command(
            "docker compose up -d --build --remove-orphans", 
            WORK_DIR, 
            self.log
        )
        
        return success

    def nuke(self):
        self.log("💥 NUKING ENVIRONMENT...")
        if WORK_DIR.exists():
            utils.stream_command("docker compose down -v", WORK_DIR, self.log)
            def on_rm_error(func, path, exc_info):
                os.chmod(path, 0o777)
                os.remove(path)
            shutil.rmtree(WORK_DIR, onerror=on_rm_error)
        self.log("✅ Wiped successfully.")

    def stop(self):
        if WORK_DIR.exists():
            utils.stream_command("docker compose down", WORK_DIR, self.log)