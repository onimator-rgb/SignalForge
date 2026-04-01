"""MarketPulse Orchestrator — autonomous tech lead agent.

Researches the project, selects features from the roadmap, generates task specs,
dispatches to Coder Worker + Validator, and loops until time runs out.

Uses Claude MAX subscription via `claude` CLI — zero API cost.
"""

from __future__ import annotations

import datetime
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("marketpulse.orchestrator")

ORCHESTRATOR_ROOT = Path(__file__).resolve().parent
REPO_ROOT = ORCHESTRATOR_ROOT.parent
ROADMAP_DIR = ORCHESTRATOR_ROOT / "roadmap"
BRAIN_PROMPT_PATH = ORCHESTRATOR_ROOT / "prompts" / "orchestrator_brain.md"
TASK_STORE = ORCHESTRATOR_ROOT / "task_store"
LOG_DIR = REPO_ROOT / "logs"
REPORT_DIR = REPO_ROOT / "reports"

# Venv Python detection
_venv_win = REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
_venv_unix = REPO_ROOT / "backend" / ".venv" / "bin" / "python"
PYTHON = str(_venv_win) if _venv_win.exists() else (str(_venv_unix) if _venv_unix.exists() else "python")

MIN_TASK_TIME_MINUTES = 12


def _ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")


def _run_cmd(cmd: str, cwd: str | None = None, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd or str(REPO_ROOT),
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr)[:3000]
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT {timeout}s"
    except Exception as e:
        return -1, str(e)[:500]


