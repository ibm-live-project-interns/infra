from pathlib import Path

# --- GLOBAL CONFIGURATION ---
BASE_DIR = Path.cwd()
PROJECT_NAME = "prod"
WORK_DIR = BASE_DIR / PROJECT_NAME

# Repository Definitions
REPOS = [
    {"name": "datasource", "url": "https://github.com/ibm-live-project-interns/datasource.git"},
    {"name": "ingestor", "url": "https://github.com/ibm-live-project-interns/ingestor.git"},
    {"name": "ai-core", "url": "https://github.com/ibm-live-project-interns/ai-core.git"},
    {"name": "ui", "url": "https://github.com/ibm-live-project-interns/ui.git"}
]

# Database Init Script (NOC Platform Schema)
INIT_SQL = """
-- NOC Database Initialization Script
-- Creates required tables for the NOC platform

-- Ingested events from datasource
CREATE TABLE IF NOT EXISTS ingestion_data (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI analysis results
CREATE TABLE IF NOT EXISTS ai_results (
    id SERIAL PRIMARY KEY,
    ingestion_id INT REFERENCES ingestion_data(id),
    result JSONB,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(50) PRIMARY KEY,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor', 'info')),
    status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'acknowledged', 'in-progress', 'resolved', 'dismissed')),
    device_name VARCHAR(100) NOT NULL,
    device_ip VARCHAR(45),
    device_icon VARCHAR(50),
    device_model VARCHAR(100),
    device_vendor VARCHAR(100),
    ai_title TEXT,
    ai_summary TEXT,
    confidence INT DEFAULT 0,
    timestamp_absolute TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp_relative VARCHAR(50),
    raw_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert history for tracking
CREATE TABLE IF NOT EXISTS alert_history (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(50) REFERENCES alerts(id),
    title TEXT,
    resolution TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ip VARCHAR(45),
    icon VARCHAR(50),
    model VARCHAR(100),
    vendor VARCHAR(100),
    location VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active',
    alert_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI metrics for dashboard
CREATE TABLE IF NOT EXISTS ai_metrics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    change VARCHAR(20),
    trend VARCHAR(20) CHECK (trend IN ('positive', 'negative', 'neutral')),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data for testing
INSERT INTO alerts (id, severity, status, device_name, device_ip, device_icon, device_model, device_vendor, ai_title, ai_summary, confidence)
VALUES 
    ('alert-001', 'critical', 'new', 'Core-SW-01', '192.168.1.10', 'switch', 'Cisco Catalyst 9300', 'Cisco Systems', 'Interface GigabitEthernet0/1 Down', 'Network interface has transitioned to down state.', 94),
    ('alert-002', 'major', 'acknowledged', 'FW-DMZ-03', '172.16.3.1', 'firewall', 'Palo Alto PA-5220', 'Palo Alto Networks', 'High CPU Utilization (85%)', 'Firewall processing load exceeding thresholds.', 88)
ON CONFLICT (id) DO NOTHING;

INSERT INTO devices (id, name, ip, icon, model, vendor, location)
VALUES 
    ('dev-001', 'Core-SW-01', '192.168.1.10', 'switch', 'Cisco Catalyst 9300', 'Cisco Systems', 'DC1-Rack1'),
    ('dev-002', 'FW-DMZ-03', '172.16.3.1', 'firewall', 'Palo Alto PA-5220', 'Palo Alto Networks', 'DC1-Rack2'),
    ('dev-003', 'RTR-EDGE-05', '10.0.5.1', 'router', 'Juniper MX960', 'Juniper Networks', 'DC2-Rack5')
ON CONFLICT (id) DO NOTHING;

INSERT INTO ai_metrics (name, value, change, trend)
VALUES 
    ('Resolution Time', 50, '-50%', 'positive'),
    ('Escalations', 47, '-47%', 'positive'),
    ('Accuracy', 94.8, '94.8%', 'positive')
ON CONFLICT DO NOTHING;
"""

# Mock Dockerfile Content
MOCK_DOCKERFILE = """FROM alpine:latest
ARG SERVICE_NAME
ENV MY_SVC_NAME=$SERVICE_NAME
RUN echo "Mock Setup Complete"
CMD ["sh", "-c", "while true; do echo [MOCK] Service is sleeping...; sleep 30; done"]
"""