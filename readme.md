# DevOps Orchestrator

Zero-config bootstrap tool for the NOC Platform microservices environment (Go, React, Kafka, Postgres).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-ff4b4b)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

---

## Prerequisites

1. **Docker Desktop** - installed and running
2. **Git** - authenticated with GitHub (credential manager configured)
3. **Python 3.10+**

---

## Quick Start

```bash
pip install streamlit
streamlit run app.py
```

Click **Initialize & Start** on the dashboard. That's it.

---

## What It Does

The orchestrator clones **4 repos** and spins up **6 microservices** + infrastructure.

After containers are healthy, it **automatically seeds the database** with the full schema (16 tables) and demo data — no manual SQL execution required.

| Repo | Docker Service(s) | Port |
|------|-------------------|------|
| `datasource` | datasource | - |
| `ingestor` | **api-gateway**, **event-router**, **ingestor-core** | 8080, 8082, 8001 |
| `ai-core` | ai-core | - |
| `ui` | ui | 3000 |

Plus infrastructure: Postgres (5432), Kafka (9092), PgAdmin (5050), Kafka UI (8090), Zookeeper (2181).

---

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| React Frontend | http://localhost:3000 | `admin@admin.com` / `admin123` |
| API Gateway | http://localhost:8080 | JWT auth |
| PgAdmin | http://localhost:5050 | `admin@admin.com` / `root` |
| Kafka UI | http://localhost:8090 | - |

**PgAdmin DB connection:** Host: `postgres`, User: `admin`, Password: `secret`, DB: `noc_alerts`

---

## Controls

| Goal | Action |
|------|--------|
| Start Environment | Click **Initialize & Start** (clones repos, builds images, starts containers) |
| Stop Environment | Click **Stop** (graceful shutdown) |
| Fix Broken State | Click **Hard Reset** (wipes `prod/` folder, destroys volumes, rebuilds) |
| Change Branch | Open **Repository Config**, set branch names, then click Start |

---

## Database

The orchestrator auto-seeds the database after containers start (Step 7 in bootstrap). The init.sql is **fully idempotent** (`CREATE TABLE IF NOT EXISTS` + `INSERT ... ON CONFLICT DO NOTHING`), so it's safe to run on every bootstrap regardless of DB state.

**16 tables**: `ingestion_data`, `ai_results`, `alerts`, `alert_history`, `devices`, `ai_metrics`, `users`, `sessions`, `api_keys`, `tickets`, `ticket_comments`, `threshold_rules`, `notification_channels`, `escalation_policies`, `maintenance_windows`, `audit_logs`

**Seed data**: 10 alerts with AI analysis, 10 devices, 6 tickets with comments, 5 threshold rules, 3 notification channels, 2 escalation policies, 2 maintenance windows, 1 admin user

Default admin user: `admin@admin.com` / `admin123` (role: `sysadmin`)

> **Note**: Docker's `/docker-entrypoint-initdb.d/` only runs on first init (empty data dir). The orchestrator bypasses this limitation by piping init.sql directly via `docker compose exec -T postgres psql` after postgres is healthy.

---

## Kafka Integration

Kafka is the message bus between the ingestor pipeline and the AI core. The orchestrator auto-creates the Kafka cluster with auto-topic creation enabled.

### Topic

- **`ingestion-events`** - main topic for normalized events flowing from ingestor to AI

### Connecting Your Service to Kafka

Every service gets `KAFKA_BROKER=kafka:9092` via the shared `.env`. If you need to add a new service that connects to Kafka, create a `docker-compose.yml` in your repo:

```yaml
version: '3.8'
services:
  app:
    build: .
    container_name: my_service
    networks:
      - prod_org-network
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=noc_alerts
      - POSTGRES_PORT=5432
      - KAFKA_BROKER=kafka:9092

networks:
  prod_org-network:
    external: true
```

Then run: `docker compose up -d` (while the orchestrator infra is running).

### Producer Example (Go - Ingestor -> Kafka)

