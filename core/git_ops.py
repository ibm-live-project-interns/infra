import subprocess
import shutil
from .utils import stream_command, is_mock_file

def clone_or_update(repo_name, repo_url, target_dir, branch, log_callback):
    dockerfile = target_dir / "Dockerfile"
    
    # 1. Ensure Directory Exists
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check for Corruption (Dir exists but no .git)
    if target_dir.exists() and any(target_dir.iterdir()) and not (target_dir / ".git").exists():
        log_callback(f"⚠️ {repo_name} corrupt. Wiping.")
        shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    # 3. Clone
    if not (target_dir / ".git").exists():
        log_callback(f"⬇️ Cloning {repo_name} ({branch})...")
        subprocess.run(
            f'git clone -b {branch} {repo_url} "{target_dir}"', 
            shell=True, encoding='utf-8', errors='replace'
        )
    else:
        # 4. Update
        if is_mock_file(dockerfile):
            log_callback(f"🔄 Swapping Mock -> Real ({repo_name})...")
            try: os.remove(dockerfile)
            except: pass
            
        log_callback(f"🔄 Updating {repo_name} to '{branch}'...")
        subprocess.run(f"git fetch origin", shell=True, cwd=target_dir, encoding='utf-8', errors='replace')
        subprocess.run(f"git checkout {branch}", shell=True, cwd=target_dir, encoding='utf-8', errors='replace')
        stream_command(f"git pull origin {branch}", target_dir, log_callback)