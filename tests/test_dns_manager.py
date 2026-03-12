import unittest
from unittest.mock import patch, MagicMock
import os
from kalidns_modules.dns_manager import (
    set_dns, setup_dot, get_current_dns, 
    verify_dns_change, run_dns_leak_test, setup_doh,
    _find_latest_backup, run_dns_connectivity_test
)

class TestDNSManager(unittest.TestCase):

    @patch('kalidns_modules.dns_manager.unlock_file')
    @patch('kalidns_modules.dns_manager.backup_file')
    @patch('kalidns_modules.dns_manager.atomic_write', return_value=True)
    @patch('kalidns_modules.dns_manager.lock_file')
    @patch('kalidns_modules.dns_manager.flush_dns_cache')
    @patch('kalidns_modules.dns_manager.verify_dns_change', return_value=True)
    @patch('kalidns_modules.dns_manager.run_dns_connectivity_test')
    @patch('kalidns_modules.dns_manager.restore_systemd_config_silent')
    def test_set_dns_success(self, mock_restore, mock_test, mock_verify, mock_flush, mock_lock, mock_write, mock_backup, mock_unlock):
        """Test set_dns successfully updates resolv.conf."""
        set_dns(['8.8.8.8', '8.8.4.4'], "Google")
        
        # Verify atomic_write was called with correct content
        content = mock_write.call_args[0][1]
        self.assertIn('nameserver 8.8.8.8', content)
        self.assertIn('nameserver 8.8.4.4', content)
        self.assertIn('Google', content)
        
        # Verify order of operations
        mock_unlock.assert_called_once()
        mock_lock.assert_called_once()
        mock_flush.assert_called_once()
        mock_verify.assert_called_once()

    @patch('kalidns_modules.dns_manager.validate_ip', side_effect=lambda x: x if '.' in x else None)
    @patch('kalidns_modules.dns_manager.restore_systemd_config_silent')
    def test_set_dns_invalid_ips(self, mock_restore, mock_validate):
        """Test set_dns handles invalid IPs by ignoring them."""
        with patch('kalidns_modules.dns_manager.atomic_write') as mock_write:
            set_dns(['invalid', '1.1.1.1'], "Custom")
            content = mock_write.call_args[0][1]
            self.assertIn('nameserver 1.1.1.1', content)
            self.assertNotIn('nameserver invalid', content)

    @patch('os.path.exists', return_value=True)
    @patch('kalidns_modules.dns_manager.atomic_write', return_value=True)
    @patch('kalidns_modules.dns_manager.safe_restart_service', return_value=True)
    @patch('kalidns_modules.dns_manager.lock_file')
    @patch('kalidns_modules.dns_manager.flush_dns_cache')
    @patch('kalidns_modules.dns_manager.run_dns_connectivity_test')
    @patch('kalidns_modules.dns_manager.unlock_file')
    def test_setup_dot_validation(self, mock_unlock, mock_test, mock_flush, mock_lock, mock_restart, mock_write, mock_exists):
        """Test setup_dot handles unknown providers gracefully (Fixes high priority bug)."""
        # Test unknown provider
        set_dns_result = setup_dot("UnknownProvider")
        self.assertIsNone(set_dns_result)
        mock_write.assert_not_called()
        
        # Test known provider
        setup_dot("Cloudflare")
        self.assertTrue(mock_write.called)
        config_content = mock_write.call_args_list[0][0][1]
        self.assertIn('1.1.1.1', config_content)

class TestVerifyDNSChange(unittest.TestCase):
    @patch('kalidns_modules.dns_manager.get_current_dns', return_value=['8.8.8.8', '8.8.4.4'])
    def test_verify_success(self, mock_dns):
        result = verify_dns_change(['8.8.8.8', '8.8.4.4'])
        self.assertTrue(result)

    @patch('kalidns_modules.dns_manager.get_current_dns', return_value=['1.1.1.1'])
    def test_verify_mismatch(self, mock_dns):
        result = verify_dns_change(['8.8.8.8', '8.8.4.4'])
        self.assertFalse(result)

class TestDNSLeakTest(unittest.TestCase):
    @patch('kalidns_modules.dns_manager.log_action')
    @patch('urllib.request.urlopen')
    @patch('socket.getaddrinfo')
    @patch('time.sleep')
    @patch('builtins.input', return_value='y')
    def test_parses_api_response(self, mock_input, mock_sleep, mock_getaddr, mock_urlopen, mock_log):
        mock_getaddr.return_value = []
        api_response = b'[{"type": "dns", "ip": "1.1.1.1", "country_name": "US", "asn_name": "Cloudflare"},{"type": "conclusion", "ip": "No leak"}]'
        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = lambda s: s
        mock_urlopen.return_value = mock_resp
        run_dns_leak_test(rich_available=False)
        mock_log.assert_called()

class TestDoHSetup(unittest.TestCase):
    @patch('kalidns_modules.dns_manager.safe_restart_service', return_value=True)
    @patch('kalidns_modules.dns_manager.atomic_write', return_value=True)
    @patch('kalidns_modules.dns_manager.backup_file')
    @patch('os.path.exists', return_value=True)
    @patch('os.makedirs')
    @patch('shutil.which', return_value='/usr/sbin/dnscrypt-proxy')
    @patch('kalidns_modules.dns_manager.lock_file')
    @patch('kalidns_modules.dns_manager.unlock_file')
    @patch('kalidns_modules.dns_manager.flush_dns_cache')
    @patch('kalidns_modules.dns_manager.run_dns_connectivity_test')
    def test_doh_cloudflare_success(self, mock_test, mock_flush, mock_unlock, mock_lock, mock_which, mock_makedirs, mock_exists, mock_backup, mock_write, mock_restart):
        setup_doh("Cloudflare", rich_available=False)
        self.assertTrue(mock_write.called)

class TestFindLatestBackup(unittest.TestCase):
    @patch('os.listdir', return_value=['resolved.conf.backup_1', 'resolved.conf.backup_2'])
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getmtime', side_effect=lambda x: 1 if '1' in x else 2)
    def test_find_latest(self, mock_mtime, mock_isfile, mock_exists, mock_listdir):
        result = _find_latest_backup('/etc/resolved.conf')
        self.assertIn('backup_2', result)

if __name__ == '__main__':
    unittest.main()
