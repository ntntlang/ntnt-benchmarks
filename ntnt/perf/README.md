# ntnt internal performance fixtures

These fixtures support DD-061-style before/after measurements for ntnt runtime and interpreter work. They live in this benchmark repo rather than the language core repo so opt-in benchmark tooling stays with the benchmark lab instead of becoming a barnacle on `ntnt` itself.

## Quick run

```bash
python3 scripts/run-ntnt-benchmarks.py --quick
```

By default the harness looks for a sibling `../ntnt` source checkout, builds it with `cargo build --profile dev-release`, starts `ntnt/perf/server.tnt` on `127.0.0.1:18080`, runs the HTTP routes with `wrk` when available or a sequential `urllib` fallback otherwise, runs the CLI compute fixture, and writes JSON/Markdown results under `results/ntnt-internal/`.

You can pin the ntnt binary or source checkout explicitly:

```bash
NTNT_BIN=/path/to/ntnt python3 scripts/run-ntnt-benchmarks.py --quick
NTNT_REPO=/path/to/ntnt python3 scripts/run-ntnt-benchmarks.py --duration 10s --runs 3
```

Durations use `s` or `m` suffixes. Bare numbers are normalized to seconds for wrk compatibility; `ms` is rejected so wrk and the fallback runner do not measure different windows while pretending everything is fine. Very benchmark of them.

## Fuller local run

```bash
python3 scripts/run-ntnt-benchmarks.py --duration 10s --runs 3 --connections 32 --threads 4
```

Use the same command on `main` and on the performance branch, then compare the generated Markdown summaries.

## Optional PostgreSQL routes

DB routes are skipped unless both of these are true:

- `DATABASE_URL` is set
- `--include-db` is passed

Example:

```bash
DATABASE_URL=postgres://ntnt:***@localhost/benchmarks \
  python3 scripts/run-ntnt-benchmarks.py --quick --include-db
```

The DB fixtures use simple `SELECT` queries so they do not require schema setup. They intentionally measure the current full connect-query-close request path rather than pooled query-only latency. Keep DB numbers separate from the default HTTP/template/interpreter results.

## Benchmarked routes

- `/` — plaintext response
- `/json` — small JSON response
- `/param/{id}` — route params and map reads
- `/compute` — interpreter loop inside an HTTP request
- `/template/layout` — external template render with layout, partial, and loop
- `/template/rows` — template-heavy 100-row render
- `/db/single` — optional single PostgreSQL query
- `/db/multi` — optional small multi-query PostgreSQL handler
