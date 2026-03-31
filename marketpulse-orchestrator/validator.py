#!/usr/bin/env python3
"""
MarketPulse Orchestrator — Validator
Validates coder output against task_spec. Returns verdict JSON.

Usage:
    python validator.py --task-spec task_store/task_example.json --repo mock_repo --base master
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_task_spec(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def run_cmd(cmd: str, cwd: str, timeout: int = 120) -> Tuple[int, str]:
    """Run a shell command, return (exit_code, stdout_truncated)."""
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


def check_commit_messages(repo_path: str, base_ref: str, task_id: str) -> Tuple[bool, str]:
    """Verify all commits on task branch contain task_id."""
    code, output = run_cmd(f"git log {base_ref}..HEAD --oneline", repo_path)
    if code != 0:
        return False, f"git log failed: {output}"
    lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
    if not lines:
        return False, "No commits found on task branch"
    missing = [l for l in lines if task_id not in l]
    if missing:
        return False, f"Commits missing task_id: {missing}"
    return True, f"All {len(lines)} commits contain {task_id}"


def check_files_changed(repo_path: str, base_ref: str, files_expected: List[str]) -> Tuple[bool, str, List[str]]:
    """Compare changed files vs files_expected (prefix matching)."""
    code, output = run_cmd(f"git diff --name-only {base_ref}..HEAD", repo_path)
    if code != 0:
        return False, f"git diff failed: {output}", []
    changed = [f.strip() for f in output.strip().split("\n") if f.strip()]

    # Build set of expected parent directories for lenient matching
    expected_parents = set()
    for exp in files_expected:
        parts = exp.split("/")
        for i in range(1, len(parts)):
            expected_parents.add("/".join(parts[:i]))

    # Prefix matching: a changed file matches if it starts with any expected prefix
    unmatched = []
    for cf in changed:
        matched = False
        for exp in files_expected:
            # Direct match or prefix match (src/services/ matches src/services/anomalies.py)
            if cf == exp or cf.startswith(exp.rstrip("/") + "/") or exp.startswith(cf.rstrip("/") + "/"):
                matched = True
                break
        if not matched:
            # Allow __pycache__, __init__.py, rationale.md, .gitkeep as acceptable extras
            basename = os.path.basename(cf)
            if basename in ("__init__.py", ".gitkeep") or "__pycache__" in cf or cf == "rationale.md":
                continue
            # Allow files in same parent directory as expected files (e.g. src/app.py when src/api/* expected)
            cf_parent = "/".join(cf.split("/")[:-1]) if "/" in cf else ""
            if cf_parent and cf_parent in expected_parents:
                continue
            unmatched.append(cf)

    if unmatched:
        return False, f"Unexpected files: {unmatched}", changed
    return True, f"{len(changed)} files changed, all match expected", changed


def check_forbidden_paths(repo_path: str, base_ref: str, forbidden: List[str]) -> Tuple[bool, str]:
    """Ensure no forbidden paths are in the diff."""
    code, output = run_cmd(f"git diff --name-only {base_ref}..HEAD", repo_path)
    if code != 0:
        return False, f"git diff failed: {output}"
    changed = [f.strip() for f in output.strip().split("\n") if f.strip()]

    violations = []
    for cf in changed:
        for fp in forbidden:
            if cf == fp or cf.startswith(fp):
                violations.append(f"{cf} matches forbidden {fp}")
    if violations:
        return False, f"FORBIDDEN PATH VIOLATIONS: {violations}"
    return True, "No forbidden paths touched"


def check_rationale(repo_path: str) -> Tuple[bool, str]:
    """Check rationale.md exists and has section headers."""
    rationale_path = os.path.join(repo_path, "rationale.md")
    if not os.path.exists(rationale_path):
        return False, "rationale.md not found"
    with open(rationale_path) as f:
        content = f.read()
    section_count = content.count("\n## ")
    if section_count < 10:
        return False, f"rationale.md has only {section_count} sections (expected >= 10)"
    return True, f"rationale.md present with {section_count} sections"


def run_required_checks(repo_path: str, checks: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Run each required check command and collect results."""
    results = []
    all_pass = True
    for cmd in checks:
        code, output = run_cmd(cmd, repo_path)
        results.append({
            "cmd": cmd,
            "exit_code": code,
            "stdout_excerpt": output[:2000]
        })
        if code != 0:
            all_pass = False
    return all_pass, results


