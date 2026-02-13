from pathlib import Path

# --- GLOBAL CONFIGURATION ---
BASE_DIR = Path.cwd()
PROJECT_NAME = "prod"
WORK_DIR = BASE_DIR / PROJECT_NAME

# --- REPOSITORIES (for git clone operations) ---
REPOS = [
    {"name": "datasource", "url": "https://github.com/ibm-live-project-interns/datasource.git"},
    {"name": "ingestor", "url": "https://github.com/ibm-live-project-interns/ingestor.git"},
    {"name": "ai-core", "url": "https://github.com/ibm-live-project-interns/ai-core.git"},
    {"name": "ui", "url": "https://github.com/ibm-live-project-interns/ui.git"},
]

# --- DOCKER SERVICES (for docker-compose generation) ---
# The ingestor repo produces 3 services: api-gateway, event-router, ingestor-core
# Build contexts are relative to prod/ (where docker-compose.yml lives)
SERVICES = [
    {
        "name": "datasource",
        "context": "./services",           # remote: cloned repos under services/
        "local_context": "../..",           # local: project root (Dockerfile COPYs datasource/ + ingestor/shared/)
        "dockerfile": "datasource/Dockerfile",
        "ports": [],
        "depends_on": [("postgres", "service_healthy")],
    },
    {
        "name": "api-gateway",
        "context": "./services",
        "local_context": "../..",
        "dockerfile": "ingestor/api_gateway/Dockerfile",
        "ports": ["8080:8080"],
        "depends_on": [("postgres", "service_healthy"), ("kafka", "service_healthy")],
    },
    {
        "name": "event-router",
        "context": "./services/ingestor",
        "local_context": "../../ingestor",  # local: ingestor repo root (Dockerfile COPYs shared/ + event_router/)
        "dockerfile": "event_router/Dockerfile",
        "ports": ["8082:8082"],
        "depends_on": [("kafka", "service_healthy"), ("api-gateway", "service_started")],
    },
    {
        "name": "ingestor-core",
        "context": "./services/ingestor",
        "local_context": "../../ingestor",
        "dockerfile": "ingestor_core/Dockerfile",
        "ports": ["8001:8001"],
        "depends_on": [("kafka", "service_healthy")],
    },
    {
        "name": "ai-core",
        "context": "./services",
        "local_context": "../..",
        "dockerfile": "ai-core/Dockerfile",
        "ports": [],
        "depends_on": [("kafka", "service_healthy")],
    },
    {
        "name": "ui",
        "context": "./services/ui",
        "local_context": "../../ui",        # local: ui repo root (Dockerfile COPYs . .)
        "dockerfile": "Dockerfile",
        "ports": ["3000:3000"],
        "depends_on": [],
    },
]

# Maps docker service name -> cloned repo name (for health checks / UI)
SERVICE_TO_REPO = {
    "datasource": "datasource",
    "api-gateway": "ingestor",
    "event-router": "ingestor",
    "ingestor-core": "ingestor",
    "ai-core": "ai-core",
    "ui": "ui",
}

# --- DEFAULT ENVIRONMENT ---
DEFAULT_ENV = """\
ENV=dev
JWT_SECRET=noc-platform-dev-secret-key-2026

# Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=noc_alerts
DB_HOST=postgres
DB_PORT=5432
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://admin:secret@postgres:5432/noc_alerts

# Kafka
KAFKA_BROKER=kafka:9092

# Service URLs
INGESTOR_CORE_URL=http://ingestor-core:8001
EVENT_ROUTER_URL=http://event-router:8082
API_GATEWAY_URL=http://api-gateway:8080

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Watson AI (ai-core service)
WATSONX_API_KEYS=bUhO1vxgQMDHhpxCQFochF3_QL9INFBxeYNo94ywLNZb
WATSONX_REGION=eu-gb
WATSONX_PROJECT_ID=913d34b6-2c2c-4fc7-9701-6b2ed8db5487
FORWARD_TO_GATEWAY=false
"""

