# Background job benchmarks

Measures how fast worker processes drain a backlog of jobs, and how that
changes as worker processes are added. Run it with
`scripts/run-jobs-benchmarks.py`.

| Target | Store | Fixture |
|---|---|---|
| `ntnt-sqlite` | SQLite file (fresh per run) | [`ntnt/`](ntnt/) with `JOBS_STORE=sqlite:...` |
| `ntnt-redis` | Redis | [`ntnt/`](ntnt/) with `JOBS_STORE=redis://...` |
| `bullmq` | Redis | [`bullmq/`](bullmq/) (Node) |
| `sidekiq` | Redis | [`sidekiq/`](sidekiq/) (Ruby) |

The ntnt SQLite and Redis targets use the same `app.tnt`/`producer.tnt`; only
`JOBS_STORE` differs.

## Method

1. Enqueue `--jobs` identical jobs. Each one sleeps `--work-ms` (default 20 ms).
2. Start P worker processes with C slots each, and wait until every job has completed.
3. Every worker writes one JSON line per completed job to stderr, in the shape ntnt's job events already use (`{"event":"job.completed","job_id":...,"timestamp":<unix ns>}`), so all targets are scored the same way.
4. Throughput is **steady-state**: completions per second across the middle 80% of completions, which excludes worker startup and the tail. The median of `--runs` runs is reported.

Each run also records:
- whether every job completed, and any duplicate completions
- Redis commands per job (from `INFO commandstats`)
- CPU cores used by Redis and by the workers, and how busy the host was
- ntnt claim deferrals, and how many jobs each worker process completed

A run is rejected if a worker process exits before the backlog drains.

With sleep-bound jobs, ideal throughput is `P × C × 1000 / work_ms`. The gap
from that ideal is queue overhead. Use `--work-ms 0` to measure pure queue cost.

**CPU placement.** By default the script starts a disposable `redis:7.4-alpine`
container with persistence off, pins it to the last 2 CPUs, and pins workers
and producers to the rest, so Redis never competes with the workers for CPU.
The layout is recorded in the results. `--cpu-layout none` turns pinning off.
`--redis-url` uses an existing Redis instead, for example on another host.
**Its database is flushed before every run.**

**ntnt specifics.** Each worker process gets its own `--worker-group`, because
one checkout allows only one worker process per group on a host (control-socket
ownership). ntnt's default poll interval is used unless you pass `--ntnt-poll-ms`.

## Setup

```bash
# ntnt: build the binary you want to measure
(cd ../ntnt && cargo build --release)

# BullMQ
(cd jobs/bullmq && npm ci)

# Sidekiq
(cd jobs/sidekiq && bundle config set --local path vendor/bundle && bundle install)
```

Docker is required unless you pass `--redis-url`. The script itself is Python
stdlib only.

## Running

```bash
# Smoke test (1 and 4 processes x 4 slots, 400 jobs, 1 run)
NTNT_REPO=../ntnt python3 scripts/run-jobs-benchmarks.py --quick

# Default matrix: 1,2,4,8,16 processes x 16 slots, 8,000 jobs, 3 runs, all targets
NTNT_REPO=../ntnt python3 scripts/run-jobs-benchmarks.py

# ntnt before/after for a runtime PR
NTNT_BIN=/path/to/main/ntnt python3 scripts/run-jobs-benchmarks.py --targets ntnt-sqlite,ntnt-redis
NTNT_BIN=/path/to/branch/ntnt python3 scripts/run-jobs-benchmarks.py --targets ntnt-sqlite,ntnt-redis

# Pure queue overhead, one slot per process
python3 scripts/run-jobs-benchmarks.py --work-ms 0 --concurrency 1
```

Results go to `results/jobs/runs/<timestamp>/`: `summary.md`, `summary.json`,
and `raw/<target>-<P>x<C>-run<N>/worker-*.err`. That directory is gitignored.
Reviewed baselines that are worth keeping are copied to `results/jobs/baselines/`.

## Adding a framework

1. Add a directory under `jobs/` with a producer that enqueues `BENCH_JOBS` jobs sleeping `BENCH_WORK_MS`, and a worker that uses `BENCH_CONCURRENCY` slots and prints the completion line above to stderr.
2. Add it to `TARGETS` and `build_target()` in the script.
3. Pin its dependency versions.
