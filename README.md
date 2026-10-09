# ntnt-benchmarks

HTTP framework performance benchmarks comparing **ntnt** against popular alternatives across real-world workloads.

> **Language:** choose an explicit `NTNT_BIN`; the latest validated release run uses official NTNT 0.5.5
> **Competitors:** Actix Web · Gin · FastAPI · Fastify · Hono/Bun · Django · Express · Rails
> **Tools:** `benchmark.sh` for cross-framework HTTP benchmarks; `scripts/run-ntnt-benchmarks.py` for DD-061 ntnt-internal before/after runs

---

## Latest validated run: NTNT 0.5.5 (October 9, 2026)

Median requests/sec from three 10-second runs after 3-second warmups: 100 connections, four wrk threads, four workers where supported. Launch commands use logical CPUs 4–7 on a shared Ryzen 7 host; client, server and local PostgreSQL contend for those CPUs. These are observations of the recorded fixtures, not a universal framework ranking or a controlled comparison against NTNT 0.4.2.

<!-- RESULTS_TABLE_START -->

| Workload | NTNT 0.5.5 | Actix Web | Gin | FastAPI | Fastify | Hono/Bun | Django | Express | Rails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Plaintext | 90,775 | 213,732 | 118,411 | 51,771† | 64,267 | 88,583 | 14,157 | 32,559 | 8,431 |
| JSON | 88,416 | 205,475 | 129,615† | 48,531 | 56,597† | 79,701† | 13,884 | 31,049 | 7,854† |
| Params | 82,273 | 204,645 | 127,239 | 39,367 | 60,911 | 77,117 | 13,740 | 29,012 | 7,874 |
| JSON body | 74,080 | 186,575 | 83,287† | 36,007 | 33,408† | 59,926 | 13,069 | 18,134 | 7,685 |
| DB (1 query) | 21,962 | 11,576 | 27,407 | 8,961 | 17,285 | 13,674 | 243 | 11,200 | 4,363† |
| Queries (20) | 1,748 | 611 | 1,631 | 1,065 | 929 | 770 | 193 | 542† | 752 |
| Template | 3,320 | 1,210 | 3,083† | 2,247 | 1,902 | 1,538 | 214 | 1,277 | 1,385 |

† Run spread exceeds 10%; do not use these cells to claim a reliable ordering. All seven NTNT cells meet the spread threshold. Worker/process models and database pool sizes remain fixture-specific. The POST payload is 74 bytes, not 1 KB.

[Method, runtime versions and complete evidence](results/http-v0.5.5-2026-10-09/README.md) · [Revalidated summary](results/http-v0.5.5-2026-10-09/validated-summary.md) · [Historical 0.4.2 charts](results/charts.html)

<!-- RESULTS_TABLE_END -->

---

## Benchmark Suite

### Tier 1 — Micro (raw throughput)

| ID | Route | What it tests |
|----|-------|---------------|
| `plaintext` | `GET /plaintext` | Raw HTTP overhead — parsing, routing, response writing |
| `json` | `GET /json` | JSON serialization on top of plaintext |
| `params` | `GET /users/:id` | Router pattern matching + param extraction |

### Tier 2 — Real-world patterns

| ID | Route | What it tests |
|----|-------|---------------|
| `db` | `GET /db` | Single random PostgreSQL row |
| `queries` | `GET /queries?count=20` | 20 sequential individual queries |
| `template` | `GET /template` | 10 DB rows rendered as HTML |
| `json-body` | `POST /json` | 74-byte JSON body parse + echo (see `post.lua`) |

---

## Implementations

Each framework implements identical endpoints using idiomatic code for that ecosystem — no hand-optimization.

| Framework | Language | Runtime | Port |
|-----------|----------|---------|------|
| [ntnt](./ntnt/) | ntnt | Rust (Axum/Tokio) | 3100 |
| [FastAPI](./fastapi/) | Python 3.12 | uvicorn (multi-worker) | 3101 |
| [Express](./express/) | TypeScript | Node.js (one process) | 3102 |
| [Gin](./gin/) | Go | net/http + goroutines | 3103 |
| [Hono](./hono-bun/) | TypeScript | Bun (one process) | 3104 |
| [Actix Web](./actix/) | Rust | Tokio (multi-worker) | 3105 |
| [Fastify](./fastify/) | JavaScript | Node.js (one process) | 3106 |
| [Rails](./rails/) | Ruby 3.2 | Puma (4 workers) | 3107 |
| [Django](./django/) | Python 3.12 | gunicorn (4 sync workers) | 3108 |