```go
import (
    "encoding/json"
    "os"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type AIJobPayload struct {
    JobID     string `json:"job_id"`
    RawData   string `json:"raw_data"`
    Timestamp int64  `json:"timestamp"`
}

func SendToAI(payload AIJobPayload) error {
    broker := os.Getenv("KAFKA_BROKER")
    if broker == "" { broker = "kafka:9092" }

    p, err := kafka.NewProducer(&kafka.ConfigMap{
        "bootstrap.servers": broker,
        "client.id":         os.Getenv("HOSTNAME"),
        "acks":              "all",
    })
    if err != nil {
        return fmt.Errorf("failed to create producer: %w", err)
    }
    defer p.Close()

    val, _ := json.Marshal(payload)
    topic := "ingestion-events"

    deliveryChan := make(chan kafka.Event)
    err = p.Produce(&kafka.Message{
        TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
        Value:          val,
    }, deliveryChan)

    e := <-deliveryChan
    m := e.(*kafka.Message)
    close(deliveryChan)

    if m.TopicPartition.Error != nil {
        return fmt.Errorf("delivery failed: %v", m.TopicPartition.Error)
    }
    return nil
}
```

### Consumer Example (Go - AI Core <- Kafka)

```go
func StartAIWorker() {
    broker := os.Getenv("KAFKA_BROKER")
    if broker == "" { broker = "kafka:9092" }

    c, err := kafka.NewConsumer(&kafka.ConfigMap{
        "bootstrap.servers": broker,
        "group.id":          "ai-processing-group",
        "auto.offset.reset": "earliest",
    })
    if err != nil {
        log.Fatalf("Failed to create consumer: %v", err)
    }

    c.SubscribeTopics([]string{"ingestion-events"}, nil)
    defer c.Close()

    for {
        msg, err := c.ReadMessage(100 * time.Millisecond)
        if err == nil {
            var job AIJobPayload
            if jsonErr := json.Unmarshal(msg.Value, &job); jsonErr != nil {
                log.Printf("Corrupt JSON: %v", jsonErr)
                continue
            }
            // Process the job...
            fmt.Printf("Processing Job: %s\n", job.JobID)
        } else if !err.(kafka.Error).IsTimeout() {
            log.Printf("Consumer error: %v", err)
            time.Sleep(2 * time.Second)
        }
    }
}
```

### Go Dependency

```bash
go get github.com/confluentinc/confluent-kafka-go/v2/kafka
```

---

## Data Flow

```
datasource (SNMP/syslog simulator)
    |
    v  HTTP POST /ingest
ingestor-core (:8001) -- normalize, validate, enrich
    |
    v  Kafka topic: ingestion-events
ai-core -- IBM Watson analysis
    |
    v  Results stored in DB
api-gateway (:8080) -- REST API
    |
    v  HTTP
ui (:3000) -- React frontend
```

---

## Architecture

```
infra/
├── app.py              # Streamlit UI dashboard
├── orchestrator.py     # DevOpsManager (bootstrap/stop/nuke/seed)
├── core/
│   ├── config.py       # REPOS, SERVICES, INIT_SQL, DEFAULT_ENV
│   ├── docker_ops.py   # Docker Compose generation & status
│   ├── git_ops.py      # Git clone/update operations
│   └── utils.py        # Helpers (stream_command, timestamps)
└── prod/               # Generated at runtime
    ├── docker-compose.yml
    ├── .env
    ├── .mode           # "local" or "remote"
    ├── postgres-init/init.sql
    └── services/       # Cloned repos (remote mode)
```

### Bootstrap Steps

1. Scaffold directories (`prod/`, `services/`, `_failsafe/`, `postgres-init/`)
2. Write static files (init.sql, mock Dockerfile)
3. Generate `docker-compose.yml` from service config
4. Clone repos (remote mode) or validate local repos (local mode)
5. Write `.env` configuration
6. `docker compose up -d --build --remove-orphans`
7. **Seed database** — wait for postgres health, then pipe init.sql via `psql`

---

## Environment Variables

All services receive these via `.env` (auto-generated):

| Variable | Value | Used By |
|----------|-------|---------|
| `POSTGRES_HOST` | `postgres` | api-gateway, datasource |
| `POSTGRES_DB` | `noc_alerts` | all DB consumers |
| `POSTGRES_USER` | `admin` | all DB consumers |
| `POSTGRES_PASSWORD` | `secret` | all DB consumers |
| `KAFKA_BROKER` | `kafka:9092` | ingestor-core, event-router, ai-core, api-gateway |
| `JWT_SECRET` | `noc-platform-dev-secret-key-2026` | api-gateway |
| `CORS_ALLOWED_ORIGINS` | `localhost:3000,5173` | api-gateway |
| `WATSONX_API_KEYS` | your Watson API key | ai-core |
| `WATSONX_REGION` | `eu-gb` | ai-core |
| `WATSONX_PROJECT_ID` | your Watson project ID | ai-core |
| `FORWARD_TO_GATEWAY` | `false` | ai-core, event-router |
| `ENV` | `dev` | all services |
