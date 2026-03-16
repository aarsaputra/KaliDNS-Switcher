import os

# --- KONFIGURASI FILE ---
RESOLV_CONF = "/etc/resolv.conf"
SYSTEMD_RESOLVED_CONF = "/etc/systemd/resolved.conf"
LOG_DIR = "/var/log/kalidns"
LOG_FILE = os.path.join(LOG_DIR, "dns.log")
DNSCRYPT_PROXY_CONF = "/etc/dnscrypt-proxy/dnscrypt-proxy.toml"

# --- MAGIC NUMBERS ---
MAX_BACKUP_AGE_DAYS = 7
MAX_BACKUP_FILES = 10
DEFAULT_BENCHMARK_ROUNDS = 3
DEFAULT_TIMEOUT = 10

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

# --- DoT PROVIDER CONFIG ---
DOT_PROVIDERS = {
    'Cloudflare': {
        'dns_ip': '1.1.1.1 1.0.0.1 2606:4700:4700::1111 2606:4700:4700::1001',
        'fallback': '8.8.8.8'
    },
    'Google': {
        'dns_ip': '8.8.8.8 8.8.4.4 2001:4860:4860::8888 2001:4860:4860::8844',
        'fallback': '1.1.1.1'
    },
    'Quad9': {
        'dns_ip': '9.9.9.9 149.112.112.112 2620:fe::fe 2620:fe::9',
        'fallback': '1.1.1.1'
    }
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
    'Quad9': {
        'server_name': 'dns.quad9.net',
        'stamp': 'sdns://AgMAAAAAAAAABzkuOS45LjkACGRucy5xdWFkOQovZG5zLXF1ZXJ5',
        'listen': '127.0.0.1:53',
    }
}
