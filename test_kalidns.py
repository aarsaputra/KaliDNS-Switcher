#!/usr/bin/env python3
"""Unit tests for kalidns.py"""
import os
import sys
import time
import shutil
import tempfile
import unittest
from unittest.mock import patch, mock_open, MagicMock, call

# Import the module under test
import kalidns


class TestValidateIP(unittest.TestCase):
    """Test IP address validation."""

    def test_valid_ipv4(self):
        self.assertEqual(kalidns.validate_ip('8.8.8.8'), '8.8.8.8')

    def test_valid_ipv4_with_whitespace(self):
        self.assertEqual(kalidns.validate_ip('  1.1.1.1  '), '1.1.1.1')

    def test_valid_ipv6(self):
        result = kalidns.validate_ip('2606:4700:4700::1111')
        self.assertEqual(result, '2606:4700:4700::1111')

    def test_invalid_string(self):
        self.assertIsNone(kalidns.validate_ip('not-an-ip'))

    def test_empty_string(self):
        self.assertIsNone(kalidns.validate_ip(''))

    def test_out_of_range(self):
        self.assertIsNone(kalidns.validate_ip('999.999.999.999'))

    def test_partial_ip(self):
        self.assertIsNone(kalidns.validate_ip('192.168'))


class TestGetCurrentDNS(unittest.TestCase):
    """Test reading current DNS from resolv.conf."""

    def test_normal_resolv(self):
        content = "# comment\nnameserver 8.8.8.8\nnameserver 1.1.1.1\n"
        with patch('builtins.open', mock_open(read_data=content)):
            result = kalidns.get_current_dns()
        self.assertEqual(result, ['8.8.8.8', '1.1.1.1'])

    def test_empty_resolv(self):
        content = "# only comments\n"
        with patch('builtins.open', mock_open(read_data=content)):
            result = kalidns.get_current_dns()
        self.assertEqual(result, ["(Kosong / Tidak ada nameserver)"])

    def test_missing_file(self):
        with patch('builtins.open', side_effect=FileNotFoundError):
            result = kalidns.get_current_dns()
        self.assertEqual(result, ["File belum ada (Akan dibuat otomatis)"])

    def test_single_nameserver(self):
        content = "nameserver 127.0.0.53\n"
        with patch('builtins.open', mock_open(read_data=content)):
            result = kalidns.get_current_dns()
        self.assertEqual(result, ['127.0.0.53'])


class TestAtomicWrite(unittest.TestCase):
    """Test atomic file writing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.tmpdir, 'test.conf')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_successful_write(self):
        result = kalidns.atomic_write(self.filepath, 'nameserver 8.8.8.8\n')
        self.assertTrue(result)
        with open(self.filepath) as f:
            self.assertEqual(f.read(), 'nameserver 8.8.8.8\n')

    def test_temp_file_cleaned_on_success(self):
        kalidns.atomic_write(self.filepath, 'test')
        tmp_file = self.filepath + '.tmp'
        self.assertFalse(os.path.exists(tmp_file))

    def test_content_integrity(self):
        content = "# Generated\nnameserver 1.1.1.1\nnameserver 1.0.0.1\n"
        kalidns.atomic_write(self.filepath, content)
        with open(self.filepath) as f:
            self.assertEqual(f.read(), content)

    def test_overwrite_existing(self):
        with open(self.filepath, 'w') as f:
            f.write('old content')
        kalidns.atomic_write(self.filepath, 'new content')
        with open(self.filepath) as f:
            self.assertEqual(f.read(), 'new content')

    def test_failure_returns_false(self):
        # Write to a path with nonexistent deep directory
        bad_path = '/nonexistent/deep/path/file.conf'
        result = kalidns.atomic_write(bad_path, 'test')
        self.assertFalse(result)


class TestFindLatestBackup(unittest.TestCase):
    """Test _find_latest_backup correctly finds the newest backup."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.tmpdir, 'resolved.conf')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_backups(self):
        result = kalidns._find_latest_backup(self.config_file)
        self.assertIsNone(result)

    def test_single_backup(self):
        backup = os.path.join(self.tmpdir, 'resolved.conf.backup_20260101_120000')
        with open(backup, 'w') as f:
            f.write('backup1')
        result = kalidns._find_latest_backup(self.config_file)
        self.assertEqual(result, backup)

    def test_multiple_backups_returns_newest(self):
        old = os.path.join(self.tmpdir, 'resolved.conf.backup_20260101_120000')
        new = os.path.join(self.tmpdir, 'resolved.conf.backup_20260220_120000')
        with open(old, 'w') as f:
            f.write('old')
        time.sleep(0.05)
        with open(new, 'w') as f:
            f.write('new')
        result = kalidns._find_latest_backup(self.config_file)
        self.assertEqual(result, new)

    def test_ignores_unrelated_files(self):
        unrelated = os.path.join(self.tmpdir, 'other.conf.backup_20260101_120000')
        with open(unrelated, 'w') as f:
            f.write('unrelated')
        result = kalidns._find_latest_backup(self.config_file)
        self.assertIsNone(result)

    def test_nonexistent_directory(self):
        result = kalidns._find_latest_backup('/nonexistent/dir/resolved.conf')
        self.assertIsNone(result)


