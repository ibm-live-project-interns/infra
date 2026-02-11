import datetime
import subprocess
from pathlib import Path

def get_timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

def stream_command(cmd, cwd, log_callback=None):
    """
    Runs a shell command and streams output to a callback function.
    Decoupled from Streamlit.
    """
    if not Path(cwd).exists():
        if log_callback: log_callback(f"❌ Error: Path {cwd} does not exist.")
        return False
        
    try:
        # Force UTF-8 and replace errors to avoid Windows encoding crashes
        process = subprocess.Popen(
            cmd, cwd=str(cwd), shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding='utf-8', errors='replace'
        )
        
        for line in iter(process.stdout.readline, ''):
            if log_callback:
                log_callback(line.strip())
                
        process.stdout.close()
        return process.wait() == 0
    except Exception as e:
        if log_callback: log_callback(f"❌ Execution Exception: {e}")
        return False

def is_mock_file(file_path):
    try:
        if not file_path.exists(): return False
        with open(file_path, 'r', encoding='utf-8') as f:
            return "FAILSAFE MODE" in f.read()
    except:
        return False