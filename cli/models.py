"""数据模型定义"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid


class EntrySource(Enum):
    """日报条目来源"""
    GIT_COMMIT = "git_commit"   # 自动从 Git 提交解析
    MANUAL = "manual"           # 用户手动添加


@dataclass
class DailyEntry:
    """日报中的单条工作记录"""
    content: str                            # 条目描述
    source: EntrySource                     # 来源
    repo_name: str = "manual"               # 所属仓库名
    branch: Optional[str] = None            # 分支名
    commit_hash: Optional[str] = None       # Git commit hash (仅 Git 条目)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    order: int = 0                          # 排序序号

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source.value,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "created_at": self.created_at,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DailyEntry":
        return cls(
            id=d.get("id", ""),
            content=d["content"],
            source=EntrySource(d["source"]),
            repo_name=d.get("repo_name", "manual"),
            branch=d.get("branch"),
            commit_hash=d.get("commit_hash"),
            created_at=d.get("created_at", ""),
            order=d.get("order", 0),
        )


@dataclass
class CommitInfo:
    """Git 提交信息 (从 git log 解析)"""
    hash: str
    message: str
    author: str
    timestamp: datetime
    repo_name: str
    branch: str = ""
    files_changed: int = 0

    def to_daily_entry(self) -> DailyEntry:
        """将 Git 提交转换为日报条目"""
        return DailyEntry(
            content=self.message.strip(),
            source=EntrySource.GIT_COMMIT,
            repo_name=self.repo_name,
            branch=self.branch,
            commit_hash=self.hash,
        )


@dataclass
class DailyReport:
    """单天日报"""
    date: str                           # "2026-06-04"
    day_of_week: str                    # "星期四"
    entries: list[DailyEntry] = field(default_factory=list)
    extra_notes: str = ""               # 额外备注
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "day_of_week": self.day_of_week,
            "entries": [e.to_dict() for e in self.entries],
            "extra_notes": self.extra_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DailyReport":
        return cls(
            date=d["date"],
            day_of_week=d.get("day_of_week", ""),
            entries=[DailyEntry.from_dict(e) for e in d.get("entries", [])],
            extra_notes=d.get("extra_notes", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class Config:
    """全局配置"""
    # Git 相关
    git_author: str = ""
    git_author_email: str = ""
    scan_repos: list[str] = field(default_factory=list)
    auto_detect_repos: bool = True          # 自动扫描工作区下所有 Git 仓库
    scan_max_depth: int = 3                 # 自动扫描最大目录深度
    include_branches: list[str] = field(default_factory=lambda: ["*"])
    exclude_branches: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=lambda: [
        r"^(Merge|chore|WIP)",
        r"auto-commit",
    ])

    # 报告相关
    report_language: str = "zh"
    daily_template: str = "daily.md.j2"
    weekly_template: str = "weekly.md.j2"
    custom_template_dir: str = ""           # 用户自定义模板目录

    # LLM 总结
    llm_api_key: str = ""                   # API Key（支持环境变量 LLM_API_KEY）
    llm_api_base: str = ""                  # API 地址（空=默认 OpenAI / Anthropic）
    llm_model: str = "claude-sonnet-4-6"    # 模型名

    # 导出 & 推送
    export_webhook_url: str = ""            # 飞书/钉钉机器人 Webhook
    export_format: str = "markdown"         # 默认导出格式

    # 定时调度
    schedule_enabled: bool = True           # 是否启用自动定时总结
    schedule_daily_time: str = "18:00"      # 每日自动生成日报的时间
    schedule_weekly_day: int = 5            # 周报生成日 (5=周五)
    schedule_weekly_time: str = "18:30"     # 周报生成时间
    schedule_auto_save: bool = True         # 是否自动保存
    schedule_auto_summary: bool = False     # 周报是否启用 LLM 总结

    def to_dict(self) -> dict:
        return {
            "git_author": self.git_author,
            "git_author_email": self.git_author_email,
            "scan_repos": self.scan_repos,
            "auto_detect_repos": self.auto_detect_repos,
            "scan_max_depth": self.scan_max_depth,
            "include_branches": self.include_branches,
            "exclude_branches": self.exclude_branches,
            "exclude_patterns": self.exclude_patterns,
            "report_language": self.report_language,
            "daily_template": self.daily_template,
            "weekly_template": self.weekly_template,
            "custom_template_dir": self.custom_template_dir,
            "llm_api_key": self.llm_api_key,
            "llm_api_base": self.llm_api_base,
            "llm_model": self.llm_model,
            "export_webhook_url": self.export_webhook_url,
            "export_format": self.export_format,
            "schedule_enabled": self.schedule_enabled,
            "schedule_daily_time": self.schedule_daily_time,
            "schedule_weekly_day": self.schedule_weekly_day,
            "schedule_weekly_time": self.schedule_weekly_time,
            "schedule_auto_save": self.schedule_auto_save,
            "schedule_auto_summary": self.schedule_auto_summary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        return cls(
            git_author=d.get("git_author", ""),
            git_author_email=d.get("git_author_email", ""),
            scan_repos=d.get("scan_repos", []),
            auto_detect_repos=d.get("auto_detect_repos", True),
            scan_max_depth=d.get("scan_max_depth", 3),
            include_branches=d.get("include_branches", ["*"]),
            exclude_branches=d.get("exclude_branches", []),
            exclude_patterns=d.get("exclude_patterns", [
                r"^(Merge|chore|WIP)",
                r"auto-commit",
            ]),
            report_language=d.get("report_language", "zh"),
            daily_template=d.get("daily_template", "daily.md.j2"),
            weekly_template=d.get("weekly_template", "weekly.md.j2"),
            custom_template_dir=d.get("custom_template_dir", ""),
            llm_api_key=d.get("llm_api_key", ""),
            llm_api_base=d.get("llm_api_base", ""),
            llm_model=d.get("llm_model", "claude-sonnet-4-6"),
            export_webhook_url=d.get("export_webhook_url", ""),
            export_format=d.get("export_format", "markdown"),
            schedule_enabled=d.get("schedule_enabled", True),
            schedule_daily_time=d.get("schedule_daily_time", "18:00"),
            schedule_weekly_day=d.get("schedule_weekly_day", 5),
            schedule_weekly_time=d.get("schedule_weekly_time", "18:30"),
            schedule_auto_save=d.get("schedule_auto_save", True),
            schedule_auto_summary=d.get("schedule_auto_summary", False),
        )
