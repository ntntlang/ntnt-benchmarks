#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ntnt-benchmarks — HTTP Framework Benchmark Runner
# =============================================================================
# Usage: ./benchmark.sh [--frameworks "ntnt fastapi express gin hono actix"]
#                       [--benchmarks "plaintext json params db queries template json-body"]
#                       [--duration 30] [--connections 100] [--threads 4] [--runs 3]
#                       [--warmup 5] [--output results/]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Defaults
FRAMEWORKS="${FRAMEWORKS:-ntnt fastapi express gin hono actix}"
BENCHMARKS="${BENCHMARKS:-plaintext json params db queries template json-body}"
DURATION=30
CONNECTIONS=100
THREADS=4
RUNS=3
WARMUP=5

# Ports per framework
declare -A PORTS=(
    [ntnt]=3100
    [fastapi]=3101
    [express]=3102
    [gin]=3103
    [hono]=3104
    [actix]=3105
)

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --frameworks) FRAMEWORKS="$2"; shift 2 ;;
        --benchmarks) BENCHMARKS="$2"; shift 2 ;;
        --duration)   DURATION="$2"; shift 2 ;;
        --connections) CONNECTIONS="$2"; shift 2 ;;
        --threads)    THREADS="$2"; shift 2 ;;
        --runs)       RUNS="$2"; shift 2 ;;
        --warmup)     WARMUP="$2"; shift 2 ;;
        --output)     RESULTS_DIR="$2"; shift 2 ;;
        *)            echo "Unknown option: $1"; exit 1 ;;
    esac
done

mkdir -p "$RESULTS_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${BLUE}[bench]${NC} $*"; }
ok()   { echo -e "${GREEN}[  ok ]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn ]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# =============================================================================
# Framework lifecycle
# =============================================================================

start_framework() {
    local fw="$1"
    local port="${PORTS[$fw]}"
    log "Starting $fw on port $port..."

    case $fw in
        ntnt)
            cd "$SCRIPT_DIR/ntnt"
            NTNT_BIN="${NTNT_BIN:-ntnt}"
            NTNT_ENV=production "$NTNT_BIN" run server.tnt &
            ;;
        fastapi)
            cd "$SCRIPT_DIR/fastapi"
            if [ ! -d .venv ]; then
                python3 -m venv .venv
                .venv/bin/pip install -q -r requirements.txt
            fi
            .venv/bin/uvicorn app:app --host 0.0.0.0 --port "$port" --workers "$(nproc)" --log-level error &
            ;;
        express)
            cd "$SCRIPT_DIR/express"
            [ -d node_modules ] || npm install --silent
            [ -d dist ] || npx tsc
            PORT="$port" node dist/app.js &
            ;;
        gin)
            cd "$SCRIPT_DIR/gin"
            export PATH="/usr/local/go/bin:$PATH"
            if [ ! -f gin-bench ]; then
                go build -o gin-bench .
            fi
            ./gin-bench &
            ;;
        hono)
            cd "$SCRIPT_DIR/hono-bun"
            export PATH="$HOME/.bun/bin:$PATH"
            [ -d node_modules ] || bun install --silent
            bun run app.ts &
            ;;
        actix)
            cd "$SCRIPT_DIR/actix"
            export PATH="$HOME/.cargo/bin:$PATH"
            if [ ! -f target/release/actix-bench ]; then
                cargo build --release 2>/dev/null
            fi
            ./target/release/actix-bench 2>&1 &
            ;;
    esac

    local pid=$!
    echo "$pid" > "/tmp/bench-${fw}.pid"

    # Wait for server to be ready
    local retries=30
    while ! curl -sf "http://127.0.0.1:${port}/plaintext" > /dev/null 2>&1; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            err "$fw failed to start on port $port"
            kill "$pid" 2>/dev/null || true
            return 1
        fi
        sleep 1
    done
    ok "$fw is ready (pid $pid)"
}

stop_framework() {
    local fw="$1"
    if [ -f "/tmp/bench-${fw}.pid" ]; then
        local pid=$(cat "/tmp/bench-${fw}.pid")
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        rm -f "/tmp/bench-${fw}.pid"
        ok "Stopped $fw (pid $pid)"
    fi
}

