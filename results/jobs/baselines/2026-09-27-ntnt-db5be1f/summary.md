# Job throughput benchmark — 20260927T174254Z

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
| 1 × 16 | 78.7 | 739.9 | 774.4 | 784.3 |
| 2 × 16 | 69.3 | 1,206.0 | 1,544.0 | 1,567.0 |
| 4 × 16 | 58.3 | 2,212.7 | 3,069.1 | 3,142.2 |
| 8 × 16 | 71.5 | 2,879.6 | 6,080.4 | 6,266.8 |
| 16 × 16 | 74.2 | 2,896.8 | 12,018.7 | 11,490.1 |

## Details

| Target | P × C | jobs/s (min–max) | drain s | enqueue s | Redis cmds/job | Redis cores | worker cores | host busy % | dupes | deferrals |
|---|---|---|---|---|---|---|---|---|---|---|
| ntnt-sqlite | 1 × 16 | 78.7 (76.4–79.0) | 52.1 | 15.5 | – | – | 0.13 | 9.50 | 0 | 33 |
| ntnt-sqlite | 2 × 16 | 69.3 (57.1–69.4) | 66.3 | 15.4 | – | – | 0.11 | 9.10 | 0 | 84 |
| ntnt-sqlite | 4 × 16 | 58.3 (57.7–58.7) | 67.6 | 15.5 | – | – | 0.11 | 9.30 | 0 | 168 |
| ntnt-sqlite | 8 × 16 | 71.5 (50.3–71.9) | 64.5 | 15.4 | – | – | 0.13 | 9.40 | 0 | 336 |
| ntnt-sqlite | 16 × 16 | 74.2 (74.0–74.7) | 57.0 | 21.4 | – | – | 0.16 | 9.90 | 0 | 560 |
| ntnt-redis | 1 × 16 | 739.9 (738.0–742.3) | 5.40 | 0.44 | 74.2 | 0.27 | 0.44 | 13.5 | 0 | 0 |
| ntnt-redis | 2 × 16 | 1,206.0 (1,206.0–1,282.0) | 3.27 | 0.40 | 74.5 | 0.42 | 0.73 | 14.6 | 0 | 0 |
| ntnt-redis | 4 × 16 | 2,212.7 (2,195.8–2,291.6) | 1.79 | 0.41 | 74.9 | 0.68 | 1.25 | 19.3 | 0 | 0 |
| ntnt-redis | 8 × 16 | 2,879.6 (2,653.7–3,004.8) | 1.38 | 0.41 | 76.1 | 0.85 | 1.61 | 25.0 | 0 | 0 |
| ntnt-redis | 16 × 16 | 2,896.8 (2,876.9–2,940.8) | 1.42 | 0.42 | 79.1 | 0.89 | 1.82 | 23.1 | 0 | 0 |
| bullmq | 1 × 16 | 774.4 (773.3–775.4) | 5.17 | 0.23 | 23.0 | 0.07 | 0.12 | 8.30 | 0 | 0 |
| bullmq | 2 × 16 | 1,544.0 (1,532.4–1,546.2) | 2.60 | 0.24 | 23.1 | 0.11 | 0.32 | 13.0 | 0 | 0 |
| bullmq | 4 × 16 | 3,069.1 (3,044.2–3,069.2) | 1.30 | 0.23 | 23.2 | 0.16 | 0.79 | 12.9 | 0 | 0 |
| bullmq | 8 × 16 | 6,080.4 (6,054.3–6,081.0) | 0.66 | 0.23 | 23.3 | 0.23 | 2.02 | 21.0 | 0 | 0 |
| bullmq | 16 × 16 | 12,018.7 (11,779.1–12,064.0) | 0.35 | 0.24 | 23.6 | 0.37 | 6.31 | 51.8 | 0 | 0 |
| sidekiq | 1 × 16 | 784.3 (781.2–785.9) | 5.10 | 0.30 | 1.00 | 0.02 | 0.19 | 10.8 | 0 | 0 |
| sidekiq | 2 × 16 | 1,567.0 (1,566.0–1,568.6) | 2.54 | 0.29 | 1.00 | 0.03 | 0.43 | 11.6 | 0 | 0 |
| sidekiq | 4 × 16 | 3,142.2 (3,132.0–3,144.4) | 1.27 | 0.30 | 1.00 | 0.05 | 1.18 | 15.1 | 0 | 0 |
| sidekiq | 8 × 16 | 6,266.8 (6,265.8–6,300.9) | 0.64 | 0.31 | 1.10 | 0.09 | 3.31 | 27.3 | 0 | 0 |
| sidekiq | 16 × 16 | 11,490.1 (10,248.4–11,739.5) | 0.39 | 0.29 | 1.20 | 0.10 | 8.29 | 65.3 | 0 | 0 |

Ideal scaling for sleep-bound jobs is processes × slots × 1000 / work_ms jobs/s. `deferrals` counts ntnt `job claim deferred` log lines (a claim that hit storage contention and was retried later). `enqueue s` includes producer process startup.
