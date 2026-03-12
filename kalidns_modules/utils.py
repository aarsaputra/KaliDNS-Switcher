import os
import sys
import subprocess
import shutil
import time
import datetime
import ipaddress
import signal
import atexit
from .config import LOG_DIR, LOG_FILE, RESOLV_CONF

try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# --- KONFIGURASI WARNA ---
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- GLOBAL CONSOLE (to be initialized by TUI) ---
console = None

def check_root():
    if os.geteuid() != 0:
        print(f"{Color.FAIL}[!] Script ini harus dijalankan sebagai ROOT (sudo).{Color.ENDC}")
        input(f"{Color.BLUE}Tekan Enter untuk keluar...{Color.ENDC}")
        sys.exit(1)

def log_action(action, details):
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} | {action} | {details}\n"
        with open(LOG_FILE, 'a') as f:
            f.write(entry)
    except Exception:
        pass

def validate_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        return str(ip_obj)
    except ValueError:
        return None

def cleanup_old_backups(max_age_days=7):
    now = time.time()
    backup_dir = os.path.dirname(RESOLV_CONF) 
    cleaned = 0
    try:
        if not os.path.exists(backup_dir):
            return
        for file in os.listdir(backup_dir):
            if ('resolv.conf.backup_' in file or 'resolved.conf.backup_' in file):
                filepath = os.path.join(backup_dir, file)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    if (now - mtime) > (max_age_days * 86400):
                        try:
                            os.remove(filepath)
                            cleaned += 1
                        except Exception:
                            pass
        if cleaned > 0:
            msg = f"Auto-Cleanup: Membersihkan {cleaned} file backup lama (> {max_age_days} hari)."
            print(f"{Color.BLUE}[i] {msg}{Color.ENDC}")
            log_action("CLEANUP", msg)
    except Exception:
        pass

def backup_file(filepath):
    if os.path.exists(filepath):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.backup_{timestamp}"
        try:
            shutil.copy2(filepath, backup_path)
            log_action("BACKUP", f"Created backup: {backup_path}")
        except Exception as e:
            print(f"{Color.WARNING}[!] Gagal membuat backup: {e}{Color.ENDC}")

def unlock_file():
    try:
        subprocess.run(['chattr', '-i', RESOLV_CONF], stderr=subprocess.DEVNULL)
    except Exception:
        pass

def lock_file():
    try:
        subprocess.run(['chattr', '+i', RESOLV_CONF], check=True, stderr=subprocess.PIPE)
        print(f"{Color.BLUE}[i] File resolv.conf dikunci (Immutable).{Color.ENDC}")
        # Register unlock_file on exit to prevent permanent lock if script crashes
        atexit.register(unlock_file)
    except subprocess.CalledProcessError:
        # Silently fail if filesystem doesn't support chattr +i
        pass
    except Exception as e:
        print(f"{Color.WARNING}[!] Gagal mengunci file: {e}{Color.ENDC}")

def signal_handler(sig, frame):
    """Handle termination signals to ensure cleanup."""
    if console:
        console.print(f"\n[bold yellow][!] Sinyal ({sig}) diterima. Melakukan cleanup...[/bold yellow]")
    else:
        print(f"\n{Color.WARNING}[!] Sinyal ({sig}) diterima. Melakukan cleanup...{Color.ENDC}")
    unlock_file()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def atomic_write(filepath, content):
    temp_file = f"{filepath}.tmp"
    try:
        with open(temp_file, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno()) 
        os.rename(temp_file, filepath)
        return True
    except Exception as e:
        print(f"{Color.FAIL}[!] Gagal menulis file {filepath}: {e}{Color.ENDC}")
        log_action("ERROR", f"Atomic write failed for {filepath}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

def safe_restart_service(service_name):
    print(f"{Color.BLUE}[i] Merestart service {service_name}...{Color.ENDC}")
    try:
        # Use timeout to prevent hanging
        subprocess.run(['systemctl', 'stop', service_name], stderr=subprocess.DEVNULL, timeout=10)
        time.sleep(1) 
        subprocess.run(['systemctl', 'start', service_name], check=True, timeout=15)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        msg = f"Gagal mengontrol {service_name}: {e}"
        print(f"{Color.FAIL}[!] {msg}{Color.ENDC}")
        log_action("SERVICE_ERROR", msg)
        return False
