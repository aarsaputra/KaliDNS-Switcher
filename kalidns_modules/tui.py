import os
import subprocess
from .config import DNS_PRESETS, DOT_PROVIDERS, DOH_PROVIDERS, SYSTEMD_RESOLVED_CONF, DNSCRYPT_PROXY_CONF
from . import utils
from .utils import Color, RICH_AVAILABLE
from .benchmark import collect_benchmark_results, DEFAULT_BENCHMARK_ROUNDS

try:
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import box
except ImportError:
    pass

def get_dot_doh_status():
    dot_status = f"{Color.FAIL}Non-Aktif (Standard){Color.ENDC}"
    doh_status = f"{Color.FAIL}Non-Aktif{Color.ENDC}"
    
    if os.path.exists(SYSTEMD_RESOLVED_CONF):
        try:
            with open(SYSTEMD_RESOLVED_CONF, 'r') as f:
                if "DNSOverTLS=yes" in f.read():
                    dot_status = f"{Color.GREEN}AKTIF (Secure/Encrypted){Color.ENDC}"
        except Exception: pass
        
    if os.path.exists(DNSCRYPT_PROXY_CONF):
        try:
            with open(DNSCRYPT_PROXY_CONF, 'r') as f:
                if 'doh_servers = true' in f.read():
                    result = subprocess.run(['systemctl', 'is-active', 'dnscrypt-proxy'],
                                          capture_output=True, text=True)
                    if result.stdout.strip() == 'active':
                        doh_status = f"{Color.GREEN}AKTIF (DoH via dnscrypt-proxy){Color.ENDC}"
        except Exception: pass
        
    return dot_status, doh_status

def banner():
    if RICH_AVAILABLE and utils.console:
        banner_text = Text()
        banner_text.append("KALI LINUX DNS CHANGER TOOL\n", style="bold cyan")
        banner_text.append("v2.2 MODULAR EDITION\n", style="bold white")
        banner_text.append("DoT • DoH • Utilities • VPN Ready", style="dim")
        utils.console.print(Panel(banner_text, border_style="bright_cyan", box=box.DOUBLE_EDGE, padding=(1, 2)))
    else:
        print(f"{Color.HEADER}{Color.BOLD}")
        print("="*60)
        print("   KALI LINUX DNS CHANGER TOOL (MODULAR EDITION v2.2)")
        print("   DoT • DoH • Utilities • VPN Ready")
        print("="*60)
        print(f"{Color.ENDC}")

def run_benchmark_rich():
    if not (RICH_AVAILABLE and utils.console): return
    import shutil
    
    if not shutil.which('nslookup'):
        utils.console.print("[bold red][!] 'nslookup' tidak ditemukan. Install: sudo apt install dnsutils[/bold red]")
        return

    utils.console.print(f"\n[bold yellow][*] Benchmarking DNS Speed ({DEFAULT_BENCHMARK_ROUNDS}-round avg)...[/bold yellow]")
    
    results = []
    table = Table(title="DNS Benchmark Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Provider", style="bold white", min_width=20)
    table.add_column("Avg Speed", justify="right", min_width=12)
    table.add_column("Status", justify="center")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), transient=True, console=utils.console) as progress:
        task = progress.add_task("Testing...", total=len(DNS_PRESETS))
        
        def progress_callback(name):
            progress.update(task, description=f"Testing {name}...")
        
        all_raw = collect_benchmark_results(progress_callback)
        for name, avg_time in all_raw:
            if avg_time != float('inf'):
                table.add_row(name, f"{avg_time:.4f}s", "[green]✓ OK[/green]")
                results.append((name, avg_time))
            else:
                table.add_row(name, "---", "[red]✗ Timeout[/red]")
            progress.advance(task)

    utils.console.print(table)
    if results:
        best = min(results, key=lambda x: x[1])
        utils.console.print(f"\n[bold cyan][i] Rekomendasi Tercepat: [bold white]{best[0]} ({best[1]:.4f}s)[/bold white][/bold cyan]")
    else:
        utils.console.status.print("\n[bold red][!] Semua koneksi timeout.[/bold red]")

def generate_menu_map():
    menu_map = {}
    for k in DNS_PRESETS:
        menu_map[str(k)] = ('preset', k)
    menu_map['6'] = ('custom', None)
    
    idx = 7
    for prov in DOT_PROVIDERS:
        menu_map[str(idx)] = ('dot', prov)
        idx += 1
    for prov in DOH_PROVIDERS:
        menu_map[str(idx)] = ('doh', prov)
        idx += 1
        
    menu_map[str(idx)] = ('benchmark', None)
    idx += 1
    menu_map[str(idx)] = ('connectivity', None)
    idx += 1
    menu_map[str(idx)] = ('leak', None)
    idx += 1
    menu_map[str(idx)] = ('system_check', None)
    idx += 1
    menu_map[str(idx)] = ('unlock', None)
    idx += 1
    menu_map[str(idx)] = ('reset', None)
    idx += 1
    
    menu_map['0'] = ('exit', None)
    return menu_map

