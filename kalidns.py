#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import time
import ipaddress
import datetime
import json
import socket
import urllib.request
import random
import string

# --- RICH TUI (optional, graceful fallback) ---
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import box
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# --- KONFIGURASI WARNA (fallback when rich unavailable) ---
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
    '1': {'name': 'Google', 'ips': ['8.8.8.8', '8.8.4.4'],
          'ipv6': ['2001:4860:4860::8888', '2001:4860:4860::8844']},
    '2': {'name': 'Cloudflare', 'ips': ['1.1.1.1', '1.0.0.1'],
          'ipv6': ['2606:4700:4700::1111', '2606:4700:4700::1001']},
    '3': {'name': 'Quad9 (Security)', 'ips': ['9.9.9.9', '149.112.112.112'],
          'ipv6': ['2620:fe::fe', '2620:fe::9']},
    '4': {'name': 'AdGuard (No Ads)', 'ips': ['94.140.14.14', '94.140.15.15'],
          'ipv6': ['2a10:50c0::ad1:ff', '2a10:50c0::ad2:ff']},
    '5': {'name': 'CleanBrowsing (Family)', 'ips': ['185.228.168.9', '185.228.169.9'],
          'ipv6': ['2a0d:2a00:1::2', '2a0d:2a00:2::2']},
}

# --- DoH PROVIDER CONFIG ---
DOH_PROVIDERS = {
    'Cloudflare': {
        'server_name': 'cloudflare-dns.com',
        'stamp': 'sdns://AgcAAAAAAAAABzEuMC4wLjEAEmRucy5jbG91ZGZsYXJlLmNvbQovZG5zLXF1ZXJ5',
        'listen': '127.0.0.1:53',
    },
    'Google': {
        'server_name': 'dns.google',
        'stamp': 'sdns://AgUAAAAAAAAABzguOC44LjigHvYkz_9ea9O63fP92_3qVlRn43cpncfuZnUWbzAMwbkgRE69Z7uD-IB7OSHpOKyReLiCvVCq2xEjHwRM9fCN984KZG5zLmdvb2dsZQovZG5zLXF1ZXJ5',
        'listen': '127.0.0.1:53',
    },
}

DNSCRYPT_PROXY_CONF = "/etc/dnscrypt-proxy/dnscrypt-proxy.toml"

# --- FUNGSI UTILITAS ---

def check_root():
    if os.geteuid() != 0:
        print(f"{Color.FAIL}[!] Script ini harus dijalankan sebagai ROOT (sudo).{Color.ENDC}")
        sys.exit(1)

def clear_screen():
    if RICH_AVAILABLE:
        console.clear()
    else:
        subprocess.run(['clear'], stderr=subprocess.DEVNULL)

def banner():
    if RICH_AVAILABLE:
        banner_text = Text()
        banner_text.append("KALI LINUX DNS CHANGER TOOL\n", style="bold cyan")
        banner_text.append("v2.0 ULTIMATE EDITION\n", style="bold white")
        banner_text.append("DoT • DoH • Leak Test • Benchmark • IPv6", style="dim")
        console.print(Panel(banner_text, border_style="bright_cyan", box=box.DOUBLE_EDGE, padding=(1, 2)))
    else:
        print(f"{Color.HEADER}{Color.BOLD}")
        print("="*60)
        print("   KALI LINUX DNS CHANGER TOOL (ULTIMATE EDITION v2.0)")
        print("   DoT • DoH • Leak Test • Benchmark • IPv6")
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