# --- DATABASE INIT SCRIPT (Full NOC Platform Schema) ---
INIT_SQL = """\
-- NOC Database Initialization Script
-- Full schema for the NOC monitoring platform

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

-- Alerts table (matches Go Alert model in shared/models/alert.go)
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    title VARCHAR(255) NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'major', 'medium', 'minor', 'low', 'info')),
    category VARCHAR(50) NOT NULL DEFAULT 'network',
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('new', 'open', 'acknowledged', 'in-progress', 'resolved', 'dismissed')),
    source VARCHAR(50) DEFAULT '',
    source_ip VARCHAR(45) DEFAULT '',
    device VARCHAR(100) DEFAULT '',
    device_name VARCHAR(100) DEFAULT '',
    device_ip VARCHAR(45),
    device_icon VARCHAR(50),
    device_model VARCHAR(100),
    device_vendor VARCHAR(100),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100) DEFAULT '',
    resolved_by VARCHAR(100) DEFAULT '',
    dismissed_by VARCHAR(100) DEFAULT '',
    ai_title TEXT,
    ai_summary TEXT,
    ai_root_cause TEXT,
    ai_impact TEXT,
    ai_recommendation TEXT,
    ai_confidence FLOAT DEFAULT 0,
    confidence INT DEFAULT 0,
    raw_payload TEXT DEFAULT '',
    ticket_id VARCHAR(50),
    raw_data TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_deleted_at ON alerts(deleted_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_source_ip ON alerts(source_ip);
CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    ip VARCHAR(45),
    icon VARCHAR(50),
    model VARCHAR(100),
    vendor VARCHAR(100),
    location VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active',
    alert_count INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_devices_deleted_at ON devices(deleted_at);

-- AI metrics for dashboard
CREATE TABLE IF NOT EXISTS ai_metrics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value FLOAT NOT NULL,
    change VARCHAR(20),
    trend VARCHAR(20) CHECK (trend IN ('positive', 'negative', 'neutral')),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table (authentication)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    first_name VARCHAR(100) DEFAULT '',
    last_name VARCHAR(100) DEFAULT '',
    avatar VARCHAR(500) DEFAULT '',
    role VARCHAR(50) NOT NULL DEFAULT 'network-ops',
    google_id VARCHAR(100) DEFAULT '',
    o_auth_token TEXT DEFAULT '',
    o_auth_refresh TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,
    last_login TIMESTAMP,
    failed_attempts INT DEFAULT 0,
    locked_until TIMESTAMP,
    verification_token VARCHAR(100) DEFAULT '',
    verified_at TIMESTAMP,
    reset_token VARCHAR(100) DEFAULT '',
    reset_token_exp TIMESTAMP,
    email_alerts BOOLEAN DEFAULT true,
    push_notifications BOOLEAN DEFAULT true,
    sound_enabled BOOLEAN DEFAULT false,
    critical_only BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at);

-- User sessions
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    user_id INT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45) DEFAULT '',
    user_agent VARCHAR(500) DEFAULT '',
    is_active BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_sessions_deleted_at ON sessions(deleted_at);

-- API keys for programmatic access
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    key VARCHAR(100) UNIQUE NOT NULL,
    prefix VARCHAR(10) NOT NULL,
    permissions TEXT DEFAULT '',
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_api_keys_deleted_at ON api_keys(deleted_at);

-- Support tickets
CREATE TABLE IF NOT EXISTS tickets (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    category VARCHAR(50) DEFAULT '',
    assignee VARCHAR(100) DEFAULT '',
    reporter VARCHAR(100) DEFAULT '',
    alert_id VARCHAR(50),
    device_id VARCHAR(100),
    due_date TIMESTAMP,
    resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tickets_deleted_at ON tickets(deleted_at);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

-- Ticket comments
CREATE TABLE IF NOT EXISTS ticket_comments (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    ticket_id VARCHAR(50) NOT NULL,
    author VARCHAR(100) NOT NULL,
    content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_comments_ticket_id ON ticket_comments(ticket_id);

-- Threshold Rules (alert triggering configuration)
CREATE TABLE IF NOT EXISTS threshold_rules (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    condition VARCHAR(255) NOT NULL DEFAULT '',
    duration VARCHAR(50) DEFAULT '',
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    enabled BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_threshold_rules_deleted_at ON threshold_rules(deleted_at);

-- Notification Channels
CREATE TABLE IF NOT EXISTS notification_channels (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'Email',
    meta TEXT DEFAULT '',
    active BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_notification_channels_deleted_at ON notification_channels(deleted_at);

-- Escalation Policies
CREATE TABLE IF NOT EXISTS escalation_policies (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    steps INT DEFAULT 1,
    active BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_escalation_policies_deleted_at ON escalation_policies(deleted_at);

-- Maintenance Windows
CREATE TABLE IF NOT EXISTS maintenance_windows (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(100) NOT NULL,
    schedule VARCHAR(200) DEFAULT '',
    duration VARCHAR(100) DEFAULT '',
    status VARCHAR(20) DEFAULT 'scheduled'
);
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_deleted_at ON maintenance_windows(deleted_at);

-- Audit Logs (system-wide activity trail)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    user_id INTEGER NOT NULL,
    username VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    result VARCHAR(20) NOT NULL DEFAULT 'success'
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_username ON audit_logs(username);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_id ON audit_logs(resource_id);

-- ============ SEED DATA ============

-- Alerts (10 total: mix of severities, statuses, and categories)
INSERT INTO alerts (id, title, severity, category, status, source, source_ip, device, device_name, device_ip, device_icon, device_model, device_vendor, ai_title, ai_summary, ai_root_cause, ai_impact, ai_recommendation, ai_confidence, confidence)
VALUES
    ('alert-001', 'Interface GigabitEthernet0/1 Down', 'critical', 'network', 'new', 'snmp', '192.168.1.10', 'Core-SW-01', 'Core-SW-01', '192.168.1.10', 'switch', 'Cisco Catalyst 9300', 'Cisco Systems', 'Interface GigabitEthernet0/1 Down', 'Network interface has transitioned to down state.', 'Physical link failure or SFP module malfunction.', 'Loss of connectivity for 120 hosts on VLAN 10.', 'Check physical cabling and replace SFP module if faulty.', 0.94, 94),
    ('alert-002', 'High CPU Utilization (85%%)', 'major', 'security', 'acknowledged', 'snmp', '172.16.3.1', 'FW-DMZ-03', 'FW-DMZ-03', '172.16.3.1', 'firewall', 'Palo Alto PA-5220', 'Palo Alto Networks', 'High CPU Utilization (85%%)', 'Firewall processing load exceeding thresholds.', 'Excessive policy evaluation due to 2400 active rules.', 'Increased packet inspection latency affecting DMZ traffic.', 'Audit and consolidate firewall rules to reduce CPU overhead.', 0.88, 88),
    ('alert-003', 'BGP Peer Session Flapping', 'high', 'routing', 'open', 'snmp', '10.0.5.1', 'RTR-EDGE-05', 'RTR-EDGE-05', '10.0.5.1', 'router', 'Juniper MX960', 'Juniper Networks', 'BGP Peer Session Flapping', 'BGP session with upstream peer 203.0.113.1 is oscillating between Established and Idle states.', 'Unstable physical link or MTU mismatch on peering interface.', 'Intermittent routing blackholes affecting 15%% of egress traffic.', 'Check interface error counters and verify MTU settings on both ends.', 0.91, 91),
    ('alert-004', 'High Client Association Failures', 'medium', 'wireless', 'open', 'snmp', '10.10.3.12', 'AP-FLOOR3-12', 'AP-FLOOR3-12', '10.10.3.12', 'wifi', 'Aruba AP-535', 'Aruba Networks', 'High Client Association Failures', 'Wireless access point reporting 23%% association failure rate over last 30 minutes.', 'Channel congestion or RADIUS authentication timeout.', 'Approximately 45 users on Floor 3 experiencing connectivity drops.', 'Check RADIUS server response times and adjust channel assignments.', 0.85, 85),
    ('alert-005', 'Spanning Tree Topology Change Storm', 'critical', 'network', 'acknowledged', 'snmp', '192.168.1.20', 'CORE-SW-02', 'CORE-SW-02', '192.168.1.20', 'switch', 'Cisco Nexus 9336C', 'Cisco Systems', 'Spanning Tree Topology Change Storm', 'Excessive STP TCN events detected (>50/min) on trunk interfaces.', 'Misconfigured downstream switch creating a loop.', 'Network-wide broadcast storms affecting all VLANs in Building A.', 'Identify the port sourcing TCN events and temporarily shut it down.', 0.96, 96),
    ('alert-006', 'SSL Decryption Engine Overloaded', 'major', 'security', 'in-progress', 'snmp', '172.16.3.1', 'FW-DMZ-03', 'FW-DMZ-03', '172.16.3.1', 'firewall', 'Palo Alto PA-5220', 'Palo Alto Networks', 'SSL Decryption Engine Overloaded', 'SSL/TLS inspection queue depth exceeding 85%% capacity threshold.', 'Spike in encrypted traffic volume during business hours peak.', 'Increased latency for HTTPS-inspected traffic; some sessions timing out.', 'Add SSL decryption exclusions for trusted CDN domains.', 0.89, 89),
    ('alert-007', 'Port Security Violation Detected', 'low', 'security', 'open', 'snmp', '10.20.1.14', 'SW-ACCESS-14', 'SW-ACCESS-14', '10.20.1.14', 'switch', 'Cisco Catalyst 9200', 'Cisco Systems', 'Port Security Violation Detected', 'MAC address limit exceeded on Gi1/0/24 - unknown device connected.', 'Unauthorized device plugged into secured port.', 'Single port disabled; no broader impact.', 'Investigate the unauthorized MAC address.', 0.93, 93),
    ('alert-008', 'OSPF Neighbor Adjacency Restored', 'info', 'routing', 'resolved', 'snmp', '10.0.0.1', 'RTR-CORE-01', 'RTR-CORE-01', '10.0.0.1', 'router', 'Cisco ASR 9000', 'Cisco Systems', 'OSPF Neighbor Adjacency Restored', 'OSPF adjacency with neighbor 10.0.0.2 re-established after 3-minute outage.', 'Brief interface flap on interconnect link.', 'Routing convergence completed; traffic paths restored.', 'Monitor for recurring flaps.', 0.97, 97),
    ('alert-009', 'Backend Pool Member Health Degraded', 'high', 'application', 'open', 'snmp', '10.30.1.5', 'LB-PROD-01', 'LB-PROD-01', '10.30.1.5', 'server', 'F5 BIG-IP i5800', 'F5 Networks', 'Backend Pool Member Health Degraded', '2 of 6 backend servers in prod-web-pool failing health checks.', 'Application server memory exhaustion causing HTTP 503 responses.', '33%% capacity reduction for production web traffic.', 'Restart application services on affected servers.', 0.88, 88),
    ('alert-010', 'UPS Battery Runtime Below Threshold', 'critical', 'infrastructure', 'new', 'snmp', '10.50.1.1', 'UPS-DC1-A', 'UPS-DC1-A', '10.50.1.1', 'server', 'APC Smart-UPS SRT 10000', 'APC by Schneider', 'UPS Battery Runtime Below Threshold', 'Estimated battery runtime dropped to 8 minutes (threshold: 15 min).', 'Prolonged utility power fluctuations draining battery reserves.', 'Risk of unclean shutdown for all DC1 Rack A equipment.', 'URGENT: Verify utility power status. Prepare for controlled shutdown.', 0.99, 99)
ON CONFLICT (id) DO UPDATE SET
    ai_summary = EXCLUDED.ai_summary,
    ai_root_cause = EXCLUDED.ai_root_cause,
    ai_impact = EXCLUDED.ai_impact,
    ai_recommendation = EXCLUDED.ai_recommendation,
    ai_confidence = EXCLUDED.ai_confidence,
    confidence = EXCLUDED.confidence;

-- Set resolved_at for resolved alert (needed for MTTR calculations)
UPDATE alerts SET resolved_at = created_at + INTERVAL '41 minutes 45 seconds' WHERE id = 'alert-008' AND resolved_at IS NULL;

-- Devices (10 total: mix of types)
INSERT INTO devices (id, name, ip, icon, model, vendor, location, status, alert_count)
VALUES
    ('dev-001', 'Core-SW-01', '192.168.1.10', 'switch', 'Cisco Catalyst 9300', 'Cisco Systems', 'DC1-Rack1', 'active', 1),
    ('dev-002', 'FW-DMZ-03', '172.16.3.1', 'firewall', 'Palo Alto PA-5220', 'Palo Alto Networks', 'DC1-Rack2', 'active', 2),
    ('dev-003', 'RTR-EDGE-05', '10.0.5.1', 'router', 'Juniper MX960', 'Juniper Networks', 'DC2-Rack5', 'active', 1),
    ('dev-004', 'CORE-SW-02', '192.168.1.20', 'switch', 'Cisco Nexus 9336C', 'Cisco Systems', 'DC1-Rack3', 'active', 1),
    ('dev-005', 'AP-FLOOR3-12', '10.10.3.12', 'wifi', 'Aruba AP-535', 'Aruba Networks', 'Building-A-Floor3', 'active', 1),
    ('dev-006', 'SW-ACCESS-14', '10.20.1.14', 'switch', 'Cisco Catalyst 9200', 'Cisco Systems', 'Building-B-Floor1', 'active', 1),
    ('dev-007', 'RTR-CORE-01', '10.0.0.1', 'router', 'Cisco ASR 9000', 'Cisco Systems', 'DC1-CoreRack', 'active', 0),
    ('dev-008', 'LB-PROD-01', '10.30.1.5', 'server', 'F5 BIG-IP i5800', 'F5 Networks', 'DC1-Rack5', 'warning', 1),
    ('dev-009', 'UPS-DC1-A', '10.50.1.1', 'server', 'APC Smart-UPS SRT 10000', 'APC by Schneider', 'DC1-PowerRoom', 'critical', 1),
    ('dev-010', 'WLC-MAIN-01', '10.10.0.1', 'wifi', 'Cisco 9800-40', 'Cisco Systems', 'DC1-Rack2', 'active', 0)
ON CONFLICT (id) DO NOTHING;

-- AI Metrics
INSERT INTO ai_metrics (name, value, change, trend)
VALUES
    ('Resolution Time', 50, '-50%%', 'positive'),
    ('Escalations', 47, '-47%%', 'positive'),
    ('Accuracy', 94.8, '94.8%%', 'positive')
ON CONFLICT DO NOTHING;

-- Threshold Rules (5)
INSERT INTO threshold_rules (id, name, description, condition, severity, enabled)
VALUES
    ('RULE-001', 'High CPU Usage', 'Alert when CPU usage exceeds threshold', 'CPU > 90%% for 5m', 'critical', true),
    ('RULE-002', 'Memory Pressure', 'Alert on high memory utilization', 'Memory > 85%% for 10m', 'major', true),
    ('RULE-003', 'Interface Packet Loss', 'Alert when packet loss is detected', 'Packet Loss > 1%% for 3m', 'warning', true),
    ('RULE-004', 'Disk Space Warning', 'Alert when disk usage is high', 'Disk > 80%% for 15m', 'warning', true),
    ('RULE-005', 'BGP Session Down', 'Alert when BGP session drops', 'BGP State != Established', 'critical', true)
ON CONFLICT (id) DO NOTHING;

-- Notification Channels (3)
INSERT INTO notification_channels (id, name, type, meta, active)
VALUES
    ('CH-001', '#netops-alerts', 'Slack', '14 alerts/hr', true),
    ('CH-002', 'oncall@company.com', 'Email', '8 alerts/hr', true),
    ('CH-003', '+1-555-0100', 'Twilio', 'Critical only', false)
ON CONFLICT (id) DO NOTHING;

-- Escalation Policies (2)
INSERT INTO escalation_policies (id, name, description, steps, active)
VALUES
    ('POL-001', 'Critical Infrastructure', 'For critical network failures - immediate escalation', 3, true),
    ('POL-002', 'Standard Operations', 'For medium/low alerts - gradual escalation', 5, true)
ON CONFLICT (id) DO NOTHING;

-- Maintenance Windows (2)
INSERT INTO maintenance_windows (id, name, schedule, duration, status)
VALUES
    ('MW-001', 'Weekly Switch Maintenance', 'Sundays 02:00-06:00 UTC', '4 hours', 'active'),
    ('MW-002', 'Monthly Firmware Updates', '1st Saturday 00:00-04:00 UTC', '4 hours', 'scheduled')
ON CONFLICT (id) DO NOTHING;

-- Tickets (6: linked to alerts and devices)
INSERT INTO tickets (id, title, description, priority, status, category, assignee, reporter, alert_id, device_id)
VALUES
    ('TKT-001', 'Investigate Core Switch Interface Down', 'GigabitEthernet0/1 on Core-SW-01 went down. Need to check physical connectivity and SFP module.', 'critical', 'open', 'Network', 'admin', 'system', 'alert-001', 'dev-001'),
    ('TKT-002', 'Firewall CPU Usage Remediation', 'PA-5220 CPU consistently above 85%%. Need to review policy complexity and consider hardware upgrade.', 'high', 'in-progress', 'Security', 'admin', 'system', 'alert-002', 'dev-002'),
    ('TKT-003', 'BGP Peering Link Investigation', 'Edge router BGP session flapping with upstream peer. Schedule maintenance window for link testing.', 'high', 'open', 'Network', 'admin', 'system', 'alert-003', 'dev-003'),
    ('TKT-004', 'Floor 3 WiFi Client Issues', 'Multiple users reporting WiFi drops on Floor 3. Check AP channel assignments and RADIUS config.', 'medium', 'open', 'Wireless', 'admin', 'system', 'alert-004', 'dev-005'),
    ('TKT-005', 'STP Storm Root Cause Analysis', 'Critical: STP topology change storm on CORE-SW-02. Identify offending port and remediate.', 'critical', 'in-progress', 'Network', 'admin', 'system', 'alert-005', 'dev-004'),
    ('TKT-006', 'UPS Battery Replacement - DC1 Rack A', 'UPS runtime critically low. Order replacement batteries and schedule installation.', 'critical', 'open', 'Facilities', 'admin', 'system', 'alert-010', 'dev-009')
ON CONFLICT (id) DO NOTHING;

-- Ticket Comments (3)
INSERT INTO ticket_comments (id, ticket_id, author, content)
VALUES
    ('CMT-001', 'TKT-001', 'admin', 'SFP module replaced on Gi0/1. Monitoring for stability.'),
    ('CMT-002', 'TKT-002', 'admin', 'Policy audit initiated. Found 340 unused rules that can be removed.'),
    ('CMT-003', 'TKT-005', 'admin', 'Isolated port Gi1/0/48 as source of TCN storm. Downstream switch had loop.')
ON CONFLICT (id) DO NOTHING;

-- Alert History
INSERT INTO alert_history (alert_id, title, resolution, severity)
VALUES
    ('alert-008', 'OSPF Neighbor Adjacency Restored', 'Auto-resolved: adjacency re-established after link flap recovery', 'info'),
    ('alert-001', 'Interface GigabitEthernet0/1 Down', 'SFP module replaced, interface came back up', 'critical')
ON CONFLICT DO NOTHING;

-- Default admin user (email: admin@admin.com, password: admin123)
INSERT INTO users (email, username, password, first_name, last_name, role, is_active, email_verified)
VALUES ('admin@admin.com', 'admin', '$2a$12$UbCuBbijlSXuVgyAG4Iwk.tiY9VOp16P4r6zhbsTt3IOL5HPzUAVC', 'Admin', 'User', 'sysadmin', true, true)
ON CONFLICT (email) DO NOTHING;
"""

# Mock Dockerfile Content
MOCK_DOCKERFILE = """FROM alpine:latest
ARG SERVICE_NAME
ENV MY_SVC_NAME=$SERVICE_NAME
RUN echo "Mock Setup Complete"
CMD ["sh", "-c", "while true; do echo [MOCK] Service is sleeping...; sleep 30; done"]
"""
