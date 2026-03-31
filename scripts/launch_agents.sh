#!/usr/bin/env bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════════════
# MarketPulse AI — Agent Launcher (Linux/macOS)
#
# Modes:
#   --manual   (default) All agents run with --dry-run, no commits, no LLM.
#   --auto     Agents run autonomously: LLM-enabled, auto_approve, commits.
#   --use-tmux Use tmux instead of background processes.
#
# Before running:
#   1. export ANTHROPIC_API_KEY="sk-ant-..."
#   2. pip install flask pytest mypy ruff anthropic
#   3. ./launch_agents.sh              # dry-run (safe)
#      ./launch_agents.sh --auto       # autonomous
#
# To stop all agents:
#   kill $(cat artifacts/run-*.json | jq -r '.processes[].pid') 2>/dev/null
#   # or: pkill -f 'coder_worker\|validator\|orchestrator'
#
# Security:
#   - API keys NEVER logged. Only "present" or "missing".
#   - --dangerously-skip-permissions NEVER used.
#   - Default mode: --manual (dry-run).
# ══════════════════════════════════════════════════════════════════════

# ── Parse args ────────────────────────────────────────────────────────
MODE="manual"
USE_TMUX=false
TASK_SPEC="marketpulse-orchestrator/task_store/task_example.json"
REPO_PATH="."
BASE_REF="main"
AUTH_FILE="auth/authorization.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto)     MODE="auto"; shift ;;
        --manual)   MODE="manual"; shift ;;
        --use-tmux) USE_TMUX=true; shift ;;
        --task)     TASK_SPEC="$2"; shift 2 ;;
        --repo)     REPO_PATH="$2"; shift 2 ;;
        --base)     BASE_REF="$2"; shift 2 ;;
        --auth)     AUTH_FILE="$2"; shift 2 ;;
        *)          echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Resolve repo root ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

echo "============================================"
echo " MarketPulse AI — Agent Launcher"
echo " Mode: $MODE"
echo " Time: $TIMESTAMP"
echo "============================================"

# ── Security: check API key (never log value) ────────────────────────
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    API_KEY_STATUS="present"
    echo "[security] ANTHROPIC_API_KEY: present"
else
    API_KEY_STATUS="missing"
    echo "[security] ANTHROPIC_API_KEY: missing"
fi

if [ "$MODE" = "auto" ] && [ "$API_KEY_STATUS" = "missing" ]; then
    echo "[ERROR] --auto mode requires ANTHROPIC_API_KEY. Set it:"
    echo '  export ANTHROPIC_API_KEY="sk-ant-..."'
    exit 1
fi

# ── Verify authorization file ─────────────────────────────────────────
if [ ! -f "$AUTH_FILE" ]; then
    echo "[ERROR] Authorization file not found: $AUTH_FILE"
    exit 1
fi
AUTH_LEVEL=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['level'])" 2>/dev/null || echo "unknown")
echo "[auth] Level: $AUTH_LEVEL"

# ── Create dirs ───────────────────────────────────────────────────────
mkdir -p logs artifacts

LOG_ORCH="logs/orchestrator.log"
LOG_CODER="logs/coder_worker.log"
LOG_VALIDATOR="logs/validator.log"

# ── Build flags ───────────────────────────────────────────────────────
DRY_RUN_FLAG=""
NO_LLM_FLAG=""
if [ "$MODE" = "manual" ]; then
    DRY_RUN_FLAG="--dry-run"
    NO_LLM_FLAG="--no-llm"
fi

# ── Warn in auto mode ────────────────────────────────────────────────
if [ "$MODE" = "auto" ]; then
    echo ""
    echo "[WARNING] AUTONOMOUS MODE — agents will call Claude API and commit."
    echo "  Press Ctrl+C within 5 seconds to abort..."
    sleep 5
fi

# ── Helper: launch process ────────────────────────────────────────────
launch() {
    local name="$1"
    local cmd="$2"
    local logfile="$3"

    if $USE_TMUX; then
        tmux new-window -t marketpulse -n "$name" "$cmd > $logfile 2>&1"
    else
        echo "[start] $name"
        bash -c "$cmd" > "$logfile" 2>&1 &
        echo "  PID: $! | Log: $logfile"
        eval "PID_${name}=$!"
    fi
}

