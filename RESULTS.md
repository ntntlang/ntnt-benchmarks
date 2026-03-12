# ntnt Benchmark Results

> Full benchmark suite: ntnt vs FastAPI, Express/TS, Gin, Hono/Bun, Actix-Web  
> Plus: ntnt v0.4.1 → v0.4.2 performance progression

---

## System

| | |
|---|---|
| **OS** | Linux 6.8.0-71-generic |
| **CPUs** | 16 |
| **RAM** | 59 GiB |
| **wrk config** | 4 threads, 100 connections, 15s, 3 runs (median reported) |
| **Warmup** | 5s before each run |

---

## ntnt v0.4.1 → v0.4.2 Progression

v0.4.2 introduces a worker pool: N interpreter threads (CPU count, capped at 8) sharing a
[flume](https://crates.io/crates/flume) MPMC channel. Each worker runs its own Interpreter
instance, evaluating the source file in `Worker` mode (routes register, `listen()` skips).
This eliminates the single-thread bottleneck that serialized all I/O.

| Benchmark | v0.4.1 | v0.4.2 | Improvement |
|-----------|-------:|-------:|-------------|
| plaintext | 118,208 | **302,141** | **2.6×** 🚀 |
| json | 108,929 | **295,990** | **2.7×** 🚀 |
| params | 88,926 | **267,832** | **3.0×** 🚀 |
| json-body (POST) | 76,398 | **252,284** | **3.3×** 🚀 |
| db (1 query) | 8,371 | **37,818** | **4.5×** 🔥 |
| 20 queries | 457 | **2,349** | **5.1×** 🔥 |
| template (10 queries + HTML) | 899 | **4,614** | **5.1×** 🔥 |

DB-heavy workloads saw the biggest gains because the bottleneck was the single interpreter
thread blocking on every query. With 8 workers, queries run concurrently.

---

## Framework Comparison (ntnt v0.4.2)

All frameworks in production mode, same PostgreSQL instance, same 10K-row `world` table.
See each framework's README section for exact commands used.

### plaintext — `GET /plaintext` → `Hello, World!`

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| **ntnt 0.4.2** | **302,141** | 307µs | 283µs | 713µs |
| actix-web 4 | 476,661 | 115µs | 106µs | 223µs |
| gin 1.9 | 406,060 | 186µs | 116µs | 0.88ms |
| fastapi 0.109 | 173,783 | 532µs | 499µs | 1.44ms |
| hono/bun 4.0 | 118,409 | 843µs | 822µs | 1.16ms |
| ntnt 0.4.1 | 118,208 | 840µs | 830µs | 1.06ms |
| express/ts 4.18 | 18,167 | 5.86ms | 5.15ms | 8.34ms |

### json — `GET /json` → `{"message":"Hello, World!"}`

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| **ntnt 0.4.2** | **295,990** | 314µs | 291µs | 710µs |
| actix-web 4 | 476,342 | 115µs | 107µs | 221µs |
| gin 1.9 | 387,095 | 209µs | — | — |
| fastapi 0.109 | 151,696 | 614µs | 568µs | 1.60ms |
| hono/bun 4.0 | 105,152 | 952µs | 918µs | 1.34ms |
| ntnt 0.4.1 | 108,929 | 920µs | — | — |
| express/ts 4.18 | 17,017 | 6.21ms | 5.51ms | 8.96ms |

### params — `GET /users/{id}` → `{"id":"42"}`

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| **ntnt 0.4.2** | **267,832** | 346µs | 325µs | 766µs |
| actix-web 4 | 469,648 | 117µs | — | — |
| gin 1.9 | 384,301 | 208µs | 121µs | 0.96ms |
| fastapi 0.109 | 130,802 | 713µs | 661µs | 1.90ms |
| hono/bun 4.0 | 101,625 | 980µs | 947µs | 1.40ms |
| ntnt 0.4.1 | 88,926 | 1.12ms | 1.11ms | 1.39ms |
| express/ts 4.18 | 16,788 | 6.52ms | 5.59ms | 9.41ms |

### json-body — `POST /json` with JSON body, echo response

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| **ntnt 0.4.2** | **252,284** | 366µs | 341µs | 822µs |
| actix-web 4 | 447,592 | 124µs | 113µs | 237µs |
| gin 1.9 | 324,507 | 327µs | — | — |
| hono/bun 4.0 | 82,927 | 1.20ms | 1.17ms | 1.64ms |
| ntnt 0.4.1 | 76,398 | 1.30ms | 1.29ms | 1.67ms |
| fastapi 0.109 | 116,140 | 817µs | 749µs | 2.24ms |
| express/ts 4.18 | 11,828 | 8.83ms | 8.00ms | 12.33ms |

### db — `GET /db` → 1 random PostgreSQL query

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| gin 1.9 | 130,190 | 728µs | 651µs | 2.11ms |
| actix-web 4 | 64,003 | 1.55ms | 1.53ms | 2.08ms |
| hono/bun 4.0 | 32,399 | 3.09ms | 2.98ms | 5.07ms |
| fastapi 0.109 | 36,859 | 2.73ms | 2.59ms | 6.10ms |
| **ntnt 0.4.2** | **37,818** | 2.64ms | 2.60ms | 3.13ms |
| express/ts 4.18 | 11,817 | 8.55ms | 8.41ms | 13.17ms |
| ntnt 0.4.1 | 8,371 | 11.94ms | 11.65ms | 14.93ms |

ntnt 0.4.2 is now on par with FastAPI for single-query throughput.

### queries — `GET /queries?count=20` → 20 parallel PostgreSQL queries

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| gin 1.9 | 9,296 | 10.75ms | 10.62ms | 14.04ms |
| fastapi 0.109 | 5,818 | 17.27ms | — | — |
| hono/bun 4.0 | 2,789 | 35.80ms | 34.88ms | 45.08ms |
| **ntnt 0.4.2** | **2,349** | 42.46ms | 41.70ms | 52.25ms |
| express/ts 4.18 | 2,419 | 41.27ms | 39.92ms | 51.79ms |
| actix-web 4 | 3,916 | 25.50ms | — | — |
| ntnt 0.4.1 | 457 | 216.90ms | 216.54ms | 243.90ms |

ntnt 0.4.2 is now in the same tier as Express for multi-query workloads (5.1× improvement over 0.4.1).

### template — `GET /template` → 10 DB queries + HTML render

| Framework | Req/sec | Avg Latency | p50 | p99 |
|-----------|--------:|-------------|-----|-----|
| gin 1.9 | 18,014 | 5.54ms | 5.47ms | 7.29ms |
| actix-web 4 | 7,696 | 12.98ms | 12.90ms | 15.08ms |
| fastapi 0.109 | 10,431 | 9.68ms | 9.32ms | 20.45ms |
| hono/bun 4.0 | 5,171 | 19.32ms | — | — |
| **ntnt 0.4.2** | **4,614** | 21.64ms | 21.33ms | 25.53ms |
| express/ts 4.18 | 4,112 | 24.31ms | 23.58ms | 31.08ms |
| ntnt 0.4.1 | 899 | 110.82ms | 110.18ms | 128.21ms |

ntnt 0.4.2 is now faster than Express for template-heavy workloads.

---

## Redis KV — v0.4.1 → v0.4.2

Same worker pool improvement applies to Redis KV operations. Each worker gets its own
Redis connection, eliminating the single-connection serialization bottleneck.

Benchmark: 1000 pre-seeded keys, random read/write per request, same wrk config.

| Benchmark | v0.4.1 | v0.4.2 | Improvement | p50 (v0.4.2) | p99 (v0.4.2) |
|-----------|-------:|-------:|-------------|-------------|-------------|
| Redis read | 21,403 | **66,963** | **3.1×** 🔥 | 1.48ms | 1.70ms |
| Redis write | 20,784 | **62,319** | **3.0×** 🔥 | 1.59ms | 1.87ms |
| Redis mixed (read+write) | 11,605 | **34,309** | **3.0×** 🔥 | 2.88ms | 3.34ms |

v0.4.1 latencies were 3-4× higher (p50: 4.6ms read, 8.5ms mixed) due to single-thread queueing.

---

## Developer Experience

Same benchmark implemented in each framework. Lines of code comparison:

| Framework | Lines of Code | Dependencies | Notes |
|-----------|:------------:|:------------:|-------|
| **ntnt** | **99** | **0** | Single binary, zero imports from package manager |
| fastapi | 99 | 3 | uvicorn + asyncpg + fastapi |
| hono/bun | 92 | 2 | Bun runtime built-in |
| express/ts | 90 | 2 | +devDependencies for TypeScript |
| gin | 118 | 2 | Go modules |
| actix-web | 144 | 13 | Cargo.toml dependencies |

---

## How to Reproduce

### Prerequisites

```bash
# PostgreSQL with the benchmark database
# See setup-db.sql for schema and seed data

# Runtime versions used:
# ntnt 0.4.2
# Python 3.12.3 + pip
# Node v22.22.0 / Bun 1.3.10
# Go 1.23.6
# Rust/Cargo 1.94.0
```

### Run everything

```bash
git clone https://github.com/ntntlang/ntnt-benchmarks
cd ntnt-benchmarks
export DATABASE_URL="postgres://user:pass@localhost/benchmarks"
bash benchmark.sh
```

### Run a single framework

```bash
bash benchmark.sh --frameworks ntnt --benchmarks "plaintext db"
```

Results are saved to `results/` as raw wrk output files and a summary markdown.

---

## Raw Data

All raw `wrk` output is in `results/` — 3 runs per benchmark per framework.  
v0.4.1 results: `results/20260312-100031-summary.md`  
v0.4.2 results: `results/v042/`

---

*Benchmarked 2026-03-12 on dedicated server (16 CPUs, 59 GiB RAM)*  
*ntnt: https://ntnt-lang.org · Repo: https://github.com/ntntlang/ntnt*
