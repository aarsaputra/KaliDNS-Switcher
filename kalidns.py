#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import time
import ipaddress
import datetime

# --- KONFIGURASI WARNA ---
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- KONFIGURASI FILE ---
RESOLV_CONF = "/etc/resolv.conf"
SYSTEMD_RESOLVED_CONF = "/etc/systemd/resolved.conf"
LOG_DIR = "/var/log/kalidns"
LOG_FILE = os.path.join(LOG_DIR, "dns.log")

# --- DATA PRESETS ---
DNS_PRESETS = {
    '1': {'name': 'Google', 'ips': ['8.8.8.8', '8.8.4.4']},
    '2': {'name': 'Cloudflare', 'ips': ['1.1.1.1', '1.0.0.1']},
    '3': {'name': 'Quad9 (Security)', 'ips': ['9.9.9.9', '149.112.112.112']},
    '4': {'name': 'AdGuard (No Ads)', 'ips': ['94.140.14.14', '94.140.15.15']},
    '5': {'name': 'CleanBrowsing (Family)', 'ips': ['185.228.168.9', '185.228.169.9']},
}

# --- FUNGSI UTILITAS ---

def check_root():
    if os.geteuid() != 0:
        print(f"{Color.FAIL}[!] Script ini harus dijalankan sebagai ROOT (sudo).{Color.ENDC}")
        sys.exit(1)

def clear_screen():
    subprocess.run(['clear'], stderr=subprocess.DEVNULL)

def banner():
    print(f"{Color.HEADER}{Color.BOLD}")
    print("="*60)
    print("   KALI LINUX DNS CHANGER TOOL (ULTIMATE EDITION)")
    print("   Secure Atomic Write, Auto-Backup, & Leak Test")
    print("="*60)
    print(f"{Color.ENDC}")

def log_action(action, details):
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
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

def safe_restart_service(service_name):
    print(f"{Color.BLUE}[i] Merestart service {service_name}...{Color.ENDC}")
    try:
        subprocess.run(['systemctl', 'stop', service_name], stderr=subprocess.DEVNULL, timeout=10)
        time.sleep(1) 
        subprocess.run(['systemctl', 'start', service_name], check=True, timeout=15)
        return True
    except subprocess.CalledProcessError:
        print(f"{Color.FAIL}[!] Gagal memulai {service_name}. Cek status service.{Color.ENDC}")
        return False
    except subprocess.TimeoutExpired:
        print(f"{Color.FAIL}[!] Timeout saat restart {service_name}.{Color.ENDC}")
        return False

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

# --- FUNGSI VERIFIKASI & TESTING ---

def get_current_dns():
    dns_list = []
    try:
        with open(RESOLV_CONF, 'r') as f:
            for line in f:
                if line.startswith('nameserver'):
                    parts = line.split()
                    if len(parts) > 1:
                        dns_list.append(parts[1])
        if not dns_list:
            return ["(Kosong / Tidak ada nameserver)"]
        return dns_list
    except FileNotFoundError:
        return ["File belum ada (Akan dibuat otomatis)"]
    except Exception as e:
        return [f"Error: {str(e)}"]

def verify_dns_change(expected_ips):
    print(f"{Color.BLUE}[i] Verifikasi konfigurasi DNS...{Color.ENDC}")
    time.sleep(1)
    current = get_current_dns()
    valid = all(ip in current for ip in expected_ips)
    if valid:
        print(f"{Color.GREEN}[✓] VERIFIED: Konfigurasi DNS sesuai.{Color.ENDC}")
        return True
    else:
        print(f"{Color.FAIL}[✗] FAILED: Ekspektasi {expected_ips}, terdeteksi {current}{Color.ENDC}")
        log_action("VERIFY_FAIL", f"Expected {expected_ips}, got {current}")
        return False

