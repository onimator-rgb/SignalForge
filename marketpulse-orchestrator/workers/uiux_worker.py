#!/usr/bin/env python3
"""
MarketPulse UI/UX Analysis Worker — Agent 4

Clones a target repository, collects all frontend source files,
sends them to Claude for expert UI/UX analysis, and produces:
  1. A structured JSON analysis report
  2. A plain-text handoff document for the Coder Agent

Usage:
    # Analyze SignalForge (default target):
    python uiux_worker.py

    # Analyze a custom repo:
    python uiux_worker.py --repo https://github.com/user/repo

    # Use local repo instead of cloning:
    python uiux_worker.py --local-repo /path/to/local/repo

    # Dry-run (collect files but don't call LLM):
    python uiux_worker.py --dry-run

    # Use Claude MAX CLI (zero API cost):
    python uiux_worker.py --use-max

Security: Read-only analysis. No file writes to target repo. No deploys.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent dir to path for lib imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [uiux] %(message)s",
)
logger = logging.getLogger("marketpulse.uiux_worker")

from lib.model_caller import MaxModelCaller, ModelCaller, ModelCallerError  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────

DEFAULT_REPO = "https://github.com/onimator-rgb/SignalForge"
ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ORCHESTRATOR_ROOT / "prompts" / "uiux_agent.md"
OUTPUT_DIR = ORCHESTRATOR_ROOT.parent / "reports" / "uiux"

# File extensions to collect for analysis
FRONTEND_EXTENSIONS = {
    ".vue", ".ts", ".tsx", ".js", ".jsx",
    ".css", ".scss", ".sass", ".less",
    ".html", ".json", ".yaml", ".yml",
    ".md",
}

# Files to always include if they exist
PRIORITY_FILES = [
    "package.json",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "tailwind.config.ts",
    "tailwind.config.js",
    "tailwind.config.cjs",
    "postcss.config.js",
    "postcss.config.cjs",
    "index.html",
    "app.css",
]

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".nuxt", ".next",
    ".output", "coverage", "__pycache__", ".pytest_cache",
    "public/assets", "vendor",
}

# Max file size to include (100KB)
MAX_FILE_SIZE = 100_000

# Max total context size (chars) to send to model
MAX_CONTEXT_CHARS = 400_000


# ── Helpers ───────────────────────────────────────────────────────────

def clone_repo(repo_url: str, target_dir: str) -> bool:
    """Clone a git repository. Returns True on success."""
    logger.info("Cloning %s -> %s", repo_url, target_dir)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, target_dir],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("Git clone failed: %s", result.stderr[:500])
            return False
        logger.info("Clone successful")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Git clone timed out after 120s")
        return False
    except FileNotFoundError:
        logger.error("git not found in PATH")
        return False


def get_file_tree(repo_dir: str) -> str:
    """Generate a directory tree listing of the repo."""
    lines = []
    repo_path = Path(repo_dir)
    for item in sorted(repo_path.rglob("*")):
        rel = item.relative_to(repo_path)
        # Skip excluded dirs
        parts = rel.parts
        if any(skip in parts for skip in SKIP_DIRS):
            continue
        indent = "  " * (len(parts) - 1)
        name = item.name
        if item.is_dir():
            lines.append(f"{indent}{name}/")
        else:
            size = item.stat().st_size
            lines.append(f"{indent}{name} ({size}B)")
    return "\n".join(lines[:500])  # Limit tree size


def collect_frontend_files(repo_dir: str) -> List[Dict[str, str]]:
    """Collect all frontend source files from the repo."""
    files = []
    repo_path = Path(repo_dir)
    total_chars = 0

    # First pass: collect priority files
    for pf in PRIORITY_FILES:
        for match in repo_path.rglob(pf):
            rel = str(match.relative_to(repo_path))
            parts = Path(rel).parts
            if any(skip in parts for skip in SKIP_DIRS):
                continue
            if match.is_file() and match.stat().st_size <= MAX_FILE_SIZE:
                try:
                    content = match.read_text(encoding="utf-8", errors="replace")
                    files.append({"path": rel, "content": content})
                    total_chars += len(content)
                except Exception:
                    pass

    collected_paths = {f["path"] for f in files}

    # Second pass: collect all frontend files
    for item in sorted(repo_path.rglob("*")):
        if total_chars >= MAX_CONTEXT_CHARS:
            logger.warning("Context limit reached (%d chars), stopping collection", total_chars)
            break

        if not item.is_file():
            continue

        rel = str(item.relative_to(repo_path))
        if rel in collected_paths:
            continue

        parts = Path(rel).parts
        if any(skip in parts for skip in SKIP_DIRS):
            continue

        if item.suffix.lower() not in FRONTEND_EXTENSIONS:
            continue

        if item.stat().st_size > MAX_FILE_SIZE:
            logger.debug("Skipping large file: %s (%d bytes)", rel, item.stat().st_size)
            continue

        try:
            content = item.read_text(encoding="utf-8", errors="replace")
            files.append({"path": rel, "content": content})
            total_chars += len(content)
            collected_paths.add(rel)
        except Exception as e:
            logger.debug("Could not read %s: %s", rel, e)

    logger.info("Collected %d files (%d chars total)", len(files), total_chars)
    return files


def find_special_files(files: List[Dict[str, str]]) -> Dict[str, str]:
    """Extract special config files from the collected set."""
    special = {}
    patterns = {
        "package_json": "package.json",
        "tailwind_config": "tailwind.config",
        "router_config": "router",
        "vite_config": "vite.config",
        "app_vue": "App.vue",
        "main_ts": "main.ts",
    }

    for f in files:
        path_lower = f["path"].lower()
        for key, pattern in patterns.items():
            if key not in special and pattern.lower() in path_lower:
                special[key] = f["content"]

    return special


def load_system_prompt() -> str:
    """Load the UI/UX agent system prompt."""
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    logger.error("System prompt not found at %s", PROMPT_PATH)
    sys.exit(1)


def build_user_prompt(
    repo_url: str,
    files: List[Dict[str, str]],
    file_tree: str,
    special: Dict[str, str],
) -> str:
    """Build the user prompt with all collected data."""
    # Build a compact version of files for the prompt
    files_for_prompt = []
    for f in files:
        files_for_prompt.append({
            "path": f["path"],
            "content": f["content"][:30000],  # Truncate very large files
        })

    context = {
        "repo_url": repo_url,
        "file_tree": file_tree,
        "files": files_for_prompt,
        "package_json": special.get("package_json", "[not found]"),
        "tailwind_config": special.get("tailwind_config", "[not found]"),
        "router_config": special.get("router_config", "[not found]"),
        "vite_config": special.get("vite_config", "[not found]"),
    }

    prompt = (
        "Analyze the following SignalForge repository frontend code.\n"
        "Execute all 5 phases as defined in your system prompt.\n"
        "Return the complete JSON output as specified.\n\n"
        "=== REPOSITORY DATA ===\n\n"
        f"```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n"
    )

    return prompt


def call_claude_cli_direct(system_prompt: str, user_prompt: str, timeout: int = 600) -> str:
    """Call Claude CLI directly for complex analysis (supports long context)."""
    logger.info("Calling Claude CLI for UI/UX analysis...")

    # Write prompts to temp files to avoid argument length limits
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as sys_f:
        sys_f.write(system_prompt)
        sys_prompt_path = sys_f.name

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as usr_f:
        usr_f.write(user_prompt)
        usr_prompt_path = usr_f.name

    try:
        # Use claude CLI with --print for non-interactive mode
        cmd = [
            "claude",
            "--print",
            "--system-prompt", sys_prompt_path,
            "--max-turns", "1",
        ]

        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )

        if result.returncode != 0:
            logger.error("Claude CLI error: %s", result.stderr[:500])
            raise ModelCallerError(f"Claude CLI failed: {result.stderr[:200]}")

        return result.stdout

    except subprocess.TimeoutExpired:
        raise ModelCallerError(f"Claude CLI timed out after {timeout}s")
    finally:
        # Clean up temp files
        for p in [sys_prompt_path, usr_prompt_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def call_model_api(system_prompt: str, user_prompt: str, use_max: bool) -> str:
    """Call Claude via API or MAX CLI."""
    if use_max:
        caller = MaxModelCaller()
    else:
        caller = ModelCaller()

    # For API calls, we need to format as the expected JSON structure
    # But UI/UX agent uses a different response format, so we call raw
    try:
        if use_max:
            return call_claude_cli_direct(system_prompt, user_prompt, timeout=900)
        else:
            # Direct API call with Anthropic SDK
            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
            if not api_key:
                raise ModelCallerError("No ANTHROPIC_API_KEY or CLAUDE_API_KEY found")

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=64000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            return response.content[0].text

    except Exception as e:
        logger.error("Model call failed: %s", str(e)[:300])
        raise


def extract_handoff(raw_output: str) -> str:
    """Extract the handoff document from Claude's output."""
    # Try to parse as JSON first
    try:
        # Find JSON in the output
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw_output[start:end])
            if "phase5_handoff" in data:
                return data["phase5_handoff"]
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: look for the handoff section markers
    markers = [
        "=== SIGNALFORGE UI/UX IMPLEMENTATION BRIEF ===",
        "PHASE 5",
        "CODING AGENT HANDOFF",
        "IMPLEMENTATION BRIEF",
    ]

    for marker in markers:
        idx = raw_output.find(marker)
        if idx >= 0:
            return raw_output[idx:]

    # Last resort: return the full output
    logger.warning("Could not isolate handoff document, returning full output")
    return raw_output


