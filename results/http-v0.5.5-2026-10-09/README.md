# NTNT 0.5.5 HTTP benchmark run — October 9, 2026

Use [validated-summary.md](validated-summary.md) and [validated-results.json](validated-results.json). The original [summary.md](summary.md) and [results.json](results.json) are retained unchanged and contain a known pre-fix parser error in the memory-soak results. They are not the authoritative publication summary.

## What ran

Nine framework fixtures, seven workloads. Every cell has three 10-second measured runs after a 3-second warmup. Client settings: four wrk threads, 100 connections, loopback HTTP. Server/client launch commands use taskset on logical CPUs 4–7. NTNT and Actix have four HTTP workers; FastAPI/Rails/Django use four server processes, Gin uses GOMAXPROCS=4, and Node/Bun fixtures remain single-process. This is a shared AMD Ryzen 7 H 255 host, not an isolated benchmark machine.

Database workloads use a new, owned PostgreSQL 16 container, capped at one CPU and 512 MiB. The 10,000-row seed is included. No production database or Redis was used. Pool sizes and connection reuse differ by fixture; the template route includes ten sequential database queries and is not a pure template-engine benchmark. The JSON-body payload is 74 bytes.

## Validation

Offline revalidation checked 63 matrix cells, 261 raw wrk files, 810 response-body samples and 1,049 memory samples. It exited 0 with no invalid cells or soaks. Status/socket counters must be clean; body samples must match the expected output and exact database seed. Body sampling happens before/after timed traffic, not on every timed response.

All seven NTNT cells have `(max-min)/median` spread below 10%. Ten competitor cells exceed it. Unstable observations are flagged, not converted into reliable rankings.

## Finite memory observations

Each framework received 120 seconds of sustained JSON-body traffic. All nine passed the stated bounded-PSS criterion. NTNT served 8,524,125 requests at 70,989.27 req/s, with 27,879 KiB peak server-session PSS and 9 KiB loaded-window PSS growth. The growth criterion is last-quarter minus second-quarter median PSS <= max(32 MiB, 20%). A two-minute trace is not proof of absence of leaks or evidence for every application workload.

## Corrections and provenance

- wrk prints `requests in 2.00m` for the soaks. The original seconds-only parser lost their request counts and marked those soaks invalid. The parser is corrected and regression-tested. Revalidation rereads immutable traffic/body/seed/memory files, verifies their recorded hashes, and writes separate derived outputs; it does not generate replacement traffic or overwrite the original report.
- `preparation.*.cpu_affinity` in the original report was sampled immediately after Popen and could race taskset. Treat it as an unreliable early snapshot, not the running server's measured mask. The exact taskset launch commands retain the requested CPU set. Future runs sample affinity after readiness. No original metadata is silently repaired.
- Measurement-time fixture revision: `43920a6343a190da8f08f5af8190eb1e76ac4857`. Parser/readiness/reporting corrections were made afterward; fixture workload semantics were not rewritten for aggregation. Original source hashes and runtime/dependency versions remain in results.json.
- The official [NTNT v0.5.5 Linux x64 release](https://github.com/ntntlang/ntnt/releases/tag/v0.5.5) was downloaded and checksum-verified. Binary SHA256: `797f47ce6e976e3b2d2242d713d0e688d399b48b554a8bf47f21359526755160`. Archive SHA256: `4cbf5f2ee889b0fda3929fc83e89783fa37c538ccc1f9564d9365b82f9a7f7ec`.
- The standalone release-provenance file created during an earlier interrupted step is excluded from publication; existing verification output and recorded binary identity are used here.

Do not compare these numbers as percentages against the March 0.4.2 run: hardware allocation, process models, workloads and database constraints differ. This is not production-capacity evidence.

## Reproduce

```bash
NTNT_BIN=/path/to/checksum-verified/ntnt-0.5.5 ./benchmark.sh \
  --isolated-db --db-subnet 10.250.55.0/28 --cpus 4-7 --workers 4 \
  --port-base 33300 --duration 10 --runs 3 --warmup 3 \
  --stability-seconds 120 --output results/http-v055-new-run
```

Choose unused local ports, a nonoverlapping subnet and a CPU subset appropriate for your machine. The runner prepares fixtures by default; add --skip-prepare only after preparing their dependencies. Pin the recorded runtime/dependency versions when reproducing this historical setup.
