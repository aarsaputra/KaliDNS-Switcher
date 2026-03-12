import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import tempfile
import shutil
import time
from kalidns_modules.utils import (
    validate_ip, atomic_write, cleanup_old_backups, backup_file
)
import kalidns_modules.config as config

class TestUtils(unittest.TestCase):

    def test_validate_ip(self):
        self.assertEqual(validate_ip('8.8.8.8'), '8.8.8.8')
        self.assertEqual(validate_ip('  1.1.1.1  '), '1.1.1.1')
        self.assertEqual(validate_ip('2606:4700:4700::1111'), '2606:4700:4700::1111')
        self.assertIsNone(validate_ip('not-an-ip'))
        self.assertIsNone(validate_ip(''))

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.conf')
            result = atomic_write(filepath, 'test content')
            self.assertTrue(result)
            with open(filepath) as f:
                self.assertEqual(f.read(), 'test content')

    def test_cleanup_old_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock RESOLV_CONF to point to tmpdir
            with patch('kalidns_modules.utils.RESOLV_CONF', os.path.join(tmpdir, 'resolv.conf')):
                old_file = os.path.join(tmpdir, 'resolv.conf.backup_old')
                with open(old_file, 'w') as f: f.write('old')
                
                # Set mtime to 30 days ago
                old_time = time.time() - (30 * 86400)
                os.utime(old_file, (old_time, old_time))
                
                cleanup_old_backups(max_age_days=7)
                self.assertFalse(os.path.exists(old_file))

    def test_cleanup_permission_error(self):
        """Test cleanup handles permission errors (Gaps #4)."""
        with patch('os.listdir', side_effect=PermissionError):
            # Should not raise exception
            cleanup_old_backups()

if __name__ == '__main__':
    unittest.main()