def save_outputs(
    raw_output: str,
    handoff: str,
    repo_url: str,
    output_dir: Path,
) -> Tuple[str, str]:
    """Save analysis report and handoff document."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Save full analysis report
    report_path = output_dir / f"uiux_analysis_{timestamp}.md"
    report_path.write_text(raw_output, encoding="utf-8")
    logger.info("Full analysis saved: %s", report_path)

    # Save handoff document as TXT
    handoff_filename = "signalforge_uiux_handoff_for_coding_agent.txt"
    handoff_path = output_dir / handoff_filename
    handoff_path.write_text(handoff, encoding="utf-8")
    logger.info("Handoff document saved: %s", handoff_path)

    # Also save a copy in the repo root for easy access
    repo_root = ORCHESTRATOR_ROOT.parent
    handoff_root_path = repo_root / handoff_filename
    handoff_root_path.write_text(handoff, encoding="utf-8")
    logger.info("Handoff copy saved: %s", handoff_root_path)

    return str(report_path), str(handoff_path)


# ── JSON Report ──────────────────────────────────────────────────────

def build_worker_report(
    repo_url: str,
    files_collected: int,
    report_path: str,
    handoff_path: str,
    duration_sec: float,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build structured JSON report for orchestrator."""
    return {
        "agent": "uiux_worker",
        "task_type": "ui_ux_analysis",
        "repo_analyzed": repo_url,
        "files_collected": files_collected,
        "report_path": report_path,
        "handoff_path": handoff_path,
        "handoff_filename": "signalforge_uiux_handoff_for_coding_agent.txt",
        "duration_seconds": round(duration_sec, 1),
        "status": "error" if error else "completed",
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "next_recommended_step": "dispatch_to_coder" if not error else "ask_human",
    }


