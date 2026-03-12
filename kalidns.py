#!/usr/bin/env python3
import sys
import subprocess
from kalidns_modules.config import DNS_PRESETS
from kalidns_modules.utils import (
    Color, check_root, cleanup_old_backups, 
    log_action, unlock_file, RICH_AVAILABLE
)
from kalidns_modules.dns_manager import (
    get_current_dns, set_dns, setup_dot, setup_doh, 
    restore_default, run_dns_connectivity_test, run_dns_leak_test
)
from kalidns_modules.benchmark import run_benchmark_plain
from kalidns_modules.tui import (
    banner, display_menu, run_benchmark_rich,
    get_dot_doh_status
)

# --- RICH TUI INITIALIZATION ---
if RICH_AVAILABLE:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    console = Console()
    # Share console back to modules
    import kalidns_modules.utils as utils
    utils.console = console
else:
    console = None

def parse_args():
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        arg = args[0]
        use_ipv6 = '--ipv6' in args
        
        if arg in DNS_PRESETS:
            preset = DNS_PRESETS[arg]
            ips = list(preset['ips'])
            if use_ipv6 and 'ipv6' in preset:
                ips.extend(preset['ipv6'])
            set_dns(ips, preset['name'])
            return True
        elif arg == '--connectivity' or arg == '--test': # Support legacy and better name
            run_dns_connectivity_test()
            return True
        elif arg == '--leak':
            run_dns_leak_test(RICH_AVAILABLE)
            return True
        elif arg == '--benchmark':
            if RICH_AVAILABLE: run_benchmark_rich()
            else: run_benchmark_plain()
            return True
        elif arg == '--status':
            current = get_current_dns()
            print(f"Current DNS: {', '.join(current)}")
            dot_s, doh_s = get_dot_doh_status()
            print(f"Status Anti-Blokir (DoT): {dot_s}")
            print(f"Status DoH             : {doh_s}")
            return True
        elif arg == '--reset':
            restore_default(RICH_AVAILABLE)
            return True
        elif arg == '--help' or arg == '-h':
            print(f"{Color.BOLD}Usage:{Color.ENDC} sudo kalidns [OPTION]")
            print("\nOptions:")
            print("  1-5          : Apply preset (add --ipv6 for IPv6)")
            print("  --connectivity: Run DNS connectivity test")
            print("  --leak       : Run DNS leak test (bash.ws)")
            print("  --benchmark  : Run speed test")
            print("  --status     : Show status")
            print("  --reset      : Restore default")
            print("  --ipv6       : Include IPv6 with presets")
            return True
        elif arg == '--ipv6' and len(args) == 1:
            print(f"{Color.WARNING}[!] Gunakan --ipv6 bersamaan dengan preset (contoh: sudo kalidns 1 --ipv6){Color.ENDC}")
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
        # Clear screen
        if RICH_AVAILABLE: console.clear()
        else: subprocess.run(['clear'], stderr=subprocess.DEVNULL)
        
        banner()
        current = get_current_dns()
        display_menu(current)

        if RICH_AVAILABLE:
            choice = Prompt.ask("\n[bold]Pilihan", default="0")
        else:
            choice = input(f"\n{Color.BOLD}Masukan Pilihan: {Color.ENDC}")

        if choice in DNS_PRESETS:
            preset = DNS_PRESETS[choice]
            if RICH_AVAILABLE:
                use_v6 = Confirm.ask("Tambahkan IPv6?", default=False)
            else:
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
        elif choice == '10': setup_doh("Cloudflare", RICH_AVAILABLE)
        elif choice == '11': setup_doh("Google", RICH_AVAILABLE)
        elif choice == '12':
            if RICH_AVAILABLE: run_benchmark_rich()
            else: run_benchmark_plain()
        elif choice == '13': run_dns_connectivity_test()
        elif choice == '14': run_dns_leak_test(RICH_AVAILABLE)
        elif choice == '15': restore_default(RICH_AVAILABLE)
        elif choice == '0':
            print("Keluar.")
            sys.exit()
        
        if RICH_AVAILABLE:
            input("\nTekan Enter untuk kembali ke menu...")
        else:
            input(f"\n{Color.BLUE}Tekan Enter untuk kembali ke menu...{Color.ENDC}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt:
        print("\nOperasi dibatalkan pengguna.")
        unlock_file()
        sys.exit(0)
