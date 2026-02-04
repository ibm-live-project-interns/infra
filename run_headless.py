
import sys
import os

# Add the current directory to sys.path so that imports work
sys.path.append(os.getcwd())

from orchestrator import DevOpsManager
from core.config import REPOS

def log_callback(msg):
    print(msg)

def main():
    print("Starting Headless Bootstrap via Infra Orchestrator...")
    manager = DevOpsManager(log_callback=log_callback)
    
    # Define branch map - use 'main' for all repos by default
    branch_map = {repo['name']: 'main' for repo in REPOS}
    
    print("Bootstrap Environment...")
    success = manager.bootstrap_environment(branch_map)
    
    if success:
        print("\n\nSUCCESS! Environment bootstrapped and started.")
        print("Use 'docker compose logs -f' in infra/prod to monitor.")
    else:
        print("\n\nFAILURE. Check logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
