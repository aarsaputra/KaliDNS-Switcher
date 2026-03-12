import unittest
from kalidns_modules.config import DNS_PRESETS, DOH_PROVIDERS
from kalidns_modules.utils import validate_ip

class TestConfig(unittest.TestCase):

    def test_all_presets_have_ipv6(self):
        for key, data in DNS_PRESETS.items():
            self.assertIn('ipv6', data, f"Preset {key} ({data['name']}) missing 'ipv6' key")
            self.assertGreater(len(data['ipv6']), 0, f"Preset {key} has empty ipv6 list")

    def test_all_ipv6_addresses_valid(self):
        for key, data in DNS_PRESETS.items():
            for addr in data['ipv6']:
                result = validate_ip(addr)
                self.assertIsNotNone(result, f"Invalid IPv6 in preset {key}: {addr}")

    def test_all_doh_providers_have_required_fields(self):
        for name, prov in DOH_PROVIDERS.items():
            self.assertIn('server_name', prov, f"{name} missing server_name")
            self.assertIn('stamp', prov, f"{name} missing stamp")
            self.assertIn('listen', prov, f"{name} missing listen")

if __name__ == '__main__':
    unittest.main()
