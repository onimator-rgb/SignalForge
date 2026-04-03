#!/usr/bin/env python3
"""
MarketPulse UI/UX Analysis Agent — Session Runner

Launches the UI/UX analysis worker to analyze a frontend repository
and produce a handoff document for the Coder Agent.

Usage:
    # Default: analyze SignalForge with Claude MAX CLI
    python scripts/run_uiux_agent.py

    # Analyze a different repo
    python scripts/run_uiux_agent.py --repo https://github.com/user/repo

    # Use local repo (already cloned)
    python scripts/run_uiux_agent.py --local-repo /path/to/repo

    # Dry run (collect files, don't call LLM)
    python scripts/run_uiux_agent.py --dry-run

    # Use Anthropic API instead of Claude MAX
    python scripts/run_uiux_agent.py --use-api

Output:
    - Full analysis report:  reports/uiux/uiux_analysis_<timestamp>.md
    - Handoff for coder:     reports/uiux/signalforge_uiux_handoff_for_coding_agent.txt
    - Handoff copy:          signalforge_uiux_handoff_for_coding_agent.txt (repo root)
"""

import os
import subprocess
import sys
from pathlib import Path

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WORKER_PATH = REPO_ROOT / "marketpulse-orchestrator" / "workers" / "uiux_worker.py"
PYTHON = sys.executable


def main():
    # Verify worker exists
    if not WORKER_PATH.exists():
        print(f"ERROR: Worker not found at {WORKER_PATH}")
        sys.exit(1)

    # Forward all CLI arguments to the worker
    cmd = [PYTHON, str(WORKER_PATH)] + sys.argv[1:]

    print("=" * 60)
    print("  MarketPulse UI/UX Analysis Agent")
    print("=" * 60)
    print(f"  Worker:  {WORKER_PATH}")
    print(f"  Python:  {PYTHON}")
    print(f"  Args:    {' '.join(sys.argv[1:]) or '(defaults)'}")
    print("=" * 60)
    print()

    # Set working directory to repo root
    env = os.environ.copy()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=1200,  # 20 min max
        )
        sys.exit(result.returncode)

    except subprocess.TimeoutExpired:
        print("\nERROR: Analysis timed out after 20 minutes")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
