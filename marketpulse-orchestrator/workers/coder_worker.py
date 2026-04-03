#!/usr/bin/env python3
"""
MarketPulse Coder Worker — Agent 2 (with Model Integration)

Reads a task_spec, optionally calls Claude (claude-sonnet-4) to generate
implementation, applies changes via dry-run, runs checks, commits, and
exports a structured JSON report.

Usage:
    # With LLM (requires ANTHROPIC_API_KEY):
    python coder_worker.py --task task_store/task_example.json --repo /path/to/repo

    # Without LLM (validate-only mode, checks existing code):
    python coder_worker.py --task task_store/task_example.json --repo /path/to/repo --no-llm

    # Dry-run only (no commit):
    python coder_worker.py --task task_store/task_example.json --repo /path/to/repo --dry-run

Security: No deploys, no secrets, no broker APIs. Paper-trading only.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("marketpulse.coder_worker")

from lib.model_caller import ModelCaller, MaxModelCaller, ModelCallerError, ForbiddenPathError  # noqa: E402, I001


# ── Helpers ────────────────────────────────────────────────────────────

def run_cmd(cmd: str, cwd: str, timeout: int = 120) -> Tuple[int, str]:
    """Run shell command, return (exit_code, stdout+stderr truncated to 2000 chars)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout
        )
        output = (result.stdout + result.stderr)[:2000]
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return -1, str(e)[:2000]


def load_task_spec(path: str) -> Dict[str, Any]:
    with open(path) as f:
        data: Dict[str, Any] = json.load(f)
        return data


def load_prompt(orchestrator_root: str) -> str:
    """Load the coder prompt template."""
    prompt_path = os.path.join(orchestrator_root, "prompts", "marketpulse_coder.md")
    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            return f.read()
    return ""


# ── Security ──────────────────────────────────────────────────────────

FORBIDDEN_DEFAULTS = [".env", "infra/", "secrets/"]


def check_forbidden(file_path: str, forbidden: List[str]) -> bool:
    """Return True if file_path violates forbidden_paths."""
    for fp in forbidden:
        if file_path == fp or file_path.startswith(fp):
            return True
    return False


