#!/usr/bin/env python3
"""Background-job throughput benchmarks: ntnt (SQLite, Redis) vs BullMQ and Sidekiq.

Each run enqueues a backlog of identical jobs (each sleeps --work-ms), then
starts P worker processes with C slots each and measures how fast the backlog
drains. Every framework's worker writes one JSON line per completed job to
stderr in the same shape ntnt's job events already use:

    {"event":"job.completed","job_id":"...","timestamp":"<unix nanos>"}

so throughput, duplicates and timing are computed identically for all of them.

Stdlib only. Redis is either a disposable Docker container started by this
script (default) or an existing server via --redis-url.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
JOBS_DIR = REPO / "jobs"
DEFAULT_OUTPUT = REPO / "results" / "jobs" / "runs"
REDIS_IMAGE = "redis:7.4-alpine"
TARGETS = ["ntnt-sqlite", "ntnt-redis", "bullmq", "sidekiq"]


# ---------------------------------------------------------------------------
# Minimal Redis client (RESP2) for FLUSHDB / stats; no third-party deps.
# ---------------------------------------------------------------------------


class Redis:
    def __init__(self, url: str) -> None:
        u = urlparse(url)
        if u.scheme != "redis":
            raise SystemExit(f"only redis:// URLs are supported by the runner (got {u.scheme}://)")
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or 6379
        self.db = int((u.path or "/0").lstrip("/") or 0)
        self.auth = [a for a in (u.username, u.password) if a] if u.password else []

    def call(self, *args: str) -> Any:
        with socket.create_connection((self.host, self.port), timeout=10) as s:
            f = s.makefile("rb")
            prelude = [("AUTH", *self.auth)] if self.auth else []
            for cmd in (*prelude, ("SELECT", str(self.db)), args):
                out = f"*{len(cmd)}\r\n".encode()
                for a in cmd:
                    b = str(a).encode()
                    out += b"$%d\r\n%s\r\n" % (len(b), b)
                s.sendall(out)
                reply = self._read(f)
            return reply

    def _read(self, f: Any) -> Any:
        line = f.readline().rstrip(b"\r\n")
        kind, rest = line[:1], line[1:]
        if kind == b"+":
            return rest.decode()
        if kind == b"-":
            raise RuntimeError(rest.decode())
        if kind == b":":
            return int(rest)
        if kind == b"$":
            n = int(rest)
            if n < 0:
                return None
            data = f.read(n + 2)[:-2]
            return data.decode()
        if kind == b"*":
            return [self._read(f) for _ in range(int(rest))]
        raise RuntimeError(f"bad RESP reply: {line!r}")

    def commandstats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for line in self.call("INFO", "commandstats").splitlines():
            if line.startswith("cmdstat_"):
                name, rest = line[len("cmdstat_"):].split(":", 1)
                calls = dict(kv.split("=", 1) for kv in rest.split(","))["calls"]
                stats[name] = int(calls)
        return stats


def wait_for_redis(url: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    while True:
        try:
            if Redis(url).call("PING") == "PONG":
                return
        except OSError:
            pass
        if time.time() > deadline:
            raise SystemExit(f"Redis at {url} did not become ready")
        time.sleep(0.2)


# ---------------------------------------------------------------------------
# CPU placement and accounting
# ---------------------------------------------------------------------------


def parse_cpus(spec: str) -> list[int]:
    cpus: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            cpus.extend(range(int(a), int(b) + 1))
        elif part:
            cpus.append(int(part))
    return cpus


def cpu_spec(cpus: list[int]) -> str:
    return ",".join(str(c) for c in cpus)


def host_ticks() -> tuple[int, int]:
    fields = [int(x) for x in open("/proc/stat").readline().split()[1:8]]
    return sum(fields), fields[3] + fields[4]


def proc_ticks(pid: int) -> int:
    try:
        stat = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return int(stat[11]) + int(stat[12])
    except (OSError, IndexError):
        return 0


def tree_ticks(pid: int) -> int:
    """CPU ticks of a process plus its live descendants (bundler/npm wrappers)."""
    total = proc_ticks(pid)
    try:
        kids = open(f"/proc/{pid}/task/{pid}/children").read().split()
    except OSError:
        kids = []
    return total + sum(tree_ticks(int(k)) for k in kids)


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@dataclass
class Target:
    name: str
    backend: str  # "sqlite" | "redis"
    cwd: Path
    produce: list[str]
    work: list[str]  # "{concurrency}" is substituted
    env: dict[str, str] = field(default_factory=dict)
    version: str = ""


def build_target(name: str, args: argparse.Namespace, ntnt_bin: str) -> Target:
    if name.startswith("ntnt-"):
        # One checkout allows one worker process per worker group on a host
        # (control-socket ownership), so each process gets its own group.
        work = [ntnt_bin, "worker", "app.tnt", "--concurrency", "{concurrency}", "--worker-group", "bench-{index}"]
        if args.ntnt_poll_ms is not None:
            work += ["--poll-interval", str(args.ntnt_poll_ms)]
        return Target(
            name=name,
            backend=name.split("-", 1)[1],
            cwd=JOBS_DIR / "ntnt",
            produce=[ntnt_bin, "run", "producer.tnt"],
            work=work,
            env={"NTNT_ENV": "production"},
            version=command_output([ntnt_bin, "--version"]),
        )
    if name == "bullmq":
        return Target(
            name=name,
            backend="redis",
            cwd=JOBS_DIR / "bullmq",
            produce=["node", "producer.mjs"],
            work=["node", "worker.mjs"],
            version="bullmq " + json.loads((JOBS_DIR / "bullmq" / "node_modules" / "bullmq" / "package.json").read_text())["version"]
            + ", node " + command_output(["node", "--version"]),
        )
    if name == "sidekiq":
        return Target(
            name=name,
            backend="redis",
            cwd=JOBS_DIR / "sidekiq",
            produce=["bundle", "exec", "ruby", "producer.rb"],
            work=["bundle", "exec", "sidekiq", "-r", "./worker.rb", "-c", "{concurrency}", "-q", "bench"],
            env={"BUNDLE_GEMFILE": str(JOBS_DIR / "sidekiq" / "Gemfile"), "RUBYOPT": "-W0"},
            version=command_output(["bundle", "exec", "ruby", "-e", "require 'sidekiq'; print \"sidekiq #{Sidekiq::VERSION}, ruby #{RUBY_VERSION}\""], cwd=JOBS_DIR / "sidekiq"),
        )
    raise SystemExit(f"unknown target {name}; choose from {', '.join(TARGETS)}")


def command_output(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------


def taskset(cmd: list[str], cpus: list[int] | None) -> list[str]:
    return ["taskset", "-c", cpu_spec(cpus), *cmd] if cpus else cmd


def run_once(
    target: Target,
    processes: int,
    concurrency: int,
    args: argparse.Namespace,
    redis_url: str | None,
    redis_pid: int | None,
    worker_cpus: list[int] | None,
    run_dir: Path,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, **target.env)
    env["BENCH_JOBS"] = str(args.jobs)
    env["BENCH_WORK_MS"] = str(args.work_ms)
    env["BENCH_CONCURRENCY"] = str(concurrency)
    sqlite_dir = None
    if target.backend == "sqlite":
        sqlite_dir = Path(tempfile.mkdtemp(prefix="ntnt-jobs-bench-"))
        env["JOBS_STORE"] = f"sqlite:{sqlite_dir / 'jobs.db'}"
    else:
        assert redis_url
        env["JOBS_STORE"] = redis_url
        env["REDIS_URL"] = redis_url
        Redis(redis_url).call("FLUSHDB")

    # 1. Enqueue the backlog.
    t0 = time.perf_counter()
    produced = subprocess.run(
        taskset(target.produce, worker_cpus), cwd=target.cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=args.run_timeout,
    )
    enqueue_s = time.perf_counter() - t0
    if produced.returncode != 0:
        raise SystemExit(f"{target.name} producer failed:\n{produced.stderr[-2000:]}")

    # 2. Drain it.
    redis = Redis(redis_url) if redis_url else None
    if redis:
        redis.call("CONFIG", "RESETSTAT")
    def work(index: int) -> list[str]:
        return [a.replace("{concurrency}", str(concurrency)).replace("{index}", str(index)) for a in target.work]

    logs = [open(run_dir / f"worker-{i}.err", "wb") for i in range(processes)]
    h1 = host_ticks()
    r1 = proc_ticks(redis_pid) if redis_pid else 0
    started = time.time()
    procs = [
        subprocess.Popen(taskset(work(i), worker_cpus), cwd=target.cwd, env=env,
                         stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        for i, log in enumerate(logs)
    ]
    readers = [LogReader(run_dir / f"worker-{i}.err") for i in range(processes)]
    completions: list[tuple[int, str]] = []
    deadline = time.time() + args.run_timeout
    worker_ticks = 0
    timed_out = False
    while True:
        time.sleep(0.2)
        for r in readers:
            completions.extend(r.poll())
        if len({i for _, i in completions}) >= args.jobs:
            break
        if time.time() > deadline:
            timed_out = True
            break
        if all(p.poll() is not None for p in procs):
            break
    drain_wall = time.time() - started
    exited_early = [i for i, p in enumerate(procs) if p.poll() is not None]
    worker_ticks = sum(tree_ticks(p.pid) for p in procs)
    h2 = host_ticks()
    r2 = proc_ticks(redis_pid) if redis_pid else 0
    commands = redis.commandstats() if redis else {}
    for p in procs:
        stop(p)
    for log in logs:
        log.close()
    for r in readers:
        completions.extend(r.poll())
    deferrals = sum(r.deferrals for r in readers)
    if sqlite_dir:
        shutil.rmtree(sqlite_dir, ignore_errors=True)

    per_process = [r.completed for r in readers]
    if exited_early:
        tail = (run_dir / f"worker-{exited_early[0]}.err").read_text(errors="replace")[-1500:]
        raise SystemExit(
            f"{target.name} {processes}x{concurrency}: worker process(es) {exited_early} exited "
            f"before the backlog drained; the result would be invalid.\n{tail}"
        )

    hz = os.sysconf("SC_CLK_TCK")
    ts = sorted(t for t, _ in completions)
    ids = [i for _, i in completions]
    measured = [k for k in commands if k not in {"info", "config", "select", "ping", "flushdb", "client", "hello"}]
    return {
        "processes": processes,
        "concurrency": concurrency,
        "jobs": args.jobs,
        "completed": len(completions),
        "unique_completed": len(set(ids)),
        "timed_out": timed_out,
        "steady_jobs_per_s": steady_rate(ts),
        "drain_s": round((ts[-1] - ts[0]) / 1e9, 3) if len(ts) > 1 else None,
        "first_completion_s": round(ts[0] / 1e9 - started, 3) if ts else None,
        "enqueue_s": round(enqueue_s, 3),
        "redis_commands_per_job": round(sum(commands[k] for k in measured) / max(len(completions), 1), 1) if commands else None,
        "redis_cores": round((r2 - r1) / hz / drain_wall, 2) if redis_pid else None,
        "worker_cores": round(worker_ticks / hz / drain_wall, 2),
        "host_busy_pct": round(100 * (1 - (h2[1] - h1[1]) / max(h2[0] - h1[0], 1)), 1),
        "claim_deferrals": deferrals,
        "per_process_completed": per_process,
    }


class LogReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.partial = b""
        self.deferrals = 0
        self.completed = 0

    def poll(self) -> list[tuple[int, str]]:
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return []
        self.offset += len(data)
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()
        out = []
        for line in lines:
            if b"claim deferred" in line:
                self.deferrals += 1
            if b'"job.completed"' not in line:
                continue
            try:
                event = json.loads(line)
                out.append((int(event["timestamp"]), str(event["job_id"])))
                self.completed += 1
            except (ValueError, KeyError):
                continue
        return out


def steady_rate(ts: list[int]) -> float | None:
    """Jobs/s over the middle 80% of completions (drops startup and tail)."""
    if len(ts) < 20:
        return None
    lo, hi = len(ts) // 10, len(ts) - len(ts) // 10 - 1
    span = (ts[hi] - ts[lo]) / 1e9
    return round((hi - lo) / span, 1) if span > 0 else None


def stop(p: subprocess.Popen[bytes]) -> None:
    if p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()


# ---------------------------------------------------------------------------
# Redis provisioning
# ---------------------------------------------------------------------------


class DockerRedis:
    def __init__(self, cpus: list[int] | None) -> None:
        self.name = f"ntnt-jobs-bench-redis-{os.getpid()}"
        cmd = ["docker", "run", "-d", "--rm", "--name", self.name]
        if cpus:
            cmd += ["--cpuset-cpus", cpu_spec(cpus)]
        cmd += [REDIS_IMAGE, "redis-server", "--save", "", "--appendonly", "no"]
        subprocess.run(cmd, check=True, capture_output=True)
        ip = command_output(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", self.name])
        self.pid = int(command_output(["docker", "inspect", "-f", "{{.State.Pid}}", self.name]))
        self.url = f"redis://{ip}:6379/0"
        wait_for_redis(self.url)
        self.version = Redis(self.url).call("INFO", "server").split("redis_version:")[1].split()[0]

    def close(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def valid(run: dict[str, Any]) -> bool:
    return not run["timed_out"] and run["unique_completed"] >= run["jobs"]


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    # Incomplete or timed-out runs are kept in the JSON but never scored.
    rates = [r["steady_jobs_per_s"] for r in runs if valid(r) and r["steady_jobs_per_s"]]
    def med(key: str) -> Any:
        vals = [r[key] for r in runs if r.get(key) is not None]
        return round(statistics.median(vals), 2) if vals else None
    return {
        "median_jobs_per_s": round(statistics.median(rates), 1) if rates else None,
        "min_jobs_per_s": min(rates) if rates else None,
        "max_jobs_per_s": max(rates) if rates else None,
        "all_completed": all(valid(r) for r in runs),
        "scored_runs": len(rates),
        "duplicates": sum(r["completed"] - r["unique_completed"] for r in runs),
        "median_drain_s": med("drain_s"),
        "median_enqueue_s": med("enqueue_s"),
        "median_redis_commands_per_job": med("redis_commands_per_job"),
        "median_redis_cores": med("redis_cores"),
        "median_worker_cores": med("worker_cores"),
        "median_host_busy_pct": med("host_busy_pct"),
        "claim_deferrals": sum(r["claim_deferrals"] for r in runs),
    }


def fmt(v: Any) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:,.1f}" if v >= 10 else f"{v:.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def render_markdown(result: dict[str, Any]) -> str:
    m = result["meta"]
    lines = [
        f"# Job throughput benchmark — {m['started_at']}",
        "",
        f"- Host: {m['host']['cpu']} ({m['host']['cpus']} CPUs), {m['host']['os']}",
        f"- Jobs per run: {m['jobs']:,}, each sleeping {m['work_ms']} ms; median of {m['runs']} run(s)",
        f"- Throughput is steady-state: the middle 80% of completions (startup and tail excluded)",
        f"- CPU layout: workers/producers on `{m['cpu_layout']['workers'] or 'any'}`, Redis on `{m['cpu_layout']['redis'] or 'any'}`",
        f"- Redis: {m.get('redis_version') or 'n/a'} ({m.get('redis_source') or 'n/a'})",
    ]
    for t in result["targets"]:
        lines.append(f"- {t['name']}: {t['version']}")
    ntnt = m.get("ntnt_git")
    if ntnt:
        lines.append(f"- ntnt source: {ntnt}")
    lines += ["", "## Throughput (jobs/s, higher is better)", ""]
    configs = sorted({(c["processes"], c["concurrency"]) for t in result["targets"] for c in t["configs"]})
    header = "| Processes × slots | " + " | ".join(t["name"] for t in result["targets"]) + " |"
    lines += [header, "|" + "---|" * (len(result["targets"]) + 1)]
    for p, c in configs:
        row = [f"{p} × {c}"]
        for t in result["targets"]:
            cfg = next((x for x in t["configs"] if (x["processes"], x["concurrency"]) == (p, c)), None)
            s = cfg["summary"] if cfg else None
            cell = fmt(s["median_jobs_per_s"]) if s else "–"
            if s and not s["all_completed"]:
                cell += " ⚠ incomplete"
            row.append(cell)
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Details", ""]
    lines.append("| Target | P × C | jobs/s (min–max) | drain s | enqueue s | Redis cmds/job | Redis cores | worker cores | host busy % | dupes | deferrals |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in result["targets"]:
        for cfg in t["configs"]:
            s = cfg["summary"]
            lines.append(
                f"| {t['name']} | {cfg['processes']} × {cfg['concurrency']} | {fmt(s['median_jobs_per_s'])} ({fmt(s['min_jobs_per_s'])}–{fmt(s['max_jobs_per_s'])}) "
                f"| {fmt(s['median_drain_s'])} | {fmt(s['median_enqueue_s'])} | {fmt(s['median_redis_commands_per_job'])} | {fmt(s['median_redis_cores'])} "
                f"| {fmt(s['median_worker_cores'])} | {fmt(s['median_host_busy_pct'])} | {s['duplicates']} | {s['claim_deferrals']} |"
            )
    lines += [
        "",
        "Ideal scaling for sleep-bound jobs is processes × slots × 1000 / work_ms jobs/s. "
        "`deferrals` counts ntnt `job claim deferred` log lines (a claim that hit storage contention and was retried later). "
        "`enqueue s` includes producer process startup.",
        "",
    ]
    return "\n".join(lines)


def git_describe(path: Path) -> str | None:
    sha = command_output(["git", "-C", str(path), "rev-parse", "--short", "HEAD"])
    if not sha or sha == "unknown":
        return None
    subject = command_output(["git", "-C", str(path), "log", "-1", "--format=%s"])
    return f"{sha} {subject}"


def host_info() -> dict[str, Any]:
    cpu = "unknown"
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {"cpu": cpu, "cpus": os.cpu_count(), "os": f"{platform.system()} {platform.release()}"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--targets", default="ntnt-sqlite,ntnt-redis,bullmq,sidekiq", help=f"Comma list from: {', '.join(TARGETS)}")
    p.add_argument("--processes", type=parse_list, default=[1, 2, 4, 8, 16], help="Worker process counts, e.g. 1,2,4,8,16")
    p.add_argument("--concurrency", type=parse_list, default=[16], help="Slots per worker process, e.g. 16 or 1,16")
    p.add_argument("--jobs", type=int, default=8000, help="Jobs per run")
    p.add_argument("--work-ms", type=int, default=20, help="Sleep per job (0 = no-op job)")
    p.add_argument("--runs", type=int, default=3, help="Runs per configuration (median reported)")
    p.add_argument("--quick", action="store_true", help="Smoke test: 1,4 processes x 4 slots, 400 jobs, 1 run")
    p.add_argument("--ntnt-bin", default=os.environ.get("NTNT_BIN"), help="ntnt binary (default NTNT_BIN, NTNT_REPO/target/release/ntnt, or ntnt on PATH)")
    p.add_argument("--ntnt-repo", default=os.environ.get("NTNT_REPO"), help="ntnt checkout, recorded in results and used to find the binary")
    p.add_argument("--ntnt-poll-ms", type=int, default=None, help="Pass --poll-interval to ntnt workers (default: ntnt's own default)")
    p.add_argument("--redis-url", default=os.environ.get("BENCH_REDIS_URL"), help="Use an existing redis:// server instead of a Docker container (requires --flush-redis-db)")
    p.add_argument("--flush-redis-db", action="store_true", help="Confirm the --redis-url database may be FLUSHDB'd before every run")
    p.add_argument("--cpu-layout", choices=["auto", "none"], default="auto", help="auto: pin Docker Redis to the last 2 CPUs and everything else to the rest")
    p.add_argument("--run-timeout", type=float, default=300.0)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    if args.quick:
        args.processes, args.concurrency, args.jobs, args.runs = [1, 4], [4], 400, 1
    if args.redis_url and not args.flush_redis_db:
        p.error("--redis-url erases that database (FLUSHDB) before every run; use a dedicated "
                "database number and pass --flush-redis-db to confirm")
    return args


def resolve_ntnt(args: argparse.Namespace) -> str:
    if args.ntnt_bin:
        return str(Path(args.ntnt_bin).resolve())
    if args.ntnt_repo:
        for profile in ("release", "dev-release"):
            candidate = Path(args.ntnt_repo) / "target" / profile / "ntnt"
            if candidate.exists():
                return str(candidate.resolve())
    found = shutil.which("ntnt")
    if not found:
        raise SystemExit("no ntnt binary: pass --ntnt-bin or set NTNT_BIN / NTNT_REPO")
    return found


def main() -> None:
    args = parse_args()
    names = [n.strip() for n in args.targets.split(",") if n.strip()]
    ntnt_bin = resolve_ntnt(args) if any(n.startswith("ntnt-") for n in names) else ""
    targets = [build_target(n, args, ntnt_bin) for n in names]
    needs_redis = any(t.backend == "redis" for t in targets)

    cpus = sorted(os.sched_getaffinity(0))
    redis_cpus = worker_cpus = None
    if args.cpu_layout == "auto" and needs_redis and not args.redis_url and len(cpus) >= 8:
        redis_cpus, worker_cpus = cpus[-2:], cpus[:-2]

    docker_redis = None
    redis_url, redis_pid, redis_version, redis_source = args.redis_url, None, None, None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / stamp
    try:
        if needs_redis:
            if redis_url:
                wait_for_redis(redis_url)
                redis_source = "external --redis-url"
                redis_version = Redis(redis_url).call("INFO", "server").split("redis_version:")[1].split()[0]
            else:
                docker_redis = DockerRedis(redis_cpus)
                redis_url, redis_pid = docker_redis.url, docker_redis.pid
                redis_version, redis_source = docker_redis.version, f"disposable Docker {REDIS_IMAGE}, persistence off"

        result: dict[str, Any] = {
            "meta": {
                "started_at": stamp,
                "host": host_info(),
                "jobs": args.jobs,
                "work_ms": args.work_ms,
                "runs": args.runs,
                "cpu_layout": {"workers": cpu_spec(worker_cpus) if worker_cpus else None, "redis": cpu_spec(redis_cpus) if redis_cpus else None},
                "redis_version": redis_version,
                "redis_source": redis_source,
                "ntnt_git": git_describe(Path(args.ntnt_repo)) if args.ntnt_repo else None,
                "ntnt_poll_ms": args.ntnt_poll_ms,
            },
            "targets": [],
        }
        for target in targets:
            entry = {"name": target.name, "backend": target.backend, "version": target.version, "configs": []}
            for c in args.concurrency:
                for p in args.processes:
                    runs = []
                    for i in range(args.runs):
                        run_dir = out_dir / "raw" / f"{target.name}-{p}x{c}-run{i + 1}"
                        r = run_once(target, p, c, args, redis_url if target.backend == "redis" else None,
                                     redis_pid if target.backend == "redis" else None, worker_cpus, run_dir)
                        runs.append(r)
                        print(f"{target.name:12} {p:>2}x{c:<3} run {i + 1}: {fmt(r['steady_jobs_per_s'])} jobs/s, "
                              f"{r['completed']}/{r['jobs']} done, cmds/job {fmt(r['redis_commands_per_job'])}, "
                              f"deferrals {r['claim_deferrals']}", flush=True)
                    entry["configs"].append({"processes": p, "concurrency": c, "runs": runs, "summary": summarize(runs)})
            result["targets"].append(entry)
    finally:
        if docker_redis:
            docker_redis.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(result))
    print(f"\nWrote {out_dir / 'summary.md'}")
    print(f"      {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
