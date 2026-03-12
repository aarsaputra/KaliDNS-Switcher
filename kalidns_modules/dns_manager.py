import os
import time
import subprocess
import datetime
import shutil
import socket
import urllib.request
import json
import random
import string
from .config import (
    RESOLV_CONF, SYSTEMD_RESOLVED_CONF, DNSCRYPT_PROXY_CONF,
    DOH_PROVIDERS, DNS_PRESETS
)
from .utils import (
    Color, log_action, validate_ip, backup_file, unlock_file, 
    lock_file, atomic_write, safe_restart_service
)

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

def run_dns_connectivity_test():
    print(f"\n{Color.WARNING}[*] Melakukan DNS Connectivity Test...{Color.ENDC}")
    test_domains = ['google.com', 'cloudflare.com', 'github.com']
    success_count = 0
    for domain in test_domains:
        try:
            # Use getent for system resolution check
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

def run_dns_leak_test(rich_available=False):
    from rich.prompt import Confirm
    print(f"\n{Color.WARNING}[*] Melakukan DNS Leak Test (via bash.ws)...{Color.ENDC}")
    
    # Disclaimer
    print(f"{Color.WARNING}[!] DISCLAIMER: Tes ini mengirimkan query DNS test ke server pihak ketiga (bash.ws).")
    print(f"    IP publik dan Test ID Anda akan terlihat oleh bash.ws.{Color.ENDC}")
    
    if rich_available:
        if not Confirm.ask("Lanjutkan DNS Leak Test?", default=False):
            return
    else:
        confirm = input(f"{Color.WARNING}[?] Lanjutkan DNS Leak Test? (y/N): {Color.ENDC}")
        if confirm.strip().lower() != 'y':
            return

    test_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

    print(f"{Color.BLUE}[i] Mengirim query DNS test...{Color.ENDC}")
    resolve_domains = [f"{i}.{test_id}.bash.ws" for i in range(1, 11)]
    for domain in resolve_domains:
        try:
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
        except Exception:
            pass
        time.sleep(0.3)

    time.sleep(2)
    api_url = f"https://bash.ws/dnsleak/test/{test_id}?json"
    print(f"{Color.BLUE}[i] Mengambil hasil dari API...{Color.ENDC}")
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'KaliDNS/2.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"{Color.FAIL}[!] Gagal mengambil hasil leak test: {e}{Color.ENDC}")
        log_action("DNS_LEAK", f"API error: {e}")
        return

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
            isp = entry.get('asn_name', 'Unknown')
            dns_servers.append({'ip': ip, 'country': country, 'isp': isp})
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

    log_action("DNS_LEAK", f"Servers: {len(dns_servers)}")

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
    
    # Reset systemd-resolved to ensure standard mode works
    restore_systemd_config_silent()
    unlock_file()
    backup_file(RESOLV_CONF)

    content = f"# Generated by KaliDNS Tool - {provider_name}\n# Updated at: {datetime.datetime.now()}\n"
    for ns in valid_ips: content += f"nameserver {ns}\n"

    if atomic_write(RESOLV_CONF, content):
        print(f"{Color.GREEN}[+] Berhasil mengubah DNS ke: {', '.join(valid_ips)}{Color.ENDC}")
        lock_file()
        flush_dns_cache()
        if verify_dns_change(valid_ips): run_dns_connectivity_test()

def setup_dot(provider="Cloudflare"):
    print(f"\n{Color.WARNING}[*] Mengaktifkan Mode Anti-Blokir (DoT - {provider})...{Color.ENDC}")
    log_action("SETUP_DOT", f"Provider: {provider}")

    if not os.path.exists(SYSTEMD_RESOLVED_CONF):
        print(f"{Color.FAIL}[!] Config {SYSTEMD_RESOLVED_CONF} tidak ditemukan.{Color.ENDC}")
        return

    # Configuration for DoT Providers
    if provider == "Cloudflare":
        dns_ip = "1.1.1.1 1.0.0.1 2606:4700:4700::1111 2606:4700:4700::1001"
        fallback = "8.8.8.8"
    elif provider == "Google":
        dns_ip = "8.8.8.8 8.8.4.4 2001:4860:4860::8888 2001:4860:4860::8844"
        fallback = "1.1.1.1"
    elif provider == "Quad9":
        dns_ip = "9.9.9.9 149.112.112.112 2620:fe::fe 2620:fe::9"
        fallback = "1.1.1.1"
    else:
        print(f"{Color.FAIL}[!] Provider DoT '{provider}' tidak dikenal.{Color.ENDC}")
        return
    
    config_content = f"[Resolve]\nDNS={dns_ip}\nFallbackDNS={fallback}\nDomains=~.\nDNSOverTLS=yes\nDNSSEC=allow-downgrade\n"
    
    backup_file(SYSTEMD_RESOLVED_CONF)
    if not atomic_write(SYSTEMD_RESOLVED_CONF, config_content): return

    try:
        subprocess.run(['systemctl', 'enable', 'systemd-resolved'], stderr=subprocess.DEVNULL)
    except Exception:
        pass
    
    if not safe_restart_service('systemd-resolved'):
        return

    unlock_file()
    resolv_content = "# Generated by KaliDNS Tool - DoT SECURE MODE\nnameserver 127.0.0.53\noptions edns0 trust-ad\n"
    
    if atomic_write(RESOLV_CONF, resolv_content):
        lock_file()
        flush_dns_cache()
        print(f"{Color.GREEN}[+] SUKSES! Mode Anti-Blokir (DoT) aktif.{Color.ENDC}")
        run_dns_connectivity_test()

