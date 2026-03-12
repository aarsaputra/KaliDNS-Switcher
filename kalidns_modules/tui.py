import os
import subprocess
from .config import DNS_PRESETS, SYSTEMD_RESOLVED_CONF, DNSCRYPT_PROXY_CONF
from .utils import Color, console
from .benchmark import collect_benchmark_results, DEFAULT_BENCHMARK_ROUNDS

try:
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

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
    if RICH_AVAILABLE:
        banner_text = Text()
        banner_text.append("KALI LINUX DNS CHANGER TOOL\n", style="bold cyan")
        banner_text.append("v2.1 MODULAR EDITION\n", style="bold white")
        banner_text.append("DoT • DoH • Leak Test • Benchmark • IPv6", style="dim")
        console.print(Panel(banner_text, border_style="bright_cyan", box=box.DOUBLE_EDGE, padding=(1, 2)))
    else:
        print(f"{Color.HEADER}{Color.BOLD}")
        print("="*60)
        print("   KALI LINUX DNS CHANGER TOOL (MODULAR EDITION v2.1)")
        print("   DoT • DoH • Leak Test • Benchmark • IPv6")
        print("="*60)
        print(f"{Color.ENDC}")

def run_benchmark_rich():
    if not RICH_AVAILABLE: return
    from .utils import console
    import shutil
    
    if not shutil.which('nslookup'):
        console.print("[bold red][!] 'nslookup' tidak ditemukan. Install: sudo apt install dnsutils[/bold red]")
        return

    console.print(f"\n[bold yellow][*] Benchmarking DNS Speed ({DEFAULT_BENCHMARK_ROUNDS}-round avg)...[/bold yellow]")
    
    results = []
    table = Table(title="DNS Benchmark Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Provider", style="bold white", min_width=20)
    table.add_column("Avg Speed", justify="right", min_width=12)
    table.add_column("Status", justify="center")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), transient=True, console=console) as progress:
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

    console.print(table)
    if results:
        best = min(results, key=lambda x: x[1])
        console.print(f"\n[bold cyan][i] Rekomendasi Tercepat: [bold white]{best[0]} ({best[1]:.4f}s)[/bold white][/bold cyan]")
    else:
        console.print("\n[bold red][!] Semua koneksi timeout.[/bold red]")

def display_menu(current_dns):
    dot_status, doh_status = get_dot_doh_status()
    
    if RICH_AVAILABLE:
        console.print(f"DNS: [bold green]{', '.join(current_dns)}[/bold green]")
        console.print(f"Status Anti-Blokir (DoT): {dot_status}")
        console.print(f"Status DoH             : {doh_status}")
        console.print()

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