class TestCleanupOldBackups(unittest.TestCase):
    """Test auto-cleanup of old backup files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_resolv = kalidns.RESOLV_CONF
        kalidns.RESOLV_CONF = os.path.join(self.tmpdir, 'resolv.conf')
        with open(kalidns.RESOLV_CONF, 'w') as f:
            f.write('nameserver 8.8.8.8\n')

    def tearDown(self):
        kalidns.RESOLV_CONF = self.original_resolv
        shutil.rmtree(self.tmpdir)

    def test_removes_old_backups(self):
        old_file = os.path.join(self.tmpdir, 'resolv.conf.backup_20250101_120000')
        with open(old_file, 'w') as f:
            f.write('old')
        # Set mtime to 30 days ago
        old_time = time.time() - (30 * 86400)
        os.utime(old_file, (old_time, old_time))

        kalidns.cleanup_old_backups(max_age_days=7)
        self.assertFalse(os.path.exists(old_file))

    def test_keeps_recent_backups(self):
        recent_file = os.path.join(self.tmpdir, 'resolv.conf.backup_20260220_120000')
        with open(recent_file, 'w') as f:
            f.write('recent')

        kalidns.cleanup_old_backups(max_age_days=7)
        self.assertTrue(os.path.exists(recent_file))


class TestBenchmarkDNS(unittest.TestCase):
    """Test DNS benchmark averaging logic."""

    @patch('shutil.which', return_value='/usr/bin/nslookup')
    @patch('subprocess.run')
    def test_averages_multiple_rounds(self, mock_run, mock_which):
        # Simulate 3 rounds each taking ~0s (instant mock)
        mock_run.return_value = MagicMock(returncode=0)
        result = kalidns.benchmark_dns('8.8.8.8', rounds=3)
        self.assertIsInstance(result, float)
        self.assertNotEqual(result, float('inf'))
        # subprocess.run should be called 3 times (3 rounds)
        self.assertEqual(mock_run.call_count, 3)

    @patch('shutil.which', return_value='/usr/bin/nslookup')
    @patch('subprocess.run', side_effect=Exception('timeout'))
    def test_all_fail_returns_inf(self, mock_run, mock_which):
        result = kalidns.benchmark_dns('invalid', rounds=3)
        self.assertEqual(result, float('inf'))

    @patch('shutil.which', return_value=None)
    def test_missing_nslookup(self, mock_which):
        result = kalidns.benchmark_dns('8.8.8.8')
        self.assertEqual(result, float('inf'))


class TestBareExceptRemoved(unittest.TestCase):
    """Verify no bare except clauses remain in the source."""

    def test_no_bare_except(self):
        with open(os.path.join(os.path.dirname(__file__), 'kalidns.py'), 'r') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == 'except:' or stripped.startswith('except:'):
                # Allow 'except Exception:' etc.
                if 'except:' in stripped and 'Exception' not in stripped:
                    self.fail(f"Bare except found at line {i}: {line.strip()}")


class TestDNSSECSetting(unittest.TestCase):
    """Verify DoT config uses DNSSEC=allow-downgrade."""

    @patch('kalidns.backup_file')
    @patch('kalidns.atomic_write', return_value=True)
    @patch('kalidns.safe_restart_service', return_value=True)
    @patch('kalidns.lock_file')
    @patch('kalidns.flush_dns_cache')
    @patch('kalidns.test_dns_connectivity')
    @patch('kalidns.unlock_file')
    @patch('os.path.exists', return_value=True)
    def test_dot_uses_allow_downgrade(self, mock_exists, mock_unlock,
                                       mock_test, mock_flush, mock_lock,
                                       mock_restart, mock_write, mock_backup):
        kalidns.setup_dot("Cloudflare")
        # First call to atomic_write is for resolved.conf (contains DNSSEC)
        resolved_content = mock_write.call_args_list[0][0][1]
        self.assertIn('DNSSEC=allow-downgrade', resolved_content)
        self.assertNotIn('DNSSEC=no', resolved_content)


class TestRestoreDefault(unittest.TestCase):
    """Test that restore_default requires confirmation."""

    @patch('builtins.input', return_value='n')
    def test_cancel_on_no(self, mock_input):
        # Should return without doing anything destructive
        with patch('kalidns.atomic_write') as mock_write:
            kalidns.restore_default()
            mock_write.assert_not_called()

    @patch('builtins.input', return_value='')
    def test_cancel_on_empty(self, mock_input):
        with patch('kalidns.atomic_write') as mock_write:
            kalidns.restore_default()
            mock_write.assert_not_called()


class TestVerifyDNSChange(unittest.TestCase):
    """Test DNS verification logic."""

    @patch('kalidns.get_current_dns', return_value=['8.8.8.8', '8.8.4.4'])
    def test_verify_success(self, mock_dns):
        result = kalidns.verify_dns_change(['8.8.8.8', '8.8.4.4'])
        self.assertTrue(result)

    @patch('kalidns.get_current_dns', return_value=['1.1.1.1'])
    def test_verify_mismatch(self, mock_dns):
        result = kalidns.verify_dns_change(['8.8.8.8', '8.8.4.4'])
        self.assertFalse(result)


class TestLogAction(unittest.TestCase):
    """Test logging functionality."""

    def test_log_writes_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = kalidns.LOG_DIR
            original_file = kalidns.LOG_FILE
            kalidns.LOG_DIR = tmpdir
            kalidns.LOG_FILE = os.path.join(tmpdir, 'dns.log')
            try:
                kalidns.log_action("TEST", "unit test entry")
                with open(kalidns.LOG_FILE) as f:
                    content = f.read()
                self.assertIn("TEST", content)
                self.assertIn("unit test entry", content)
            finally:
                kalidns.LOG_DIR = original_dir
                kalidns.LOG_FILE = original_file


if __name__ == '__main__':
    unittest.main()