def test_dns_leak():
    """Perform a real DNS leak test using bash.ws API."""
    print(f"\n{Color.WARNING}[*] Melakukan DNS Leak Test (via bash.ws)...{Color.ENDC}")
    # Generate unique test ID
    test_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

    # Step 1: Trigger DNS resolution through the system resolver
    print(f"{Color.BLUE}[i] Mengirim query DNS test...{Color.ENDC}")
    resolve_domains = [f"{i}.{test_id}.bash.ws" for i in range(1, 11)]
    for domain in resolve_domains:
        try:
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
        except Exception:
            pass
        time.sleep(0.3)

    # Step 2: Fetch results from API
    time.sleep(2)
    api_url = f"https://bash.ws/dnsleak/test/{test_id}?json"
    print(f"{Color.BLUE}[i] Mengambil hasil dari API...{Color.ENDC}")
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'KaliDNS/2.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"{Color.FAIL}[!] Gagal mengambil hasil leak test: {e}{Color.ENDC}")
        print(f"{Color.BLUE}[i] Coba manual: https://bash.ws/dnsleak{Color.ENDC}")
        log_action("DNS_LEAK", f"API error: {e}")
        return

    # Step 3: Parse and display results
    if not data:
        print(f"{Color.WARNING}[!] Tidak ada data dari API. Server mungkin sibuk.{Color.ENDC}")
        return

    dns_servers = []
    conclusion = ""
    for entry in data:
        entry_type = entry.get('type', '')
        if entry_type == 'dns':
            ip = entry.get('ip', 'N/A')
            country = entry.get('country_name', 'Unknown')
            asn = entry.get('asn', '')
            isp = entry.get('asn_name', 'Unknown')
            dns_servers.append({'ip': ip, 'country': country, 'isp': isp, 'asn': asn})
        elif entry_type == 'conclusion':
            conclusion = entry.get('ip', '')

    if dns_servers:
        print(f"\n{Color.BOLD}DNS Resolvers Terdeteksi:{Color.ENDC}")
        print(f"{'No':>3}  {'IP Address':<20} {'Country':<15} {'ISP':<30}")
        print("-" * 70)
        for i, srv in enumerate(dns_servers, 1):
            print(f"{i:>3}  {srv['ip']:<20} {srv['country']:<15} {srv['isp']:<30}")

        unique_isps = set(s['isp'] for s in dns_servers)
        if len(unique_isps) == 1:
            print(f"\n{Color.GREEN}[✓] AMAN: Semua DNS query melalui satu provider ({list(unique_isps)[0]}).{Color.ENDC}")
        else:
            print(f"\n{Color.FAIL}[!] PERHATIAN: DNS query melalui {len(unique_isps)} provider berbeda!{Color.ENDC}")
            print(f"{Color.FAIL}    Kemungkinan DNS LEAK terdeteksi.{Color.ENDC}")
    else:
        print(f"{Color.WARNING}[!] Tidak ada DNS resolver terdeteksi.{Color.ENDC}")

    if conclusion:
        print(f"\n{Color.BLUE}[i] Kesimpulan: {conclusion}{Color.ENDC}")

    log_action("DNS_LEAK", f"Servers: {len(dns_servers)}, ISPs: {len(set(s['isp'] for s in dns_servers)) if dns_servers else 0}")

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
    if RICH_AVAILABLE:
        _run_benchmark_rich()
    else:
        _run_benchmark_plain()

def _run_benchmark_rich():
    if not shutil.which('nslookup'):
        console.print("[bold red][!] 'nslookup' tidak ditemukan. Install: sudo apt install dnsutils[/bold red]")
        return
    console.print("\n[bold yellow][*] Benchmarking DNS Speed (3-round avg)...[/bold yellow]")
    results = []
    table = Table(title="DNS Benchmark Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Provider", style="bold white", min_width=20)
    table.add_column("Avg Speed", justify="right", min_width=12)
    table.add_column("Status", justify="center")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), transient=True, console=console) as progress:
        task = progress.add_task("Testing...", total=len(DNS_PRESETS))
        for key, data in DNS_PRESETS.items():
            name = data['name']
            progress.update(task, description=f"Testing {name}...")
            avg_time = benchmark_dns(data['ips'][0])
            if avg_time != float('inf'):
                table.add_row(name, f"{avg_time:.4f}s", "[green]✓ OK[/green]")
                results.append((name, avg_time))
            else:
                table.add_row(name, "---", "[red]✗ Timeout[/red]")
            progress.advance(task)

    console.print(table)
    if results:
        best = min(results, key=lambda x: x[1])
        console.print(f"\n[bold cyan][i] Rekomendasi Tercepat: [bold white]{best[0]} ({best[1]:.4f}s)[/bold white][/bold cyan]")
        log_action("BENCHMARK", f"Best: {best[0]} ({best[1]:.4f}s)")
    else:
        console.print("\n[bold red][!] Semua koneksi timeout.[/bold red]")

def _run_benchmark_plain():
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

