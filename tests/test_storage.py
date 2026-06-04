"""存储模块单元测试"""

import json
import tempfile
from datetime import date
from pathlib import Path

from cli.storage import Storage, ConfigManager
from cli.models import DailyReport, DailyEntry, EntrySource, Config


class TestStorage:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage = Storage(data_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_entry(self, content: str, **kwargs) -> DailyEntry:
        return DailyEntry(content=content, source=EntrySource.MANUAL, **kwargs)

    def test_save_and_load(self):
        report = DailyReport(
            date="2026-06-04",
            day_of_week="星期四",
            entries=[self._make_entry("测试工作")],
        )
        self.storage.save_daily_report(report)

        loaded = self.storage.load_daily_report(date(2026, 6, 4))
        assert loaded is not None
        assert loaded.entries[0].content == "测试工作"

    def test_report_exists(self):
        assert not self.storage.report_exists(date(2026, 6, 4))
        report = DailyReport(date="2026-06-04", day_of_week="星期四")
        self.storage.save_daily_report(report)
        assert self.storage.report_exists(date(2026, 6, 4))

    def test_delete_report(self):
        report = DailyReport(date="2026-06-04", day_of_week="星期四")
        self.storage.save_daily_report(report)
        assert self.storage.report_exists(date(2026, 6, 4))
        self.storage.delete_daily_report(date(2026, 6, 4))
        assert not self.storage.report_exists(date(2026, 6, 4))

    def test_upsert_entry_new(self):
        entry = self._make_entry("新条目")
        self.storage.upsert_entry(date(2026, 6, 4), entry)

        report = self.storage.load_daily_report(date(2026, 6, 4))
        assert len(report.entries) == 1
        assert report.entries[0].content == "新条目"

    def test_upsert_entry_update(self):
        entry = self._make_entry("原始内容")
        self.storage.upsert_entry(date(2026, 6, 4), entry)

        # 修改内容
        entry.content = "修改后内容"
        self.storage.upsert_entry(date(2026, 6, 4), entry)

        report = self.storage.load_daily_report(date(2026, 6, 4))
        assert len(report.entries) == 1
        assert report.entries[0].content == "修改后内容"

    def test_remove_entry(self):
        entry = self._make_entry("要删除的")
        self.storage.upsert_entry(date(2026, 6, 4), entry)
        assert self.storage.report_exists(date(2026, 6, 4))

        assert self.storage.remove_entry(date(2026, 6, 4), entry.id)
        report = self.storage.load_daily_report(date(2026, 6, 4))
        assert len(report.entries) == 0

    def test_remove_nonexistent_entry(self):
        assert not self.storage.remove_entry(date(2026, 6, 4), "no-such-id")

    def test_load_week_reports(self):
        monday = date(2026, 6, 1)
        for i in range(3):
            d = monday + date.resolution * i
            report = DailyReport(date=d.isoformat(), day_of_week="星期" + str(d.weekday() + 1))
            self.storage.save_daily_report(report)

        reports = self.storage.load_week_reports(week_start=monday)
        assert len(reports) == 3

    def test_load_month_reports(self):
        for day in [1, 15, 28]:
            d = date(2026, 6, day)
            report = DailyReport(date=d.isoformat(), day_of_week="")
            self.storage.save_daily_report(report)

        reports = self.storage.load_month_reports(2026, 6)
        assert len(reports) == 3

    def test_list_all_report_dates(self):
        for d in [date(2026, 6, 1), date(2026, 6, 4)]:
            report = DailyReport(date=d.isoformat(), day_of_week="")
            self.storage.save_daily_report(report)

        dates = self.storage.list_all_report_dates()
        assert len(dates) == 2
        assert date(2026, 6, 1) in dates

    def test_update_notes(self):
        report = DailyReport(date="2026-06-04", day_of_week="星期四")
        self.storage.save_daily_report(report)

        self.storage.update_notes(date(2026, 6, 4), "新备注")
        loaded = self.storage.load_daily_report(date(2026, 6, 4))
        assert loaded.extra_notes == "新备注"


class TestConfigManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = ConfigManager(data_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_default_config(self):
        config = self.manager.load_config()
        assert isinstance(config, Config)
        assert config.report_language == "zh"

    def test_save_and_load(self):
        config = Config(git_author="test-user", scan_repos=["/test"])
        self.manager.save_config(config)

        loaded = self.manager.load_config()
        assert loaded.git_author == "test-user"
        assert loaded.scan_repos == ["/test"]
