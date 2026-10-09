#!/usr/bin/env python3
"""Local cross-framework measurements; raw errors are never eligible medians."""
import re
import json
import os
import signal
import socket
import statistics
import subprocess
import time
import argparse
import datetime
import hashlib
import ipaddress
import pathlib
import shutil
import sys
import urllib.request
import uuid
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMEWORKS = 'ntnt fastapi express gin hono actix fastify rails django'.split()
BENCHMARKS = 'plaintext json params db queries template json-body'.split()
DIRS = {'hono': 'hono-bun'}
PATHS = {'plaintext': '/plaintext', 'json': '/json', 'params': '/users/42', 'db': '/db', 'queries': '/queries?count=20', 'template': '/template', 'json-body': '/json'}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def command(argv, cwd=ROOT, env=None, timeout=120):
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{argv!r} exited {result.returncode}: {result.stdout[-3000:]} {result.stderr[-3000:]}')
    return result.stdout.strip()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def host_state():
    return {'time': utcnow(), 'loadavg': list(os.getloadavg()),
            'meminfo': pathlib.Path('/proc/meminfo').read_text(),
            'cpu_pressure': pathlib.Path('/proc/pressure/cpu').read_text()}


def tool(name, fallback=None):
    found = shutil.which(name) or (fallback if fallback and pathlib.Path(fallback).exists() else None)
    if not found:
        raise RuntimeError(f'missing executable: {name}')
    return found


def environment(args):
    env = os.environ.copy()
    # Never inherit a production database target or unconstrained worker count.
    env.update(DATABASE_URL='', DB_HOST='127.0.0.1', DB_PORT=str(args.db_port), DB_PASSWORD='benchmark-local-only',
               NODE_ENV='production', NTNT_ENV='production', RAILS_ENV='production',
               WEB_CONCURRENCY=str(args.workers), RAILS_MAX_THREADS='5',
               GOMAXPROCS=str(args.workers), TOKIO_WORKER_THREADS=str(args.workers),
               RAYON_NUM_THREADS=str(args.workers), BENCH_WORKERS=str(args.workers), NTNT_DB_POOL_SIZE='5',
               CARGO_BUILD_JOBS='2', BUNDLE_JOBS='2', BUNDLE_PATH=str(ROOT / 'rails/vendor/bundle'), BUNDLE_FROZEN='true',
               SECRET_KEY_BASE='benchmark-local-only-not-for-production')
    return env


def framework_commands(fw, args):
    path = ROOT / DIRS.get(fw, fw)
    python = os.environ.get('PYTHON_BIN', '/usr/bin/python3')
    if fw == 'ntnt':
        binary = tool(os.environ.get('NTNT_BIN', 'ntnt'))
        return path, [], [binary, 'run', '--workers', str(args.workers), 'server.tnt'], [[binary, '--version']]
    if fw in ('fastapi', 'django'):
        venv = path / '.venv/bin'
        prepare = [[python, '-m', 'venv', str(path / '.venv')], [str(venv / 'pip'), 'install', '-r', 'requirements.txt']]
        if fw == 'fastapi':
            launch = [str(venv / 'uvicorn'), 'app:app', '--host', '127.0.0.1', '--port', str(args.port_base + FRAMEWORKS.index(fw)), '--workers', str(args.workers), '--log-level', 'error', '--no-access-log']
        else:
            launch = [str(venv / 'gunicorn'), 'bench.wsgi:application', '--bind', f'127.0.0.1:{args.port_base + FRAMEWORKS.index(fw)}', '--workers', str(args.workers), '--log-level', 'error']
        return path, prepare, launch, [[str(venv / 'python'), '--version'], [str(venv / 'pip'), 'freeze']]
    if fw in ('express', 'fastify'):
        node, npm = tool('node'), tool('npm')
        prepare = [[npm, 'ci', '--include=dev', '--no-audit', '--no-fund']]
        if fw == 'express':
            prepare.append([str(path / 'node_modules/.bin/tsc')])
        return path, prepare, [node, 'dist/app.js' if fw == 'express' else 'app.js'], [[node, '--version'], [npm, 'ls', '--all', '--json']]
    if fw == 'hono':
        bun = tool('bun', str(pathlib.Path.home() / '.bun/bin/bun'))
        return path, [[bun, 'install', '--frozen-lockfile']], [bun, 'run', 'app.ts'], [[bun, '--version'], [bun, 'pm', 'ls', '--all']]
    if fw == 'gin':
        go = tool(os.environ.get('GO_BIN', '/usr/local/go/bin/go' if pathlib.Path('/usr/local/go/bin/go').exists() else 'go'))
        return path, [[go, 'build', '-mod=readonly', '-p', '2', '-o', 'gin-bench', '.']], [str(path / 'gin-bench')], [[go, 'version'], [go, 'version', '-m', 'gin-bench']]
    if fw == 'actix':
        cargo = tool('cargo')
        return path, [[cargo, 'build', '--release', '--locked', '-j', '2']], [str(path / 'target/release/actix-bench')], [[tool('rustc'), '--version'], [cargo, 'tree', '--locked']]
    bundle = tool('bundle', '/usr/bin/bundle3.2')
    return path, [[bundle, 'install', '--jobs', '2']], [bundle, 'exec', 'puma', '-C', 'config/puma.rb'], [[tool('ruby'), '--version'], [bundle, '--version'], [bundle, 'list']]