def setup_doh(provider="Cloudflare"):
    """Setup DNS-over-HTTPS using dnscrypt-proxy."""
    print(f"\n{Color.WARNING}[*] Mengaktifkan Mode DoH - {provider}...{Color.ENDC}")
    log_action("SETUP_DOH", f"Provider: {provider}")

    if provider not in DOH_PROVIDERS:
        print(f"{Color.FAIL}[!] Provider DoH '{provider}' tidak dikenal.{Color.ENDC}")
        return

    # Check if dnscrypt-proxy is installed
    if not shutil.which('dnscrypt-proxy'):
        print(f"{Color.WARNING}[!] dnscrypt-proxy belum terinstall.{Color.ENDC}")
        confirm = input(f"{Color.WARNING}[?] Install dnscrypt-proxy sekarang? (y/N): {Color.ENDC}")
        if confirm.strip().lower() != 'y':
            print(f"{Color.BLUE}[i] Install manual: sudo apt install dnscrypt-proxy{Color.ENDC}")
            return
        print(f"{Color.BLUE}[i] Menginstall dnscrypt-proxy (ini bisa memakan waktu)...{Color.ENDC}")
        try:
            subprocess.run(['apt', 'update', '-qq'], check=True, timeout=180)
        except subprocess.TimeoutExpired:
            print(f"{Color.FAIL}[!] 'apt update' timeout. Kemungkinan DNS belum aktif atau koneksi lambat.{Color.ENDC}")
            print(f"{Color.BLUE}[i] Coba: 1) Reset DNS dulu (menu 15), 2) Pastikan internet aktif, 3) Install manual: sudo apt install dnscrypt-proxy{Color.ENDC}")
            return
        except Exception as e:
            print(f"{Color.FAIL}[!] Gagal apt update: {e}{Color.ENDC}")
            return
        try:
            subprocess.run(['apt', 'install', '-y', '-qq', 'dnscrypt-proxy'], check=True, timeout=300)
        except subprocess.TimeoutExpired:
            print(f"{Color.FAIL}[!] Install dnscrypt-proxy timeout. Coba manual: sudo apt install dnscrypt-proxy{Color.ENDC}")
            return
        except Exception as e:
            print(f"{Color.FAIL}[!] Gagal install: {e}{Color.ENDC}")
            return

    prov = DOH_PROVIDERS[provider]

    # Generate dnscrypt-proxy config
    config = f"""# Generated by KaliDNS Tool - DoH Mode ({provider})
listen_addresses = ['{prov['listen']}']
max_clients = 250
ipv4_servers = true
ipv6_servers = false
dnscrypt_servers = false
doh_servers = true
require_dnssec = false
require_nolog = true
require_nofilter = true
force_tcp = false
timeout = 5000
keepalive = 30
log_level = 2
use_syslog = false
cache = true
cache_size = 4096
cache_min_ttl = 2400
cache_max_ttl = 86400
cache_neg_min_ttl = 60
cache_neg_max_ttl = 600

[static]
[static.'{prov['server_name']}']
stamp = '{prov['stamp']}'
"""

    conf_dir = os.path.dirname(DNSCRYPT_PROXY_CONF)
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir, exist_ok=True)

    backup_file(DNSCRYPT_PROXY_CONF)
    if not atomic_write(DNSCRYPT_PROXY_CONF, config):
        return

    # Stop systemd-resolved to free port 53
    try:
        subprocess.run(['systemctl', 'stop', 'systemd-resolved'], stderr=subprocess.DEVNULL, timeout=10)
        subprocess.run(['systemctl', 'disable', 'systemd-resolved'], stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass

    # Start dnscrypt-proxy
    if not safe_restart_service('dnscrypt-proxy'):
        print(f"{Color.FAIL}[!] Gagal menjalankan dnscrypt-proxy.{Color.ENDC}")
        return

    # Point resolv.conf to localhost
    unlock_file()
    resolv_content = f"# Generated by KaliDNS Tool - DoH MODE ({provider})\nnameserver 127.0.0.1\n"
    if atomic_write(RESOLV_CONF, resolv_content):
        lock_file()
        flush_dns_cache()
        print(f"{Color.GREEN}[+] SUKSES! Mode DoH ({provider}) aktif via dnscrypt-proxy.{Color.ENDC}")
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
    doh_status = "Non-Aktif"
    if os.path.exists(SYSTEMD_RESOLVED_CONF):
        try:
            with open(SYSTEMD_RESOLVED_CONF, 'r') as f:
                if "DNSOverTLS=yes" in f.read():
                    dot_status = f"{Color.GREEN}AKTIF (Secure/Encrypted){Color.ENDC}"
        except Exception:
            pass
    if os.path.exists(DNSCRYPT_PROXY_CONF):
        try:
            with open(DNSCRYPT_PROXY_CONF, 'r') as f:
                content = f.read()
                if 'doh_servers = true' in content:
                    # Check if dnscrypt-proxy is running
                    result = subprocess.run(['systemctl', 'is-active', 'dnscrypt-proxy'],
                                          capture_output=True, text=True)
                    if result.stdout.strip() == 'active':
                        doh_status = f"{Color.GREEN}AKTIF (DoH via dnscrypt-proxy){Color.ENDC}"
        except Exception:
            pass
    print(f"Status Anti-Blokir (DoT): {dot_status}")
    print(f"Status DoH             : {doh_status}")

def parse_args():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        use_ipv6 = '--ipv6' in sys.argv
        if arg in DNS_PRESETS:
            preset = DNS_PRESETS[arg]
            ips = list(preset['ips'])
            if use_ipv6 and 'ipv6' in preset:
                ips.extend(preset['ipv6'])
            set_dns(ips, preset['name'])
            return True
        elif arg == '--test':
            test_dns_connectivity()
            return True
        elif arg == '--leak':
            test_dns_leak()
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
            print("  1-5          : Apply preset (add --ipv6 for IPv6)")
            print("  --test       : Run DNS connectivity test")
            print("  --leak       : Run DNS leak test (bash.ws)")
            print("  --benchmark  : Run speed test")
            print("  --status     : Show status")
            print("  --reset      : Restore default")
            print("  --ipv6       : Include IPv6 with presets")
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

        if RICH_AVAILABLE:
            console.print(f"DNS: [bold green]{', '.join(current)}[/bold green]")
            print_dot_status()
            console.print()

            # Presets table
            t = Table(title="DNS Presets", box=box.SIMPLE_HEAVY, border_style="cyan")
            t.add_column("#", style="bold", width=3)
            t.add_column("Provider", style="bold white")
            t.add_column("IPv4", style="green")
            t.add_column("IPv6", style="dim")
            for key, data in DNS_PRESETS.items():
                t.add_row(key, data['name'], ', '.join(data['ips']), ', '.join(data.get('ipv6', [])[:1]))
            t.add_row("6", "Custom (Manual)", "IPv4/IPv6", "")
            console.print(t)

            console.print("\n[bold yellow]ANTI-BLOKIR (Enkripsi):[/bold yellow]")
            console.print(" 7-9.   DoT (Cloudflare / Google / Quad9)")
            console.print(" 10-11. DoH (Cloudflare / Google via dnscrypt-proxy)")
            console.print(f"\n[bold cyan]UTILITIES:[/bold cyan]")
            console.print(" 12. Benchmark  |  13. Connectivity  |  14. Leak Test")
            console.print(" [bold red]15. Reset ke Default[/bold red]  |  0. Keluar")
            choice = Prompt.ask("\n[bold]Pilihan", default="0")
        else:
            print(f"DNS di /etc/resolv.conf: {Color.GREEN}{', '.join(current)}{Color.ENDC}")
            print_dot_status()
            print("")
            print("PILIHAN DNS STANDARD (Cepat & Stabil):")
            for key, data in DNS_PRESETS.items():
                ipv6_info = f" | IPv6: {', '.join(data.get('ipv6', [])[:1])}" if data.get('ipv6') else ''
                print(f"{key}. {data['name']} ({', '.join(data['ips'])}{ipv6_info})")
            print(f"6. Input Custom (Manual, mendukung IPv4/IPv6)")
            print("-" * 60)
            print(f"{Color.WARNING}PILIHAN ANTI-BLOKIR (Enkripsi):{Color.ENDC}")
            print("7.  Aktifkan DoT (Cloudflare Secure)")
            print("8.  Aktifkan DoT (Google Secure)")
            print("9.  Aktifkan DoT (Quad9 Secure)")
            print("10. Aktifkan DoH (Cloudflare via dnscrypt-proxy)")
            print("11. Aktifkan DoH (Google via dnscrypt-proxy)")
            print("-" * 60)
            print(f"{Color.BLUE}UTILITIES:{Color.ENDC}")
            print("12. Benchmark Kecepatan DNS (Speed Test)")
            print("13. Cek Koneksi DNS (Connectivity Test)")
            print("14. DNS Leak Test (bash.ws)")
            print(f"15. {Color.FAIL}Reset ke Default (Hapus Semua Config){Color.ENDC}")
            print("0.  Keluar")
            choice = input(f"\n{Color.BOLD}Masukan Pilihan: {Color.ENDC}")
        if choice in DNS_PRESETS:
            preset = DNS_PRESETS[choice]
            use_v6 = input("Tambahkan IPv6? (y/N): ").strip().lower() == 'y'
            ips = list(preset['ips'])
            if use_v6 and 'ipv6' in preset:
                ips.extend(preset['ipv6'])
            set_dns(ips, preset['name'])
        elif choice == '6':
            print(f"{Color.BLUE}[i] Contoh IPv4: 8.8.8.8 | IPv6: 2001:4860:4860::8888{Color.ENDC}")
            ns1 = input("Masukkan Primary DNS  : ")
            ns2 = input("Masukkan Secondary DNS (opsional): ")
            servers = [ns1]
            if ns2.strip(): servers.append(ns2)
            set_dns(servers, "Custom")
        elif choice == '7': setup_dot("Cloudflare")
        elif choice == '8': setup_dot("Google")
        elif choice == '9': setup_dot("Quad9")
        elif choice == '10': setup_doh("Cloudflare")
        elif choice == '11': setup_doh("Google")
        elif choice == '12': run_benchmark()
        elif choice == '13': test_dns_connectivity()
        elif choice == '14': test_dns_leak()
        elif choice == '15': restore_default()
        elif choice == '0':
            print("Keluar.")
            sys.exit()
        input(f"\n{Color.BLUE}Tekan Enter untuk kembali ke menu...{Color.ENDC}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nOperasi dibatalkan pengguna.")