def setup_doh(provider="Cloudflare", rich_available=False):
    from rich.prompt import Confirm
    print(f"\n{Color.WARNING}[*] Mengaktifkan Mode DoH - {provider}...{Color.ENDC}")
    log_action("SETUP_DOH", f"Provider: {provider}")

    if provider not in DOH_PROVIDERS:
        print(f"{Color.FAIL}[!] Provider DoH '{provider}' tidak dikenal.{Color.ENDC}")
        return

    if not shutil.which('dnscrypt-proxy'):
        print(f"{Color.WARNING}[!] dnscrypt-proxy belum terinstall.{Color.ENDC}")
        if rich_available:
            confirm = Confirm.ask("Install dnscrypt-proxy sekarang?", default=False)
        else:
            confirm_raw = input(f"{Color.WARNING}[?] Install dnscrypt-proxy sekarang? (y/N): {Color.ENDC}")
            confirm = confirm_raw.strip().lower() == 'y'
        
        if not confirm:
            print(f"{Color.BLUE}[i] Install manual: sudo apt install dnscrypt-proxy{Color.ENDC}")
            return
            
        print(f"{Color.BLUE}[i] Menginstall dnscrypt-proxy...{Color.ENDC}")
        try:
            subprocess.run(['apt', 'update', '-qq'], check=True, timeout=180)
            subprocess.run(['apt', 'install', '-y', '-qq', 'dnscrypt-proxy'], check=True, timeout=300)
        except Exception as e:
            print(f"{Color.FAIL}[!] Gagal install: {e}{Color.ENDC}")
            return

    prov = DOH_PROVIDERS[provider]
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
    os.makedirs(conf_dir, exist_ok=True)

    backup_file(DNSCRYPT_PROXY_CONF)
    if not atomic_write(DNSCRYPT_PROXY_CONF, config): return

    try:
        subprocess.run(['systemctl', 'stop', 'systemd-resolved'], stderr=subprocess.DEVNULL)
        subprocess.run(['systemctl', 'disable', 'systemd-resolved'], stderr=subprocess.DEVNULL)
    except Exception: pass

    if not safe_restart_service('dnscrypt-proxy'): return

    unlock_file()
    resolv_content = f"# Generated by KaliDNS Tool - DoH MODE ({provider})\nnameserver 127.0.0.1\n"
    if atomic_write(RESOLV_CONF, resolv_content):
        lock_file()
        flush_dns_cache()
        print(f"{Color.GREEN}[+] SUKSES! Mode DoH ({provider}) aktif via dnscrypt-proxy.{Color.ENDC}")
        run_dns_connectivity_test()

def _find_latest_backup(filepath):
    backup_dir = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    backups = []
    try:
        if not os.path.exists(backup_dir): return None
        for f in os.listdir(backup_dir):
            if f.startswith(basename + '.backup_'):
                full = os.path.join(backup_dir, f)
                if os.path.isfile(full): backups.append(full)
    except Exception: return None
    if not backups: return None
    return max(backups, key=os.path.getmtime)

def restore_systemd_config_silent():
    """Silently restore systemd-resolved to default state to avoid conflicts in standard mode."""
    latest = _find_latest_backup(SYSTEMD_RESOLVED_CONF)
    if latest:
        shutil.copy2(latest, SYSTEMD_RESOLVED_CONF)
        safe_restart_service('systemd-resolved')

def restore_default(rich_available=False):
    from rich.prompt import Confirm
    if rich_available:
        confirm = Confirm.ask("Yakin ingin mereset semua konfigurasi DNS?", default=False)
    else:
        confirm_raw = input(f"{Color.WARNING}[?] Yakin ingin mereset semua konfigurasi DNS? (y/N): {Color.ENDC}")
        confirm = confirm_raw.strip().lower() == 'y'
        
    if not confirm:
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
