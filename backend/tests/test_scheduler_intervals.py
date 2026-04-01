"""Tests for scheduler multi-timeframe ingestion loops.

Verifies that start_scheduler creates 6 tasks (1h, 4h, 1d for crypto and stock),
get_scheduler_status reports on all of them, and stop_scheduler cancels all.

Task: marketpulse-task-2026-04-01-0005
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


EXPECTED_JOB_NAMES = [
    "ingest_crypto_1h",
    "ingest_stock_1h",
    "ingest_crypto_4h",
    "ingest_stock_4h",
    "ingest_crypto_1d",
    "ingest_stock_1d",
]


@pytest.fixture(autouse=True)
def _clear_scheduler_state():
    """Reset scheduler module-level state between tests."""
    from app import scheduler
    scheduler._tasks.clear()
    scheduler._job_stats.clear()
    yield
    scheduler._tasks.clear()
    scheduler._job_stats.clear()


@pytest.mark.asyncio
async def test_start_scheduler_creates_six_tasks():
    """start_scheduler() should create exactly 6 asyncio tasks."""
    created_coroutines: list = []

    def fake_create_task(coro):
        # Cancel the coroutine to avoid it actually running
        coro.close()
        mock_task = MagicMock(spec=asyncio.Task)
        created_coroutines.append(mock_task)
        return mock_task

    with (
        patch("app.scheduler.settings") as mock_settings,
        patch("asyncio.create_task", side_effect=fake_create_task),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGESTION_INTERVAL_MINUTES = 5

        from app.scheduler import start_scheduler, _tasks
        await start_scheduler()

        assert len(_tasks) == 6, f"Expected 6 tasks, got {len(_tasks)}"


@pytest.mark.asyncio
async def test_start_scheduler_correct_job_names():
    """All 6 expected job names should appear in _periodic_loop calls."""
    captured_calls: list[tuple] = []

    original_periodic_loop = None

    async def fake_periodic_loop(job_name: str, interval_str: str, asset_class: str, interval_seconds: int):
        captured_calls.append((job_name, interval_str, asset_class, interval_seconds))

    def fake_create_task(coro):
        # Run the coroutine to capture args, then close
        # Since fake_periodic_loop returns immediately, we can extract info
        mock_task = MagicMock(spec=asyncio.Task)
        # We need to actually run the coro to capture args
        loop = asyncio.get_event_loop()
        loop.run_until_complete(coro)
        return mock_task

    with (
        patch("app.scheduler.settings") as mock_settings,
        patch("app.scheduler._periodic_loop", side_effect=fake_periodic_loop) as mock_loop,
        patch("asyncio.create_task") as mock_create_task,
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGESTION_INTERVAL_MINUTES = 5
        mock_create_task.side_effect = lambda coro: (coro.close(), MagicMock(spec=asyncio.Task))[1]

        from app.scheduler import start_scheduler, _tasks
        _tasks.clear()
        await start_scheduler()

        # Extract job names from the calls to _periodic_loop
        call_args_list = mock_loop.call_args_list
        job_names = [call.args[0] if call.args else call.kwargs.get("job_name") for call in call_args_list]

        for expected in EXPECTED_JOB_NAMES:
            assert expected in job_names, f"Missing job: {expected}. Got: {job_names}"


@pytest.mark.asyncio
async def test_4h_jobs_use_correct_interval():
    """4h jobs should use interval_seconds=14400."""
    mock_loop = AsyncMock()

    def _close_safe(coro):
        if hasattr(coro, 'close'):
            coro.close()
        return MagicMock(spec=asyncio.Task)

    with (
        patch("app.scheduler.settings") as mock_settings,
        patch("app.scheduler._periodic_loop", mock_loop),
        patch("asyncio.create_task", side_effect=_close_safe),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGESTION_INTERVAL_MINUTES = 5

        from app.scheduler import _tasks
        _tasks.clear()
        from app.scheduler import start_scheduler
        await start_scheduler()

        for call in mock_loop.call_args_list:
            job_name = call.args[0]
            interval_sec = call.args[3]
            if "4h" in job_name:
                assert interval_sec == 14400, f"{job_name} should have interval 14400, got {interval_sec}"


@pytest.mark.asyncio
async def test_1d_jobs_use_correct_interval():
    """1d jobs should use interval_seconds=86400."""
    mock_loop = AsyncMock()

    def _close_safe(coro):
        if hasattr(coro, 'close'):
            coro.close()
        return MagicMock(spec=asyncio.Task)

    with (
        patch("app.scheduler.settings") as mock_settings,
        patch("app.scheduler._periodic_loop", mock_loop),
        patch("asyncio.create_task", side_effect=_close_safe),
    ):
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.INGESTION_INTERVAL_MINUTES = 5

        from app.scheduler import _tasks
        _tasks.clear()
        from app.scheduler import start_scheduler
        await start_scheduler()

        for call in mock_loop.call_args_list:
            job_name = call.args[0]
            interval_sec = call.args[3]
            if "1d" in job_name:
                assert interval_sec == 86400, f"{job_name} should have interval 86400, got {interval_sec}"


@pytest.mark.asyncio
async def test_scheduler_disabled_creates_no_tasks():
    """When SCHEDULER_ENABLED=False, no tasks should be created."""
    with patch("app.scheduler.settings") as mock_settings:
        mock_settings.SCHEDULER_ENABLED = False

        from app.scheduler import start_scheduler, _tasks
        _tasks.clear()
        await start_scheduler()

        assert len(_tasks) == 0, f"Expected 0 tasks when disabled, got {len(_tasks)}"


def test_stop_scheduler_cancels_all_tasks():
    """stop_scheduler() should cancel all tasks and clear _tasks list."""
    from app.scheduler import stop_scheduler, _tasks

    mock_tasks = [MagicMock(spec=asyncio.Task) for _ in range(6)]
    _tasks.extend(mock_tasks)

    stop_scheduler()

    for t in mock_tasks:
        t.cancel.assert_called_once()
    assert len(_tasks) == 0


def test_get_scheduler_status_reports_all_jobs():
    """get_scheduler_status() should report on all tracked jobs."""
    from datetime import datetime, timezone
    from app.scheduler import get_scheduler_status, _job_stats, _tasks

    now = datetime.now(timezone.utc)

    for name in EXPECTED_JOB_NAMES:
        _job_stats[name] = {
            "run_count": 1,
            "error_count": 0,
            "last_started_at": now,
            "last_completed_at": now,
        }
    # Simulate 6 running tasks
    _tasks.extend([MagicMock(spec=asyncio.Task) for _ in range(6)])

    status = get_scheduler_status()

    assert status["running"] is True
    assert status["task_count"] == 6
    for name in EXPECTED_JOB_NAMES:
        assert name in status["jobs"], f"Missing job {name} in status"
        assert status["jobs"][name]["run_count"] == 1
