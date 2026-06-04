"""定时自动总结与断点追赶模块

支持：
- 检查指定时间段内缺失的日报/周报
- 自动生成缺失报告
- 持久化"上次检查时间"以支持断点追赶
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from cli.models import Config, DailyReport, DailyEntry, EntrySource
from cli.storage import Storage
from cli.utils import today, this_week_range, format_date, get_weekday_zh
from cli.report_generator import (
    generate_daily_report, generate_weekly_report, entries_from_commits,
)
from cli.git_parser import GitParser, auto_detect_repos

# 调度状态文件名
_SCHEDULE_STATE_FILE = ".schedule_state.json"


def _get_state_path(data_dir: str) -> Path:
    return Path(data_dir).resolve() / _SCHEDULE_STATE_FILE


def load_schedule_state(data_dir: str) -> dict:
    """加载调度状态，不存在则返回默认值"""
    path = _get_state_path(data_dir)
    if not path.exists():
        return {
            "last_daily_check": None,
            "last_weekly_check": None,
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_schedule_state(data_dir: str, state: dict):
    """保存调度状态"""
    path = _get_state_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _resolve_repos_from_config(config: Config) -> list[str]:
    """解析仓库列表"""
    if config.scan_repos:
        return config.scan_repos
    if config.auto_detect_repos:
        detected = auto_detect_repos(max_depth=config.scan_max_depth)
        if detected:
            return detected
    return ["."]


def _collect_commits_for_date(
    config: Config, target_date: date,
) -> list[DailyEntry]:
    """收集指定日期所有仓库的 Git 提交并转为日报条目"""
    repos = _resolve_repos_from_config(config)
    author = config.git_author
    if not author:
        from cli.utils import get_default_author
        author = get_default_author()

    all_entries = []
    for rp in repos:
        parser = GitParser(repo_path=rp, author=author)
        if not parser.is_available():
            continue
        commits = parser.get_commits_by_date(target_date)
        if commits:
            all_entries.extend(entries_from_commits(commits, config.exclude_patterns))

    return all_entries


def catchup_daily_reports(
    storage: Storage, config: Config,
    from_date: date, to_date: date,
) -> list[str]:
    """检查并补全缺失的日报

    Args:
        storage: 存储实例
        config: 配置
        from_date: 起始日期（含）
        to_date: 结束日期（含）

    Returns:
        新生成的日报日期列表
    """
    generated = []
    d = from_date
    while d <= to_date:
        # 跳过周末
        if d.weekday() >= 5:  # 周六=5，周日=6
            d += timedelta(days=1)
            continue

        # 检查是否已有日报
        if not storage.report_exists(d):
            entries = _collect_commits_for_date(config, d)
            # 合并已存在的手动条目
            existing = storage.load_daily_report(d)
            if existing:
                manual = [e for e in existing.entries
                          if e.source == EntrySource.MANUAL]
                entries.extend(manual)

            if entries:
                report = DailyReport(
                    date=format_date(d),
                    day_of_week=get_weekday_zh(d),
                    entries=entries,
                )
                storage.save_daily_report(report)
                generated.append(format_date(d))

        d += timedelta(days=1)

    return generated


def catchup_weekly_report(
    storage: Storage, config: Config,
    from_week_start: date,
) -> Optional[str]:
    """检查并补全缺失的周报

    Args:
        storage: 存储实例
        config: 配置
        from_week_start: 起始周的周一日期

    Returns:
        生成周报的周范围字符串，None 表示无需生成
    """
    today_date = today()
    current_week_start, _ = this_week_range(today_date)

    # 从 from_week_start 到上一周（含）
    monday = from_week_start
    while monday < current_week_start:
        sunday = monday + timedelta(days=6)
        daily_reports = storage.load_week_reports(week_start=monday)

        if len(daily_reports) >= 3:  # 至少 3 天日报才生成周报
            # LLM 总结（如果配置了 API Key）
            summary_text = ""
            if config.llm_api_key:
                try:
                    from cli.llm_summary import generate_weekly_summary
                    summary_text = generate_weekly_summary(
                        daily_reports, config
                    ) or ""
                except Exception:
                    pass

            text = generate_weekly_report(
                daily_reports=daily_reports,
                week_start=monday,
                summary=summary_text,
            )
            # 保存周报为文件
            week_file = (
                Path(storage.reports_dir) /
                str(monday.year) /
                f"{monday.month:02d}" /
                f"weekly-{format_date(monday)}.md"
            )
            week_file.parent.mkdir(parents=True, exist_ok=True)
            week_file.write_text(text, encoding="utf-8")
            return f"{format_date(monday)} ~ {format_date(sunday)}"

        monday += timedelta(days=7)

    return None


def run_catchup(storage: Storage, config: Config) -> dict:
    """执行完整的追赶流程

    Returns:
        {
            "status": "ok",
            "daily_generated": ["2026-06-03", "2026-06-04"],
            "weekly_generated": "2026-06-01 ~ 2026-06-07",
            "last_daily_check": "2026-06-04",
            "last_weekly_check": "2026-06-01"
        }
    """
    data_dir = str(storage.reports_dir.parent)
    state = load_schedule_state(data_dir)
    today_date = today()

    # 确定起始日期
    last_daily = state.get("last_daily_check")
    if last_daily:
        from_daily = date.fromisoformat(last_daily) + timedelta(days=1)
    else:
        # 首次运行：检查最近 7 天
        from_daily = today_date - timedelta(days=7)

    last_weekly = state.get("last_weekly_check")
    if last_weekly:
        from_weekly = date.fromisoformat(last_weekly)
    else:
        from_weekly = today_date - timedelta(days=7)
        # 对齐到周一
        from_weekly = from_weekly - timedelta(days=from_weekly.weekday())

    # 补全日报
    daily_generated = catchup_daily_reports(
        storage, config, from_daily, today_date
    )

    # 补全周报
    weekly_generated = catchup_weekly_report(
        storage, config, from_weekly
    )

    # 更新状态
    state["last_daily_check"] = format_date(today_date)
    if weekly_generated:
        current_week_start, _ = this_week_range(today_date)
        state["last_weekly_check"] = format_date(current_week_start)

    save_schedule_state(data_dir, state)

    return {
        "status": "ok",
        "daily_generated": daily_generated,
        "weekly_generated": weekly_generated or "",
        "last_daily_check": state["last_daily_check"],
        "last_weekly_check": state.get("last_weekly_check", ""),
    }
