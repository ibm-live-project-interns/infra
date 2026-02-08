import subprocess
import json
from .config import REPOS

# Explicitly list infra services to check status for
# Added 'kafka-ui' and 'pgadmin'
INFRA_NAMES = ["postgres", "kafka", "zookeeper", "kafka-ui", "pgadmin"]

def check_engine():
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        return True
    except:
        return False

def generate_compose_file(repos, use_local=False):
    """Generates the Docker Compose YAML string."""
    services_block = ""
    for repo in repos:
        name = repo["name"]

        # Dependency Logic
        depends_on = []
        if name in ["datasource", "api-gateway"]:
            depends_on.append(("postgres", "service_healthy"))
        if name in ["api-gateway", "ingestor-core", "event-router", "ai-core"]:
            depends_on.append(("kafka", "service_healthy"))
        if name == "event-router":
            depends_on.append(("api-gateway", "service_started"))

        depends_block = ""
        if depends_on:
            conditions = []
            for dep, condition in depends_on:
                conditions.append(f"      {dep}:\n        condition: {condition}")
            depends_block = "    depends_on:\n" + "\n".join(conditions)

        # Ports
        ports_block = ""
        if "ports" in repo:
            ports_list = '", "'.join(repo["ports"])
            ports_block = f'    ports: [ "{ports_list}" ]\n'

        # Build context - use the repo's specified context and dockerfile
        context = repo.get("context", f"./services/{name}")
        dockerfile = repo.get("dockerfile", f"{name}/Dockerfile")

        build_block = f"""    build:
      context: {context}
      dockerfile: {dockerfile}"""

        services_block += f"""
  {name}:
{build_block}
    env_file: .env
    networks: [ org-network ]
    restart: on-failure
{ports_block}{depends_block}
"""
    return f"""networks:
  org-network:
    driver: bridge
volumes:
  postgres_data:
  kafka_data:
  zookeeper_data:
  pgadmin_data:
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
      POSTGRES_DB: ${{POSTGRES_DB}}
    volumes: 
      - postgres_data:/var/lib/postgresql/data
      - ./postgres-init:/docker-entrypoint-initdb.d
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${{POSTGRES_USER}} -d ${{POSTGRES_DB}}"]
      interval: 5s
      timeout: 5s
      retries: 5

  # GUI for Postgres
  pgadmin:
    image: dpage/pgadmin4:latest
    ports: ["5050:80"]
    environment:
      PGADMIN_DEFAULT_EMAIL: "admin@admin.com"
      PGADMIN_DEFAULT_PASSWORD: "root"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    networks: [org-network]
    depends_on:
      postgres:
        condition: service_healthy

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    ports: ["2181:2181"]
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - zookeeper_data:/var/lib/zookeeper/data
    networks: [org-network]
    healthcheck:
      test: echo srvr | nc localhost 2181 || exit 1
      interval: 5s
      timeout: 5s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports: ["9092:9092"]
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
      zookeeper:
        condition: service_healthy
    networks: [org-network]
    healthcheck:
      test: nc -z localhost 9092 || exit 1
      interval: 5s
      timeout: 5s
      retries: 10

  # GUI for Kafka
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    ports: ["8090:8080"]
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
      KAFKA_CLUSTERS_0_ZOOKEEPER: zookeeper:2181
    networks: [org-network]
    depends_on:
      kafka:
        condition: service_healthy

  # --- MICROSERVICES ---
{services_block}
"""

def get_containers_status(work_dir):
    """Returns a dict of service_name -> status"""
    status_map = {}
    
    if not (work_dir / "docker-compose.yml").exists():
        return status_map
        
    try:
        # Use JSON formatting
        res = subprocess.run(
            ["docker", "compose", "ps", "-a", "--format", "json"],
            cwd=work_dir, capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=5
        )
        
        output = res.stdout.strip()
        if output:
            containers = []
            
            # --- ROBUST PARSING LOGIC ---
            try:
                parsed = json.loads(output)
                if isinstance(parsed, list):
                    containers = parsed
                elif isinstance(parsed, dict):
                    containers = [parsed]
            except json.JSONDecodeError:
                for line in output.splitlines():
                    if line.strip():
                        try:
                            containers.append(json.loads(line))
                        except:
                            pass
            
            for c in containers:
                svc_name = c.get("Service")
                state = c.get("State", "").lower()
                
                # Normalization
                if state.startswith("up") or state == "running":
                    clean_state = "Running"
                elif "exited" in state:
                    clean_state = f"Stopped ({c.get('ExitCode', '?')})"
                else:
                    clean_state = state.title()

                # 1. Primary Match: Service Name
                if svc_name:
                    status_map[svc_name] = clean_state
                    
                # 2. Fallback Match: Container Name
                container_name = c.get("Name", "")
                
                for repo in REPOS:
                    if repo["name"] in container_name and repo["name"] not in status_map:
                        status_map[repo["name"]] = clean_state
                        
                for infra in INFRA_NAMES:
                    if infra in container_name and infra not in status_map:
                        status_map[infra] = clean_state
                            
    except Exception: 
        pass
        
    return status_map