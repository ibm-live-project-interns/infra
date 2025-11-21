# 🚀 DevOps Orchestrator

A GUI-based automation tool for setting up the microservices environment locally on Windows.

-----

## 📋 Project Status (Kanban)

| Status | Task | Description |
| :--- | :--- | :--- |
| ✅ **Done** | **Automated Bootstrap** | One-click script (`devops_orchestrator.py`) creates `prod` dir & `.env`. |
| ✅ **Done** | **Dynamic Infrastructure** | `docker-compose.yml` auto-generated from the repository list. |
| ✅ **Done** | **Database Setup** | PostgreSQL initialized with persistent volumes and default credentials. |
| ✅ **Done** | **Failsafe Architecture** | Mock Containers injected automatically for missing or broken repos. |
| ✅ **Done** | **Smart Swapping** | Auto-detects repo fixes (via `git pull`) and swaps Mock for Real code. |
| ✅ **Done** | **Zero-Config UI** | Streamlit dashboard runs relative to script location (no path setup needed). |
| ⏳ **Pending** | **Kafka Infrastructure** | Add Kafka and Zookeeper to the dynamic Docker Compose generation. |
| ⏳ **Pending** | **Database Migration** | Create a migration container to apply initial SQL schemas to Postgres. |
| ⏳ **Pending** | **Connectivity: HTTP** | Verify the UI container can reach the Ingestor API. |
| ⏳ **Pending** | **Connectivity: gRPC** | Verify Ingestor can successfully call AI-Core methods. |
| ⏳ **Pending** | **Service Verification** | Automate "Health Check" pings to ensure services are serving traffic. |

-----

## ⚠️ Critical Prerequisites

To use this tool, your machine **MUST** meet these requirements:

1.  **Docker Desktop:**
      * Must be installed and **Running** in the background (Icon visible in taskbar).
2.  **Python 3.10+:**
      * Required to run the orchestrator script.
      * [Download Python](https://www.python.org/downloads/)
3.  **Git Authentication:**
      * You must be logged into GitHub on your machine.
      * **Windows Credential Manager** must be configured so `git clone` works without asking for a password in the terminal.
      * *Test:* Run `git clone https://github.com/ibm-live-project-interns/datasource.git` in a random folder. If it works without a prompt, you are ready.

-----

## 🚀 How to Run

1.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Orchestrator:**

    ```bash
    streamlit run devops_orchestrator.py
    ```

3.  **Interact:**

      * Click **▶ Initialize & Start** to clone repos and start the stack.
      * Check the dashboard for status (Green = Good, Orange = Mock/Failsafe).