def display_menu(current_dns, menu_map):
    dot_status, doh_status = get_dot_doh_status()
    
    if RICH_AVAILABLE and utils.console:
        utils.console.print(f"DNS: [bold green]{', '.join(current_dns)}[/bold green]")
        utils.console.print(f"Status Anti-Blokir (DoT): {dot_status}")
        utils.console.print(f"Status DoH             : {doh_status}")
        utils.console.print()

        t = Table(title="DNS Presets", box=box.SIMPLE_HEAVY, border_style="cyan")
        t.add_column("#", style="bold", width=3)
        t.add_column("Provider", style="bold white")
        t.add_column("IPv4", style="green")
        t.add_column("IPv6", style="dim")
        for key, data in DNS_PRESETS.items():
            t.add_row(key, data['name'], ', '.join(data['ips']), ', '.join(data.get('ipv6', [])[:1]))
        t.add_row("6", "Custom (Manual)", "IPv4/IPv6", "")
        utils.console.print(t)

        utils.console.print("\n[bold yellow]ANTI-BLOKIR (Enkripsi):[/bold yellow]")
        for k, v in menu_map.items():
            if v[0] == 'dot':
                utils.console.print(f" {k}. Aktifkan DoT ({v[1]} Secure)")
            elif v[0] == 'doh':
                utils.console.print(f" {k}. Aktifkan DoH ({v[1]} via dnscrypt-proxy)")

        utils.console.print(f"\n[bold cyan]UTILITIES:[/bold cyan]")
        for k, v in menu_map.items():
            if v[0] == 'benchmark':
                utils.console.print(f" {k}. Benchmark (Speed Test)")
            elif v[0] == 'connectivity':
                utils.console.print(f" {k}. Connectivity Test")
            elif v[0] == 'leak':
                utils.console.print(f" {k}. DNS Leak Test")
            elif v[0] == 'system_check':
                utils.console.print(f" {k}. System Check (Doctor)")
            elif v[0] == 'unlock':
                utils.console.print(f" {k}. Buka Kunci resolv.conf (VPN Mode)")
            elif v[0] == 'reset':
                utils.console.print(f" [bold red]{k}. Reset ke Default[/bold red]")
                
        utils.console.print(" 0. Keluar")
    else:
        print(f"DNS di /etc/resolv.conf: {Color.GREEN}{', '.join(current_dns)}{Color.ENDC}")
        print(f"Status Anti-Blokir (DoT): {dot_status}")
        print(f"Status DoH             : {doh_status}")
        print("")
        print("PILIHAN DNS STANDARD (Cepat & Stabil):")
        for key, data in DNS_PRESETS.items():
            ipv6_info = f" | IPv6: {', '.join(data.get('ipv6', [])[:1])}" if data.get('ipv6') else ''
            print(f"{key}. {data['name']} ({', '.join(data['ips'])}{ipv6_info})")
        print(f"6. Input Custom (Manual, mendukung IPv4/IPv6)")
        print("-" * 60)
        print(f"{Color.WARNING}PILIHAN ANTI-BLOKIR (Enkripsi):{Color.ENDC}")
        for k, v in menu_map.items():
            if v[0] == 'dot':
                print(f"{k}.  Aktifkan DoT ({v[1]} Secure)")
            elif v[0] == 'doh':
                print(f"{k}.  Aktifkan DoH ({v[1]} via dnscrypt-proxy)")
        print("-" * 60)
        print(f"{Color.BLUE}UTILITIES:{Color.ENDC}")
        for k, v in menu_map.items():
            if v[0] == 'benchmark':
                print(f"{k}.  Benchmark Kecepatan DNS (Speed Test)")
            elif v[0] == 'connectivity':
                print(f"{k}.  Cek Koneksi DNS (Connectivity Test)")
            elif v[0] == 'leak':
                print(f"{k}.  DNS Leak Test (bash.ws)")
            elif v[0] == 'system_check':
                print(f"{k}.  Cek Sistem / Dependencies (System Check)")
            elif v[0] == 'unlock':
                print(f"{k}.  Buka Kunci manual (Unlock resolv.conf untuk VPN)")
            elif v[0] == 'reset':
                print(f"{k}.  {Color.FAIL}Reset ke Default (Hapus Semua Config){Color.ENDC}")
        print("0.   Keluar")
