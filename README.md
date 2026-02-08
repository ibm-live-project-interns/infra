

# 🚀 DevOps Orchestrator

A **Zero-Config Bootstrap Tool** that automates the setup of our NOC Platform Microservices environment (Go, React, Kafka, Postgres) with AI-powered alert management.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-ff4b4b)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Go](https://img.shields.io/badge/Go-1.23-00ADD8)
![React](https://img.shields.io/badge/React-18-61DAFB)

---

## ⚠️ Prerequisites (Check Before Running)

1. [ ] **Docker Desktop:** Must be installed and **Running** in the background (check system tray/taskbar icon).
2. [ ] **Git Authentication:** You must be logged into GitHub. Credential manager must be configured so `git clone` works without password prompts.
3. [ ] **Python:** Version 3.10 or higher.
4. [ ] **Docker Resources:** Minimum 4GB RAM and 2 CPU cores allocated to Docker.

---

## ⚡ Quick Start

### 1. Installation
Navigate to the tool directory and install the UI framework:

```bash
pip install streamlit

```

### 2. Run the Orchestrator

Launch the dashboard:

```bash
streamlit run app.py
```

### 3. Alternative: Run with Python Scripts

For local development with your code:

```bash
python run_local.py
```

For production deployment from GitHub:

```bash
python run_headless.py
```

---

## 🎮 One-Liner User Guide

| Goal | Streamlit UI | Python CLI |
| --- | --- | --- |
| **Start Environment** | Click **▶ Initialize & Start** on the dashboard | `python run_headless.py` or `python run_local.py` |
| **Stop Environment** | Click **⏹ Stop** | `cd prod && docker compose down` |
| **Fix Broken State** | Click **💀 Hard Reset** | `cd prod && docker compose down -v` |
| **Change Branch** | Open **⚙️ Repository Config**, select branch | Edit `branch_map` in run_headless.py |
| **View Logs** | Check dashboard status panel | `cd prod && docker compose logs -f [service]` |

---

## 🔗 Access Points & Credentials

Once all services are running (Green status), access these endpoints:

### User Interfaces
* **React Frontend:** [http://localhost:3000](http://localhost:3000)
  - NOC Alert Dashboard
  - Priority Alerts View
  - Device Monitoring

* **Kafka UI:** [http://localhost:8090](http://localhost:8090)
  - View Kafka topics (ingestion-events)
  - Monitor message flow
  - Inspect event payloads

* **PgAdmin (Database UI):** [http://localhost:5050](http://localhost:5050)
  - **Login:** `admin@admin.com` / `root`
  - **DB Connection:**
    - Host: `postgres`
    - Port: `5432`
    - Database: `my_org_db`
    - Username: `admin`
    - Password: `secret`

### API Endpoints
* **API Gateway:** [http://localhost:8080](http://localhost:8080)
  - `/api/v1/alerts` - Get all alerts
  - `/api/v1/alerts/:id` - Get specific alert
  - `/api/v1/alerts/summary` - Get alert summary
  - `/api/v1/ai/metrics` - Get AI metrics
  - `/api/v1/ai/insights` - Get AI insights and recommendations
  - `/api/v1/devices` - Get devices
  - `/api/v1/devices/noisy` - Get noisy devices

* **Ingestor Core:** [http://localhost:8001](http://localhost:8001)
  - `/ingest/event` - Ingest events (POST)
  - `/health` - Health check

* **Event Router:** [http://localhost:8082](http://localhost:8082)
  - `/route` - Route events (POST)
  - `/health` - Health check

---

## 📂 Architecture

### System Components

```
NOC Platform
├── Infrastructure Services
│   ├── postgres (PostgreSQL 15) - Port 5432
│   ├── pgadmin (Database UI) - Port 5050
│   ├── zookeeper (Kafka coordination) - Port 2181
│   ├── kafka (Message broker) - Port 9092
│   └── kafka-ui (Kafka management) - Port 8090
│
├── Backend Microservices (Go)
│   ├── datasource - Event data generator
│   ├── api-gateway - REST API & frontend proxy - Port 8080
│   ├── ingestor-core - Event ingestion pipeline - Port 8001
│   ├── event-router - Event routing & Kafka publishing - Port 8082
│   └── ai-core - IBM Watson AI integration - Port 9000
│
└── Frontend (React + Vite)
    └── ui - Dashboard & Alert UI - Port 3000
```

### Orchestrator Architecture

```text
infra/
├── app.py                 # Streamlit UI Layer
├── run_headless.py        # Production bootstrap (GitHub repos)
├── run_local.py           # Development bootstrap (local code)
├── orchestrator.py        # State Management & Lifecycle
├── core/
│   ├── docker_ops.py      # Docker Compose generation & monitoring
│   ├── git_ops.py         # Git clone & branch switching
│   └── config.py          # Service definitions & config
└── prod/                  # Generated deployment folder
    ├── docker-compose.yml # Auto-generated compose file
    ├── .env               # Environment variables
    └── postgres-init/     # Database initialization scripts
        └── init.sql       # Schema & sample data
```

---

## 🔄 Event Processing Flow

```
Event Source (datasource)
    ↓ HTTP POST
Ingestor Core (:8001)
    ↓ Normalize, Validate, Enrich
Event Router (:8082)
    ↓ Route & Publish
Kafka (ingestion-events topic)
    ↓ Consume
AI Core (:9000) - IBM Watson Analysis
    ↓ Enriched Alerts
API Gateway (:8080)
    ↓ REST API
Frontend UI (:3000) / PgAdmin (:5050)
```

---

## 🗄️ Database Schema

The postgres-init script automatically creates:

**Tables:**
- `alerts` - Network alerts with AI analysis
- `devices` - Monitored network devices
- `ai_metrics` - AI performance metrics
- `ingestion_data` - Raw event data
- `ai_results` - AI analysis results
- `alert_history` - Alert change tracking

**Sample Data:**
- 4 alerts (critical, major, minor, info)
- 4 devices (switch, firewall, router, load balancer)
- 4 AI metrics (Resolution Time, Escalations, Accuracy, Auto-Resolved)

---

## 🤖 AI Integration

The ai-core service uses **IBM Watson AI** (watsonx) for real-time alert analysis:

**Model:** `ibm/granite-3-8b-instruct`
**Features:**
- Automatic severity classification
- Natural language explanations
- Recommended actions
- Confidence scoring

**Configuration:**
Set these environment variables in `infra/prod/.env`:
```bash
WATSONX_API_KEYS=your_api_key_here
WATSONX_PROJECT_ID=your_project_id
WATSONX_REGION=eu-gb
```

---

## 🐛 Troubleshooting

| Issue | Solution |
| --- | --- |
| **Containers exiting** | Run `docker compose down -v` to clean volumes, then restart |
| **Database connection errors** | Check postgres is healthy: `docker compose ps postgres` |
| **Kafka topics not showing** | Send a test event to create topics (see API endpoints) |
| **UI build failures** | Increase Docker RAM to 4GB+ |
| **Port conflicts** | Check no other services using ports 3000, 5432, 8080, 8090, 9092 |

---

## 📝 Development Notes

### Running Locally
Use `run_local.py` to link your local code directories:
- Creates symbolic links from `../ui`, `../ai-core`, etc. to `prod/services/`
- Hot-reload changes without rebuilding Docker images

### Production Deployment
Use `run_headless.py` to clone from GitHub:
- Clones all repositories into `prod/services/`
- Can switch branches via branch_map configuration

---

## 🔍 Service Status

Check service health:
```bash
cd infra/prod
docker compose ps
docker compose logs -f [service-name]
```

All services expose `/health` endpoints for monitoring.