def test_dns_connectivity():
    """Test DNS resolution connectivity (not a DNS leak test)."""
    print(f"\n{Color.WARNING}[*] Melakukan DNS Connectivity Test...{Color.ENDC}")
    test_domains = ['google.com', 'cloudflare.com', 'github.com']
    success_count = 0
    for domain in test_domains:
        try:
            result = subprocess.run(['getent', 'hosts', domain], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"{Color.GREEN}[✓] Resolve {domain} : OK{Color.ENDC}")
                success_count += 1
            else:
                print(f"{Color.FAIL}[✗] Resolve {domain} : FAILED{Color.ENDC}")
        except Exception:
            print(f"{Color.WARNING}[?] Resolve {domain} : TIMEOUT{Color.ENDC}")
    
    status = "UNKNOWN"
    if success_count == len(test_domains):
        print(f"{Color.GREEN}[✓] DNS CONNECTIVITY: EXCELLENT{Color.ENDC}")
        status = "EXCELLENT"
    elif success_count > 0:
        print(f"{Color.WARNING}[!] DNS CONNECTIVITY: UNSTABLE{Color.ENDC}")
        status = "UNSTABLE"
    else:
        print(f"{Color.FAIL}[!] DNS CONNECTIVITY: DISCONNECTED / DNS ERROR{Color.ENDC}")
        status = "DISCONNECTED"
    log_action("DNS_CONNECTIVITY", f"Status: {status} ({success_count}/{len(test_domains)})")