# =============================================================================
# Benchmark endpoints
# =============================================================================

get_url() {
    local bench="$1"
    local port="$2"
    case $bench in
        plaintext)  echo "http://127.0.0.1:${port}/plaintext" ;;
        json)       echo "http://127.0.0.1:${port}/json" ;;
        params)     echo "http://127.0.0.1:${port}/users/42" ;;
        db)         echo "http://127.0.0.1:${port}/db" ;;
        queries)    echo "http://127.0.0.1:${port}/queries?count=20" ;;
        template)   echo "http://127.0.0.1:${port}/template" ;;
        json-body)  echo "POST:http://127.0.0.1:${port}/json" ;;
    esac
}

run_wrk() {
    local url="$1"
    local method="${2:-GET}"
    local output="$3"

    if [[ "$url" == POST:* ]]; then
        url="${url#POST:}"
        wrk -t"$THREADS" -c"$CONNECTIONS" -d"${DURATION}s" --latency \
            -s "$SCRIPT_DIR/post.lua" "$url" > "$output" 2>&1
    else
        wrk -t"$THREADS" -c"$CONNECTIONS" -d"${DURATION}s" --latency \
            "$url" > "$output" 2>&1
    fi
}

# =============================================================================
# Result parsing
# =============================================================================

parse_wrk_output() {
    local file="$1"
    # Extract: requests/sec, avg latency, p50, p75, p90, p99, transfer/sec
    local rps=$(grep "Requests/sec:" "$file" | awk '{print $2}')
    local avg_lat=$(grep "Latency" "$file" | head -1 | awk '{print $2}')
    local p50=$(grep "50%" "$file" | awk '{print $2}')
    local p75=$(grep "75%" "$file" | awk '{print $2}')
    local p90=$(grep "90%" "$file" | awk '{print $2}')
    local p99=$(grep "99%" "$file" | awk '{print $2}')
    local transfer=$(grep "Transfer/sec:" "$file" | awk '{print $2}')
    local errors=$(grep -c "Socket errors\|Non-2xx" "$file" || echo "0")

    echo "${rps:-0}|${avg_lat:-0}|${p50:-0}|${p75:-0}|${p90:-0}|${p99:-0}|${transfer:-0}|${errors}"
}

# =============================================================================
# Main
# =============================================================================

log "=== ntnt-benchmarks ==="
log "Date: $DATE"
log "Frameworks: $FRAMEWORKS"
log "Benchmarks: $BENCHMARKS"
log "Config: ${THREADS}t / ${CONNECTIONS}c / ${DURATION}s / ${RUNS} runs"
log ""

# Create Lua script for POST benchmarks
cat > "$SCRIPT_DIR/post.lua" << 'POSTLUA'
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"message":"Hello, World!","numbers":[1,2,3,4,5],"nested":{"key":"value"}}'
POSTLUA

# JSON results accumulator
RESULTS_JSON="$RESULTS_DIR/${TIMESTAMP}.json"
echo '{"date":"'"$DATE"'","config":{"threads":'$THREADS',"connections":'$CONNECTIONS',"duration":'$DURATION',"runs":'$RUNS'},"results":{}}' > "$RESULTS_JSON"

# Summary table
SUMMARY_FILE="$RESULTS_DIR/${TIMESTAMP}-summary.md"
{
echo "# Benchmark Results — $DATE"
echo ""
echo "**Config:** $THREADS threads, $CONNECTIONS connections, ${DURATION}s duration, $RUNS runs (median)"
echo ""
echo "**System:** $(uname -sr), $(nproc) CPUs, $(free -h | awk '/Mem:/{print $2}') RAM"
echo ""
} > "$SUMMARY_FILE"