# ── Start tmux session if needed ──────────────────────────────────────
if $USE_TMUX; then
    tmux new-session -d -s marketpulse -n main 2>/dev/null || true
    echo "[tmux] Session 'marketpulse' ready. Attach with: tmux attach -t marketpulse"
fi

# ── 1. Orchestrator ──────────────────────────────────────────────────
echo ""
echo "[1/3] Starting Orchestrator..."
ORCH_CMD="python3 -c \"
from flask import Flask, jsonify
import json, os
app = Flask('orchestrator')

@app.route('/health')
def health():
    api = 'present' if os.environ.get('ANTHROPIC_API_KEY') else 'missing'
    return jsonify({'status': 'ok', 'mode': '$MODE', 'api_key': api})

@app.route('/task')
def task():
    with open('$TASK_SPEC') as f:
        return jsonify(json.load(f))

app.run(host='0.0.0.0', port=5050, debug=False)
\""
launch "orchestrator" "$ORCH_CMD" "$LOG_ORCH"

# ── 2. Coder Worker ──────────────────────────────────────────────────
echo "[2/3] Starting Coder Worker ($MODE)..."
CODER_CMD="python3 marketpulse-orchestrator/workers/coder_worker.py --task $TASK_SPEC --repo $REPO_PATH --base $BASE_REF $DRY_RUN_FLAG $NO_LLM_FLAG"
launch "coder" "$CODER_CMD" "$LOG_CODER"

# ── 3. Validator ──────────────────────────────────────────────────────
echo "[3/3] Starting Validator..."
VAL_CMD="python3 marketpulse-orchestrator/validator.py --task-spec $TASK_SPEC --repo $REPO_PATH --base $BASE_REF"
launch "validator" "$VAL_CMD" "$LOG_VALIDATOR"

# ── Write audit artifact ──────────────────────────────────────────────
ARTIFACT="artifacts/run-$TIMESTAMP.json"
cat > "$ARTIFACT" <<AUDIT_EOF
{
  "timestamp": "$TIMESTAMP",
  "mode": "$MODE",
  "api_key_status": "$API_KEY_STATUS",
  "authorization": {
    "level": "$AUTH_LEVEL",
    "file": "$AUTH_FILE"
  },
  "processes": [
    {"name": "orchestrator", "pid": ${PID_orchestrator:-0}, "log": "$LOG_ORCH"},
    {"name": "coder_worker", "pid": ${PID_coder:-0}, "log": "$LOG_CODER"},
    {"name": "validator",    "pid": ${PID_validator:-0}, "log": "$LOG_VALIDATOR"}
  ],
  "task_spec": "$TASK_SPEC",
  "repo_path": "$(realpath "$REPO_PATH")",
  "base_ref": "$BASE_REF"
}
AUDIT_EOF
echo ""
echo "[audit] Artifact: $ARTIFACT"

# ── Health check (30s) ────────────────────────────────────────────────
echo ""
echo "[health] Waiting for Orchestrator /health..."
HEALTH_OK=false
for i in $(seq 1 10); do
    sleep 3
    RESP=$(curl -sf http://localhost:5050/health 2>/dev/null || true)
    if echo "$RESP" | grep -q '"ok"'; then
        echo "[health] Orchestrator OK: $RESP"
        HEALTH_OK=true
        break
    fi
    echo "  ... waiting ($((i * 3))s)"
done
if ! $HEALTH_OK; then
    echo "[health] Orchestrator not responding. Check $LOG_ORCH"
fi

# ── Worker log tail ───────────────────────────────────────────────────
echo ""
echo "[status] Checking worker output (5s)..."
sleep 5
if [ -f "$LOG_CODER" ]; then
    echo "[coder] Last lines:"
    tail -5 "$LOG_CODER" 2>/dev/null | sed 's/^/  /'
fi
if [ -f "$LOG_VALIDATOR" ]; then
    echo "[validator] Last lines:"
    tail -5 "$LOG_VALIDATOR" 2>/dev/null | sed 's/^/  /'
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo " All agents launched."
echo "   Orchestrator : PID ${PID_orchestrator:-N/A}"
echo "   Coder Worker : PID ${PID_coder:-N/A}"
echo "   Validator    : PID ${PID_validator:-N/A}"
echo ""
echo " To stop all:"
echo "   kill ${PID_orchestrator:-0} ${PID_coder:-0} ${PID_validator:-0}"
echo " Or:"
echo "   pkill -f 'coder_worker|validator|orchestrator'"
echo "============================================"
