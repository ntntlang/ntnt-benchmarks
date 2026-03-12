# ntnt-benchmarks

HTTP framework performance benchmarks comparing **ntnt** against popular alternatives across real-world workloads.

> **Language:** ntnt v0.4.1 (Rust runtime, Axum/Tokio)  
> **Competitors:** FastAPI · Express/TypeScript · Gin · Hono/Bun · Actix Web  
> **Tool:** [wrk](https://github.com/wg/wrk) — 4 threads, 100 connections, 30s per run, 3 runs (median)

---

## Latest Results

<!-- RESULTS_TABLE_START -->
*Run `./benchmark.sh` to generate results — see results/ for the latest.*
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
| `json-body` | `POST /json` | 1KB JSON body parse + echo |

---

## Implementations

Each framework implements identical endpoints using idiomatic code for that ecosystem — no hand-optimization.

| Framework | Language | Runtime | Port |
|-----------|----------|---------|------|
| [ntnt](./ntnt/) | ntnt | Rust (Axum/Tokio) | 3100 |
| [FastAPI](./fastapi/) | Python 3.12 | uvicorn (multi-worker) | 3101 |
| [Express](./express/) | TypeScript | Node.js v22 | 3102 |
| [Gin](./gin/) | Go | net/http + goroutines | 3103 |
| [Hono](./hono-bun/) | TypeScript | Bun v1.3 | 3104 |
| [Actix Web](./actix/) | Rust | Tokio (multi-worker) | 3105 |

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

All DB benchmarks use a shared PostgreSQL instance with the [TechEmpower](https://www.techempower.com/benchmarks/) `world` table (10,000 rows).

```bash
# Create the benchmark database
createdb benchmarks

# Seed it
psql -d benchmarks -f setup-db.sql
```

By default, implementations connect to `172.19.0.3:5432` (Docker-hosted PG). Override with:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/benchmarks"
```

### Running

```bash
# Full suite (all frameworks, all benchmarks)
./benchmark.sh

# Custom frameworks/benchmarks
./benchmark.sh --frameworks "ntnt gin actix" --benchmarks "plaintext db queries"

# Faster run (shorter duration)
./benchmark.sh --duration 10 --runs 1

# All options
./benchmark.sh --help
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--frameworks` | all | Space-separated list: `ntnt fastapi express gin hono actix` |
| `--benchmarks` | all | Space-separated list: `plaintext json params db queries template json-body` |
| `--duration` | `30` | Seconds per wrk run |
| `--connections` | `100` | Concurrent connections |
| `--threads` | `4` | wrk thread count |
| `--runs` | `3` | Runs per benchmark (median is used) |
| `--warmup` | `5` | Warmup duration in seconds |
| `--output` | `results/` | Directory for raw output and summaries |

### Results

After each run, results are saved to `results/`:

```
results/
├── 20260312-095500-summary.md      ← Human-readable table
├── 20260312-095500.json            ← Machine-readable
└── raw-<framework>-<bench>-run*.txt  ← Full wrk output (proof)
```

---

## Methodology

### Fairness rules

1. **Idiomatic code** — each implementation is written the way that framework's own docs recommend. No hand-tuning, no disabling features.
2. **Same database** — shared PostgreSQL instance, same table, same query, 50-connection pool per framework.
3. **Production mode** — debug logging disabled, hot-reload off, production flags set.
4. **Pinned versions** — all runtime and dependency versions are pinned. See each subdirectory.
5. **Median of 3** — each benchmark runs 3 times; the median result is reported. Eliminates warm-up noise.
6. **Sequential** — frameworks run one at a time, never concurrently, so they don't compete for resources.

### Known caveats

- **FastAPI** uses `--workers $(nproc)` (multi-process). ntnt, Gin, and Actix are multi-threaded single-process. Express and Hono are single-threaded.
- **Same machine** — benchmarks run on the same host as PostgreSQL. Production would have separate hosts; DB-heavy benchmarks would look different.
- **No reverse proxy** — no nginx in front. Real deployments add a layer.
- **Actix** is included as a theoretical ceiling — it shows the interpreter overhead of ntnt vs raw Rust.

### Hardware

Run on: see `results/<timestamp>-summary.md` for the system info of each run.

---

## Contributing

Run the suite, open a PR with your `results/` output. If you're adding a new framework, add a new subdirectory with the same 7 endpoints and update `benchmark.sh`.

---

## License

MIT
