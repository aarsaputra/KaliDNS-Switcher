import unittest
import os

class TestLint(unittest.TestCase):
    """Verify code quality across all modules."""

    def test_no_bare_except(self):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        paths_to_check = [
            os.path.join(base_dir, 'kalidns.py'),
            os.path.join(base_dir, 'kalidns_modules', 'config.py'),
            os.path.join(base_dir, 'kalidns_modules', 'utils.py'),
            os.path.join(base_dir, 'kalidns_modules', 'dns_manager.py'),
            os.path.join(base_dir, 'kalidns_modules', 'benchmark.py'),
            os.path.join(base_dir, 'kalidns_modules', 'tui.py'),
        ]
        
        for path in paths_to_check:
            if not os.path.exists(path): continue
            with open(path, 'r') as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped == 'except:' or stripped.startswith('except:'):
                    if 'except:' in stripped and 'Exception' not in stripped:
                        self.fail(f"Bare except found in {os.path.basename(path)} at line {i}: {line.strip()}")

if __name__ == '__main__':
    unittest.main()