def prepare_framework(fw, args, env, out):
    path, builds, launch, versions = framework_commands(fw, args)
    info = {'cwd': str(path), 'command': launch, 'requested_workers': args.workers, 'prepare_commands': builds}
    if not args.skip_prepare:
        with (out / f'prepare-{fw}.log').open('w') as log:
            for build in builds:
                log.write(repr(build) + '\n'); log.flush()
                process = subprocess.Popen(['taskset', '-c', args.cpus] + build, cwd=path, env=env,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    rc = process.wait(timeout=1200)
                    if rc:
                        raise RuntimeError(f'preparation exited {rc}; see prepare-{fw}.log')
                finally:
                    stop_owned(process)
    info['versions'] = [{'command': v, 'output': command(v, path, env, timeout=120)} for v in versions]
    info['status'] = 'prepared'
    return info


def validate_subnet(subnet, occupied):
    candidate = ipaddress.ip_network(subnet, strict=True)
    if candidate.version != 4 or not candidate.is_private or not 24 <= candidate.prefixlen <= 28:
        raise ValueError('DB subnet must be a private IPv4 /24 through /28')
    for value in occupied:
        other = ipaddress.ip_network(value, strict=False)
        if other.version == 4 and other.prefixlen and candidate.overlaps(other):
            raise ValueError(f'DB subnet {candidate} overlaps existing network/route {other}')
    return str(candidate)


def create_database(args, env, out, owned):
    require_free_port(args.db_port)
    ids = command(['docker', 'network', 'ls', '-q']).split()
    networks = json.loads(command(['docker', 'network', 'inspect'] + ids))
    occupied = [c['Subnet'] for n in networks for c in (n['IPAM'].get('Config') or []) if c.get('Subnet')]
    routes = json.loads(command(['ip', '-4', '-j', 'route', 'show', 'table', 'all']))
    occupied += [r['dst'] for r in routes if r.get('dst') and r['dst'] != 'default']
    subnet = validate_subnet(args.db_subnet, occupied)
    name = 'ntnt-benchmark-' + uuid.uuid4().hex[:12]
    owned['network'] = command(['docker', 'network', 'create', '--subnet', subnet, '--label', 'ntnt.benchmark=' + name, name])
    owned['container'] = command(['docker', 'run', '-d', '--name', name, '--label', 'ntnt.benchmark=' + name,
        '--network', owned['network'], '--cpuset-cpus', args.cpus, '--cpus', '1', '--memory', '512m',
        '--pids-limit', '256', '--shm-size', '128m', '-p', f'127.0.0.1:{args.db_port}:5432',
        '-e', 'POSTGRES_USER=ntnt', '-e', 'POSTGRES_PASSWORD=benchmark-local-only', '-e', 'POSTGRES_DB=benchmarks',
        args.pg_image, '-c', 'max_connections=300'])
    cid = owned['container']
    for _ in range(60):
        ready = subprocess.run(['docker', 'exec', cid, 'pg_isready', '-h', '127.0.0.1', '-U', 'ntnt', '-d', 'benchmarks'], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('isolated PostgreSQL readiness timeout')
    with (ROOT / 'setup-db.sql').open() as seed:
        subprocess.run(['docker', 'exec', '-i', cid, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'ntnt', '-d', 'benchmarks'], stdin=seed, check=True, capture_output=True)
    rows = command(['docker', 'exec', cid, 'psql', '-At', '-U', 'ntnt', '-d', 'benchmarks', '-c', 'SELECT id, randomnumber FROM world ORDER BY id'])
    world = dict(tuple(map(int, line.split('|'))) for line in rows.splitlines())
    if set(world) != set(range(1, 10001)) or not all(1 <= n <= 10000 for n in world.values()):
        raise RuntimeError('world seed must be 10000 rows with valid randomnumber')
    (out / 'world-seed.txt').write_text(rows + '\n')
    env['DATABASE_URL'] = f'postgresql://ntnt:benchmark-local-only@127.0.0.1:{args.db_port}/benchmarks'
    return world, {'container_id': cid, 'network_id': owned['network'], 'name': name,
        'image': command(['docker', 'inspect', cid, '--format', '{{.Image}}']),
        'image_ref': args.pg_image, 'version': command(['docker', 'exec', cid, 'postgres', '--version']), 'subnet': subnet,
        'world_rows': len(world), 'world_seed_sha256': hashlib.sha256((rows + '\n').encode()).hexdigest(),
        'cpus': args.cpus, 'cpu_quota': 1, 'max_connections': 300, 'memory_limit': '512m'}


def probe(benchmark, port, world, out, label, samples=3):
    records = []
    for n in range(samples):
        req = urllib.request.Request(f'http://127.0.0.1:{port}' + PATHS[benchmark],
            data=PAYLOAD if benchmark == 'json-body' else None,
            headers={'Content-Type': 'application/json'} if benchmark == 'json-body' else {})
        record: dict[str, Any] = {'time': utcnow(), 'url': req.full_url, 'method': req.get_method()}
        try:
            # No redirect following: a fallback/login page is not the fixture.
            opener = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=5) as response:
                body = response.read(1_000_000)
                record.update(status=response.status, headers=dict(response.headers), body_bytes=len(body))
                body_path = out / f'body-{label}-{n + 1}.txt'
                body_path.write_bytes(body)
                record.update(body_file=body_path.name, sha256=hashlib.sha256(body).hexdigest())
                if response.status != 200:
                    raise ValueError(f'HTTP {response.status}')
                validate_body(benchmark, body, world)
                record['valid'] = True
        except Exception as exc:
            record.update(valid=False, error=str(exc))
        records.append(record)
    return records


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def memory_sample(session_id, started):
    """Account only for processes in the server's owned session, not wrk/PG."""
    processes, errors = [], []
    for directory in pathlib.Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            stat = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(stat[3]) != session_id or stat[0] == 'Z':
                continue
            status = (directory / 'status').read_text()
            rss = int(re.search(r'^VmRSS:\s+(\d+)', status, re.M)[1])
            rollup = (directory / 'smaps_rollup').read_text()
            pss = int(re.search(r'^Pss:\s+(\d+)', rollup, re.M)[1])
            processes.append({'pid': int(directory.name), 'rss_kib': rss, 'pss_kib': pss,
                              'threads': int(re.search(r'^Threads:\s+(\d+)', status, re.M)[1])})
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, TypeError, ValueError) as exc:
            errors.append({'pid': directory.name, 'error': str(exc)})
    return {'time': utcnow(), 'elapsed_seconds': time.monotonic() - started,
            'processes': processes, 'rss_kib': sum(p['rss_kib'] for p in processes),
            'pss_kib': sum(p['pss_kib'] for p in processes), 'errors': errors,
            'valid': bool(processes) and not errors}


