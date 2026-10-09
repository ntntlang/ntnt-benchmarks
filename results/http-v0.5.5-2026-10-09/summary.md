# Validated HTTP benchmark results

Shared live-service host; loopback client, servers and local PostgreSQL contend for the recorded CPU set. Not an isolated capacity test or a percentage comparison to historical NTNT 0.4.2.

Config: {'frameworks': 'ntnt fastapi express gin hono actix fastify rails django', 'benchmarks': 'plaintext json params db queries template json-body', 'duration': 10, 'runs': 3, 'warmup': 3, 'connections': 100, 'threads': 4, 'workers': 4, 'port_base': 33300, 'db_port': 55455, 'cpus': '4-7', 'output': 'results/http-v0.5.5-2026-10-09', 'isolated_db': True, 'pg_image': 'postgres:16', 'db_subnet': '10.250.55.0/28', 'stability_seconds': 120, 'memory_limit_mib': 1024, 'prepare_only': False, 'skip_prepare': True}

Body semantics sampled before warmup and after every run; wrk status/socket counters checked for every warmup and measured run. No per-request body validation overhead in timed wrk traffic.

A median requires every configured run to be error-free and all body samples/warmup to pass. Stability flag: (max-min)/median <= 10%; unstable medians are observations, not rankings.

| Framework | Workload | Status | Median req/s | Min–max req/s | Spread % | Stable |
|---|---|---|---:|---|---:|---|
| ntnt | plaintext | valid | 90775.04 | 85402.69–91369.51 | 6.573194569784814 | True |
| ntnt | json | valid | 88415.57 | 87386.18–90663.84 | 3.7071072436676067 | True |
| ntnt | params | valid | 82272.8 | 77426.26–82918.31 | 6.675413988584323 | True |
| ntnt | db | valid | 21961.83 | 21631.85–22226.5 | 2.7076523222336273 | True |
| ntnt | queries | valid | 1747.64 | 1659.9–1778.07 | 6.76169005058249 | True |
| ntnt | template | valid | 3320.37 | 3308.54–3513.66 | 6.177624782780229 | True |
| ntnt | json-body | valid | 74079.89 | 70105.36–74099.1 | 5.391125715764434 | True |
| fastapi | plaintext | valid | 51771.14 | 45907.11–53160.28 | 14.010064294508481 | False |
| fastapi | json | valid | 48530.61 | 46440.59–48891.73 | 5.050709232791442 | True |
| fastapi | params | valid | 39367.24 | 38801.32–42333.08 | 8.971317267860288 | True |
| fastapi | db | valid | 8961.24 | 8841.05–8969.89 | 1.437747454593339 | True |
| fastapi | queries | valid | 1064.61 | 988.78–1088.83 | 9.397807647871048 | True |
| fastapi | template | valid | 2247.32 | 2241.34–2254.95 | 0.6056102379723258 | True |
| fastapi | json-body | valid | 36006.58 | 35378.85–36337.29 | 2.6618468068891916 | True |
| express | plaintext | valid | 32559.27 | 31068.0–33876.04 | 8.624394834405074 | True |
| express | json | valid | 31048.64 | 30573.42–32370.06 | 5.786533645274005 | True |
| express | params | valid | 29012.4 | 28876.33–29585.7 | 2.445057975210596 | True |
| express | db | valid | 11200.5 | 10960.08–11787.0 | 7.382884692647649 | True |
| express | queries | valid | 541.51 | 504.74–684.35 | 33.16836254178132 | False |
| express | template | valid | 1276.77 | 1270.73–1292.93 | 1.7387626588970644 | True |
| express | json-body | valid | 18133.66 | 16746.57–18455.6 | 9.424628012215951 | True |
| gin | plaintext | valid | 118411.13 | 112969.11–118458.82 | 4.636143578732849 | True |
| gin | json | valid | 129615.28 | 105968.92–130293.23 | 18.76654511721149 | False |
| gin | params | valid | 127238.6 | 123046.84–133649.9 | 8.333210205079274 | True |
| gin | db | valid | 27406.93 | 26939.39–29504.71 | 9.360114394425057 | True |
| gin | queries | valid | 1631.04 | 1580.3–1672.28 | 5.639346674514421 | True |
| gin | template | valid | 3082.97 | 3009.11–3362.36 | 11.458106955306086 | False |
| gin | json-body | valid | 83287.06 | 74847.37–94695.37 | 23.830832784828758 | False |
| hono | plaintext | valid | 88583.14 | 87203.63–88690.06 | 1.6780055437185823 | True |
| hono | json | valid | 79701.14 | 72295.93–80399.43 | 10.167357706552254 | False |
| hono | params | valid | 77117.03 | 76692.08–77420.79 | 0.9449404366324687 | True |
| hono | db | valid | 13674.3 | 13451.67–13692.96 | 1.7645510190649545 | True |
| hono | queries | valid | 770.0 | 720.55–785.4 | 8.422077922077925 | True |
| hono | template | valid | 1537.88 | 1529.26–1549.52 | 1.3173979764350918 | True |
| hono | json-body | valid | 59926.11 | 59449.88–60851.98 | 2.3397146919765124 | True |
| actix | plaintext | valid | 213732.09 | 209308.47–214987.76 | 2.6572004232027155 | True |
| actix | json | valid | 205474.92 | 196020.4–209039.46 | 6.336082281964142 | True |
| actix | params | valid | 204645.03 | 204074.23–206512.91 | 1.191663437905134 | True |
| actix | db | valid | 11575.74 | 10683.88–11703.91 | 8.811790866069908 | True |
| actix | queries | valid | 611.13 | 594.36–615.96 | 3.5344362083353826 | True |
| actix | template | valid | 1209.98 | 1198.65–1235.15 | 3.016578786426222 | True |
| actix | json-body | valid | 186574.81 | 175235.73–186636.04 | 6.11031574948408 | True |
| fastify | plaintext | valid | 64266.65 | 59176.44–64460.83 | 8.222600680135029 | True |
| fastify | json | valid | 56596.8 | 51070.31–59790.83 | 15.40815028411501 | False |
| fastify | params | valid | 60911.15 | 59781.45–61601.67 | 2.988319872469985 | True |
| fastify | db | valid | 17285.05 | 15927.55–17364.91 | 8.315625352544544 | True |
| fastify | queries | valid | 928.56 | 889.31–943.09 | 5.7917635909365135 | True |
| fastify | template | valid | 1901.97 | 1768.77–1909.52 | 7.400221875213594 | True |
| fastify | json-body | valid | 33408.07 | 29998.92–33621.78 | 10.844266071042117 | False |
| rails | plaintext | valid | 8431.1 | 8377.51–8648.69 | 3.2164249030375665 | True |
| rails | json | valid | 7854.49 | 7115.1–8239.08 | 14.31003158702856 | False |
| rails | params | valid | 7873.59 | 7819.64–7976.58 | 1.9932457747990382 | True |
| rails | db | valid | 4362.51 | 4104.61–4722.39 | 14.161113670799622 | False |
| rails | queries | valid | 751.62 | 731.0–751.76 | 2.7620340065458597 | True |
| rails | template | valid | 1384.68 | 1287.54–1417.7 | 9.400005777508166 | True |
| rails | json-body | valid | 7685.17 | 7637.81–7696.9 | 0.7688834469504153 | True |
| django | plaintext | valid | 14156.93 | 13323.48–14282.92 | 6.777175559955446 | True |
| django | json | valid | 13884.45 | 12915.97–13975.63 | 7.631991184382528 | True |
| django | params | valid | 13739.68 | 13720.0–13760.19 | 0.29251045148067867 | True |
| django | db | valid | 243.15 | 242.78–247.84 | 2.081019946535062 | True |
| django | queries | valid | 193.38 | 186.94–196.55 | 4.969490123073748 | True |
| django | template | valid | 213.74 | 208.74–223.97 | 7.12547955459904 | True |
| django | json-body | valid | 13069.17 | 13015.32–13070.1 | 0.4191543915948806 | True |

## Sustained JSON-body memory observations

Server session only, 1s PSS/RSS samples; RSS sums double-count shared pages. Finite duration is not proof of absence of leaks.

| Framework | Valid traffic | Bounded PSS | Growth KiB | Peak PSS KiB | Requests |
|---|---|---|---:|---:|---:|
| ntnt | False | False | 9 | 27879 | 0 |
| fastapi | False | False | -6 | 168639 | 0 |
| express | False | False | -34 | 129205 | 0 |
| gin | False | False | -100 | 34935 | 0 |
| hono | False | False | 44 | 115348 | 0 |
| actix | False | False | -1 | 9217 | 0 |
| fastify | False | False | 13076 | 153168 | 0 |
| rails | False | False | 3024.5 | 383992 | 0 |
| django | False | False | 2 | 121108 | 0 |
