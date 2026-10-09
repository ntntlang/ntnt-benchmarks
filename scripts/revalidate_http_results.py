#!/usr/bin/env python3
"""Recheck captured benchmark evidence; never replace raw traffic or original JSON."""
import argparse
import hashlib
import json
import pathlib
import sys

import http_benchmarks as bench


def revalidate(directory):
    original = directory / 'results.json'
    report = json.loads(original.read_text())
    if not report.get('finished_at') or report.get('fatal_error'):
        raise ValueError('refuse unfinished/fatal measurement report')
    if (directory / 'validated-results.json').exists():
        raise ValueError('validated output exists; do not silently replace it')
    config = report['config']
    expected = {(fw, workload) for fw in config['frameworks'].split() for workload in config['benchmarks'].split()}
    cells = report['results']
    if len(cells) != len(expected) or {(c['framework'], c['benchmark']) for c in cells} != expected:
        raise ValueError('missing/duplicate matrix cells')
    seed = (directory / 'world-seed.txt').read_bytes() if config['isolated_db'] else b''
    if seed and hashlib.sha256(seed).hexdigest() != report['database']['world_seed_sha256']:
        raise ValueError('seed hash mismatch')
    world = {int(line.split('|')[0]): int(line.split('|')[1]) for line in seed.decode().splitlines()}
    counts = {'cells': len(cells), 'wrk_files': 0, 'body_samples': 0, 'memory_samples': 0}

    def bodies(workload, records):
        if not records:
            return False
        valid = True
        for sample in records:
            counts['body_samples'] += 1
            if sample.get('status') != 200 or not sample.get('body_file'):
                valid = False
                continue
            body = (directory / sample['body_file']).read_bytes()
            if hashlib.sha256(body).hexdigest() != sample['sha256'] or len(body) != sample['body_bytes']:
                raise ValueError('body hash/size mismatch')
            try:
                bench.validate_body(workload, body, world)
            except (ValueError, TypeError, KeyError):
                valid = False
        return valid

    def raw(run):
        text = (directory / run['raw_file']).read_text()
        if hashlib.sha256(text.encode()).hexdigest() != run['raw_sha256']:
            raise ValueError('raw wrk hash mismatch')
        counts['wrk_files'] += 1
        run.update(bench.parse_wrk(text, run['returncode']))

    for cell in cells:
        workload = cell['benchmark']
        if cell['status'] in ('startup_failed', 'preparation_failed'):
            continue
        preflight = bodies(workload, cell['preflight'])
        if not preflight or 'warmup' not in cell:
            cell.update(status='preflight_failed', summary={'median_rps': None, 'stable': False})
            continue
        raw(cell['warmup'])
        for run in cell['runs']:
            raw(run)
            run['valid'] = bodies(workload, run['body_samples']) and run['valid']
        cell['summary'] = bench.summarize(cell['runs'], config['runs'])
        if not cell['warmup']['valid']:
            cell['summary'] = {'median_rps': None, 'stable': False, 'reason': 'invalid warmup'}
        cell['status'] = 'valid' if cell['summary']['median_rps'] is not None else 'invalid'
    for soak in report.get('stability', {}).values():
        if 'run' not in soak:
            continue
        run = soak['run']
        raw(run)
        memory_bytes = (directory / run['memory_file']).read_bytes()
        if hashlib.sha256(memory_bytes).hexdigest() != run['memory_sha256']:
            raise ValueError('memory log hash mismatch')
        samples = [json.loads(line) for line in memory_bytes.decode().splitlines()]
        counts['memory_samples'] += len(samples)
        run['memory'] = bench.summarize_memory(samples)
        run['valid'] = run['valid'] and run['memory']['valid'] and not run.get('aborted')
        soak['valid'] = bodies('json-body', soak['preflight']) and bodies('json-body', soak['postflight']) and run['valid']
        soak['bounded'] = soak['valid'] and run['memory'].get('bounded', False)
    report['revalidation'] = {'time': bench.utcnow(), 'original_file': original.name,
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'reason': 'wrk uses minutes for 120s runs; original seconds-only parser lost soak counts. All immutable raw/body/seed/memory evidence rechecked with corrected parser.',
        'counts': counts}
    bench.save_results(directory, report, 'validated-results.json', 'validated-summary.md')
    bad_cells = [f"{c['framework']}/{c['benchmark']}" for c in cells if c['status'] != 'valid']
    bad_soaks = [fw for fw in config['frameworks'].split() if config['stability_seconds'] and not report.get('stability', {}).get(fw, {}).get('bounded')]
    print(json.dumps({'verified': counts, 'invalid_cells': bad_cells, 'invalid_soaks': bad_soaks,
                      'unstable_cells': [f"{c['framework']}/{c['benchmark']}" for c in cells if not c.get('summary', {}).get('stable')]}, indent=2))
    return int(bool(bad_cells or bad_soaks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    args = parser.parse_args()
    sys.exit(revalidate(args.directory.resolve()))
