"""日报 / 周报生成模块

负责：
- 将 DailyEntry 列表按仓库/类型分组
- 用 Jinja2 模板渲染 Markdown 报告
- 周报条目去重和合并
"""

import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from cli.models import DailyReport, DailyEntry, EntrySource, CommitInfo
from cli.utils import get_weekday_zh, format_date


# ─── 模板环境 ─────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(template_name: str, **kwargs) -> str:
    """渲染 Jinja2 模板"""
    template = _jinja_env.get_template(template_name)
    return template.render(**kwargs).strip()


# ─── 日报生成 ─────────────────────────────────────

def generate_daily_report(
    entries: list[DailyEntry],
    report_date: Optional[date] = None,
    extra_notes: str = "",
) -> str:
    """生成日报 Markdown 文本

    Args:
        entries: 日报条目列表
        report_date: 日报日期，默认今天
        extra_notes: 额外备注

    Returns:
        日报 Markdown 文本
    """
    d = report_date or date.today()

    # 分离 Git 提交和手动条目
    git_entries = [e for e in entries if e.source == EntrySource.GIT_COMMIT]
    manual_entries = [e for e in entries if e.source == EntrySource.MANUAL]

    # 按仓库分组 Git 条目
    grouped: dict[str, list[DailyEntry]] = defaultdict(list)
    for e in sorted(git_entries, key=lambda x: x.order):
        grouped[e.repo_name].append(e)

    return _render(
        "daily.md.j2",
        date=format_date(d),
        day_of_week=get_weekday_zh(d),
        grouped_entries=grouped,
        manual_entries=sorted(manual_entries, key=lambda x: x.order),
        extra_notes=extra_notes,
    )


# ─── 周报生成 ─────────────────────────────────────

def _deduplicate_entries(entries: list[DailyEntry]) -> list[DailyEntry]:
    """去重：相同 commit_hash 只保留一个"""
    seen_hashes: set[str] = set()
    seen_content: set[str] = set()
    result = []
    for e in entries:
        key = e.commit_hash if e.commit_hash else e.content
        # Git 条目按 hash 去重
        if e.source == EntrySource.GIT_COMMIT:
            if e.commit_hash and e.commit_hash in seen_hashes:
                continue
            seen_hashes.add(e.commit_hash or "")
        # 手动条目按内容去重
        else:
            if e.content in seen_content:
                continue
            seen_content.add(e.content)
        result.append(e)
    return result


def _merge_similar_entries(entries: list[DailyEntry]) -> list[DailyEntry]:
    """合并同仓库同分支的相似条目

    将相同前缀的 commit message 合并为一条汇总描述。
    例如：
      "feat: 用户登录页面"
      "feat: 用户注册接口"
      → "feat: 用户模块开发（登录页面、注册接口）"
    """
    if not entries:
        return entries

    # 只合并 Git 条目
    git_entries = [e for e in entries if e.source == EntrySource.GIT_COMMIT]
    manual_entries = [e for e in entries if e.source == EntrySource.MANUAL]

    # 按仓库+分支分组
    groups: dict[tuple[str, str], list[DailyEntry]] = defaultdict(list)
    for e in git_entries:
        key = (e.repo_name, e.branch or "")
        groups[key].append(e)

    merged = []
    for (repo_name, branch), group in groups.items():
        if len(group) <= 2:
            merged.extend(group)
            continue

        # 提取 message 前缀（如 "feat:", "fix:", "refactor:"）
        prefix_groups: dict[str, list[DailyEntry]] = defaultdict(list)
        for e in group:
            match = re.match(r"^(\w+[:\(（])", e.content)
            prefix = match.group(0) if match else "__other__"
            prefix_groups[prefix].append(e)

        for prefix, p_entries in prefix_groups.items():
            if len(p_entries) >= 3:
                prefix_label = prefix.rstrip(":(（")
                contents = []
                for e in p_entries:
                    # 去掉前缀后的内容
                    short = re.sub(r"^\w+[:\(（]\s*", "", e.content, count=1)
                    contents.append(short)
                merged_content = f"{prefix_label}: {'、'.join(contents)}"
                # 用第一个条目的信息
                merged.append(DailyEntry(
                    content=merged_content,
                    source=EntrySource.GIT_COMMIT,
                    repo_name=repo_name,
                    branch=branch,
                ))
            else:
                merged.extend(p_entries)

    return merged + manual_entries


def generate_weekly_report(
    daily_reports: list[DailyReport],
    week_start: Optional[date] = None,
    summary: str = "",
    next_week_plan: str = "",
) -> str:
    """生成周报 Markdown 文本

    Args:
        daily_reports: 一周的日报列表
        week_start: 周一日期
        summary: 智能总结文本（可选）
        next_week_plan: 下周计划

    Returns:
        周报 Markdown 文本
    """
    if not daily_reports:
        d = date.today()
        monday = d - timedelta(days=d.weekday())
        return f"# 周报 ({format_date(monday)} ~ {format_date(monday + timedelta(days=6))})\n\n本周暂无日报记录。"

    # 合并所有条目
    all_entries = []
    for report in daily_reports:
        all_entries.extend(report.entries)

    # 去重
    deduped = _deduplicate_entries(all_entries)

    # 收集统计信息
    repo_names = {
        e.repo_name for e in all_entries
        if e.source == EntrySource.GIT_COMMIT
    }
    stats = {
        "total_commits": len(deduped),
        "repo_count": len(repo_names),
        "manual_count": sum(1 for e in all_entries if e.source == EntrySource.MANUAL),
    }

    # 确定周范围
    if week_start is None:
        first_date_str = daily_reports[0].date
        first_date = date.fromisoformat(first_date_str)
        week_start = first_date - timedelta(days=first_date.weekday())
    week_end = week_start + timedelta(days=6)

    return _render(
        "weekly.md.j2",
        week_start=format_date(week_start),
        week_end=format_date(week_end),
        daily_reports=daily_reports,
        stats=stats,
        summary=summary,
        next_week_plan=next_week_plan,
    )


# ─── 工具函数 ─────────────────────────────────────


def entries_from_commits(
    commits: list[CommitInfo],
    exclude_patterns: Optional[list[str]] = None,
) -> list[DailyEntry]:
    """将 CommitInfo 列表转换为 DailyEntry 列表，支持过滤

    Args:
        commits: Git 提交信息列表
        exclude_patterns: 要排除的 commit message 正则模式列表
    """
    patterns = exclude_patterns or []
    entries = []
    for ci in commits:
        # 检查是否需要排除
        excluded = False
        for pat in patterns:
            if re.search(pat, ci.message):
                excluded = True
                break
        if not excluded:
            entries.append(ci.to_daily_entry())
    return entries