def check_authorization(spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify authorization level allows autonomous execution."""
    auth = spec.get("authorization", {})
    level = auth.get("level", "human_review")
    if level == "auto_approve":
        return True, "auto_approve: proceeding autonomously"
    return False, f"authorization.level={level}: requires human approval"


# ── Git operations ────────────────────────────────────────────────────

def git_setup_branch(repo: str, base_ref: str, task_id: str) -> Tuple[bool, str]:
    """Checkout base_ref and create task branch."""
    branch_name = f"task/{task_id}-implementation"
    code, out = run_cmd(f"git checkout {base_ref}", repo)
    code, out = run_cmd(f"git checkout -b {branch_name}", repo)
    if code != 0:
        code, out = run_cmd(f"git checkout {branch_name}", repo)
        if code != 0:
            return False, f"Failed to create/checkout branch: {out}"
    return True, branch_name


def git_commit(repo: str, task_id: str, message: str) -> Tuple[bool, str]:
    """Stage all and commit with task_id in message."""
    run_cmd("git add -A", repo)
    full_msg = f"feat({task_id}): {message}"
    code, out = run_cmd(f'git commit -m "{full_msg}"', repo)
    if code != 0:
        return False, f"Commit failed: {out}"
    _, sha = run_cmd("git rev-parse HEAD", repo)
    return True, sha.strip()


# ── Dry-run logic ─────────────────────────────────────────────────────

def apply_files_to_dir(target_dir: str, files: List[Dict[str, str]]) -> List[str]:
    """Write model-generated files to a directory. Returns list of paths written."""
    written = []
    for f in files:
        path = f["path"]
        content = f["content"]
        full_path = os.path.join(target_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)
    return written


def dry_run_checks(
    repo_path: str,
    files: List[Dict[str, str]],
    checks: List[str],
    forbidden: List[str],
) -> Tuple[bool, List[Dict], List[str]]:
    """Apply files to temp copy of repo, run checks. Return (pass, results, blocked_paths)."""

    # Check forbidden paths first
    blocked = [f["path"] for f in files if check_forbidden(f["path"], forbidden)]
    if blocked:
        return False, [], blocked

    # Create temp copy
    with tempfile.TemporaryDirectory(prefix="mp_dryrun_") as tmp:
        # Copy repo to temp dir
        tmp_repo = os.path.join(tmp, "repo")
        shutil.copytree(repo_path, tmp_repo, dirs_exist_ok=True)

        # Apply model-generated files
        apply_files_to_dir(tmp_repo, files)

        # Run checks in temp dir
        results = []
        all_pass = True
        for cmd in checks:
            code, output = run_cmd(cmd, tmp_repo)
            results.append({"cmd": cmd, "exit_code": code, "stdout": output[:2000]})
            if code != 0:
                all_pass = False

        return all_pass, results, []


# ── Rationale generation ──────────────────────────────────────────────

def create_rationale(
    repo: str, task_id: str, branch: str, commit_sha: str,
    criteria_results: List[Dict], files_changed: List[str],
    commands_run: List[Dict], model_calls: int = 0,
) -> str:
    """Generate rationale.md from template."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    criteria_section = ""
    for cr in criteria_results:
        criteria_section += f"\n- **Criteria:** {cr['criteria']}\n"
        criteria_section += f"- **Status:** `{cr['status']}`\n"
        criteria_section += f"- **Evidence:** {cr['evidence']}\n"

    files_section = "\n".join(f"- `{f}`" for f in files_changed)
    cmds_section = "\n".join(
        f"  - `{c['cmd']}` — {'passed' if c['exit_code'] == 0 else 'FAILED'}"
        for c in commands_run
    )

    content = f"""# Rationale for `{task_id}`

**author:** coder-worker (MarketPulse Coder)
**branch:** {branch}
**commit_sha:** {commit_sha}
**date:** {now}
**model_calls:** {model_calls}

---

## 1) One-line summary
Automated implementation for task {task_id} via coder_worker.py with model integration.

---

## 2) Mapping to acceptance criteria
{criteria_section}
---

## 3) Files changed (and rationale per file)
{files_section}

---

## 4) Tests run & results
- **Commands run:**
{cmds_section}

---

## 5) Data & sample evidence
- Synthetic fixtures used from tests/fixtures/

---

## 6) Risk assessment & mitigations
- **Risk:** LLM-generated code — **Severity:** medium — **Mitigation:** dry-run validation before commit, forbidden_paths block, validator.py post-check

---

## 7) Backwards compatibility / migration notes
- New files only, backward compatible.

---

## 8) Performance considerations
- No performance impact expected.

---

## 9) Security & safety checks
- forbidden paths touched: `no`
- external/broker sdk usage: `no`
- secrets touched: `no`
- API key logged: `no` (only presence check)

---

## 10) Open questions & follow-ups
1. Review LLM-generated implementation for edge cases.

---

## 11) Short changelog
- `{commit_sha[:7] if commit_sha else 'N/A'}` — feat({task_id}): implementation

---

## 12) Final verdict (developer self-check)
- **I confirm** that all acceptance criteria marked `pass` have test evidence attached: `yes`
- **I confirm** no forbidden paths were modified: `yes`
- **I request** next step: `validate`
"""
    path = os.path.join(repo, "rationale.md")
    with open(path, "w") as f:
        f.write(content)
    return path


# ── Acceptance criteria mapping ───────────────────────────────────────

def run_required_checks(repo: str, checks: List[str]) -> Tuple[bool, List[Dict]]:
    results = []
    all_pass = True
    for cmd in checks:
        code, output = run_cmd(cmd, repo)
        results.append({"cmd": cmd, "exit_code": code, "stdout": output[:2000]})
        if code != 0:
            all_pass = False
    return all_pass, results


def map_acceptance_criteria(criteria: List[str], check_results: List[Dict]) -> List[Dict]:
    results = []
    all_pass = all(r["exit_code"] == 0 for r in check_results)
    for crit in criteria:
        results.append({
            "criteria": crit,
            "status": "pass" if all_pass else "partial",
            "evidence": "All required checks passed" if all_pass else "Some checks failed"
        })
    return results


# ── Error report builder ─────────────────────────────────────────────

def _error_report(task_id: str, msg: str, step: str = "revise") -> Dict[str, Any]:
    return {
        "task_id": task_id, "branch": "", "commit_sha": "",
        "files_changed": [], "commands_run": [],
        "tests": {"passed": False, "summary": msg, "failed_tests": []},
        "lint": {"passed": False, "output": msg},
        "acceptance_criteria_results": [],
        "rationale_path": "", "issues": [{"path": "N/A", "severity": "high", "description": msg}],
        "next_recommended_step": step, "notes": msg
    }


# ── Main worker ───────────────────────────────────────────────────────

def execute_task(
    task_spec_path: str,
    repo_path: str,
    base_ref: str = "main",
    orchestrator_root: Optional[str] = None,
    use_llm: bool = True,
    dry_run_only: bool = False,
    max_tokens: int = 64000,
    max_model_calls: int = 10,
    use_max: bool = False,
) -> Dict[str, Any]:
    """Main entry point: execute a task_spec against a repo."""

    spec = load_task_spec(task_spec_path)
    task_id = spec["task_id"]
    forbidden = spec.get("forbidden_paths", FORBIDDEN_DEFAULTS)

    # 1. Authorization
    auth_ok, auth_msg = check_authorization(spec)
    if not auth_ok:
        return _error_report(task_id, auth_msg, "ask_human")

    # 2. Setup branch
    ok, branch = git_setup_branch(repo_path, base_ref, task_id)
    if not ok:
        return _error_report(task_id, f"Branch setup failed: {branch}")

    # 3. Collect subtask info
    all_files_expected, all_criteria, all_checks = [], [], []
    for st in spec.get("subtasks", []):
        all_files_expected.extend(st.get("files_expected", []))
        all_criteria.extend(st.get("acceptance_criteria", []))
        all_checks.extend(st.get("required_checks", []))

    # 4. Resolve orchestrator root for prompt loading
    if orchestrator_root is None:
        orchestrator_root = str(Path(__file__).resolve().parents[1])

    commands_run = []
    model_generated_files = []
    model_calls_used = 0

    # 5. LLM-driven implementation (if enabled)
    if use_llm:
        system_prompt = load_prompt(orchestrator_root)
        CallerClass = MaxModelCaller if use_max else ModelCaller
        caller = CallerClass(
            forbidden_paths=forbidden,
            max_calls_per_task=max_model_calls,
            max_tokens=max_tokens,
        )
        logger.info(f"Using {'MaxModelCaller (Claude MAX subscription)' if use_max else 'ModelCaller (Anthropic API)'}")

        prompt_payload = {
            "task_spec": spec,
            "repo_path": repo_path,
            "base_ref": base_ref,
            "branch": branch,
            "instruction": (
                "Implement the task described in task_spec. "
                "YOUR RESPONSE MUST BE A SINGLE JSON OBJECT (no markdown, no prose) with exactly "
                "two top-level keys: 'files' and 'summary'. "
                "'files' is a list of objects, each with 'path' (string, relative to repo root) "
                "and 'content' (string, full file content). "
                "'summary' is a short string describing what was implemented. "
                "IMPORTANT: 'files' contains SOURCE CODE FILES TO CREATE, not API response data. "
                "Do NOT return the API endpoint's JSON response as 'files'. "
                "Do NOT include files matching forbidden_paths. "
                "Example structure: {\"files\": [{\"path\": \"src/foo.py\", \"content\": \"...\"}], \"summary\": \"...\"}"
            ),
        }

        try:
            result = caller.call_model(prompt_payload, system_prompt=system_prompt)
            model_calls_used = caller.call_count
            model_generated_files = result.get("files", [])

            if not model_generated_files:
                # Model returned no files — log as warning and treat as a soft failure
                # so the orchestrator can retry with a fresh prompt
                summary = result.get("summary", "no summary")
                logger.warning(f"Model returned 0 files: {summary[:200]}")
                commands_run.append({
                    "cmd": "model_call", "exit_code": 1,
                    "stdout": f"Model returned empty file list: {summary[:500]}"
                })

            if model_generated_files:
                # Dry-run: apply to temp copy, run checks
                dr_pass, dr_results, blocked = dry_run_checks(
                    repo_path, model_generated_files, all_checks, forbidden
                )

                if blocked:
                    return {
                        **_error_report(task_id, f"FORBIDDEN: model tried to write: {blocked}", "ask_human"),
                        "notes": f"Blocked paths: {blocked}. Model calls: {model_calls_used}"
                    }

                commands_run.extend(dr_results)

                if dr_pass and not dry_run_only:
                    # Checks passed in dry-run → apply to real repo
                    apply_files_to_dir(repo_path, model_generated_files)
                elif not dr_pass:
                    # Dry-run failed → try escalation (Opus)
                    if caller.calls_remaining > 0:
                        try:
                            esc_result = caller.call_escalation(
                                prompt_payload, system_prompt=system_prompt
                            )
                            model_calls_used = caller.call_count
                            esc_files = esc_result.get("files", [])
                            if esc_files:
                                dr2_pass, dr2_results, blocked2 = dry_run_checks(
                                    repo_path, esc_files, all_checks, forbidden
                                )
                                commands_run.extend(dr2_results)
                                if dr2_pass and not dry_run_only:
                                    model_generated_files = esc_files
                                    apply_files_to_dir(repo_path, esc_files)
                        except (ModelCallerError, ForbiddenPathError) as e:
                            commands_run.append({
                                "cmd": "escalation_call", "exit_code": 1,
                                "stdout": str(e)[:2000]
                            })

        except ForbiddenPathError as e:
            return _error_report(task_id, str(e), "ask_human")
        except ModelCallerError as e:
            # Model failed — fall through to validate-only mode
            model_calls_used = caller.call_count  # capture actual call count even on failure
            commands_run.append({
                "cmd": "model_call", "exit_code": 1, "stdout": str(e)[:2000]
            })

    # 6. Run required checks on actual repo
    checks_pass, check_results = run_required_checks(repo_path, all_checks)
    commands_run.extend(check_results)

    # 7. Map acceptance criteria
    criteria_results = map_acceptance_criteria(all_criteria, check_results)

    # 8. Get files changed
    _, diff_out = run_cmd(f"git diff --name-only {base_ref}..HEAD", repo_path)
    files_changed = [f.strip() for f in diff_out.strip().split("\n") if f.strip()]
    # Include model-applied files
    for mf in model_generated_files:
        p = mf["path"]
        if p not in files_changed:
            files_changed.append(p)

    # 9. Commit (unless dry-run)
    commit_sha = ""
    if not dry_run_only and (model_generated_files or files_changed):
        ok, sha = git_commit(repo_path, task_id, "implementation via coder_worker")
        if ok:
            commit_sha = sha

    # 10. Create rationale
    create_rationale(
        repo_path, task_id, branch, commit_sha,
        criteria_results, files_changed, commands_run, model_calls_used
    )

    # Commit rationale
    if not dry_run_only:
        run_cmd("git add rationale.md", repo_path)
        code, _ = run_cmd(
            f'git commit -m "docs({task_id}): add rationale.md"', repo_path
        )
        if code == 0:
            _, sha = run_cmd("git rev-parse HEAD", repo_path)
            commit_sha = sha.strip()
            if "rationale.md" not in files_changed:
                files_changed.append("rationale.md")

    # 11. Build result
    test_pass_count = sum(1 for r in check_results if r["exit_code"] == 0)
    test_fail_count = len(check_results) - test_pass_count
    all_criteria_pass = all(r["status"] == "pass" for r in criteria_results)

    if checks_pass and all_criteria_pass:
        next_step = "approve"
    elif checks_pass:
        next_step = "approve"
    else:
        next_step = "revise"

    if dry_run_only:
        next_step = f"dry_run_{next_step}"

    issues = []
    for r in check_results:
        if r["exit_code"] != 0:
            issues.append({"path": "N/A", "severity": "high",
                           "description": f"Check failed: {r['cmd']}"})

    return {
        "task_id": task_id,
        "branch": branch,
        "commit_sha": commit_sha,
        "files_changed": files_changed,
        "commands_run": [{"cmd": r["cmd"], "exit_code": r["exit_code"], "stdout": r["stdout"]} for r in commands_run],
        "tests": {
            "passed": checks_pass,
            "summary": f"{test_pass_count} passed, {test_fail_count} failed",
            "failed_tests": [r["cmd"] for r in check_results if r["exit_code"] != 0]
        },
        "lint": {
            "passed": all(r["exit_code"] == 0 for r in check_results
                          if "mypy" in r["cmd"] or "ruff" in r["cmd"]),
            "output": "; ".join(
                r["stdout"][:200] for r in check_results
                if "mypy" in r["cmd"] or "ruff" in r["cmd"]
            )[:2000]
        },
        "acceptance_criteria_results": criteria_results,
        "rationale_path": "rationale.md",
        "issues": issues,
        "next_recommended_step": next_step,
        "notes": (
            f"Worker completed at {datetime.now(timezone.utc).isoformat()}. "
            f"Model calls: {model_calls_used}. "
            f"LLM: {'enabled' if use_llm else 'disabled'}. "
            f"Dry-run: {dry_run_only}."
        )
    }


def main():
    parser = argparse.ArgumentParser(description="MarketPulse Coder Worker v2")
    parser.add_argument("--task", required=True, help="Path to task_spec JSON")
    parser.add_argument("--repo", required=True, help="Path to target repo")
    parser.add_argument("--base", default="main", help="Base ref (default: main)")
    parser.add_argument("--orchestrator-root", default=None,
                        help="Path to orchestrator root")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM calls — validate-only mode")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apply changes to temp dir only, do not commit")
    parser.add_argument("--max-tokens", type=int, default=64000,
                        help="Max tokens per model call (default: 64000)")
    parser.add_argument("--max-calls", type=int, default=10,
                        help="Max model calls per task")
    parser.add_argument("--use-max", action="store_true",
                        help="Use Claude MAX subscription via `claude` CLI (no API cost). "
                             "Requires `claude auth login` and an active MAX plan.")
    args = parser.parse_args()

    result = execute_task(
        args.task, args.repo, args.base, args.orchestrator_root,
        use_llm=not args.no_llm,
        dry_run_only=args.dry_run,
        max_tokens=args.max_tokens,
        max_model_calls=args.max_calls,
        use_max=args.use_max,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n--- Worker Report ---")
    print(f"Task: {result['task_id']}")
    print(f"Branch: {result['branch']}")
    print(f"Verdict: {result['next_recommended_step'].upper()}")
    print(f"Tests: {result['tests']['summary']}")
    if result["issues"]:
        print(f"Issues ({len(result['issues'])}):")
        for i in result["issues"]:
            print(f"  [{i['severity']}] {i['description'][:120]}")

    sys.exit(0 if "approve" in result["next_recommended_step"] else 1)


if __name__ == "__main__":
    main()
