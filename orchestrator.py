import os
import shutil
import subprocess
import time
from pathlib import Path
from core.config import REPOS, SERVICES, WORK_DIR, INIT_SQL, MOCK_DOCKERFILE, DEFAULT_ENV
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

        # Detect mode (local vs remote)
        is_local = False
        mode_file = WORK_DIR / ".mode"
        if mode_file.exists():
            is_local = mode_file.read_text().strip() == "local"

        # Check Repos (4 repos)
        project_root = WORK_DIR.parent.parent
        for repo in REPOS:
            name = repo["name"]
            # In local mode, code lives at project root; in remote, under prod/services/
            path = (project_root / name) if is_local else (WORK_DIR / "services" / name)

            r_state = {"status": "Unknown", "msg": ""}
            if not path.exists():
                r_state = {"status": "Missing", "msg": "Not found"}
            elif name == "ingestor":
                # Ingestor has sub-Dockerfiles, not a root one
                if (path / "api_gateway" / "Dockerfile").exists():
                    r_state = {"status": "Valid", "msg": "Codebase Active"}
                elif utils.is_mock_file(path / "Dockerfile"):
                    r_state = {"status": "Mock", "msg": "Failsafe Mode"}
                    status["alerts"].append(f"{name}: Running in Mock Mode")
                else:
                    r_state = {"status": "Corrupt", "msg": "No Dockerfile"}
                    status["alerts"].append(f"{name}: Missing Dockerfile")
            else:
                dockerfile = path / "Dockerfile"
                if utils.is_mock_file(dockerfile):
                    r_state = {"status": "Mock", "msg": "Failsafe Mode"}
                    status["alerts"].append(f"{name}: Running in Mock Mode")
                elif dockerfile.exists():
                    r_state = {"status": "Valid", "msg": "Codebase Active"}
                else:
                    r_state = {"status": "Corrupt", "msg": "No Dockerfile"}
                    status["alerts"].append(f"{name}: Missing Dockerfile")

            status["repos"][name] = r_state

        # Check Containers (6 services + infra)
        if status["docker"]:
            raw_status = docker_ops.get_containers_status(WORK_DIR)

            status["containers"]["database"] = raw_status.get("postgres", "Not Created")
            status["containers"]["kafka"] = raw_status.get("kafka", "Not Created")
            status["containers"]["pgadmin"] = raw_status.get("pgadmin", "Not Created")
            status["containers"]["kafka-ui"] = raw_status.get("kafka-ui", "Not Created")

            for svc in SERVICES:
                status["containers"][svc["name"]] = raw_status.get(svc["name"], "Not Created")

        return status

    def bootstrap_environment(self, branch_map, use_local=False):
        self.log(f"Starting Bootstrap on {WORK_DIR} (Local: {use_local})...")

        # 1. Scaffold Directories
        self.log("Creating directory structure...")
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

        # 3. Generate Compose with correct build contexts
        self.log("Generating docker-compose.yml...")
        with open(WORK_DIR / "docker-compose.yml", "w", encoding="utf-8") as f:
            f.write(docker_ops.generate_compose_file(SERVICES, use_local=use_local))

        # 4. Git Operations (remote mode) or Validate Local Repos
        if use_local:
            # Local mode: compose points directly to project dirs, no cloning needed
            project_root = WORK_DIR.parent.parent
            for repo in REPOS:
                name = repo["name"]
                local_src = project_root / name
                if local_src.exists() and local_src.is_dir():
                    self.log(f"Using local: {name} ({local_src})")
                else:
                    self.log(f"WARNING: Local source for {name} not found at {local_src}")
        else:
            # Remote mode: clone repos into prod/services/
            for repo in REPOS:
                name = repo["name"]
                branch = branch_map.get(name, "main")
                path = WORK_DIR / "services" / name
                git_ops.clone_or_update(name, repo["url"], path, branch, self.log)

                # Inject Mock if needed (skip for ingestor - it has sub-Dockerfiles)
                if name != "ingestor":
                    dockerfile = path / "Dockerfile"
                    if not dockerfile.exists():
                        self.log(f"{name} has no Dockerfile. Injecting Mock.")
                        shutil.copy(mock_path, dockerfile)

        # 5. Write .env (always overwrite to ensure correct DB name)
        self.log("Writing .env configuration...")
        with open(WORK_DIR / ".env", "w", encoding="utf-8") as f:
            f.write(DEFAULT_ENV)

        # Store mode marker for health checks
        with open(WORK_DIR / ".mode", "w") as f:
            f.write("local" if use_local else "remote")

        # 6. Docker Launch
        self.log("Starting Docker Compose...")
        success = utils.stream_command(
            "docker compose up -d --build --remove-orphans",
            WORK_DIR,
            self.log
        )

        if not success:
            return False

        # 7. Seed Database (idempotent — safe to run every time)
        # Docker's /docker-entrypoint-initdb.d/ only runs on first init (empty data dir).
        # We explicitly execute init.sql after postgres is healthy to guarantee schema + seed data.
        self._seed_database()

        return True

    def _seed_database(self):
        """Wait for postgres to be healthy, then execute init.sql inside the container.

        The init.sql is idempotent (IF NOT EXISTS + ON CONFLICT DO NOTHING),
        so this is safe to run on every bootstrap regardless of DB state.
        """
        self.log("Waiting for PostgreSQL to be ready...")
        for attempt in range(30):
            try:
                result = subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres",
                     "pg_isready", "-U", "admin", "-d", "noc_alerts"],
                    cwd=str(WORK_DIR),
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self.log("PostgreSQL is ready.")
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            self.log("WARNING: PostgreSQL did not become ready in 60s. Skipping DB seed.")
            return

        self.log("Seeding database with init.sql...")
        init_sql_path = WORK_DIR / "postgres-init" / "init.sql"
        success = utils.stream_command(
            f"docker compose exec -T postgres psql -U admin -d noc_alerts < \"{init_sql_path}\"",
            WORK_DIR,
            self.log
        )
        if success:
            self.log("Database seeded successfully.")
        else:
            self.log("WARNING: Database seeding returned errors (may be non-fatal).")

    def nuke(self):
        self.log("NUKING ENVIRONMENT...")
        if WORK_DIR.exists():
            utils.stream_command("docker compose down -v", WORK_DIR, self.log)
            def on_rm_error(func, path, exc_info):
                os.chmod(path, 0o777)
                os.remove(path)
            shutil.rmtree(WORK_DIR, onerror=on_rm_error)
        self.log("Wiped successfully.")

    def stop(self):
        if WORK_DIR.exists():
            utils.stream_command("docker compose down", WORK_DIR, self.log)
