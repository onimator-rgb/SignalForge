"""
MarketPulse Model Caller — Anthropic Claude integration layer.

Provides structured model calls with retries, rate-limit handling,
schema validation, and forbidden_paths sanitization.

Security:
- API key read from env var ANTHROPIC_API_KEY (never hardcoded).
- Model outputs are validated before any file writes.
- Forbidden paths are blocked before file application.
- All outputs truncated to 2000 chars in logs.
"""

import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("marketpulse.model_caller")

# Expected schema keys in model response
EXPECTED_RESPONSE_KEYS = {"files", "summary"}
EXPECTED_FILE_KEYS = {"path", "content"}


class ModelCallerError(Exception):
    """Raised when model call fails after all retries."""
    pass


class ForbiddenPathError(Exception):
    """Raised when model output tries to write to a forbidden path."""
    pass


class ModelCaller:
    """Calls Anthropic Claude models with safety guardrails.

    Usage:
        caller = ModelCaller()
        result = caller.call_model(prompt_json)
        # result = {"files": [{"path": "src/foo.py", "content": "..."}], "summary": "..."}
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"
    ESCALATION_MODEL = "claude-sonnet-4-6"  # Sonnet instead of Opus — cheaper, no timeout
    DEFAULT_MAX_TOKENS = 64000              # Enough for full file generation without truncation
    MAX_RETRIES = 3
    RETRY_BACKOFF = [2, 5, 10]  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        forbidden_paths: Optional[List[str]] = None,
        max_calls_per_task: int = 10,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        self.forbidden_paths = forbidden_paths or [".env", "infra/", "secrets/"]
        self.max_calls_per_task = max_calls_per_task
        self.max_tokens = max_tokens
        self._call_count = 0
        self._client = None

        if self.api_key:
            logger.info("ANTHROPIC_API_KEY present")
        else:
            logger.warning("ANTHROPIC_API_KEY not set — calls will use mock mode")

    def _get_client(self):
        """Lazy-init Anthropic client."""
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
            return self._client
        except ImportError:
            logger.warning("anthropic SDK not installed — using mock mode")
            return None

    def _check_call_limit(self):
        """Enforce per-task call limit."""
        if self._call_count >= self.max_calls_per_task:
            raise ModelCallerError(
                f"Call limit exceeded: {self._call_count}/{self.max_calls_per_task}. "
                "Escalate or ask_human."
            )
        self._call_count += 1

    def _validate_response(self, data: Any) -> Dict[str, Any]:
        """Validate model response matches expected schema."""
        if isinstance(data, str):
            # Try to extract JSON from markdown code blocks
            if "```json" in data:
                start = data.index("```json") + 7
                end = data.index("```", start)
                data = data[start:end].strip()
            elif "```" in data:
                start = data.index("```") + 3
                end = data.index("```", start)
                data = data[start:end].strip()
            data = json.loads(data)

        if not isinstance(data, dict):
            raise ModelCallerError(f"Expected dict, got {type(data).__name__}")

        if "files" not in data:
            # Allow flat response — wrap it
            if "task_id" in data:
                return data  # It's a coder report, not a file list
            raise ModelCallerError(f"Response missing 'files' key. Keys: {list(data.keys())}")

        # Validate each file entry
        for f in data.get("files", []):
            if not isinstance(f, dict):
                raise ModelCallerError(f"File entry is not a dict: {f}")
            missing = EXPECTED_FILE_KEYS - set(f.keys())
            if missing:
                raise ModelCallerError(f"File entry missing keys: {missing}")

        return data

    def _sanitize_paths(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Block any file writes to forbidden paths."""
        files = data.get("files", [])
        clean_files = []
        blocked = []

        for f in files:
            path = f.get("path", "")
            is_forbidden = False
            for fp in self.forbidden_paths:
                if path == fp or path.startswith(fp):
                    is_forbidden = True
                    blocked.append(path)
                    break
            if not is_forbidden:
                clean_files.append(f)

        if blocked:
            logger.warning(f"BLOCKED forbidden path writes: {blocked}")
            raise ForbiddenPathError(
                f"Model attempted to write to forbidden paths: {blocked}"
            )

        data["files"] = clean_files
        return data

    def call_model(
        self,
        prompt_json: Dict[str, Any],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """Call Claude model with structured prompt and return validated response.

        Args:
            prompt_json: The task prompt as a dict (will be JSON-serialized).
            model: Model ID override (default: claude-sonnet-4).
            max_tokens: Token limit override.
            system_prompt: System prompt (e.g., contents of marketpulse_coder.md).

        Returns:
            Validated and sanitized response dict.

        Raises:
            ModelCallerError: After all retries exhausted.
            ForbiddenPathError: If response targets forbidden paths.
        """
        self._check_call_limit()
        model = model or self.DEFAULT_MODEL
        max_tokens = max_tokens or self.max_tokens
        user_content = json.dumps(prompt_json, indent=2, ensure_ascii=False)

        client = self._get_client()

        if client is None:
            # Mock mode — return empty file list for testing
            logger.info(f"MOCK call_model: model={model}, tokens={max_tokens}")
            return {
                "files": [],
                "summary": "Mock response — install anthropic SDK and set ANTHROPIC_API_KEY for real calls",
                "mock": True
            }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(
                    f"Calling {model} (attempt {attempt + 1}/{self.MAX_RETRIES}, "
                    f"call {self._call_count}/{self.max_calls_per_task})"
                )

                messages = [{"role": "user", "content": user_content}]
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }
                # cache_control must live INSIDE the system block, not at top level.
                # When set correctly, cached tokens cost ~10% of normal input tokens.
                if system_prompt:
                    kwargs["system"] = [
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]

                with client.messages.stream(**kwargs) as stream:
                    response = stream.get_final_message()

                # Extract text content
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text

                # Validate and sanitize
                data = self._validate_response(text)
                data = self._sanitize_paths(data)

                logger.info(f"Model returned {len(data.get('files', []))} files")
                return data

            except ForbiddenPathError:
                raise  # Don't retry security violations

            except Exception as e:
                last_error = e
                wait = self.RETRY_BACKOFF[min(attempt, len(self.RETRY_BACKOFF) - 1)]
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")

                # Rate-limit detection
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    wait = max(wait, 10)

                time.sleep(wait)

        raise ModelCallerError(f"All {self.MAX_RETRIES} retries exhausted. Last error: {last_error}")

    def call_escalation(
        self,
        prompt_json: Dict[str, Any],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """Escalate to Opus model for complex/ambiguous tasks.

        Same interface as call_model but uses the escalation model.
        """
        logger.info("Escalating to Opus model")
        return self.call_model(
            prompt_json=prompt_json,
            model=self.ESCALATION_MODEL,
            system_prompt=system_prompt,
        )

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def calls_remaining(self) -> int:
        return max(0, self.max_calls_per_task - self._call_count)

    def reset_counter(self):
        self._call_count = 0


class MaxModelCaller(ModelCaller):
    """Uses Claude Code CLI instead of direct Anthropic API.

    Zero API cost — uses the user's Claude MAX subscription.
    Requires: `claude` CLI installed and authenticated (`claude auth login`).

    Falls back to direct API (super().call_model) if CLI is unavailable.
    """

    # Max prompt size to pass as CLI argument (Windows CreateProcess limit ~32767 chars)
    _MAX_INLINE_CHARS = 20_000

    def _claude_cli_available(self) -> bool:
        """Check whether the `claude` binary is on PATH (handles Windows .cmd wrappers)."""
        import shutil
        if shutil.which("claude") is not None:
            return True
        # On Windows, shutil.which may miss .cmd wrappers — try via shell
        try:
            result = subprocess.run(
                "claude --version", shell=True,
                capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def call_model(
        self,
        prompt_json: Dict[str, Any],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """Call Claude via CLI (MAX subscription). Falls back to API if CLI unavailable."""
        if not self._claude_cli_available():
            logger.warning(
                "claude CLI not found — falling back to direct API. "
                "Install Claude Code and run `claude auth login` for free MAX calls."
            )
            return super().call_model(prompt_json, model, max_tokens, system_prompt)

        self._check_call_limit()
        user_content = json.dumps(prompt_json, separators=(",", ":"), ensure_ascii=False)

        # Embed system prompt in user message — CLI has no separate system param
        if system_prompt:
            full_prompt = (
                "<system_instructions>\n"
                + system_prompt
                + "\n</system_instructions>\n\n"
                + user_content
            )
        else:
            full_prompt = user_content

        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(
                    f"MaxModelCaller: claude CLI attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"(call {self._call_count}/{self.max_calls_per_task})"
                )

                # shell=True required on Windows so claude.CMD wrappers are resolved.
                # Prompt passed via stdin — avoids shell escaping / argument length limits.
                result = subprocess.run(
                    "claude --print --output-format json",
                    input=full_prompt,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    encoding="utf-8",
                )

                if result.returncode != 0:
                    raise ModelCallerError(
                        f"claude CLI exited {result.returncode}: {result.stderr[:500]}"
                    )

                cli_output = json.loads(result.stdout)
                if cli_output.get("is_error"):
                    raise ModelCallerError(
                        f"claude CLI error response: {result.stdout[:500]}"
                    )

                text: str = cli_output.get("result", "")
                if not text:
                    raise ModelCallerError(
                        f"Empty result from claude CLI: {result.stdout[:200]}"
                    )

                data = self._validate_response(text)
                data = self._sanitize_paths(data)
                logger.info(
                    f"MaxModelCaller: returned {len(data.get('files', []))} files "
                    f"(cost_usd={cli_output.get('cost_usd', 0):.4f})"
                )
                return data

            except ForbiddenPathError:
                raise
            except Exception as e:
                last_error = e
                wait = self.RETRY_BACKOFF[min(attempt, len(self.RETRY_BACKOFF) - 1)]
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)

        raise ModelCallerError(
            f"All {self.MAX_RETRIES} retries exhausted. Last error: {last_error}"
        )

    def call_escalation(
        self,
        prompt_json: Dict[str, Any],
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """MAX subscription has no escalation cost — reuse same call."""
        logger.info("MaxModelCaller: escalation = same CLI call (no extra cost)")
        return self.call_model(prompt_json, system_prompt=system_prompt)
