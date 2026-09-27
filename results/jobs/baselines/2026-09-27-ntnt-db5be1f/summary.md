# Job throughput benchmark — 20260927T171125Z

- Host: AMD Ryzen 7 H 255 w/ Radeon 780M Graphics (16 CPUs), Linux 6.8.0-138-generic
- Jobs per run: 4,000, each sleeping 20 ms; median of 3 run(s)
- Throughput is steady-state: the middle 80% of completions (startup and tail excluded)
- CPU layout: workers/producers on `0,1,2,3,4,5,6,7,8,9,10,11,12,13`, Redis on `14,15`
- Redis: 7.4.10 (disposable Docker redis:7.4-alpine, persistence off)
- ntnt-sqlite: ntnt 0.5.5
- ntnt-redis: ntnt 0.5.5
- bullmq: bullmq 6.3.9, node v26.7.0
- sidekiq: sidekiq 8.1.7, ruby 3.2.3
- ntnt source: db5be1f Merge pull request #231 from ntntlang/perf/redis-lease-round-trips

## Throughput (jobs/s, higher is better)

| Processes × slots | ntnt-sqlite | ntnt-redis | bullmq | sidekiq |
|---|---|---|---|---|
| 1 × 16 | 72.9 | 738.1 | 775.1 | 783.1 |
| 2 × 16 | 66.8 | 1,224.8 | 1,545.5 | 1,573.8 |
| 4 × 16 | 57.8 | 2,158.8 | 3,062.4 | 3,141.2 |
| 8 × 16 | 60.4 | 2,803.8 | 6,063.0 | 6,264.9 |
| 16 × 16 | 61.6 | 2,906.8 | 12,064.8 | 11,371.6 |

## Details

| Target | P × C | jobs/s (min–max) | drain s | enqueue s | Redis cmds/job | Redis cores | worker cores | host busy % | dupes | deferrals |
|---|---|---|---|---|---|---|---|---|---|---|
| ntnt-sqlite | 1 × 16 | 72.9 (69.2–74.4) | 56.0 | 15.5 | – | – | 0.12 | 14.6 | 0 | 35 |
| ntnt-sqlite | 2 × 16 | 66.8 (66.1–68.9) | 61.3 | 20.3 | – | – | 0.12 | 9.30 | 0 | 78 |
| ntnt-sqlite | 4 × 16 | 57.8 (49.5–59.2) | 74.8 | 15.6 | – | – | 0.10 | 9.10 | 0 | 180 |
| ntnt-sqlite | 8 × 16 | 60.4 (50.7–60.9) | 64.7 | 15.4 | – | – | 0.13 | 9.50 | 0 | 328 |
| ntnt-sqlite | 16 × 16 | 61.6 (57.8–74.7) | 63.5 | 15.4 | – | – | 0.15 | 9.30 | 0 | 624 |
| ntnt-redis | 1 × 16 | 738.1 (736.4–738.1) | 5.41 | 0.42 | 74.2 | 0.26 | 0.43 | 11.6 | 0 | 0 |
| ntnt-redis | 2 × 16 | 1,224.8 (1,184.7–1,231.2) | 3.27 | 0.42 | 74.5 | 0.42 | 0.73 | 16.9 | 0 | 0 |
| ntnt-redis | 4 × 16 | 2,158.8 (2,145.2–2,196.7) | 1.82 | 0.43 | 74.9 | 0.68 | 1.25 | 20.6 | 0 | 0 |
| ntnt-redis | 8 × 16 | 2,803.8 (2,566.5–2,884.5) | 1.40 | 0.42 | 76.1 | 0.83 | 1.55 | 21.3 | 0 | 0 |
| ntnt-redis | 16 × 16 | 2,906.8 (2,881.7–3,102.9) | 1.40 | 0.41 | 78.9 | 0.88 | 1.85 | 24.6 | 0 | 0 |
| bullmq | 1 × 16 | 775.1 (771.2–775.4) | 5.19 | 0.24 | 23.0 | 0.07 | 0.12 | 12.6 | 0 | 0 |
| bullmq | 2 × 16 | 1,545.5 (1,544.7–1,547.7) | 2.59 | 0.23 | 23.1 | 0.11 | 0.32 | 9.70 | 0 | 0 |
| bullmq | 4 × 16 | 3,062.4 (3,049.6–3,062.5) | 1.31 | 0.24 | 23.2 | 0.17 | 0.79 | 13.3 | 0 | 0 |
| bullmq | 8 × 16 | 6,063.0 (6,055.8–6,083.4) | 0.66 | 0.23 | 23.3 | 0.24 | 2.02 | 24.2 | 0 | 0 |
| bullmq | 16 × 16 | 12,064.8 (11,924.0–12,102.3) | 0.35 | 0.23 | 23.6 | 0.28 | 4.86 | 48.7 | 0 | 0 |
| sidekiq | 1 × 16 | 783.1 (779.1–785.5) | 5.11 | 0.30 | 1.00 | 0.02 | 0.18 | 10.0 | 0 | 0 |
| sidekiq | 2 × 16 | 1,573.8 (1,570.5–1,575.3) | 2.55 | 0.30 | 1.00 | 0.03 | 0.43 | 10.2 | 0 | 0 |
| sidekiq | 4 × 16 | 3,141.2 (3,133.7–3,147.6) | 1.27 | 0.30 | 1.00 | 0.06 | 1.17 | 16.5 | 0 | 0 |
| sidekiq | 8 × 16 | 6,264.9 (6,203.3–6,275.7) | 0.64 | 0.30 | 1.10 | 0.07 | 2.98 | 26.8 | 0 | 0 |
| sidekiq | 16 × 16 | 11,371.6 (11,046.1–11,618.1) | 0.42 | 0.30 | 1.20 | 0.11 | 8.33 | 67.5 | 0 | 0 |

Ideal scaling for sleep-bound jobs is processes × slots × 1000 / work_ms jobs/s. `deferrals` counts ntnt `job claim deferred` log lines (a claim that hit storage contention and was retried later). `enqueue s` includes producer process startup.
