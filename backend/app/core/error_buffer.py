"""In-memory ring buffer for recent errors. Used by /diagnostics/errors."""

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


_MAX_ENTRIES = 100
_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
_lock = threading.Lock()


def record_error(
    event: str,
    error: str,
    request_id: str | None = None,
    **extra: Any,
) -> None:
    """Add an error entry to the ring buffer."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "error": error[:500],
        "request_id": request_id,
        **{k: str(v)[:200] for k, v in extra.items()},
    }
    with _lock:
        _buffer.append(entry)


def get_recent_errors(limit: int = 50) -> list[dict[str, Any]]:
    """Return most recent errors, newest first."""
    with _lock:
        items = list(_buffer)
    items.reverse()
    return items[:limit]


def error_count() -> int:
    with _lock:
        return len(_buffer)