def summarize_memory(samples):
    if len(samples) < 4 or not all(s['valid'] for s in samples):
        return {'valid': False, 'reason': 'missing/incomplete memory samples'}
    width = max(1, len(samples) // 4)
    first = statistics.median(s['pss_kib'] for s in samples[width:2 * width])
    last = statistics.median(s['pss_kib'] for s in samples[-width:])
    growth = last - first
    budget = max(32 * 1024, first * 0.20)
    return {'valid': True, 'sample_count': len(samples), 'elapsed_seconds': samples[-1]['elapsed_seconds'],
            'first_loaded_quarter_pss_kib': first, 'last_quarter_pss_kib': last,
            'growth_kib': growth, 'peak_pss_kib': max(s['pss_kib'] for s in samples),
            'peak_rss_kib': max(s['rss_kib'] for s in samples),
            'bounded': growth <= budget, 'growth_budget_kib': budget,
            'criterion': 'last-quarter minus second-quarter median PSS <= max(32 MiB, 20%); finite observation, not proof of no leak'}


def wrk_run(args, benchmark, port, duration, out, name, server_process=None):
    argv = ['taskset', '-c', args.cpus, tool('wrk'), '-t' + str(args.threads), '-c' + str(args.connections), '-d' + str(duration) + 's', '--latency']
    if benchmark == 'json-body':
        argv += ['-s', str(ROOT / 'post.lua')]
    argv += [f'http://127.0.0.1:{port}' + PATHS[benchmark]]
    before = host_state()
    samples, started, aborted = [], time.monotonic(), None
    memory_path = out / (name + '.memory.jsonl')
    with (out / name).open('w') as raw:
        process = subprocess.Popen(argv, stdout=raw, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            if server_process is not None:
                with memory_path.open('w') as memory_log:
                    while process.poll() is None:
                        sample = memory_sample(server_process.pid, started)
                        samples.append(sample)
                        memory_log.write(json.dumps(sample) + '\n'); memory_log.flush()
                        if server_process.poll() is not None or sample['rss_kib'] > args.memory_limit_mib * 1024:
                            aborted = 'server exited or memory safety ceiling exceeded'
                            stop_owned(process)
                            break
                        if time.monotonic() - started > duration + 30:
                            raise subprocess.TimeoutExpired(argv, duration + 30)
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                rc = process.wait(timeout=5)
            else:
                rc = process.wait(timeout=duration + 30)
        except subprocess.TimeoutExpired:
            rc = 124
        finally:
            stop_owned(process)
    text = (out / name).read_text()
    result = parse_wrk(text, rc)
    result.update(command=argv, raw_file=name, raw_sha256=hashlib.sha256(text.encode()).hexdigest(), host_before=before, host_after=host_state())
    if server_process is not None:
        result.update(memory=summarize_memory(samples), memory_file=memory_path.name,
                      memory_sha256=hashlib.sha256(memory_path.read_bytes()).hexdigest(), aborted=aborted)
        result['valid'] = result['valid'] and not aborted and result['memory']['valid']
    return result


def save_results(out, report, json_name='results.json', markdown_name='summary.md'):
    write_json(out / json_name, report)
    lines = ['# Validated HTTP benchmark results', '',
        'Shared live-service host; loopback client, servers and local PostgreSQL contend for the recorded CPU set. Not an isolated capacity test or a percentage comparison to historical NTNT 0.4.2.', '',
        f"Config: {report['config']}", '',
        'Body semantics sampled before warmup and after every run; wrk status/socket counters checked for every warmup and measured run. No per-request body validation overhead in timed wrk traffic.', '',
        'A median requires every configured run to be error-free and all body samples/warmup to pass. Stability flag: (max-min)/median <= 10%; unstable medians are observations, not rankings.', '',
        '| Framework | Workload | Status | Median req/s | Min–max req/s | Spread % | Stable |',
        '|---|---|---|---:|---|---:|---|']
    for cell in report['results']:
        s = cell.get('summary', {})
        lines.append(f"| {cell['framework']} | {cell['benchmark']} | {cell['status']} | {s.get('median_rps', '—')} | {s.get('min_rps', '—')}–{s.get('max_rps', '—')} | {s.get('spread_percent', '—')} | {s.get('stable', False)} |")
        if cell.get('error'):
            lines.append(f"\n{cell['framework']}/{cell['benchmark']}: {cell['error']}\n")
    if report.get('stability'):
        lines += ['', '## Sustained JSON-body memory observations', '',
                  'Server session only, 1s PSS/RSS samples; RSS sums double-count shared pages. Finite duration is not proof of absence of leaks.', '',
                  '| Framework | Valid traffic | Bounded PSS | Growth KiB | Peak PSS KiB | Requests |',
                  '|---|---|---|---:|---:|---:|']
        for fw, soak in report['stability'].items():
            run = soak.get('run', {})
            memory = run.get('memory', {})
            lines.append(f"| {fw} | {soak.get('valid')} | {soak.get('bounded')} | {memory.get('growth_kib', '—')} | {memory.get('peak_pss_kib', '—')} | {run.get('requests', '—')} |")
    (out / markdown_name).write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frameworks', default=' '.join(FRAMEWORKS))
    parser.add_argument('--benchmarks', default=' '.join(BENCHMARKS))
    for name, default in [('duration', 15), ('runs', 3), ('warmup', 5), ('connections', 100), ('threads', 4), ('workers', 4), ('port-base', 3100), ('db-port', 55455)]:
        parser.add_argument('--' + name, type=int, default=default)
    parser.add_argument('--cpus', default='0-3')
    parser.add_argument('--output', default=str(ROOT / 'results' / ('http-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))))
    parser.add_argument('--isolated-db', action='store_true', help='create/seed/tear down a NEW owned local PostgreSQL container and network')
    parser.add_argument('--pg-image', default='postgres:16')
    parser.add_argument('--db-subnet', default='10.250.55.0/28', help='unused private /24–/28; checked against Docker networks and host routes')
    parser.add_argument('--stability-seconds', type=int, default=0, help='additional sustained json-body run per framework with 1s memory samples (0 disables)')
    parser.add_argument('--memory-limit-mib', type=int, default=1024, help='abort soak if summed server session RSS exceeds this ceiling')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--skip-prepare', action='store_true', help='use already prepared artifacts; still record installed versions')
    args = parser.parse_args()
    frameworks, benchmarks = args.frameworks.split(), args.benchmarks.split()
    if not frameworks or not benchmarks or set(frameworks) - set(FRAMEWORKS) or set(benchmarks) - set(BENCHMARKS):
        parser.error('unknown or empty framework/workload list')
    if len(set(frameworks)) != len(frameworks) or len(set(benchmarks)) != len(benchmarks):
        parser.error('duplicate frameworks/workloads')
    if min(args.duration, args.runs, args.warmup, args.connections, args.threads, args.workers) < 1 or args.workers > 4 or args.threads > args.connections:
        parser.error('positive settings required, workers <= 4, threads <= connections')
    if args.stability_seconds < 0 or 0 < args.stability_seconds < 4 or args.memory_limit_mib < 64:
        parser.error('stability seconds must be 0 or >=4; memory ceiling must be >=64 MiB')
    if not args.prepare_only and set(benchmarks) & {'db', 'queries', 'template'} and not args.isolated_db:
        parser.error('DB workloads require --isolated-db; inherited DATABASE_URL is never used')
    command(['taskset', '-c', args.cpus, 'true'])
    out = pathlib.Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'results.json').exists() or (out / 'preparation.json').exists():
        parser.error('output already has results; use a fresh output directory')
    env = environment(args)
    report = {'schema_version': 1, 'started_at': utcnow(), 'config': vars(args), 'invocation': sys.argv, 'json_body_payload_bytes': len(PAYLOAD), 'json_body_payload_sha256': hashlib.sha256(PAYLOAD).hexdigest(),
              'hardware': command(['lscpu']), 'kernel': command(['uname', '-a']), 'logical_cpus': os.cpu_count(),
              'host_start': host_state(), 'git': {'commit': command(['git', 'rev-parse', 'HEAD']), 'branch': command(['git', 'branch', '--show-current']), 'status': command(['git', 'status', '--porcelain'])},
              'tracked_files_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in command(['git', 'ls-files']).splitlines() if (ROOT / p).is_file()}, 'preparation': {}, 'results': []}
    for fw in frameworks:
        print('PREPARE', fw, flush=True)
        try:
            report['preparation'][fw] = prepare_framework(fw, args, env, out)
        except Exception as exc:
            report['preparation'][fw] = {'status': 'failed', 'error': str(exc)}
            print('PREPARATION FAILED', fw, str(exc), flush=True)
        write_json(out / 'preparation-progress.json', report['preparation'])
    if args.prepare_only:
        write_json(out / 'preparation.json', report)
        return int(any(v['status'] != 'prepared' for v in report['preparation'].values()))
    report['wrk_version'] = subprocess.run([tool('wrk'), '--version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip()
    ntnt_bin = os.environ.get('NTNT_BIN')
    if ntnt_bin and pathlib.Path(ntnt_bin).is_file():
        report['ntnt_binary'] = {'path': ntnt_bin, 'sha256': hashlib.sha256(pathlib.Path(ntnt_bin).read_bytes()).hexdigest()}
    owned = {}
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupt)
    try:
        world = {}
        if args.isolated_db:
            world, report['database'] = create_database(args, env, out, owned)
        save_results(out, report)
        for fw in frameworks:
            if report['preparation'][fw]['status'] != 'prepared':
                for bench in benchmarks:
                    report['results'].append({'framework': fw, 'benchmark': bench, 'status': 'preparation_failed', 'error': report['preparation'][fw]['error']})
                save_results(out, report)
                continue
            port = args.port_base + FRAMEWORKS.index(fw)
            process = None
            try:
                require_free_port(port)
                path, _, launch, _ = framework_commands(fw, args)
                fw_env = env | {'PORT': str(port)}
                report['preparation'][fw]['environment'] = {k: fw_env[k] for k in ('PORT', 'NODE_ENV', 'NTNT_ENV', 'RAILS_ENV', 'GOMAXPROCS', 'TOKIO_WORKER_THREADS', 'WEB_CONCURRENCY', 'RAILS_MAX_THREADS', 'BENCH_WORKERS', 'NTNT_DB_POOL_SIZE')}
                with (out / f'server-{fw}.log').open('w') as log:
                    process = subprocess.Popen(['taskset', '-c', args.cpus] + launch, cwd=path, env=fw_env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                report['preparation'][fw]['owned_pid'] = process.pid
                for _ in range(60):
                    if process.poll() is not None:
                        raise RuntimeError(f'server exited {process.returncode}; see server-{fw}.log')
                    ready = probe('plaintext', port, world, out, fw + '-ready', samples=1)
                    if ready[0]['valid']:
                        break
                    time.sleep(0.5)
                else:
                    raise RuntimeError(f'server readiness timeout; see server-{fw}.log')
                # taskset may not have run immediately after Popen; sample once ready.
                report['preparation'][fw]['cpu_affinity'] = sorted(os.sched_getaffinity(process.pid))
                for bench in benchmarks:
                    cell = {'framework': fw, 'benchmark': bench, 'status': 'running', 'runs': []}
                    report['results'].append(cell)
                    cell['preflight'] = probe(bench, port, world, out, f'{fw}-{bench}-preflight')
                    if not all(v['valid'] for v in cell['preflight']):
                        cell.update(status='preflight_failed', error=str([v.get('error') for v in cell['preflight'] if not v['valid']]))
                        save_results(out, report); continue
                    print('WARMUP', fw, bench, flush=True)
                    cell['warmup'] = wrk_run(args, bench, port, args.warmup, out, f'warmup-{fw}-{bench}.txt')
                    for n in range(1, args.runs + 1):
                        print('RUN', fw, bench, n, flush=True)
                        run = wrk_run(args, bench, port, args.duration, out, f'raw-{fw}-{bench}-run{n}.txt')
                        run['body_samples'] = probe(bench, port, world, out, f'{fw}-{bench}-after{n}')
                        run['valid'] = run['valid'] and all(v['valid'] for v in run['body_samples'])
                        cell['runs'].append(run)
                        save_results(out, report)
                    cell['summary'] = summarize(cell['runs'], args.runs)
                    if not cell['warmup']['valid']:
                        cell['summary'] = {'median_rps': None, 'stable': False, 'reason': 'invalid warmup'}
                    cell['status'] = 'valid' if cell['summary']['median_rps'] is not None else 'invalid'
                    print('CELL', fw, bench, cell['status'], cell['summary'], flush=True)
                    save_results(out, report)
                if args.stability_seconds:
                    print('STABILITY', fw, args.stability_seconds, flush=True)
                    soak: dict[str, Any] = {'preflight': probe('json-body', port, world, out, fw + '-soak-before')}
                    report.setdefault('stability', {})[fw] = soak
                    if all(v['valid'] for v in soak['preflight']):
                        soak['run'] = wrk_run(args, 'json-body', port, args.stability_seconds, out, f'stability-{fw}.txt', process)
                        soak['postflight'] = probe('json-body', port, world, out, fw + '-soak-after')
                        soak['valid'] = soak['run']['valid'] and all(v['valid'] for v in soak['postflight'])
                        soak['bounded'] = soak['valid'] and soak['run']['memory'].get('bounded', False)
                    else:
                        soak.update(valid=False, bounded=False, error='invalid soak response')
                    print('STABILITY RESULT', fw, soak.get('valid'), soak.get('bounded'), soak.get('run', {}).get('memory'), flush=True)
                    save_results(out, report)
            except Exception as exc:
                existing = {(c['framework'], c['benchmark']) for c in report['results']}
                for bench in benchmarks:
                    if (fw, bench) not in existing:
                        report['results'].append({'framework': fw, 'benchmark': bench, 'status': 'startup_failed', 'error': str(exc)})
                print('FRAMEWORK FAILED', fw, str(exc), flush=True)
            finally:
                if process:
                    stop_owned(process)
                save_results(out, report)
    except BaseException as exc:
        report['fatal_error'] = repr(exc)
        raise
    finally:
        cleanup = {}
        for kind, argv in [('container', ['docker', 'rm', '-f', '-v']), ('network', ['docker', 'network', 'rm'])]:
            if owned.get(kind):
                try:
                    cleanup[kind] = command(argv + [owned[kind]])
                except Exception as exc:
                    cleanup[kind] = {'error': str(exc)}
        report.update(cleanup=cleanup, finished_at=utcnow(), host_end=host_state())
        save_results(out, report)
    expected = len(frameworks) * len(benchmarks)
    bad_soaks = args.stability_seconds and (set(report.get('stability', {})) != set(frameworks) or any(not s.get('bounded') for s in report.get('stability', {}).values()))
    return int(len(report['results']) != expected or any(c['status'] != 'valid' for c in report['results']) or bad_soaks)


def summarize(runs, expected):
    if len(runs) != expected or not all(r['valid'] for r in runs):
        return {'median_rps': None, 'stable': False, 'reason': 'missing or invalid run'}
    rates = [r['requests_per_second'] for r in runs]
    median = statistics.median(rates)
    spread = (max(rates) - min(rates)) / median * 100
    return {'median_rps': median, 'min_rps': min(rates), 'max_rps': max(rates),
            'spread_percent': spread, 'cv_percent': statistics.pstdev(rates) / statistics.mean(rates) * 100,
            'stable': len(rates) >= 3 and spread <= 10, 'stability_threshold_percent': 10}


def require_free_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', port))


def stop_owned(process):
    """Only signal a session/process group this runner created."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The group can outlive its parent; do not stop at parent exit.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)

PAYLOAD = b'{"message":"Hello, World!","numbers":[1,2,3,4,5],"nested":{"key":"value"}}'


def validate_body(benchmark, body, world):
    """Require actual fixture output, including exact seeded DB values."""
    def row(value):
        if not isinstance(value, dict) or set(value) != {'id', 'randomNumber'}:
            raise ValueError('not a world row')
        i, n = value['id'], value['randomNumber']
        if type(i) is not int or type(n) is not int or i not in world or world[i] != n:
            raise ValueError('world row differs from seed')
    if benchmark == 'plaintext':
        if body != b'Hello, World!':
            raise ValueError('wrong plaintext')
        return
    if benchmark == 'template':
        html = body.decode('utf-8')
        rows = re.findall(r'<tr>\s*<td>\s*(\d+)\s*</td>\s*<td>\s*(\d+)\s*</td>\s*</tr>', html)
        if '<h1>World Database</h1>' not in html or len(rows) != 10 or '{{' in html:
            raise ValueError('template must render ten world rows')
        for i, n in rows:
            row({'id': int(i), 'randomNumber': int(n)})
        return
    data = json.loads(body)
    expected = {'json': {'message': 'Hello, World!'}, 'params': {'id': '42'}, 'json-body': json.loads(PAYLOAD)}
    if benchmark in expected:
        if data != expected[benchmark]:
            raise ValueError('wrong JSON response')
    elif benchmark == 'db':
        row(data)
    elif benchmark == 'queries':
        if not isinstance(data, list) or len(data) != 20:
            raise ValueError('queries must return twenty rows')
        for value in data:
            row(value)
    else:
        raise ValueError('unknown benchmark')


def parse_wrk(raw, returncode):
    total = re.search(r'(\d+) requests in ([\d.]+)(us|ms|s|m|h), (\S+) read', raw)
    rps = re.search(r'^Requests/sec:\s+([\d.]+)', raw, re.M)
    non = re.search(r'Non-2xx or 3xx responses:\s*(\d+)', raw)
    errors = re.search(r'Socket errors: connect (\d+), read (\d+), write (\d+), timeout (\d+)', raw)
    sockets = dict(zip(('connect', 'read', 'write', 'timeout'), map(int, errors.groups() if errors else (0, 0, 0, 0))))
    requests = int(total[1]) if total else 0
    non_success = int(non[1]) if non else 0
    latency = re.search(r'^\s+Latency\s+(\S+)\s+(\S+)\s+(\S+)', raw, re.M)
    return {
        'valid': returncode == 0 and requests > 0 and rps is not None and not non_success and not any(sockets.values()),
        'returncode': returncode, 'requests': requests,
        'successful_responses': requests - non_success, 'non_success_responses': non_success,
        'socket_errors': sockets, 'requests_per_second': float(rps[1]) if rps else None,
        'elapsed_seconds': float(total[2]) * {'us': 0.000001, 'ms': 0.001, 's': 1, 'm': 60, 'h': 3600}[total[3]] if total else None,
        'latency_avg': latency[1] if latency else None,
        'latency_stdev': latency[2] if latency else None,
        'latency_max': latency[3] if latency else None,
        'latency_percentiles': dict(re.findall(r'^\s+(50|75|90|99)%\s+(\S+)', raw, re.M)),
    }


if __name__ == '__main__':
    sys.exit(main())
