"""调度模块单元测试"""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from cli.scheduler import (
    load_schedule_state,
    save_schedule_state,
    catchup_daily_reports,
    run_catchup,
)
from cli.models import Config, DailyReport, DailyEntry, EntrySource
from cli.storage import Storage


class TestScheduleState:
    def test_load_state_not_exists(self, tmp_path):
        data_dir = str(tmp_path)
        state = load_schedule_state(data_dir)
        assert state["last_daily_check"] is None
        assert state["last_weekly_check"] is None

    def test_save_and_load(self, tmp_path):
        data_dir = str(tmp_path)
        state = {
            "last_daily_check": "2026-06-04",
            "last_weekly_check": "2026-06-01",
        }
        save_schedule_state(data_dir, state)

        loaded = load_schedule_state(data_dir)
        assert loaded["last_daily_check"] == "2026-06-04"
        assert loaded["last_weekly_check"] == "2026-06-01"


class TestCatchupDailyReports:
    def test_no_missing_reports(self, tmp_path):
        data_dir = str(tmp_path)
        storage = Storage(data_dir=data_dir)
        config = Config()

        # No repos configured, so no commits found
        generated = catchup_daily_reports(
            storage, config,
            from_date=date(2026, 6, 1),
            to_date=date(2026, 6, 1),
        )
        assert generated == []

    def test_skips_weekends(self, tmp_path):
        data_dir = str(tmp_path)
        storage = Storage(data_dir=data_dir)
        config = Config()

        # Saturday 2026-06-06
        generated = catchup_daily_reports(
            storage, config,
            from_date=date(2026, 6, 6),
            to_date=date(2026, 6, 6),
        )
        # Weekend skipped, no repos, no commits
        assert generated == []

    def test_skips_existing_reports(self, tmp_path):
        data_dir = str(tmp_path)
        storage = Storage(data_dir=data_dir)
        config = Config()

        # Save a report for June 4
        report = DailyReport(
            date="2026-06-04",
            day_of_week="星期四",
            entries=[DailyEntry(
                content="existing work",
                source=EntrySource.MANUAL,
            )],
        )
        storage.save_daily_report(report)

        # Catch up should not regenerate
        generated = catchup_daily_reports(
            storage, config,
            from_date=date(2026, 6, 4),
            to_date=date(2026, 6, 4),
        )
        assert generated == []  # already exists


class TestRunCatchup:
    def test_run_catchup_returns_status(self, tmp_path):
        data_dir = str(tmp_path)
        storage = Storage(data_dir=data_dir)
        config = Config()

        result = run_catchup(storage, config)
        assert result["status"] == "ok"
        assert isinstance(result["daily_generated"], list)
        assert "last_daily_check" in result
        assert "last_weekly_check" in result

    def test_run_catchup_updates_state(self, tmp_path):
        data_dir = str(tmp_path)
        storage = Storage(data_dir=data_dir)
        config = Config()

        run_catchup(storage, config)

        # State should be updated
        state = load_schedule_state(data_dir)
        assert state["last_daily_check"] is not None
