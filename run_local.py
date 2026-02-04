
import sys
import os

# Add the current directory to sys.path so that imports work
sys.path.append(os.getcwd())

from orchestrator import DevOpsManager
from core.config import REPOS

def log_callback(msg):
    print(msg)

def main():
    print("Starting LOCAL Bootstrap via Infra Orchestrator...")
    print("This will link your local folders (ui, ai-core, etc.) into the prod environment.")
    
    manager = DevOpsManager(log_callback=log_callback)
    
    # Define branch map - use 'main' for all repos by default (ignored for local links)
    branch_map = {repo['name']: 'main' for repo in REPOS}
    
    print("Bootstrap Environment (Mode: Local)...")
    try:
        # Pass use_local=True
        success = manager.bootstrap_environment(branch_map, use_local=True)
        
        if success:
            print("\n\nSUCCESS! Environment started with LOCAL code.")
            print("Use 'docker compose logs -f' in infra/prod to monitor.")
        else:
            print("\n\nFAILURE. Check logs above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