class Orchestrator:
    """Autonomous orchestrator that manages the Coder→Validator loop."""

    def __init__(
        self,
        repo_path: str | None = None,
        max_minutes: int = 120,
        max_retries: int = 2,
        dry_run: bool = False,
        tiers: list[str] | None = None,
    ):
        self.repo_path = repo_path or str(REPO_ROOT)
        self.max_minutes = max_minutes
        self.max_retries = max_retries
        self.dry_run = dry_run

        self.session_id = f"session-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self._t_start = time.monotonic()
        self._task_counter = 0

        # Session state
        self.completed: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.all_files_changed: set[str] = set()

        # Load roadmap and prompt
        self.roadmap = self._load_roadmap()
        self.brain_prompt = self._load_brain_prompt()

        # Auto-detect tiers from roadmap if not specified
        self.tiers = tiers or sorted(self.roadmap.get("tiers", {}).keys(), key=lambda x: int(x) if x.isdigit() else 999)

        logger.info(f"Orchestrator initialized: session={self.session_id}, "
                     f"max_minutes={max_minutes}, tiers={self.tiers}, dry_run={dry_run}")

    # ── Helpers ───────────────────────────────────────

    def _load_roadmap(self) -> dict:
        """Load and merge all roadmap JSON files from roadmap/ directory."""
        merged: dict = {"tiers": {}}
        for path in sorted(ROADMAP_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for tier_key, tier_data in data.get("tiers", {}).items():
                if tier_key in merged["tiers"]:
                    # Merge features into existing tier
                    existing_ids = {f["id"] for f in merged["tiers"][tier_key].get("features", [])}
                    for f in tier_data.get("features", []):
                        if f["id"] not in existing_ids:
                            merged["tiers"][tier_key]["features"].append(f)
                else:
                    merged["tiers"][tier_key] = tier_data
            logger.info(f"Loaded roadmap: {path.name} ({len(data.get('tiers', {}))} tiers)")
        return merged

    def _load_brain_prompt(self) -> str:
        with open(BRAIN_PROMPT_PATH, encoding="utf-8") as f:
            return f.read()

    def _elapsed_min(self) -> float:
        return (time.monotonic() - self._t_start) / 60

    def _time_remaining(self) -> float:
        return self.max_minutes - self._elapsed_min()

    def _should_continue(self) -> bool:
        return self._time_remaining() > MIN_TASK_TIME_MINUTES

    def _gen_task_id(self) -> str:
        self._task_counter += 1
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        return f"marketpulse-task-{date}-{self._task_counter:04d}"

    # ── Research (no LLM) ─────────────────────────────

    def research_project(self) -> dict:
        """Gather project state without LLM."""
        logger.info("Researching project state...")

        _, git_log = _run_cmd("git log --oneline -20", self.repo_path)
        _, git_diff = _run_cmd("git diff --stat main", self.repo_path)

        # List backend modules
        _, modules = _run_cmd(
            "find backend/app -maxdepth 1 -type d -not -name __pycache__ | sort",
            self.repo_path,
        )

        # List existing tests
        _, tests = _run_cmd(
            "find backend/tests -name 'test_*.py' -type f 2>/dev/null | sort",
            self.repo_path,
        )

        # Check indicator service for existing indicators
        _, indicators_code = _run_cmd(
            "grep -n 'def \\|class ' backend/app/indicators/service.py 2>/dev/null | head -30",
            self.repo_path,
        )

        # Check portfolio service for existing features
        _, portfolio_code = _run_cmd(
            "grep -n 'def \\|class \\|stop_loss\\|take_profit\\|trailing' backend/app/portfolio/service.py 2>/dev/null | head -40",
            self.repo_path,
        )

        # Check strategy service
        _, strategy_code = _run_cmd(
            "grep -n 'def \\|class \\|PROFILES\\|regime' backend/app/strategy/service.py 2>/dev/null | head -30",
            self.repo_path,
        )

        # Frontend views
        _, fe_views = _run_cmd(
            "find frontend/src/views -name '*.vue' -type f 2>/dev/null | sort",
            self.repo_path,
        )

        # Frontend types (what's exposed)
        _, fe_types = _run_cmd(
            "grep -n 'interface\\|export type' frontend/src/types/api.ts 2>/dev/null | head -30",
            self.repo_path,
        )

        # Frontend router (what routes exist)
        _, fe_routes = _run_cmd(
            "grep -n 'path:\\|name:\\|component:' frontend/src/router/index.ts 2>/dev/null | head -30",
            self.repo_path,
        )

        return {
            "git_log": git_log.strip(),
            "git_diff_from_main": git_diff.strip()[:1000],
            "backend_modules": modules.strip(),
            "existing_tests": tests.strip(),
            "indicators_functions": indicators_code.strip(),
            "portfolio_functions": portfolio_code.strip(),
            "strategy_functions": strategy_code.strip(),
            "frontend_views": fe_views.strip(),
            "frontend_types": fe_types.strip(),
            "frontend_routes": fe_routes.strip(),
            "files_changed_this_session": list(self.all_files_changed),
            "time_remaining_minutes": round(self._time_remaining(), 1),
        }

    # ── Completed work log ────────────────────────────

    def _build_completed_log(self) -> str:
        if not self.completed and not self.failed:
            return "No tasks completed yet this session."
        lines = ["Completed tasks this session:"]
        for i, t in enumerate(self.completed, 1):
            files = ", ".join(t.get("files_changed", [])[:5])
            lines.append(f"  {i}. [{t['task_id']}] \"{t['title']}\" — APPROVED — files: {files}")
        for t in self.failed:
            lines.append(f"  - [{t['task_id']}] \"{t['title']}\" — FAILED — {t.get('failure_reason', '?')[:100]}")
        return "\n".join(lines)

    def _get_completed_feature_ids(self) -> set[str]:
        return {t.get("feature_id", "") for t in self.completed if t.get("feature_id")}

    # ── Available features ────────────────────────────

    def _get_available_features(self) -> list[dict]:
        """Get features not yet completed, filtered by selected tiers."""
        done_ids = self._get_completed_feature_ids()
        failed_ids = {t.get("feature_id", "") for t in self.failed}
        features = []
        for tier_key in self.tiers:
            tier = self.roadmap.get("tiers", {}).get(tier_key, {})
            for f in tier.get("features", []):
                fid = f["id"]
                if fid not in done_ids and fid not in failed_ids:
                    # Check dependencies
                    deps = f.get("depends_on", [])
                    deps_met = all(d in done_ids for d in deps)
                    f_copy = {**f, "tier": tier_key, "deps_met": deps_met}
                    features.append(f_copy)
        return features

    # ── Claude CLI call ───────────────────────────────

    def _call_claude(self, user_prompt: str) -> str:
        """Call Claude CLI with brain prompt as system context. Returns raw text."""
        full_prompt = (
            "<system_instructions>\n"
            + self.brain_prompt
            + "\n</system_instructions>\n\n"
            + user_prompt
        )

        logger.info(f"Calling Claude CLI (prompt: {len(full_prompt)} chars)...")
        try:
            result = subprocess.run(
                "claude --print --output-format json",
                input=full_prompt,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
                encoding="utf-8",
            )
            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr[:500]}")
                return ""

            output = json.loads(result.stdout)
            if output.get("is_error"):
                logger.error(f"Claude CLI returned error: {result.stdout[:500]}")
                return ""

            return output.get("result", "")
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out (300s)")
            return ""
        except Exception as e:
            logger.error(f"Claude CLI exception: {e}")
            return ""

    def _parse_json_response(self, text: str) -> dict | None:
        """Extract JSON from Claude's response."""
        if not text:
            return None
        # Try direct parse
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        # Try markdown code block extraction
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass
        # Try finding JSON object in text
        for i, c in enumerate(text):
            if c == "{":
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[i : j + 1])
                        except json.JSONDecodeError:
                            break
        logger.error(f"Could not parse JSON from response: {text[:500]}")
        return None

    # ── Discover new features ────────────────────────

    def discover_new_features(self, project_state: dict) -> list[dict]:
        """Ask Claude CLI to suggest new features not in the roadmap."""
        logger.info("Roadmap exhausted — discovering new features...")

        prompt = f"""You are the Orchestrator for MarketPulse AI. The existing feature roadmap is exhausted.
Analyze the project state below and suggest 5-8 NEW features that would improve the platform.
Consider: missing tests, UI improvements, new indicators, better error handling, performance,
user experience, data visualization, API enhancements, and features inspired by ProfitTrailer.

## Project State
```
Git log (recent):
{project_state['git_log'][:800]}

Backend modules:
{project_state['backend_modules'][:300]}

Existing tests:
{project_state['existing_tests'][:400]}

Frontend views:
{project_state.get('frontend_views', 'N/A')[:300]}

Frontend routes:
{project_state.get('frontend_routes', 'N/A')[:300]}
```

## Completed Work Log
{self._build_completed_log()}

RESPOND WITH ONLY a JSON array of feature objects:
```json
[
  {{
    "id": "unique_snake_case_id",
    "name": "Feature Name",
    "description": "What to implement (2-3 sentences)",
    "scope": "which files/modules to modify",
    "files_hint": ["path/to/file1.py", "path/to/file2.vue"],
    "complexity": "small|medium|large",
    "depends_on": []
  }}
]
```
Only suggest features that do NOT require database migrations.
Do NOT suggest features already completed this session.
Focus on high-value, achievable tasks."""

        raw = self._call_claude(prompt)
        parsed = self._parse_json_response(raw)

        if parsed and isinstance(parsed, list):
            logger.info(f"Discovered {len(parsed)} new features")
            return parsed
        if parsed and isinstance(parsed, dict) and "features" in parsed:
            features = parsed["features"]
            logger.info(f"Discovered {len(features)} new features")
            return features

        logger.warning("Could not parse discovered features")
        return []

    def _add_discovered_features(self, features: list[dict]) -> None:
        """Add discovered features to roadmap tier 6 (dynamic)."""
        if "6" not in self.roadmap.get("tiers", {}):
            self.roadmap.setdefault("tiers", {})["6"] = {
                "label": "Auto-Discovered",
                "features": [],
            }
        tier6 = self.roadmap["tiers"]["6"]
        existing_ids = {f["id"] for f in tier6["features"]}
        for f in features:
            if f.get("id") and f["id"] not in existing_ids:
                f.setdefault("depends_on", [])
                f.setdefault("complexity", "medium")
                f.setdefault("marketpulse_has", "not implemented")
                tier6["features"].append(f)
                existing_ids.add(f["id"])
        # Also add tier 6 to allowed tiers if not already
        if "6" not in self.tiers:
            self.tiers.append("6")
        logger.info(f"Roadmap now has {len(tier6['features'])} auto-discovered features")

    # ── Plan next task ────────────────────────────────

    def plan_next_task(self, project_state: dict) -> tuple[dict | None, str]:
        """Ask Claude to pick next feature and generate task_spec. Returns (task_spec, feature_id)."""
        available = self._get_available_features()
        if not available:
            # Try discovering new features before giving up
            new_features = self.discover_new_features(project_state)
            if new_features:
                self._add_discovered_features(new_features)
                available = self._get_available_features()
            if not available:
                logger.info("No more features available even after discovery.")
                return None, ""

        # Build concise feature list for prompt
        feature_lines = []
        for f in available:
            deps_note = " (DEPS NOT MET)" if not f["deps_met"] else ""
            feature_lines.append(
                f"- [{f['tier']}] {f['id']}: {f['name']} — {f['complexity']}{deps_note}\n"
                f"  {f['description'][:150]}\n"
                f"  scope: {f['scope'][:150]}\n"
                f"  files_hint: {f.get('files_hint', [])}"
            )

        prompt = f"""Plan the next task for MarketPulse AI.

## Project State
```
Recent git log:
{project_state['git_log'][:1000]}

Existing tests:
{project_state['existing_tests'][:500]}

Indicator functions:
{project_state['indicators_functions'][:500]}

Portfolio functions:
{project_state['portfolio_functions'][:500]}

Strategy functions:
{project_state['strategy_functions'][:500]}

Frontend views:
{project_state.get('frontend_views', 'N/A')[:300]}

Frontend types:
{project_state.get('frontend_types', 'N/A')[:300]}

Frontend routes:
{project_state.get('frontend_routes', 'N/A')[:300]}

Files changed this session:
{project_state['files_changed_this_session']}
```

## Completed Work Log
{self._build_completed_log()}

## Available Features (pick ONE)
{chr(10).join(feature_lines)}

## Time Remaining: {project_state['time_remaining_minutes']} minutes

Pick the highest-value feature that:
1. Has all dependencies met (deps_met=True)
2. Fits within remaining time ({project_state['time_remaining_minutes']} min)
3. Has NOT been completed this session
4. Is smallest complexity first within its tier

Generate a complete task_spec JSON. Use task_id: {self._gen_task_id()}

RESPOND WITH ONLY A JSON OBJECT matching the schema from your system instructions.
"""

        raw = self._call_claude(prompt)
        parsed = self._parse_json_response(raw)

        if not parsed:
            logger.error("Failed to get valid JSON from Claude for task planning")
            return None, ""

        action = parsed.get("action", "create_task")
        if action == "stop":
            logger.info(f"Orchestrator decided to stop: {parsed.get('reason', '?')}")
            return None, ""

        task_spec = parsed.get("task_spec")
        feature_id = parsed.get("feature_id", "")

        if not task_spec or not isinstance(task_spec, dict):
            logger.error(f"No valid task_spec in response: {parsed}")
            return None, ""

        # Ensure required fields
        task_spec.setdefault("forbidden_paths", [".env", "infra/", "secrets/", "backend/alembic/"])
        task_spec.setdefault("authorization", {
            "level": "auto_approve",
            "deploy_allowed": False,
            "allowed_actions": ["read_file", "write_file", "git_commit", "run_tests", "lint_check"],
            "forbidden_actions": ["deploy", "access_secrets", "call_broker_api"],
            "audit_required": True,
            "max_iterations": 5,
        })

        return task_spec, feature_id

    # ── Dispatch to Coder ─────────────────────────────

    def dispatch_to_coder(self, task_spec_path: str) -> dict:
        """Run coder_worker.py with --use-max."""
        coder_script = str(ORCHESTRATOR_ROOT / "workers" / "coder_worker.py")
        cmd = [
            PYTHON, coder_script,
            "--task", task_spec_path,
            "--repo", self.repo_path,
            "--base", "main",
            "--use-max",
            "--max-tokens", "64000",
            "--max-calls", "5",
        ]
        if self.dry_run:
            cmd.append("--dry-run")

        logger.info(f"Dispatching to Coder Worker (--use-max)...")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1200,
                encoding="utf-8", errors="replace",
            )
            stdout = result.stdout
            # Extract JSON from output
            if "{" in stdout:
                marker = "--- Worker Report ---"
                json_end = stdout.index(marker) if marker in stdout else len(stdout)
                json_start = stdout.index("{")
                return json.loads(stdout[json_start:json_end].strip())
            return {"error": f"No JSON in coder output: {stdout[:300]}", "next_recommended_step": "revise"}
        except subprocess.TimeoutExpired:
            return {"error": "Coder timed out (600s)", "next_recommended_step": "revise"}
        except Exception as e:
            return {"error": str(e)[:500], "next_recommended_step": "revise"}

    # ── Dispatch to Validator ─────────────────────────

    def dispatch_to_validator(self, task_spec_path: str) -> dict:
        """Run validator.py."""
        validator_script = str(ORCHESTRATOR_ROOT / "validator.py")
        cmd = [
            PYTHON, validator_script,
            "--task-spec", task_spec_path,
            "--repo", self.repo_path,
            "--base", "main",
        ]

        logger.info("Dispatching to Validator...")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            stdout = result.stdout
            if "{" in stdout:
                marker = "\n---"
                json_start = stdout.index("{")
                json_end = stdout.index(marker, json_start) if marker in stdout[json_start:] else len(stdout)
                return json.loads(stdout[json_start:json_end].strip())
            return {"error": f"No JSON: {stdout[:300]}", "verdict": "revise"}
        except Exception as e:
            return {"error": str(e)[:500], "verdict": "revise"}

    # ── Process feedback ──────────────────────────────

    def process_feedback(self, validator_result: dict, attempt: int) -> str:
        """Decide: 'next', 'retry', or 'stop'."""
        verdict = validator_result.get("verdict", "revise")

        if verdict == "approve":
            return "next"
        if verdict == "reject":
            return "next"  # Don't retry rejects
        # revise
        if attempt < self.max_retries:
            return "retry"
        return "next"  # Out of retries

    # ── Main loop ─────────────────────────────────────

    def run_loop(self, single_task: bool = False) -> dict:
        """Main orchestration loop. Returns session report dict."""
        logger.info(f"Starting orchestration loop (max {self.max_minutes} min)")

        iteration = 0
        while self._should_continue():
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"[{_ts()}] Iteration {iteration} | "
                         f"Elapsed: {self._elapsed_min():.1f} min | "
                         f"Remaining: {self._time_remaining():.1f} min | "
                         f"Completed: {len(self.completed)} | Failed: {len(self.failed)}")

            # 1. Research
            project_state = self.research_project()

            # 2. Plan next task
            task_spec, feature_id = self.plan_next_task(project_state)
            if not task_spec:
                logger.info("No more tasks to do. Stopping.")
                break

            task_id = task_spec.get("task_id", self._gen_task_id())
            title = task_spec.get("title", "?")
            logger.info(f"[{_ts()}] Task: {task_id} — {title} (feature: {feature_id})")

            # 3. Write task_spec to logs/ (untracked) to avoid git conflicts
            session_task_dir = LOG_DIR / f"tasks_{self.session_id}"
            session_task_dir.mkdir(parents=True, exist_ok=True)
            task_path = session_task_dir / f"task_{task_id}.json"
            task_path.write_text(json.dumps(task_spec, indent=2, ensure_ascii=False), encoding="utf-8")

            # 4. Clean git state so Coder can create fresh branches
            #    Reset tracked files to HEAD, remove untracked (except logs/)
            _run_cmd("git checkout main", self.repo_path)
            _run_cmd("git checkout -- .", self.repo_path)
            _run_cmd("git clean -fd --exclude=logs/", self.repo_path)

            # 5. Coder → Validator loop
            task_result = {
                "task_id": task_id,
                "feature_id": feature_id,
                "title": title,
                "files_changed": [],
                "coder_verdict": "",
                "validator_verdict": "",
                "retries": 0,
            }

            for attempt in range(1 + self.max_retries):
                if not self._should_continue():
                    logger.info("Time limit approaching. Stopping mid-task.")
                    break

                if attempt > 0:
                    logger.info(f"  [{_ts()}] Retry {attempt}/{self.max_retries}")
                    task_result["retries"] = attempt

                # Dispatch to Coder
                coder_result = self.dispatch_to_coder(str(task_path))
                task_result["coder_verdict"] = coder_result.get("next_recommended_step", "error")
                task_result["files_changed"] = coder_result.get("files_changed", [])

                logger.info(f"  [{_ts()}] Coder: {task_result['coder_verdict']} | "
                             f"Files: {task_result['files_changed']} | "
                             f"Tests: {coder_result.get('tests', {}).get('summary', '?')}")

                if coder_result.get("error") and not coder_result.get("files_changed"):
                    logger.warning(f"  Coder error: {coder_result['error'][:200]}")
                    task_result["validator_verdict"] = "error"
                    task_result["failure_reason"] = coder_result.get("error", "")[:200]
                    continue

                # Dispatch to Validator
                if not self._should_continue():
                    break

                validator_result = self.dispatch_to_validator(str(task_path))
                verdict = validator_result.get("verdict", "error")
                task_result["validator_verdict"] = verdict

                logger.info(f"  [{_ts()}] Validator: {verdict}")
                if validator_result.get("issues"):
                    for iss in validator_result["issues"][:3]:
                        logger.info(f"    [{iss.get('severity')}] {iss.get('area', '?')}: "
                                     f"{iss.get('description', '?')[:80]}")

                action = self.process_feedback(validator_result, attempt)

                if action == "next":
                    break
                # action == "retry" → continue loop

            # Record result
            if task_result["validator_verdict"] == "approve":
                self.completed.append(task_result)
                self.all_files_changed.update(task_result.get("files_changed", []))
                logger.info(f"  [{_ts()}] APPROVED ✓")
            else:
                task_result.setdefault("failure_reason",
                                        f"validator: {task_result['validator_verdict']}")
                self.failed.append(task_result)
                logger.info(f"  [{_ts()}] FAILED ✗ — {task_result['failure_reason'][:100]}")

            # Save session state
            self._save_state()

            if single_task:
                logger.info("Single-task mode. Stopping after first task.")
                break

        return self._build_report()

    # ── State persistence ─────────────────────────────

    def _save_state(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "session_id": self.session_id,
            "elapsed_minutes": round(self._elapsed_min(), 1),
            "completed": self.completed,
            "failed": self.failed,
            "files_changed": list(self.all_files_changed),
        }
        path = LOG_DIR / f"orchestrator_state_{self.session_id}.json"
        path.write_text(json.dumps(state, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    # ── Report generation ─────────────────────────────

    def _build_report(self) -> dict:
        """Build session report as dict and markdown."""
        end_time = datetime.datetime.now(datetime.timezone.utc)
        elapsed = round(self._elapsed_min(), 1)

        report = {
            "session_id": self.session_id,
            "elapsed_minutes": elapsed,
            "max_minutes": self.max_minutes,
            "tiers": self.tiers,
            "dry_run": self.dry_run,
            "completed_count": len(self.completed),
            "failed_count": len(self.failed),
            "files_changed": sorted(self.all_files_changed),
            "completed_tasks": self.completed,
            "failed_tasks": self.failed,
        }

        # Markdown report
        lines = [
            f"# MarketPulse AI — Orchestrator Session Report",
            "",
            f"**Session:** {self.session_id}",
            f"**Czas trwania:** {elapsed:.1f} min / {self.max_minutes} min",
            f"**Tryb:** {'DRY RUN' if self.dry_run else 'LIVE'} | LLM: Claude MAX (claude CLI)",
            f"**Tiery:** {', '.join(self.tiers)}",
            f"**Koszt API:** $0.00",
            "",
            "---",
            "## Podsumowanie",
            "",
            f"| Metryka | Wartość |",
            f"|---------|---------|",
            f"| Completed | {len(self.completed)} |",
            f"| Failed | {len(self.failed)} |",
            f"| Files changed | {len(self.all_files_changed)} |",
            "",
        ]

        if self.completed:
            lines += [
                "---",
                "## Zrealizowane taski",
                "",
                "| # | Feature | Task ID | Files | Retries |",
                "|---|---------|---------|-------|---------|",
            ]
            for i, t in enumerate(self.completed, 1):
                files = ", ".join(f"`{f}`" for f in t.get("files_changed", [])[:3])
                lines.append(f"| {i} | {t['title'][:40]} | {t['task_id']} | {files} | {t.get('retries', 0)} |")
            lines.append("")

        if self.failed:
            lines += [
                "---",
                "## Nieudane taski",
                "",
                "| Feature | Reason |",
                "|---------|--------|",
            ]
            for t in self.failed:
                lines.append(f"| {t['title'][:40]} | {t.get('failure_reason', '?')[:60]} |")
            lines.append("")

        if self.all_files_changed:
            lines += [
                "---",
                "## Zmienione pliki",
                "",
            ]
            for f in sorted(self.all_files_changed):
                lines.append(f"- `{f}`")
            lines.append("")

        lines += [
            "---",
            f"*Raport wygenerowany: {end_time.strftime('%Y-%m-%d %H:%M UTC')}*",
        ]

        report["markdown"] = "\n".join(lines)
        return report