for bench in $BENCHMARKS; do
    log "━━━ Benchmark: $bench ━━━"

    {
    echo "## $bench"
    echo ""
    echo "| Framework | Req/sec | Avg Latency | p50 | p99 | Transfer/sec |"
    echo "|-----------|---------|-------------|-----|-----|--------------|"
    } >> "$SUMMARY_FILE"

    for fw in $FRAMEWORKS; do
        port="${PORTS[$fw]}"
        url=$(get_url "$bench" "$port")

        start_framework "$fw" || { warn "Skipping $fw"; continue; }

        # Warmup
        log "  Warming up $fw (${WARMUP}s)..."
        if [[ "$url" == POST:* ]]; then
            wrk -t2 -c10 -d"${WARMUP}s" -s "$SCRIPT_DIR/post.lua" "${url#POST:}" > /dev/null 2>&1
        else
            wrk -t2 -c10 -d"${WARMUP}s" "$url" > /dev/null 2>&1
        fi

        # Run multiple times, keep all
        best_rps=0
        best_file=""
        for run in $(seq 1 "$RUNS"); do
            local_output="$RESULTS_DIR/raw-${fw}-${bench}-run${run}.txt"
            log "  Run $run/$RUNS: $fw / $bench"
            run_wrk "$url" "" "$local_output"

            rps=$(grep "Requests/sec:" "$local_output" | awk '{print $2}' | cut -d. -f1)
            log "    → ${rps} req/sec"

            # Track median (pick middle run by sorting later)
        done

        # Find median run
        median_idx=$(( (RUNS + 1) / 2 ))
        median_file=$(for run in $(seq 1 "$RUNS"); do
            f="$RESULTS_DIR/raw-${fw}-${bench}-run${run}.txt"
            rps=$(grep "Requests/sec:" "$f" | awk '{print $2}')
            echo "$rps $f"
        done | sort -n | sed -n "${median_idx}p" | awk '{print $2}')

        if [ -n "$median_file" ]; then
            result=$(parse_wrk_output "$median_file")
            IFS='|' read -r rps avg_lat p50 p75 p90 p99 transfer errors <<< "$result"
            echo "| $fw | $rps | $avg_lat | $p50 | $p99 | $transfer |" >> "$SUMMARY_FILE"
            ok "  $fw: $rps req/sec (p99: $p99)"
        fi

        stop_framework "$fw"
        sleep 2
    done

    echo "" >> "$SUMMARY_FILE"
done

# Add DX comparison
{
echo "## Developer Experience"
echo ""
echo "| Framework | Lines of Code | Dependencies | Binary/Image Size |"
echo "|-----------|--------------|--------------|-------------------|"

for fw in $FRAMEWORKS; do
    case $fw in
        ntnt)    loc=$(wc -l < "$SCRIPT_DIR/ntnt/server.tnt"); deps=0; size="~15MB (binary)" ;;
        fastapi) loc=$(wc -l < "$SCRIPT_DIR/fastapi/app.py"); deps=$(wc -l < "$SCRIPT_DIR/fastapi/requirements.txt"); size="venv" ;;
        express) loc=$(wc -l < "$SCRIPT_DIR/express/app.ts"); deps=$(jq '.dependencies | length' "$SCRIPT_DIR/express/package.json" 2>/dev/null || echo "?"); size="node_modules" ;;
        gin)     loc=$(wc -l < "$SCRIPT_DIR/gin/main.go"); deps=2; size="~10MB (binary)" ;;
        hono)    loc=$(wc -l < "$SCRIPT_DIR/hono-bun/app.ts"); deps=$(jq '.dependencies | length' "$SCRIPT_DIR/hono-bun/package.json" 2>/dev/null || echo "?"); size="bun" ;;
        actix)   loc=$(wc -l < "$SCRIPT_DIR/actix/src/main.rs"); deps=$(grep -c '^\w' "$SCRIPT_DIR/actix/Cargo.toml" 2>/dev/null || echo "?"); size="~5MB (binary)" ;;
        *)       loc="?"; deps="?"; size="?" ;;
    esac
    echo "| $fw | $loc | $deps | $size |"
done

echo ""
echo "---"
echo ""
echo "*Generated by [ntnt-benchmarks](https://github.com/ntntlang/ntnt-benchmarks)*"
} >> "$SUMMARY_FILE"

log ""
ok "=== Benchmarks complete ==="
ok "Summary: $SUMMARY_FILE"
ok "Raw data: $RESULTS_DIR/raw-*.txt"
ok "JSON: $RESULTS_JSON"