---

## Running the Benchmarks

### Prerequisites

```bash
# Required
sudo apt-get install wrk postgresql-client

# Runtime-specific (install what you want to benchmark)
# ntnt
curl -fsSL https://ntnt-lang.org/install | sh    # or build from source

# Python
python3 -m pip install -r fastapi/requirements.txt

# Node.js / TypeScript
cd express && npm install && npx tsc

# Go
go build -o gin/gin-bench ./gin/

# Bun
curl -fsSL https://bun.sh/install | bash
cd hono-bun && bun install

# Rust
cd actix && cargo build --release
```

### Database Setup

The cross-framework runner requires `--isolated-db` for DB workloads. It creates a new, labelled PostgreSQL container, seeds the [TechEmpower](https://www.techempower.com/benchmarks/) `world` table (10,000 rows), and removes only its own container/network. The DB is published on loopback only, constrained to one CPU and 512 MiB. It never uses an inherited `DATABASE_URL` or production DB/Redis. Docker and `ip` are required.

`--db-subnet` must be an unused private IPv4 /24–/28 (default `10.250.55.0/28`). Existing Docker networks and host routes are checked before creation; select another range on overlap. This avoids exhausting Docker’s predefined address pools without cleaning up unrelated networks.

Manual seeding below is only for developing fixtures outside this runner:

```bash
# Create the benchmark database
createdb benchmarks

# Seed it
psql -d benchmarks -f setup-db.sql
```

Outside the runner, explicitly point fixtures at a development database. Do not reuse production credentials:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/benchmarks"
```

### Running

```bash
# Full cross-framework suite (all frameworks, all benchmarks)
NTNT_BIN=/path/to/official/ntnt ./benchmark.sh --isolated-db --cpus 4-7 --workers 4

# Custom frameworks/benchmarks
./benchmark.sh --isolated-db --cpus 4-7 --frameworks "ntnt gin actix" --benchmarks "plaintext db queries"

# Faster run (shorter duration)
./benchmark.sh --isolated-db --cpus 4-7 --duration 10 --runs 3

# All options
./benchmark.sh --help
```

### DD-061 ntnt-internal benchmarks

For ntnt runtime/interpreter optimization work, use the dedicated internal harness. It measures ntnt-only routes that are awkward to compare fairly across frameworks: interpreter compute loops, route-param/map reads, external-template rendering, partials, row-heavy template loops, and optional PostgreSQL probes.

```bash
# Build ../ntnt with cargo build --profile dev-release, then run a quick suite
python3 scripts/run-ntnt-benchmarks.py --quick

# Pin a specific checkout or binary
NTNT_REPO=/path/to/ntnt python3 scripts/run-ntnt-benchmarks.py --duration 10s --runs 3
NTNT_BIN=/path/to/ntnt python3 scripts/run-ntnt-benchmarks.py --quick --skip-build

# Include optional DB routes
DATABASE_URL=postgres://ntnt:***@localhost/benchmarks \
  python3 scripts/run-ntnt-benchmarks.py --quick --include-db
```

Results are written to `results/ntnt-internal/`. For performance PRs, run the same command on `main` and the candidate branch, then compare the generated Markdown summaries.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--frameworks` | all | Space-separated list: `ntnt fastapi express gin hono actix fastify rails django` |
| `--benchmarks` | all | Space-separated list: `plaintext json params db queries template json-body` |
| `--duration` | `15` | Seconds per wrk run |
| `--connections` | `100` | Concurrent connections |
| `--threads` | `4` | wrk thread count |
| `--runs` | `3` | Runs per benchmark (median is used) |
| `--warmup` | `5` | Warmup duration in seconds |
| `--output` | timestamped directory under `results/` | New directory for raw output and summaries; existing run output is refused |
| `--cpus` | `0-3` | Affinity for preparation, servers, wrk and DB; choose a safe subset on a shared host |
| `--workers` | `4` | At most 4 workers; Node/Bun fixtures remain single-process |
| `--port-base` | `3100` | Loopback ports, in framework order |
| `--isolated-db` | off | Required for `db`, `queries`, `template`; new owned local DB only |
| `--db-port` | `55455` | Loopback PostgreSQL port |
| `--db-subnet` | `10.250.55.0/28` | Explicit unused private Docker subnet, overlap-checked |
| `--pg-image` | `postgres:16` | PostgreSQL image; resolved image ID recorded |
| `--prepare-only` | off | Install/build selected fixtures and record versions, without traffic |
| `--skip-prepare` | off | Reuse already-built artifacts; versions still recorded |
| `--stability-seconds` | `0` | Sustained POST JSON echo per framework; 1s server-session PSS/RSS samples |
| `--memory-limit-mib` | `1024` | Abort soak above summed server-session RSS ceiling |

### Results

Each invocation writes atomically to its own directory under `results/`:

```
results/http-<timestamp>/
├── summary.md                     ← Median, min/max, spread and status
├── results.json                   ← Versions, hardware, source hashes, probes, errors, commands
├── world-seed.txt                 ← Exact DB values used for response validation
├── body-*.txt                     ← Before/after response samples
├── warmup-<framework>-<bench>.txt  ← Full warmup output
├── raw-<framework>-<bench>-run*.txt← Full repeated wrk output
├── stability-*.txt.memory.jsonl    ← Optional per-second server memory samples
├── validated-results.json         ← Optional offline recheck; original results.json stays unchanged
└── validated-summary.md           ← Summary from rechecked evidence
```

---

## Methodology

### Fairness rules

1. **Existing fixtures** — retain each implementation’s worker/process model and endpoint logic. Equivalent response semantics do not imply equivalent internals.
2. **Same isolated database** — same seed, schema and SQL workload; pool sizes and connection reuse remain fixture-specific, not universally 50 connections.
3. **Production mode** — debug logging disabled, hot-reload off, production flags recorded.
4. **Recorded versions** — use existing lockfiles for preparation; record actual runtime/dependency versions, binary/source hashes and launch commands. Python requirements do not pin every transitive dependency.
5. **Repeated observations** — median, min/max, coefficient of variation and `(max-min)/median` spread are retained. “Stable” requires at least three valid runs and spread ≤10%; it is not a confidence interval.
6. **Validated traffic** — exactly HTTP 200 and semantic response bodies before warmup and after every measured run, including exact seeded DB values. Every warmup/run must have zero wrk non-success responses and zero connect/read/write/timeout errors; otherwise the cell has no publishable median. Body sampling is not per-request checking of timed traffic.
7. **Sequential and bounded** — frameworks run one at a time in the selected CPU set. The loopback client and DB share that set; other live host services are not isolated. Session-scoped cleanup never kills a process just because it occupies a requested port.
8. **Finite memory test** — optional sustained JSON-body traffic records server-session PSS/RSS at 1s intervals. Compare second-quarter and last-quarter median PSS: growth must be ≤max(32 MiB, 20%). This is a bounded observation, not proof of absence of leaks. RSS sums include shared pages multiple times; PSS is preferred.

### Known caveats

- **Multi-process vs single-process** — FastAPI, Rails and Django use the requested worker count (maximum 4). NTNT and Actix receive the same worker setting; Gin receives `GOMAXPROCS`. Express, Fastify and Hono remain one server process. These are fixture configurations, not equal maximum hardware utilization.
- **Django sync caveat** — Django's DB numbers are limited by synchronous gunicorn workers + psycopg2. An async Django setup (ASGI + asyncpg) would perform significantly better.
- **Same machine, constrained DB** — servers, wrk and PostgreSQL contend on the same selected CPUs; PostgreSQL is capped at one CPU. These figures describe this shared-host setup, not production capacity or changes since the historical 0.4.2 run.
- **No reverse proxy** — no nginx in front. Real deployments add a layer.
- **Template caveat** — NTNT uses an external template; several competitors build HTML strings. The route includes ten sequential DB queries and is not a pure template-engine comparison.
- **Historical charts** — `results/charts.html` is the March 0.4.2 archive, not current 0.5.5 data.

### Hardware

Run on: see each run’s `results.json` for hardware, CPU affinity, versions and host pressure snapshots. The Markdown summary contains the selected settings.

For an offline evidence recheck (no new traffic), run `python3 scripts/revalidate_http_results.py results/<run-directory>`. It verifies recorded raw/body/seed/memory hashes and semantics, writes separate `validated-results.json` / `validated-summary.md`, and preserves the original output. This is required for the 0.5.5 run because wrk’s two-minute duration formatting exposed a seconds-only parser bug; see that run’s notes. `./generate-report.sh results/<run-directory>` prefers the revalidated summary when present.

---

## Contributing

Run the suite, open a PR with your `results/` output. If you're adding a new framework, add a new subdirectory with the same 7 endpoints and update `benchmark.sh`.

---

## License

MIT