def map_acceptance_criteria(
    repo_path: str,
    criteria: List[str],
    check_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Basic mapping: check rationale.md for each criterion text."""
    rationale_path = os.path.join(repo_path, "rationale.md")
    rationale_content = ""
    if os.path.exists(rationale_path):
        with open(rationale_path) as f:
            rationale_content = f.read()

    results = []
    for crit in criteria:
        # Check if criterion text appears in rationale (basic mapping)
        short_key = crit[:60]
        if short_key.lower() in rationale_content.lower() or crit[:40].lower() in rationale_content.lower():
            # Check if marked as pass in rationale
            if "pass" in rationale_content.lower():
                results.append({
                    "criteria": crit,
                    "status": "pass",
                    "evidence": "Mapped in rationale.md with status pass"
                })
            else:
                results.append({
                    "criteria": crit,
                    "status": "partial",
                    "evidence": "Found in rationale.md but status unclear"
                })
        else:
            results.append({
                "criteria": crit,
                "status": "fail",
                "evidence": "Not found in rationale.md"
            })
    return results


def determine_verdict(checks: Dict[str, bool], criteria_results: List[Dict]) -> str:
    """Determine verdict based on all checks."""
    if not checks.get("forbidden_paths_clean", True):
        return "reject"
    all_checks_pass = all(checks.values())
    all_criteria_pass = all(r["status"] == "pass" for r in criteria_results)
    if all_checks_pass and all_criteria_pass:
        return "approve"
    if checks.get("required_checks_pass", False) and not all_criteria_pass:
        return "revise"
    return "revise"


def validate(task_spec_path: str, repo_path: str, base_ref: str = "master") -> Dict[str, Any]:
    """Main validation entry point."""
    spec = load_task_spec(task_spec_path)
    task_id = spec["task_id"]

    # Collect all files_expected and acceptance_criteria across subtasks
    all_files_expected = []
    all_criteria = []
    all_checks = []
    for st in spec.get("subtasks", []):
        all_files_expected.extend(st.get("files_expected", []))
        all_criteria.extend(st.get("acceptance_criteria", []))
        all_checks.extend(st.get("required_checks", []))
    forbidden = spec.get("forbidden_paths", [])

    # Run all checks
    commit_ok, commit_msg = check_commit_messages(repo_path, base_ref, task_id)
    files_ok, files_msg, files_changed = check_files_changed(repo_path, base_ref, all_files_expected)
    forbidden_ok, forbidden_msg = check_forbidden_paths(repo_path, base_ref, forbidden)
    rationale_ok, rationale_msg = check_rationale(repo_path)
    checks_ok, check_results = run_required_checks(repo_path, all_checks)
    criteria_results = map_acceptance_criteria(repo_path, all_criteria, check_results)
    criteria_mapped = len(criteria_results) > 0

    checks_summary = {
        "commit_message_has_task_id": commit_ok,
        "files_match_expected": files_ok,
        "forbidden_paths_clean": forbidden_ok,
        "required_checks_pass": checks_ok,
        "rationale_present": rationale_ok,
        "acceptance_criteria_mapped": criteria_mapped
    }

    verdict = determine_verdict(checks_summary, criteria_results)

    issues = []
    if not commit_ok:
        issues.append({"area": "commits", "severity": "high", "description": commit_msg})
    if not files_ok:
        issues.append({"area": "files", "severity": "med", "description": files_msg})
    if not forbidden_ok:
        issues.append({"area": "security", "severity": "high", "description": forbidden_msg})
    if not rationale_ok:
        issues.append({"area": "rationale", "severity": "med", "description": rationale_msg})
    if not checks_ok:
        issues.append({"area": "checks", "severity": "high", "description": "Some required checks failed"})

    fix_priority = [i["description"] for i in issues if i["severity"] in ("high", "med")]

    return {
        "task_id": task_id,
        "verdict": verdict,
        "checks": checks_summary,
        "required_checks_results": check_results,
        "acceptance_criteria_results": criteria_results,
        "issues": issues,
        "fix_priority": fix_priority,
        "notes": f"Validated at {datetime.now(timezone.utc).isoformat()}"
    }


def main():
    parser = argparse.ArgumentParser(description="MarketPulse Validator")
    parser.add_argument("--task-spec", required=True, help="Path to task_spec JSON")
    parser.add_argument("--repo", required=True, help="Path to repo to validate")
    parser.add_argument("--base", default="master", help="Base ref (default: master)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")
    args = parser.parse_args()

    result = validate(args.task_spec, args.repo, args.base)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not args.json:
        print("\n---")
        print(f"Verdict: {result['verdict'].upper()}")
        if result["issues"]:
            print(f"Issues: {len(result['issues'])}")
            for i in result["issues"]:
                print(f"  [{i['severity']}] {i['area']}: {i['description'][:120]}")
        if result["fix_priority"]:
            print("Fix priority:")
            for idx, fp in enumerate(result["fix_priority"], 1):
                print(f"  {idx}. {fp[:120]}")

    sys.exit(0 if result["verdict"] == "approve" else 1)


if __name__ == "__main__":
    main()
