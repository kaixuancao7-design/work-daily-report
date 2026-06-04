"""JSON 文件存储模块

管理日报数据的持久化，包括：
- 日报的保存、加载、删除
- 单条目的增删改
- 按周 / 月加载报告
- 全局配置管理
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from cli.models import DailyReport, DailyEntry, Config
from cli.utils import parse_date


class Storage:
    """日报持久化管理"""

    def __init__(self, data_dir: str = "./data"):
        base = Path(data_dir).resolve()
        self.reports_dir = base / "daily-reports"
        self.config_path = base / "config.json"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保数据目录存在"""
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _report_path(self, report_date: date) -> Path:
        """返回日报 JSON 文件路径: data/daily-reports/2026/06/2026-06-04.json"""
        year_dir = self.reports_dir / str(report_date.year)
        month_dir = year_dir / f"{report_date.month:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir / f"{report_date.isoformat()}.json"

    # ─── 日报级别操作 ──────────────────────────────

    def save_daily_report(self, report: DailyReport):
        """保存日报（如果已存在则覆盖）"""
        from datetime import datetime
        report.updated_at = datetime.now().isoformat()
        filepath = self._report_path(parse_date(report.date))
        data = report.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_daily_report(self, report_date: date) -> Optional[DailyReport]:
        """加载指定日期的日报，不存在返回 None"""
        filepath = self._report_path(report_date)
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DailyReport.from_dict(data)

    def report_exists(self, report_date: date) -> bool:
        """检查指定日期是否有日报"""
        return self._report_path(report_date).exists()

    def delete_daily_report(self, report_date: date):
        """删除指定日期的日报"""
        filepath = self._report_path(report_date)
        if filepath.exists():
            filepath.unlink()

    def load_week_reports(
        self, week_start: Optional[date] = None
    ) -> list[DailyReport]:
        """加载一周内所有日报

        Args:
            week_start: 周一日期，默认为本周一
        """
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        reports = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            report = self.load_daily_report(d)
            if report:
                reports.append(report)

        return reports

    def load_month_reports(
        self, year: int, month: int
    ) -> list[DailyReport]:
        """加载指定月份的所有日报"""
        month_dir = self.reports_dir / str(year) / f"{month:02d}"
        if not month_dir.exists():
            return []

        reports = []
        for f in sorted(month_dir.glob("*.json")):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            reports.append(DailyReport.from_dict(data))

        return reports

    # ─── 条目级别操作 ──────────────────────────────

    def upsert_entry(self, report_date: date, entry: DailyEntry):
        """添加或更新一条日报条目

        如果 entry.id 已存在则更新，否则追加
        """
        report = self.load_daily_report(report_date)
        if report is None:
            from cli.utils import get_weekday_zh
            report = DailyReport(
                date=report_date.isoformat(),
                day_of_week=get_weekday_zh(report_date),
            )

        # 查找是否已有相同 ID
        existing_idx = next(
            (i for i, e in enumerate(report.entries) if e.id == entry.id),
            None,
        )
        if existing_idx is not None:
            report.entries[existing_idx] = entry
        else:
            report.entries.append(entry)

        # 重新编排 order
        for i, e in enumerate(report.entries):
            e.order = i

        self.save_daily_report(report)

    def remove_entry(self, report_date: date, entry_id: str) -> bool:
        """删除一条日报条目，返回是否删除成功"""
        report = self.load_daily_report(report_date)
        if report is None:
            return False

        original_len = len(report.entries)
        report.entries = [e for e in report.entries if e.id != entry_id]

        if len(report.entries) == original_len:
            return False

        # 重新编排 order
        for i, e in enumerate(report.entries):
            e.order = i

        self.save_daily_report(report)
        return True

    def update_notes(self, report_date: date, notes: str):
        """更新日报的额外备注"""
        report = self.load_daily_report(report_date)
        if report is None:
            from cli.utils import get_weekday_zh
            report = DailyReport(
                date=report_date.isoformat(),
                day_of_week=get_weekday_zh(report_date),
            )
        report.extra_notes = notes
        self.save_daily_report(report)

    # ─── 列表查询 ──────────────────────────────────

    def list_all_report_dates(self) -> list[date]:
        """列出所有存在日报的日期"""
        dates = []
        if not self.reports_dir.exists():
            return dates

        for year_dir in sorted(self.reports_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir():
                    continue
                for f in sorted(month_dir.glob("*.json")):
                    try:
                        d = parse_date(f.stem)
                        dates.append(d)
                    except ValueError:
                        pass
        return dates

    def merge_git_entries(self, report_date: date, commits):
        """将 Git 提交合并到指定日期的日报中（只新增，不覆盖已有手动条目）"""
        from cli.models import EntrySource

        report = self.load_daily_report(report_date)
        if report is None:
            from cli.utils import get_weekday_zh
            report = DailyReport(
                date=report_date.isoformat(),
                day_of_week=get_weekday_zh(report_date),
            )

        # 获取已有的 commit hash 集合
        existing_hashes = {
            e.commit_hash for e in report.entries
            if e.source == EntrySource.GIT_COMMIT and e.commit_hash
        }

        new_entries = []
        for ci in commits:
            if ci.hash not in existing_hashes:
                new_entries.append(ci.to_daily_entry())

        if new_entries:
            report.entries.extend(new_entries)
            for i, e in enumerate(report.entries):
                e.order = i
            self.save_daily_report(report)

        return report


class ConfigManager:
    """全局配置管理"""

    def __init__(self, data_dir: str = "./data"):
        self.config_path = Path(data_dir).resolve() / "config.json"

    def load_config(self) -> Config:
        """加载配置，不存在则返回默认配置"""
        if not self.config_path.exists():
            return self._default_config()
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Config.from_dict(data)

    def save_config(self, config: Config):
        """保存配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

    def _default_config(self) -> Config:
        """生成默认配置（尝试自动检测 git 用户信息）"""
        from cli.utils import get_default_author, get_default_author_email
        return Config(
            git_author=get_default_author(),
            git_author_email=get_default_author_email(),
        )
