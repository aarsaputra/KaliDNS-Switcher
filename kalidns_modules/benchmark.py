import time
import subprocess
import shutil
from .config import DNS_PRESETS, DEFAULT_BENCHMARK_ROUNDS
from .utils import Color, log_action

def benchmark_dns(ip, domain='google.com', rounds=DEFAULT_BENCHMARK_ROUNDS):
    if not shutil.which('nslookup'):
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

def collect_benchmark_results(progress_callback=None):
    results = []
    for key, data in DNS_PRESETS.items():
        name = data['name']
        if progress_callback:
            progress_callback(name)
        avg_time = benchmark_dns(data['ips'][0])
        results.append((name, avg_time))
    return results

def run_benchmark_plain():
    print(f"\n{Color.WARNING}[*] Benchmarking DNS Speed ({DEFAULT_BENCHMARK_ROUNDS}-round avg)...{Color.ENDC}")
    if not shutil.which('nslookup'):
        print(f"{Color.FAIL}[!] 'nslookup' tidak ditemukan. Install: sudo apt install dnsutils{Color.ENDC}")
        return
    
    results = []
    def progress(name):
        print(f"Testing {name.ljust(20)}...", end='', flush=True)
    
    all_raw = collect_benchmark_results(progress)
    for name, avg_time in all_raw:
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
        print(f"\n{Color.FAIL}[!] Semua koneksi timeout.{Color.ENDC}")