# ── Main ─────────────────────────────────────────────────────────────

def execute_analysis(
    repo_url: str = DEFAULT_REPO,
    local_repo: Optional[str] = None,
    use_max: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute full UI/UX analysis pipeline."""
    import time

    start = time.monotonic()
    tmp_dir = None

    try:
        # Step 1: Get the repo
        if local_repo:
            repo_dir = local_repo
            logger.info("Using local repo: %s", repo_dir)
        else:
            tmp_dir = tempfile.mkdtemp(prefix="signalforge_")
            if not clone_repo(repo_url, tmp_dir):
                return build_worker_report(
                    repo_url, 0, "", "", time.monotonic() - start,
                    error="Failed to clone repository",
                )
            repo_dir = tmp_dir

        # Step 2: Collect frontend files
        logger.info("Collecting frontend files...")
        files = collect_frontend_files(repo_dir)
        file_tree = get_file_tree(repo_dir)
        special = find_special_files(files)

        logger.info(
            "Collected: %d files | Tree: %d lines | Special configs: %s",
            len(files), file_tree.count("\n"), list(special.keys()),
        )

        if dry_run:
            logger.info("DRY RUN — skipping LLM call")
            # Save collected data for inspection
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            dry_path = OUTPUT_DIR / "dry_run_collected_files.json"
            dry_data = {
                "repo_url": repo_url,
                "file_count": len(files),
                "file_paths": [f["path"] for f in files],
                "file_tree": file_tree,
                "special_configs": list(special.keys()),
            }
            dry_path.write_text(json.dumps(dry_data, indent=2), encoding="utf-8")
            return build_worker_report(
                repo_url, len(files),
                str(dry_path), "", time.monotonic() - start,
            )

        # Step 3: Build prompts
        system_prompt = load_system_prompt()
        user_prompt = build_user_prompt(repo_url, files, file_tree, special)
        logger.info("Prompt size: system=%d chars, user=%d chars", len(system_prompt), len(user_prompt))

        # Step 4: Call Claude
        raw_output = call_model_api(system_prompt, user_prompt, use_max)
        logger.info("Received %d chars from Claude", len(raw_output))

        # Step 5: Extract handoff and save
        handoff = extract_handoff(raw_output)
        report_path, handoff_path = save_outputs(raw_output, handoff, repo_url, OUTPUT_DIR)

        elapsed = time.monotonic() - start
        report = build_worker_report(
            repo_url, len(files), report_path, handoff_path, elapsed,
        )

        # Print JSON report for orchestrator
        print(json.dumps(report, indent=2))
        print("\n--- Worker Report ---")
        print(f"UI/UX Analysis completed in {elapsed:.1f}s")
        print(f"Files analyzed: {len(files)}")
        print(f"Full report: {report_path}")
        print(f"Handoff document: {handoff_path}")
        print(f"Handoff also at: {ORCHESTRATOR_ROOT.parent / 'signalforge_uiux_handoff_for_coding_agent.txt'}")

        return report

    except Exception as e:
        elapsed = time.monotonic() - start
        logger.exception("Analysis failed")
        report = build_worker_report(
            repo_url, 0, "", "", elapsed, error=str(e),
        )
        print(json.dumps(report, indent=2))
        return report

    finally:
        # Clean up temp dir
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
                logger.info("Cleaned up temp dir: %s", tmp_dir)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="MarketPulse UI/UX Analysis Agent — analyze frontend repos",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repo URL to analyze (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--local-repo",
        default=None,
        help="Path to local repo (skip cloning)",
    )
    parser.add_argument(
        "--use-max",
        action="store_true",
        default=True,
        help="Use Claude MAX CLI (default: True)",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="Use Anthropic API instead of Claude MAX CLI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect files but don't call LLM",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for reports",
    )

    args = parser.parse_args()

    if args.use_api:
        args.use_max = False

    if args.output_dir:
        global OUTPUT_DIR
        OUTPUT_DIR = Path(args.output_dir)

    execute_analysis(
        repo_url=args.repo,
        local_repo=args.local_repo,
        use_max=args.use_max,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
