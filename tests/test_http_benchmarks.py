import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts' / 'http_benchmarks.py'


def load_runner():
    if not MODULE.exists():
        raise FileNotFoundError(MODULE)
    spec = importlib.util.spec_from_file_location('http_benchmarks', MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RAW = '''Running 15s test @ http://127.0.0.1:3100/json
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   1.00ms    0.50ms  10.00ms   90.00%
  Latency Distribution
     50%    0.90ms
     75%    1.10ms
     90%    2.00ms
     99%    5.00ms
  15000 requests in 15.01s, 2.00MB read
Requests/sec:   999.33
Transfer/sec:    136.44KB
'''


class WrkTests(unittest.TestCase):
    def test_minute_formatted_real_soak_count_is_not_lost(self):
        mod = load_runner()
        result = mod.parse_wrk(RAW.replace('15000 requests in 15.01s', '8524125 requests in 2.00m'), 0)
        self.assertTrue(result['valid'])
        self.assertEqual(result['requests'], 8524125)
        self.assertEqual(result['elapsed_seconds'], 120.0)

    def test_errorful_run_is_rejected_and_counts_retained(self):
        mod = load_runner()
        raw = RAW + '  Socket errors: connect 1, read 2, write 3, timeout 4\n  Non-2xx or 3xx responses: 7\n'
        result = mod.parse_wrk(raw, 0) if mod else {}
        self.assertEqual(result.get('successful_responses'), 14993)
        self.assertEqual(result.get('socket_errors'), {'connect': 1, 'read': 2, 'write': 3, 'timeout': 4})
        self.assertFalse(result['valid'])


class BodyTests(unittest.TestCase):
    def test_seven_response_contracts_reject_200_fallbacks(self):
        mod = load_runner()
        self.assertTrue(hasattr(mod, 'validate_body'), 'semantic response validation is missing')
        world = {i: i + 10 for i in range(1, 21)}
        import json
        payload = {'message': 'Hello, World!', 'numbers': [1, 2, 3, 4, 5], 'nested': {'key': 'value'}}
        rows = [{'id': i, 'randomNumber': world[i]} for i in range(1, 21)]
        html = '<html><h1>World Database</h1><table>' + ''.join(f'<tr><td>{i}</td><td>{world[i]}</td></tr>' for i in range(1, 11)) + '</table></html>'
        bodies = {'plaintext': 'Hello, World!', 'json': json.dumps({'message': 'Hello, World!'}), 'params': json.dumps({'id': '42'}), 'db': json.dumps(rows[0]), 'queries': json.dumps(rows), 'template': html, 'json-body': json.dumps(payload)}
        for name, body in bodies.items():
            with self.subTest(name=name):
                mod.validate_body(name, body.encode(), world)
                with self.assertRaises(ValueError):
                    mod.validate_body(name, b'{"error":"fallback"}', world)
        with self.assertRaises(ValueError):
            mod.validate_body('db', b'{"id":1,"randomNumber":999}', world)
        with self.assertRaises(ValueError):
            mod.validate_body('queries', json.dumps(rows[:19]).encode(), world)
        with self.assertRaises(ValueError):
            mod.validate_body('template', html.replace('<td>11</td>', '<td>0</td>').encode(), world)


class LifecycleTests(unittest.TestCase):
    def test_owned_descendants_cleaned_without_killing_port_occupant(self):
        mod = load_runner()
        self.assertTrue(hasattr(mod, 'stop_owned'), 'owned group cleanup missing')
        import subprocess, sys, os, time, socket
        process = subprocess.Popen([sys.executable, '-c', 'import subprocess,time;subprocess.Popen(["sleep","60"]);time.sleep(60)'], start_new_session=True)
        time.sleep(0.1)
        mod.stop_owned(process)
        self.assertIsNotNone(process.poll())
        with socket.socket() as occupant:
            occupant.bind(('127.0.0.1', 0))
            occupant.listen()
            with self.assertRaises(OSError):
                mod.require_free_port(occupant.getsockname()[1])
            self.assertEqual(occupant.getsockname()[0], '127.0.0.1')

    def test_no_median_for_errorful_or_missing_runs_and_spread_visible(self):
        mod = load_runner()
        self.assertTrue(hasattr(mod, 'summarize'), 'validated aggregation missing')
        runs = [dict(valid=True, requests_per_second=n) for n in (100, 110, 200)]
        summary = mod.summarize(runs, 3)
        self.assertEqual(summary['median_rps'], 110)
        self.assertFalse(summary['stable'])
        self.assertAlmostEqual(summary['spread_percent'], 100 / 110 * 100)
        self.assertIsNone(mod.summarize(runs[:2], 3)['median_rps'])
        runs[0]['valid'] = False
        self.assertIsNone(mod.summarize(runs, 3)['median_rps'])


class CliTests(unittest.TestCase):
    def test_cli_refuses_database_work_without_explicit_isolation(self):
        import subprocess, sys
        result = subprocess.run([sys.executable, str(MODULE), '--benchmarks', 'db'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--isolated-db', result.stderr)


class ProbeTests(unittest.TestCase):
    def test_real_wrk_rejects_500_throughput(self):
        import http.server, threading, tempfile, os, shutil
        from types import SimpleNamespace
        if not shutil.which('wrk') or not shutil.which('taskset'):
            self.skipTest('wrk/taskset unavailable; parser unit tests still run')
        mod = load_runner()
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def do_GET(self):
                self.send_response(500); self.send_header('Content-Length', '5'); self.end_headers()
                self.wfile.write(b'error')
            def log_message(self, format, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR', str(ROOT))) as directory:
                args = SimpleNamespace(cpus=str(min(os.sched_getaffinity(0))), threads=1, connections=1)
                result = mod.wrk_run(args, 'json', server.server_port, 1, pathlib.Path(directory), 'raw-error.txt')
                self.assertGreater(result['requests'], 0)
                self.assertGreater(result['non_success_responses'], 0)
                self.assertFalse(result['valid'])
                self.assertIsNone(mod.summarize([result], 1)['median_rps'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_live_get_post_wrong_body_and_partial_report(self):
        import http.server, threading, tempfile, json, os
        mod = load_runner()
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(b'Hello, World!' if self.path == '/plaintext' else b'{"error":"fallback"}')
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def log_message(self, format, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR', str(ROOT))) as directory:
                out = pathlib.Path(directory)
                get = mod.probe('plaintext', server.server_port, {}, out, 'get', 1)[0]
                post = mod.probe('json-body', server.server_port, {}, out, 'post', 1)[0]
                self.assertTrue(get['valid']); self.assertEqual(get['method'], 'GET')
                self.assertTrue(post['valid']); self.assertEqual(post['method'], 'POST')
                self.assertFalse(mod.probe('json', server.server_port, {}, out, 'fallback', 1)[0]['valid'])
                mod.save_results(out, {'config': {}, 'results': [{'framework': 'ntnt', 'benchmark': 'json', 'status': 'running', 'runs': []}]})
                self.assertEqual(json.loads((out / 'results.json').read_text())['results'][0]['status'], 'running')
        finally:
            server.shutdown(); server.server_close(); thread.join()


class IsolationMemoryTests(unittest.TestCase):
    def test_subnet_rejects_overlap_and_nonprivate_or_large_network(self):
        mod = load_runner()
        self.assertEqual(mod.validate_subnet('10.250.55.0/28', ['10.253.0.0/29', '172.19.0.0/16']), '10.250.55.0/28')
        for subnet, occupied in [('10.250.55.0/28', ['10.250.0.0/16']), ('8.8.8.0/24', []), ('10.250.0.0/16', []), ('10.250.55.1/28', [])]:
            with self.subTest(subnet=subnet), self.assertRaises(ValueError):
                mod.validate_subnet(subnet, occupied)

    def test_memory_scope_and_growth_rejection(self):
        import subprocess, sys, time
        mod = load_runner()
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], start_new_session=True)
        try:
            time.sleep(0.1)
            sample = mod.memory_sample(process.pid, time.monotonic())
            self.assertTrue(sample['valid'])
            self.assertEqual([p['pid'] for p in sample['processes']], [process.pid])
            samples = [dict(valid=True, pss_kib=10000, rss_kib=12000, elapsed_seconds=n) for n in range(8)]
            self.assertTrue(mod.summarize_memory(samples)['bounded'])
            samples[-1]['pss_kib'] = samples[-2]['pss_kib'] = 100000
            self.assertFalse(mod.summarize_memory(samples)['bounded'])
            samples[0]['valid'] = False
            self.assertFalse(mod.summarize_memory(samples)['valid'])
        finally:
            mod.stop_owned(process)


if __name__ == '__main__':
    unittest.main()
