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

# Database Init Script
INIT_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_data (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ai_results (
    id SERIAL PRIMARY KEY,
    ingestion_id INT,
    result JSONB,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Mock Dockerfile Content (FIXED)
# Removed parentheses and special chars that confuse the Alpine shell
MOCK_DOCKERFILE = """FROM alpine:latest
ARG SERVICE_NAME
ENV MY_SVC_NAME=$SERVICE_NAME
RUN echo "Mock Setup Complete"
CMD ["sh", "-c", "while true; do echo [MOCK] Service is sleeping...; sleep 30; done"]
"""