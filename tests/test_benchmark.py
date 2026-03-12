import unittest
from unittest.mock import patch, MagicMock
import shutil
from kalidns_modules.benchmark import benchmark_dns, collect_benchmark_results, DEFAULT_BENCHMARK_ROUNDS

class TestBenchmark(unittest.TestCase):

    @patch('shutil.which', return_value='/usr/bin/nslookup')
    @patch('subprocess.run')
    def test_averages_multiple_rounds(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0)
        result = benchmark_dns('8.8.8.8', rounds=3)
        self.assertIsInstance(result, float)
        self.assertNotEqual(result, float('inf'))
        self.assertEqual(mock_run.call_count, 3)

    @patch('shutil.which', return_value='/usr/bin/nslookup')
    @patch('subprocess.run', side_effect=Exception('timeout'))
    def test_all_fail_returns_inf(self, mock_run, mock_which):
        result = benchmark_dns('invalid', rounds=3)
        self.assertEqual(result, float('inf'))

    @patch('shutil.which', return_value=None)
    def test_missing_nslookup(self, mock_which):
        result = benchmark_dns('8.8.8.8')
        self.assertEqual(result, float('inf'))

    @patch('kalidns_modules.benchmark.benchmark_dns', return_value=0.1)
    def test_collect_results(self, mock_bench):
        results = collect_benchmark_results()
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0][1], 0.1)

if __name__ == '__main__':
    unittest.main()
