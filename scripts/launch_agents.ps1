<#
.SYNOPSIS
    MarketPulse AI — Agent Launcher (Windows PowerShell)
    Starts Orchestrator, Coder Worker, and Validator as separate processes.

.DESCRIPTION
    Modes:
      --manual   (default) All agents run with --dry-run, no commits, no LLM calls.
      --auto     Agents run autonomously: LLM-enabled, auto_approve, commits allowed.

    Before running:
      1. Set your API key:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
      2. Install deps:      pip install flask pytest mypy ruff anthropic
      3. Run:               .\launch_agents.ps1              # dry-run (safe)
                            .\launch_agents.ps1 --auto       # autonomous

    To stop all agents:
      Get-Process -Name python | Where-Object { $_.CommandLine -match 'marketpulse' } | Stop-Process

.NOTES
    Security:
    - API keys are NEVER logged. Only "present" or "missing" is recorded.
    - --dangerously-skip-permissions is NEVER used.
    - Default mode is --manual (dry-run). Autonomous requires explicit --auto flag.
#>

param(
    [switch]$Auto,
    [string]$TaskSpec = "marketpulse-orchestrator\task_store\task_example.json",
    [string]$RepoPath = ".",
    [string]$BaseRef = "main",
    [string]$AuthFile = "auth\authorization.json"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# ── Resolve mode ──────────────────────────────────────────────────────
$Mode = if ($Auto) { "auto" } else { "manual" }
$DryRunFlag = if ($Auto) { "" } else { "--dry-run" }
$NoLlmFlag = if ($Auto) { "" } else { "--no-llm" }
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " MarketPulse AI — Agent Launcher" -ForegroundColor Cyan
Write-Host " Mode: $Mode" -ForegroundColor $(if ($Auto) { "Yellow" } else { "Green" })
Write-Host " Time: $Timestamp" -ForegroundColor Gray
Write-Host "============================================" -ForegroundColor Cyan

# ── Security: Check API key (never log value) ────────────────────────
$ApiKeyStatus = if ($env:ANTHROPIC_API_KEY) { "present" } else { "missing" }
Write-Host "[security] ANTHROPIC_API_KEY: $ApiKeyStatus" -ForegroundColor $(if ($ApiKeyStatus -eq "present") { "Green" } else { "Red" })

if ($Auto -and $ApiKeyStatus -eq "missing") {
    Write-Host "[ERROR] --auto mode requires ANTHROPIC_API_KEY. Set it:" -ForegroundColor Red
    Write-Host '  $env:ANTHROPIC_API_KEY = "sk-ant-..."' -ForegroundColor Yellow
    exit 1
}

# ── Verify authorization file ─────────────────────────────────────────
if (-not (Test-Path $AuthFile)) {
    Write-Host "[ERROR] Authorization file not found: $AuthFile" -ForegroundColor Red
    Write-Host "  Generate with: Copy auth/authorization.json.example -> auth/authorization.json" -ForegroundColor Yellow
    exit 1
}
$AuthContent = Get-Content $AuthFile -Raw | ConvertFrom-Json
Write-Host "[auth] Level: $($AuthContent.level), max_files: $($AuthContent.max_files_changed), max_loc: $($AuthContent.max_change_loc)" -ForegroundColor Gray

# ── Create log and artifact dirs ──────────────────────────────────────
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null

$LogOrch = "logs\orchestrator.log"
$LogCoder = "logs\coder_worker.log"
$LogValidator = "logs\validator.log"

# ── Warn in auto mode ────────────────────────────────────────────────
if ($Auto) {
    Write-Host ""
    Write-Host "[WARNING] AUTONOMOUS MODE — agents will call Claude API and commit to repo." -ForegroundColor Yellow
    Write-Host "  Authorization: $AuthFile" -ForegroundColor Yellow
    Write-Host "  Press Ctrl+C within 5 seconds to abort..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

# ── Start Orchestrator (health endpoint) ──────────────────────────────
Write-Host ""
Write-Host "[1/3] Starting Orchestrator..." -ForegroundColor Cyan

# Orchestrator is a lightweight Flask app serving /health
# For MVP: inline health server
$OrchCmd = @"
python -c "
from flask import Flask, jsonify
import json, os
app = Flask('orchestrator')

@app.route('/health')
def health():
    api_key = 'present' if os.environ.get('ANTHROPIC_API_KEY') else 'missing'
    return jsonify({'status': 'ok', 'mode': '$Mode', 'api_key': api_key})

@app.route('/task', methods=['GET'])
def task():
    with open('$($TaskSpec -replace '\\','/')') as f:
        return jsonify(json.load(f))

print('Orchestrator starting on :5050...')
app.run(host='0.0.0.0', port=5050, debug=False)
"
"@

$ProcOrch = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $OrchCmd `
    -RedirectStandardOutput $LogOrch -PassThru -WindowStyle Normal
Write-Host "  PID: $($ProcOrch.Id) | Log: $LogOrch" -ForegroundColor Gray

# ── Start Coder Worker ────────────────────────────────────────────────
Write-Host "[2/3] Starting Coder Worker ($Mode)..." -ForegroundColor Cyan

$CoderArgs = "python marketpulse-orchestrator\workers\coder_worker.py --task $TaskSpec --repo $RepoPath --base $BaseRef"
if ($DryRunFlag) { $CoderArgs += " $DryRunFlag" }
if ($NoLlmFlag) { $CoderArgs += " $NoLlmFlag" }

$ProcCoder = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $CoderArgs `
    -RedirectStandardOutput $LogCoder -PassThru -WindowStyle Normal
Write-Host "  PID: $($ProcCoder.Id) | Log: $LogCoder | Flags: $DryRunFlag $NoLlmFlag" -ForegroundColor Gray

# ── Start Validator ───────────────────────────────────────────────────
Write-Host "[3/3] Starting Validator..." -ForegroundColor Cyan

$ValidatorArgs = "python marketpulse-orchestrator\validator.py --task-spec $TaskSpec --repo $RepoPath --base $BaseRef"

$ProcVal = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $ValidatorArgs `
    -RedirectStandardOutput $LogValidator -PassThru -WindowStyle Normal
Write-Host "  PID: $($ProcVal.Id) | Log: $LogValidator" -ForegroundColor Gray

# ── Write audit artifact ──────────────────────────────────────────────
$Artifact = @{
    timestamp      = $Timestamp
    mode           = $Mode
    api_key_status = $ApiKeyStatus
    authorization  = @{
        level              = $AuthContent.level
        max_files_changed  = $AuthContent.max_files_changed
        max_change_loc     = $AuthContent.max_change_loc
        deploy_allowed     = $AuthContent.deploy_allowed
    }
    processes      = @(
        @{ name = "orchestrator"; pid = $ProcOrch.Id; log = $LogOrch }
        @{ name = "coder_worker"; pid = $ProcCoder.Id; log = $LogCoder }
        @{ name = "validator";    pid = $ProcVal.Id;   log = $LogValidator }
    )
    task_spec      = $TaskSpec
    repo_path      = (Resolve-Path $RepoPath).Path
    base_ref       = $BaseRef
} | ConvertTo-Json -Depth 4

$ArtifactPath = "artifacts\run-$Timestamp.json"
$Artifact | Out-File -FilePath $ArtifactPath -Encoding UTF8
Write-Host ""
Write-Host "[audit] Artifact: $ArtifactPath" -ForegroundColor Gray

# ── Health check (30s timeout) ────────────────────────────────────────
Write-Host ""
Write-Host "[health] Waiting for Orchestrator /health..." -ForegroundColor Cyan
$HealthOk = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:5050/health" -TimeoutSec 2
        if ($resp.status -eq "ok") {
            Write-Host "[health] Orchestrator OK: mode=$($resp.mode), api_key=$($resp.api_key)" -ForegroundColor Green
            $HealthOk = $true
            break
        }
    } catch {
        Write-Host "  ... waiting ($($i * 3)s)" -ForegroundColor Gray
    }
}
if (-not $HealthOk) {
    Write-Host "[health] Orchestrator did not respond within 30s. Check $LogOrch" -ForegroundColor Red
}

# ── Check worker logs ─────────────────────────────────────────────────
Write-Host ""
Write-Host "[status] Checking worker output..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
if (Test-Path $LogCoder) {
    $CoderOut = Get-Content $LogCoder -Tail 5 -ErrorAction SilentlyContinue
    Write-Host "[coder] Last lines:" -ForegroundColor Gray
    $CoderOut | ForEach-Object { Write-Host "  $_" }
}
if (Test-Path $LogValidator) {
    $ValOut = Get-Content $LogValidator -Tail 5 -ErrorAction SilentlyContinue
    Write-Host "[validator] Last lines:" -ForegroundColor Gray
    $ValOut | ForEach-Object { Write-Host "  $_" }
}

# ── Summary ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " All agents launched. PIDs:" -ForegroundColor Cyan
Write-Host "   Orchestrator : $($ProcOrch.Id)" -ForegroundColor White
Write-Host "   Coder Worker : $($ProcCoder.Id)" -ForegroundColor White
Write-Host "   Validator    : $($ProcVal.Id)" -ForegroundColor White
Write-Host ""
Write-Host " To stop all:" -ForegroundColor Yellow
Write-Host '   Stop-Process -Id $($ProcOrch.Id),$($ProcCoder.Id),$($ProcVal.Id)' -ForegroundColor Yellow
Write-Host " Or:" -ForegroundColor Yellow
Write-Host '   Get-Process python | Stop-Process' -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
