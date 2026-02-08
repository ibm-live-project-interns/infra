
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp_absolute TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp_relative VARCHAR(50),
    raw_data TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_deleted_at ON alerts(deleted_at);

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
    reset_token_exp TIMESTAMP
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
