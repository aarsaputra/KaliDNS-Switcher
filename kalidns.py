#!/usr/bin/env python3
import sys
import argparse
import subprocess
from kalidns_modules.config import DNS_PRESETS, DOT_PROVIDERS, DOH_PROVIDERS
from kalidns_modules.utils import (
    Color, check_root, cleanup_old_backups, 
    log_action, unlock_file, unlock_file_manual, run_system_check, RICH_AVAILABLE
)
from kalidns_modules.dns_manager import (
    get_current_dns, set_dns, setup_dot, setup_doh, 
    restore_default, run_dns_connectivity_test, run_dns_leak_test
)
from kalidns_modules.benchmark import run_benchmark_plain
from kalidns_modules.tui import (
    banner, display_menu, generate_menu_map, run_benchmark_rich,
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
    if len(sys.argv) == 1:
        return False
        
    parser = argparse.ArgumentParser(description="Kali Linux DNS Changer Tool (Modular Edition v2.2)")
    parser.add_argument('--preset', type=str, choices=list(DNS_PRESETS.keys()), help="Apply preset by ID (1-5)")
    parser.add_argument('--dot', type=str, choices=list(DOT_PROVIDERS.keys()), help="Enable DoT mode")
    parser.add_argument('--doh', type=str, choices=list(DOH_PROVIDERS.keys()), help="Enable DoH mode")
    parser.add_argument('--ipv6', action='store_true', help="Include IPv6 with presets")
    parser.add_argument('--benchmark', action='store_true', help="Run DNS speed test")
    parser.add_argument('--connectivity', '--test', action='store_true', help="Run DNS connectivity test")
    parser.add_argument('--leak', action='store_true', help="Run DNS leak test (bash.ws)")
    parser.add_argument('--status', action='store_true', help="Show current DNS status")
    parser.add_argument('--check', action='store_true', help="Run system check (Doctor)")
    parser.add_argument('--unlock', action='store_true', help="Manual unlock resolv.conf for VPN")
    parser.add_argument('--reset', action='store_true', help="Restore default DNS settings")
    
    args = parser.parse_args()
    
    if args.preset:
        preset = DNS_PRESETS[args.preset]
        ips = list(preset['ips'])
        if args.ipv6 and 'ipv6' in preset:
            ips.extend(preset['ipv6'])
        set_dns(ips, preset['name'])
    elif args.dot:
        setup_dot(args.dot)
    elif args.doh:
        setup_doh(args.doh, RICH_AVAILABLE)
    elif args.benchmark:
        if RICH_AVAILABLE: run_benchmark_rich()
        else: run_benchmark_plain()
    elif args.connectivity:
        run_dns_connectivity_test()
    elif args.leak:
        run_dns_leak_test(RICH_AVAILABLE)
    elif args.status:
        current = get_current_dns()
        print(f"Current DNS: {', '.join(current)}")
        dot_s, doh_s = get_dot_doh_status()
        print(f"Status Anti-Blokir (DoT): {dot_s}")
        print(f"Status DoH             : {doh_s}")
    elif args.check:
        run_system_check()
    elif args.unlock:
        unlock_file_manual()
    elif args.reset:
        restore_default(RICH_AVAILABLE)
    else:
        parser.print_help()
    
    return True

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        parse_args()
        
    check_root()
    if parse_args(): sys.exit()
    cleanup_old_backups()
    
    menu_map = generate_menu_map()
    
    while True:
        # Clear screen
        if RICH_AVAILABLE: console.clear()
        else: subprocess.run(['clear'], stderr=subprocess.DEVNULL)
        
        banner()
        current = get_current_dns()
        display_menu(current, menu_map)

        if RICH_AVAILABLE:
            choice = Prompt.ask("\n[bold]Pilihan", default="0")
        else:
            choice = input(f"\n{Color.BOLD}Masukan Pilihan: {Color.ENDC}")

        if choice in menu_map:
            action, val = menu_map[choice]
            if action == 'preset':
                preset = DNS_PRESETS[val]
                if RICH_AVAILABLE:
                    use_v6 = Confirm.ask("Tambahkan IPv6?", default=False)
                else:
                    use_v6 = input("Tambahkan IPv6? (y/N): ").strip().lower() == 'y'
                ips = list(preset['ips'])
                if use_v6 and 'ipv6' in preset:
                    ips.extend(preset['ipv6'])
                set_dns(ips, preset['name'])
            elif action == 'custom':
                print(f"{Color.BLUE}[i] Contoh IPv4: 8.8.8.8 | IPv6: 2001:4860:4860::8888{Color.ENDC}")
                ns1 = input("Masukkan Primary DNS  : ")
                ns2 = input("Masukkan Secondary DNS (opsional): ")
                servers = [ns1]
                if ns2.strip(): servers.append(ns2)
                set_dns(servers, "Custom")
            elif action == 'dot':
                setup_dot(val)
            elif action == 'doh':
                setup_doh(val, RICH_AVAILABLE)
            elif action == 'benchmark':
                if RICH_AVAILABLE: run_benchmark_rich()
                else: run_benchmark_plain()
            elif action == 'connectivity':
                run_dns_connectivity_test()
            elif action == 'leak':
                run_dns_leak_test(RICH_AVAILABLE)
            elif action == 'system_check':
                run_system_check()
            elif action == 'unlock':
                unlock_file_manual()
            elif action == 'reset':
                restore_default(RICH_AVAILABLE)
            elif action == 'exit':
                print("Keluar.")
                sys.exit()
        else:
            print(f"{Color.FAIL}[!] Pilihan tidak valid.{Color.ENDC}")
        
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