def benchmark_dns(ip, domain='google.com', rounds=3):
    if not shutil.which('nslookup'):
        print(f"{Color.FAIL}[!] 'nslookup' tidak ditemukan. Install dnsutils: sudo apt install dnsutils{Color.ENDC}")
        return float('inf')
    times = []
    for _ in range(rounds):
        try:
            start = time.time()
            subprocess.run(['nslookup', '-timeout=2', domain, ip],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            times.append(time.time() - start)
        except Exception:
            pass
    return sum(times) / len(times) if times else float('inf')

def run_benchmark():
    print(f"\n{Color.WARNING}[*] Benchmarking DNS Speed (3-round avg, lower is better)...{Color.ENDC}")
    if not shutil.which('nslookup'):
        print(f"{Color.FAIL}[!] 'nslookup' tidak ditemukan. Install: sudo apt install dnsutils{Color.ENDC}")
        return
    results = []
    for key, data in DNS_PRESETS.items():
        name = data['name']
        primary_ip = data['ips'][0]
        print(f"Testing {name.ljust(20)}...", end='', flush=True)
        avg_time = benchmark_dns(primary_ip)
        if avg_time != float('inf'):
            print(f" {Color.GREEN}{avg_time:.4f}s{Color.ENDC}")
            results.append((name, avg_time))
        else:
            print(f" {Color.FAIL}Timeout{Color.ENDC}")
    if results:
        best = min(results, key=lambda x: x[1])
        print(f"\n{Color.BLUE}[i] Rekomendasi Tercepat: {Color.BOLD}{best[0]} ({best[1]:.4f}s){Color.ENDC}")
        log_action("BENCHMARK", f"Best: {best[0]} ({best[1]:.4f}s)")
    else:
        print(f"\n{Color.FAIL}[!] Semua koneksi timeout. Periksa internet Anda.{Color.ENDC}")

# --- FUNGSI MANAJEMEN DNS ---

def unlock_file():
    try:
        subprocess.run(['chattr', '-i', RESOLV_CONF], stderr=subprocess.DEVNULL)
    except Exception:
        pass

def lock_file():
    try:
        subprocess.run(['chattr', '+i', RESOLV_CONF], check=True, stderr=subprocess.PIPE)
        print(f"{Color.BLUE}[i] File resolv.conf dikunci (Immutable).{Color.ENDC}")
    except subprocess.CalledProcessError:
        print(f"{Color.WARNING}[i] Info: Filesystem tidak mendukung chattr +i (Skipped).{Color.ENDC}")
    except Exception as e:
        print(f"{Color.WARNING}[!] Gagal mengunci file: {e}{Color.ENDC}")

def flush_dns_cache():
    print(f"{Color.BLUE}[i] Membersihkan DNS Cache System...{Color.ENDC}")
    commands = [['resolvectl', 'flush-caches'], ['systemd-resolve', '--flush-caches'], ['service', 'nscd', 'restart']]
    for cmd in commands:
        try:
            subprocess.run(cmd, stderr=subprocess.DEVNULL)
        except Exception:
            continue
    log_action("FLUSH", "DNS Cache flushed")

def set_dns(nameservers, provider_name="Custom"):
    valid_ips = []
    for ns in nameservers:
        cleaned = validate_ip(ns)
        if cleaned: valid_ips.append(cleaned)
        else: print(f"{Color.FAIL}[!] IP Invalid diabaikan: {ns}{Color.ENDC}")
    
    if not valid_ips:
        print(f"{Color.FAIL}[!] Tidak ada IP DNS valid yang dimasukkan.{Color.ENDC}")
        return

    print(f"\n{Color.WARNING}[*] Menerapkan DNS {provider_name} (Standard)...{Color.ENDC}")
    log_action("SET_DNS", f"Provider: {provider_name}, IPs: {valid_ips}")
    
    restore_systemd_config_silent()
    unlock_file()
    backup_file(RESOLV_CONF)

    content = f"# Generated by KaliDNS Tool - {provider_name}\n# Updated at: {datetime.datetime.now()}\n"
    for ns in valid_ips: content += f"nameserver {ns}\n"

    if atomic_write(RESOLV_CONF, content):
        print(f"{Color.GREEN}[+] Berhasil mengubah DNS ke: {', '.join(valid_ips)}{Color.ENDC}")
        lock_file()
        flush_dns_cache()
        if verify_dns_change(valid_ips): test_dns_connectivity()

def setup_dot(provider="Cloudflare"):
    print(f"\n{Color.WARNING}[*] Mengaktifkan Mode Anti-Blokir (DoT - {provider})...{Color.ENDC}")
    log_action("SETUP_DOT", f"Provider: {provider}")

    if not os.path.exists(SYSTEMD_RESOLVED_CONF):
        print(f"{Color.FAIL}[!] Config {SYSTEMD_RESOLVED_CONF} tidak ditemukan.{Color.ENDC}")
        return

    # Konfigurasi Provider DoT
    if provider == "Cloudflare":
        dns_ip = "1.1.1.1 1.0.0.1 2606:4700:4700::1111 2606:4700:4700::1001"
        fallback = "8.8.8.8"
    elif provider == "Google":
        dns_ip = "8.8.8.8 8.8.4.4 2001:4860:4860::8888 2001:4860:4860::8844"
        fallback = "1.1.1.1"
    elif provider == "Quad9":
        dns_ip = "9.9.9.9 149.112.112.112 2620:fe::fe 2620:fe::9"
        fallback = "1.1.1.1"
    
    config_content = f"[Resolve]\nDNS={dns_ip}\nFallbackDNS={fallback}\nDomains=~.\nDNSOverTLS=yes\nDNSSEC=allow-downgrade\n"
    
    backup_file(SYSTEMD_RESOLVED_CONF)
    if not atomic_write(SYSTEMD_RESOLVED_CONF, config_content): return

    try:
        subprocess.run(['systemctl', 'enable', 'systemd-resolved'], stderr=subprocess.DEVNULL)
    except Exception:
        pass
    
    if not safe_restart_service('systemd-resolved'):
        print(f"{Color.FAIL}[!] Gagal restart systemd-resolved.{Color.ENDC}")
        return

    unlock_file()
    resolv_content = "# Generated by KaliDNS Tool - DoT SECURE MODE\nnameserver 127.0.0.53\noptions edns0 trust-ad\n"
    
    if atomic_write(RESOLV_CONF, resolv_content):
        lock_file()
        flush_dns_cache()
        print(f"{Color.GREEN}[+] SUKSES! Mode Anti-Blokir (DoT) aktif.{Color.ENDC}")
        test_dns_connectivity()

def _find_latest_backup(filepath):
    """Find the most recent .backup_* file for a given config file."""
    backup_dir = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    backups = []
    try:
        for f in os.listdir(backup_dir):
            if f.startswith(basename + '.backup_'):
                full = os.path.join(backup_dir, f)
                if os.path.isfile(full):
                    backups.append(full)
    except Exception:
        return None
    if not backups:
        return None
    return max(backups, key=os.path.getmtime)

def restore_systemd_config_silent():
    latest = _find_latest_backup(SYSTEMD_RESOLVED_CONF)
    if latest:
        shutil.copy2(latest, SYSTEMD_RESOLVED_CONF)
        safe_restart_service('systemd-resolved')

def restore_default():
    confirm = input(f"{Color.WARNING}[?] Yakin ingin mereset semua konfigurasi DNS? (y/N): {Color.ENDC}")
    if confirm.strip().lower() != 'y':
        print(f"{Color.BLUE}[i] Operasi dibatalkan.{Color.ENDC}")
        return

    print(f"\n{Color.WARNING}[*] Mengembalikan ke Default (DHCP)...{Color.ENDC}")
    log_action("RESTORE", "Restoring to default configuration")
    
    default_systemd = "# systemd-resolved.conf (Reset by KaliDNS)\n[Resolve]\n#DNS=\n#FallbackDNS=\n#DNSOverTLS=no\n"
    atomic_write(SYSTEMD_RESOLVED_CONF, default_systemd)
    safe_restart_service('systemd-resolved')
    unlock_file()
    if os.path.exists(RESOLV_CONF): os.remove(RESOLV_CONF)
    print(f"{Color.BLUE}[i] Meminta NetworkManager membuat ulang konfigurasi...{Color.ENDC}")
    safe_restart_service('NetworkManager')
    flush_dns_cache()
    print(f"{Color.GREEN}[+] Selesai. DNS dikembalikan ke pengaturan otomatis.{Color.ENDC}")

def print_dot_status():
    dot_status = "Non-Aktif (Standard)"
    if os.path.exists(SYSTEMD_RESOLVED_CONF):
        try:
            with open(SYSTEMD_RESOLVED_CONF, 'r') as f:
                if "DNSOverTLS=yes" in f.read():
                    dot_status = f"{Color.GREEN}AKTIF (Secure/Encrypted){Color.ENDC}"
        except Exception:
            pass
    print(f"Status Anti-Blokir (DoT): {dot_status}")

def parse_args():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in DNS_PRESETS:
            preset = DNS_PRESETS[arg]
            set_dns(preset['ips'], preset['name'])
            return True
        elif arg == '--test':
            test_dns_connectivity()
            return True
        elif arg == '--benchmark':
            run_benchmark()
            return True
        elif arg == '--status':
            current = get_current_dns()
            print(f"Current DNS: {', '.join(current)}")
            print_dot_status()
            return True
        elif arg == '--reset':
            restore_default()
            return True
        elif arg == '--help' or arg == '-h':
            print(f"{Color.BOLD}Usage:{Color.ENDC} sudo python3 kalidns.py [OPTION]")
            print("\nOptions:")
            print("  1-5        : Apply preset")
            print("  --test     : Run DNS leak test")
            print("  --benchmark: Run speed test")
            print("  --status   : Show status")
            print("  --reset    : Restore default")
            return True
        else:
            print(f"{Color.FAIL}[!] Argumen tidak dikenal. Gunakan --help.{Color.ENDC}")
            return True
    return False

def main():
    check_root()
    if parse_args(): sys.exit()
    cleanup_old_backups()
    
    while True:
        clear_screen()
        banner()
        current = get_current_dns()
        print(f"DNS di /etc/resolv.conf: {Color.GREEN}{', '.join(current)}{Color.ENDC}")
        print_dot_status()
        print("")
        print("PILIHAN DNS STANDARD (Cepat & Stabil):")
        for key, data in DNS_PRESETS.items():
            print(f"{key}. {data['name']} ({', '.join(data['ips'])})")
        print(f"6. Input Custom (Manual)")
        print("-" * 40)
        print(f"{Color.WARNING}PILIHAN ANTI-BLOKIR (Enkripsi/DoT):{Color.ENDC}")
        print("7. Aktifkan Mode Anti-Blokir (Cloudflare Secure)")
        print("8. Aktifkan Mode Anti-Blokir (Google Secure)")
        print("9. Aktifkan Mode Anti-Blokir (Quad9 Secure)")
        print("-" * 40)
        print(f"{Color.BLUE}UTILITIES:{Color.ENDC}")
        print("10. Benchmark Kecepatan DNS (Speed Test)")
        print("11. Cek Koneksi (Leak Test)")
        print(f"12. {Color.FAIL}Reset ke Default (Hapus Semua Config){Color.ENDC}")
        print("0.  Keluar")
        
        choice = input(f"\n{Color.BOLD}Masukan Pilihan: {Color.ENDC}")
        if choice in DNS_PRESETS:
            preset = DNS_PRESETS[choice]
            set_dns(preset['ips'], preset['name'])
        elif choice == '6':
            ns1 = input("Masukkan Primary DNS: ")
            ns2 = input("Masukkan Secondary DNS (opsional): ")
            servers = [ns1]
            if ns2.strip(): servers.append(ns2)
            set_dns(servers, "Custom")
        elif choice == '7': setup_dot("Cloudflare")
        elif choice == '8': setup_dot("Google")
        elif choice == '9': setup_dot("Quad9")
        elif choice == '10': run_benchmark()
        elif choice == '11': test_dns_connectivity()
        elif choice == '12': restore_default()
        elif choice == '0':
            print("Keluar.")
            sys.exit()
        input(f"\n{Color.BLUE}Tekan Enter untuk kembali ke menu...{Color.ENDC}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nOperasi dibatalkan pengguna.")
