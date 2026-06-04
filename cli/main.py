"""CLI 入口 - 工作日报工具

用法:
    daily-report generate today        # 生成今日日报
    daily-report generate week         # 生成本周周报
    daily-report list --week           # 列出本周日报
    daily-report edit 2026-06-04       # 交互式编辑日报
    daily-report config --show         # 查看配置
"""

import json
import sys

# 修复 Windows 终端编码问题，确保中文和 emoji 正常输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import click

from cli.models import (
    DailyReport, DailyEntry, EntrySource, CommitInfo, Config,
)
from cli.git_parser import GitParser, auto_detect_repos
from cli.storage import Storage, ConfigManager
from cli.report_generator import (
    generate_daily_report, generate_weekly_report,
    entries_from_commits,
    set_custom_template_dir, list_templates,
)
from cli.utils import (
    today, this_week_range, format_date, parse_date,
    get_weekday_zh, get_default_author,
)

# 默认数据目录
DEFAULT_DATA_DIR = "./data"


# ─── 辅助函数 ─────────────────────────────────────

def _get_storage(data_dir: str = DEFAULT_DATA_DIR) -> Storage:
    return Storage(data_dir=data_dir)


def _get_config(data_dir: str = DEFAULT_DATA_DIR) -> Config:
    return ConfigManager(data_dir=data_dir).load_config()


def _get_git_parser(repo_path: str = ".", author: str = "") -> GitParser:
    return GitParser(repo_path=repo_path, author=author)


def _resolve_repos(config: Config, user_repos: list[str]) -> list[str]:
    """解析仓库列表：用户指定 > 配置列表 > 自动检测"""
    if user_repos:
        return list(user_repos)
    if config.scan_repos:
        return config.scan_repos
    if config.auto_detect_repos:
        detected = auto_detect_repos(max_depth=config.scan_max_depth)
        if detected:
            click.echo(f"🔍 自动检测到 {len(detected)} 个 Git 仓库", err=True)
            for r in detected:
                click.echo(f"  📦 {r}", err=True)
            return detected
    return ["."]


def _collect_today_entries(
    config: Config,
    repo_paths: Optional[list[str]] = None,
) -> tuple[list[DailyEntry], dict[str, list[CommitInfo]]]:
    """收集今天所有 Git 提交并转换为日报条目"""
    repos = _resolve_repos(config, list(repo_paths) if repo_paths else [])

    author = config.git_author or get_default_author()

    all_commits: dict[str, list[CommitInfo]] = {}
    for rp in repos:
        parser = GitParser(repo_path=rp, author=author)
        if not parser.is_available():
            continue
        commits = parser.get_today_commits()
        if commits:
            all_commits[parser.repo_name] = commits

    entries = []
    for repo_name, commits in all_commits.items():
        entries.extend(entries_from_commits(commits, config.exclude_patterns))

    return entries, all_commits


def _prompt_manual_entry() -> Optional[DailyEntry]:
    """交互式添加一条手动条目"""
    click.echo()
    click.echo("📝 请输入手动工作条目（直接回车跳过）:")
    content = click.prompt("  内容", default="").strip()
    if not content:
        return None
    return DailyEntry(
        content=content,
        source=EntrySource.MANUAL,
        repo_name="manual",
    )


def _prompt_extra_notes(existing: str = "") -> str:
    """交互式输入备注"""
    click.echo()
    if existing:
        click.echo(f"当前备注: {existing}")
    notes = click.prompt("📌 备注（明日计划 / 遇到的问题，直接回车保持现状）",
                         default=existing).strip()
    return notes


def _output_report(text: str, output: str = "stdout"):
    """按指定方式输出报告"""
    if output == "clipboard":
        try:
            import pyperclip
            pyperclip.copy(text)
            click.echo("✅ 日报已复制到剪贴板")
        except ImportError:
            click.echo("⚠️ pyperclip 未安装，回退到 stdout 输出")
            click.echo(text)
    elif output == "file":
        d = date.today()
        filepath = Path(f"日报-{d.isoformat()}.md")
        filepath.write_text(text, encoding="utf-8")
        click.echo(f"✅ 日报已保存到 {filepath}")
    else:
        click.echo(text)


# ─── CLI 主组 ─────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0", message="daily-report v%(version)s")
def cli():
    """工作日报工具 - 基于 Git 提交记录自动生成日报 / 周报"""


# ─── generate 子命令组 ────────────────────────────

@cli.group()
def generate():
    """生成日报或周报"""


@generate.command("today")
@click.option("--author", "-a", default="", help="指定 Git 作者名")
@click.option("--repo", "-r", multiple=True, help="指定仓库路径（可多次使用）")
@click.option("--output", "-o", default="stdout",
              type=click.Choice(["stdout", "clipboard", "file"]),
              help="输出方式")
@click.option("--no-manual", is_flag=True, help="跳过交互式手动补充")
@click.option("--save/--no-save", default=True, help="是否保存日报到 JSON 存储")
@click.option("--template", "-t", default="daily.md.j2",
              help="模板名称（daily.md.j2 / daily-feishu.md.j2 / daily-dingtalk.md.j2）")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def generate_today(author, repo, output, no_manual, save, template, data_dir):
    """生成今日日报"""
    d = today()
    storage = _get_storage(data_dir)
    config = _get_config(data_dir)

    # 设置自定义模板目录
    if config.custom_template_dir:
        set_custom_template_dir(config.custom_template_dir)

    # 覆盖配置中的参数
    if author:
        config.git_author = author

    # 解析仓库列表（支持自动检测）
    repo_paths = list(repo) if repo else []

    # 1. 收集 Git 提交
    click.echo(f"🔍 扫描今日 ({format_date(d)}) Git 提交...", err=True)
    existing_report = storage.load_daily_report(d)
    existing_entries = existing_report.entries if existing_report else []

    entries, commits_by_repo = _collect_today_entries(config, repo_paths)

    if not commits_by_repo:
        click.echo("📭 今日暂无 Git 提交记录", err=True)
    else:
        for repo_name, commits in commits_by_repo.items():
            click.echo(f"  ✓ {repo_name}: {len(commits)} 条提交", err=True)

    # 合并已有的手动条目
    existing_manual = [
        e for e in existing_entries if e.source == EntrySource.MANUAL
    ]
    all_entries = entries + existing_manual

    # 2. 交互式手动补充
    new_manual_entries = []
    if not no_manual:
        while True:
            entry = _prompt_manual_entry()
            if entry is None:
                break
            new_manual_entries.append(entry)
            click.echo(f"  ✓ 已添加: {entry.content}", err=True)

    if new_manual_entries:
        all_entries.extend(new_manual_entries)

    # 3. 交互式备注
    extra_notes = ""
    if not no_manual:
        existing_notes = existing_report.extra_notes if existing_report else ""
        extra_notes = _prompt_extra_notes(existing_notes)

    # 4. 生成报告
    if not all_entries and not extra_notes:
        click.echo("📭 今日暂无工作记录", err=True)
        # 非交互模式（如 VSCode 扩展调用）仍输出空日报到 stdout
        if no_manual:
            report_text = generate_daily_report(
                entries=[],
                report_date=d,
                extra_notes="",
                template_name=template,
            )
            click.echo(report_text)
        return

    report_text = generate_daily_report(
        entries=all_entries,
        report_date=d,
        extra_notes=extra_notes,
        template_name=template,
    )

    click.echo()
    _output_report(report_text, output)

    # 5. 保存到 JSON 存储
    if save and (all_entries or extra_notes):
        report = existing_report or DailyReport(
            date=format_date(d),
            day_of_week=get_weekday_zh(d),
        )
        report.entries = all_entries
        report.extra_notes = extra_notes
        storage.save_daily_report(report)
        click.echo(f"\n💾 日报已保存到 {storage._report_path(d)}", err=True)


@generate.command("week")
@click.option("--from-date", default="", help="周起始日期 (YYYY-MM-DD)，默认本周一")
@click.option("--to-date", default="", help="周结束日期 (YYYY-MM-DD)，默认本周日")
@click.option("--output", "-o", default="stdout",
              type=click.Choice(["stdout", "clipboard", "file"]),
              help="输出方式")
@click.option("--summary", is_flag=True, help="使用 LLM 对本周工作进行智能总结")
@click.option("--template", "-t", default="weekly.md.j2",
              help="模板名称（weekly.md.j2 等）")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def generate_week(from_date, to_date, output, summary, template, data_dir):
    """生成本周周报（从已保存的日报中汇总）"""
    storage = _get_storage(data_dir)
    config = _get_config(data_dir)

    # 设置自定义模板目录
    if config.custom_template_dir:
        set_custom_template_dir(config.custom_template_dir)

    # 确定周范围
    if from_date:
        monday = parse_date(from_date)
    else:
        monday, _ = this_week_range()
    if to_date:
        sunday = parse_date(to_date)
    else:
        _, sunday = this_week_range()

    click.echo(f"📋 汇总 {format_date(monday)} ~ {format_date(sunday)} 的日报...", err=True)

    # 加载本周日报
    daily_reports = storage.load_week_reports(week_start=monday)

    if not daily_reports:
        click.echo("📭 本周暂无日报记录", err=True)
        click.echo("提示: 请先运行 `daily-report generate today` 生成日报", err=True)
        return

    click.echo(f"  ✓ 找到 {len(daily_reports)} 天日报", err=True)

    # LLM 智能总结
    summary_text = ""
    if summary:
        click.echo("🤖 正在调用 AI 生成本周总结...", err=True)
        from cli.llm_summary import generate_weekly_summary
        summary_text = generate_weekly_summary(daily_reports, config) or ""
        if summary_text:
            click.echo(f"  ✓ AI 总结: {summary_text[:80]}...", err=True)
        else:
            click.echo("  ⚠️ LLM 总结失败（请检查 API Key 配置），使用默认统计", err=True)

    # 交互式输入下周计划
    next_plan = ""
    if sys.stdin.isatty():
        next_plan = click.prompt(
            "📅 下周计划（直接回车跳过）", default=""
        ).strip()

    report_text = generate_weekly_report(
        daily_reports=daily_reports,
        week_start=monday,
        summary=summary_text,
        next_week_plan=next_plan,
        template_name=template,
    )

    click.echo()
    _output_report(report_text, output)


# ─── list 子命令 ──────────────────────────────────

@cli.command("list")
@click.option("--week", "list_week", is_flag=True, help="列出本周日报")
@click.option("--month", "list_month", is_flag=True, help="列出本月日报")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def list_reports(list_week, list_month, data_dir):
    """列出已有日报"""
    storage = _get_storage(data_dir)
    all_dates = storage.list_all_report_dates()

    if not all_dates:
        click.echo("📭 暂无日报记录")
        return

    d = today()

    if list_week:
        monday, _ = this_week_range()
        filtered = [dt for dt in all_dates if monday <= dt <= monday + timedelta(days=6)]
        click.echo(f"📋 本周日报 ({format_date(monday)} ~ {format_date(monday + timedelta(days=6))}):")
    elif list_month:
        filtered = [dt for dt in all_dates if dt.year == d.year and dt.month == d.month]
        click.echo(f"📋 本月日报 ({d.year}年{d.month}月):")
    else:
        filtered = all_dates[-14:]  # 默认显示最近14天
        click.echo("📋 最近日报:")

    if not filtered:
        click.echo("  (无)")
        return

    for dt in sorted(filtered):
        report = storage.load_daily_report(dt)
        if report:
            git_count = sum(1 for e in report.entries if e.source == EntrySource.GIT_COMMIT)
            manual_count = sum(1 for e in report.entries if e.source == EntrySource.MANUAL)
            marker = " ← 今天" if dt == d else ""
            click.echo(
                f"  {format_date(dt)} {get_weekday_zh(dt)}  "
                f"Git: {git_count}条  手动: {manual_count}条{marker}"
            )


# ─── edit 子命令 ──────────────────────────────────

@cli.command("edit")
@click.argument("report_date", default="")
@click.option("--add", "-a", "add_entry", is_flag=True, help="添加手动条目")
@click.option("--remove", "-r", "remove_id", default="", help="按 ID 删除条目")
@click.option("--notes", "-n", default="", help="修改备注")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def edit_report(report_date, add_entry, remove_id, notes, data_dir):
    """编辑日报（日期格式: YYYY-MM-DD，默认今天）"""
    storage = _get_storage(data_dir)

    d = parse_date(report_date) if report_date else today()
    report = storage.load_daily_report(d)

    if report is None:
        # 创建新日报
        report = DailyReport(
            date=format_date(d),
            day_of_week=get_weekday_zh(d),
        )

    # 删除条目
    if remove_id:
        if storage.remove_entry(d, remove_id):
            click.echo(f"✅ 已删除条目: {remove_id}")
        else:
            click.echo(f"❌ 未找到条目: {remove_id}")
        return

    # 修改备注
    if notes:
        storage.update_notes(d, notes)
        click.echo(f"✅ 备注已更新")
        return

    # 添加条目（交互式）
    if add_entry:
        click.echo(f"编辑: {format_date(d)} {get_weekday_zh(d)}")
        click.echo(f"当前条目数: {len(report.entries)}")

        while True:
            entry = _prompt_manual_entry()
            if entry is None:
                break
            storage.upsert_entry(d, entry)
            click.echo(f"  ✅ 已添加: {entry.content}")

        click.echo(f"✅ 完成，当前条目数: {len(storage.load_daily_report(d).entries)}")
        return

    # 无参数：显示当前内容
    click.echo(f"📋 {format_date(d)} {get_weekday_zh(d)} 日报")
    click.echo(f"条目数: {len(report.entries)}")
    for e in sorted(report.entries, key=lambda x: x.order):
        source_icon = "🔀" if e.source == EntrySource.GIT_COMMIT else "✍️"
        click.echo(f"  {source_icon} [{e.id}] {e.content}")
    if report.extra_notes:
        click.echo(f"\n📌 备注: {report.extra_notes}")

    click.echo("\n用法: daily-report edit [日期] --add    # 添加条目")
    click.echo("      daily-report edit [日期] --remove <id>  # 删除条目")
    click.echo("      daily-report edit [日期] --notes <文本>  # 修改备注")


# ─── config 子命令 ────────────────────────────────

@cli.command("config")
@click.option("--show", "show_config", is_flag=True, help="查看当前配置")
@click.option("--set-author", default="", help="设置 Git 作者名")
@click.option("--add-repo", default="", help="添加扫描仓库")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def config_cmd(show_config, set_author, add_repo, data_dir):
    """查看或修改配置"""
    manager = ConfigManager(data_dir=data_dir)
    config = manager.load_config()

    if set_author:
        config.git_author = set_author
        manager.save_config(config)
        click.echo(f"✅ Git 作者已设置为: {set_author}")

    if add_repo:
        if add_repo not in config.scan_repos:
            config.scan_repos.append(add_repo)
            manager.save_config(config)
            click.echo(f"✅ 已添加扫描仓库: {add_repo}")
        else:
            click.echo(f"⚠️ 该仓库已在列表中")

    if show_config or (not set_author and not add_repo):
        click.echo("📋 当前配置:")
        click.echo(f"  Git 作者: {config.git_author or '(自动检测)'}")
        click.echo(f"  Git 邮箱: {config.git_author_email or '(自动检测)'}")
        click.echo(f"  扫描仓库: {config.scan_repos or '(自动检测)'}")
        click.echo(f"  自动发现仓库: {'开' if config.auto_detect_repos else '关'}")
        click.echo(f"  扫描深度: {config.scan_max_depth}")
        click.echo(f"  排除模式: {config.exclude_patterns}")
        click.echo(f"  报告语言: {config.report_language}")
        click.echo(f"  日报模板: {config.daily_template}")
        click.echo(f"  周报模板: {config.weekly_template}")
        click.echo(f"  自定义模板目录: {config.custom_template_dir or '(未设置)'}")
        click.echo(f"  LLM 模型: {config.llm_model}")
        click.echo(f"  LLM API Key: {'已设置' if config.llm_api_key else '(未设置)'}")
        click.echo(f"  Webhook 地址: {config.export_webhook_url or '(未设置)'}")


# ─── export 子命令 ────────────────────────────────

@cli.command("export")
@click.argument("what", type=click.Choice(["today", "week"]), default="today")
@click.option("--format", "-f", "fmt", default="markdown",
              type=click.Choice(["markdown", "feishu", "dingtalk", "text"]),
              help="导出格式")
@click.option("--webhook", "-w", default="", help="Webhook 地址（飞书/钉钉机器人）")
@click.option("--output", "-o", default="stdout",
              type=click.Choice(["stdout", "clipboard", "file"]),
              help="输出方式")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def export_cmd(what, fmt, webhook, output, data_dir):
    """导出日报/周报（支持飞书、钉钉格式，可选 Webhook 推送）"""
    from cli.export import export_report

    storage = _get_storage(data_dir)
    d = today()

    if what == "today":
        click.echo(f"📋 导出 {format_date(d)} 日报...", err=True)
    else:
        click.echo(f"📋 导出本周周报...", err=True)

    text = export_report(
        storage=storage,
        report_date=d,
        export_type="daily" if what == "today" else "week",
        format=fmt,
        webhook_url=webhook or "",
    )

    _output_report(text, output)


# ─── vscode 子命令（供 VSCode 扩展调用）────────────

@cli.command("vscode")
@click.option("--today", "vscode_today", is_flag=True, help="输出今日日报 JSON")
@click.option("--week", "vscode_week", is_flag=True, help="输出周报 JSON")
@click.option("--history-tree", "vscode_history_tree", is_flag=True,
              help="输出所有日报文件的层级树 JSON（年→月→日）")
@click.option("--report", "vscode_report_date", default="",
              help="输出指定日期的 Markdown 日报（YYYY-MM-DD）")
@click.option("--catchup", "vscode_catchup", is_flag=True,
              help="检查并补全缺失的日报/周报")
@click.option("--json", "as_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--data-dir", default=DEFAULT_DATA_DIR, help="数据存储目录")
def vscode_cmd(vscode_today, vscode_week, vscode_history_tree,
               vscode_report_date, vscode_catchup, as_json, data_dir):
    """VSCode 专用子命令（以结构化 JSON 输出）"""
    storage = _get_storage(data_dir)
    config = _get_config(data_dir)

    if vscode_history_tree:
        # 输出所有日报文件的年→月→日层级树
        all_dates = storage.list_all_report_dates()
        tree = _build_history_tree(storage, all_dates)
        click.echo(json.dumps(tree, ensure_ascii=False, indent=2))

    elif vscode_report_date:
        # 输出指定日期的完整 Markdown 日报
        d = parse_date(vscode_report_date)
        report = storage.load_daily_report(d)
        if report is None:
            click.echo(json.dumps({"status": "not_found", "date": vscode_report_date},
                                  ensure_ascii=False))
            return
        if as_json:
            click.echo(json.dumps({
                "status": "ok",
                "date": report.date,
                "day_of_week": report.day_of_week,
                "entries": [e.to_dict() for e in report.entries],
                "extra_notes": report.extra_notes,
            }, ensure_ascii=False, indent=2))
        else:
            text = generate_daily_report(
                entries=report.entries,
                report_date=d,
                extra_notes=report.extra_notes,
            )
            click.echo(text)

    elif vscode_catchup:
        # 检查并补全缺失的日报/周报
        from cli.scheduler import run_catchup
        result = run_catchup(storage, config)
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    elif vscode_today:
        d = today()
        entries, commits_by_repo = _collect_today_entries(config)
        existing_report = storage.load_daily_report(d)

        # 合并已有手动条目
        if existing_report:
            existing_manual = [
                e for e in existing_report.entries
                if e.source == EntrySource.MANUAL
            ]
            entries.extend(existing_manual)

        result = {
            "status": "ok",
            "date": format_date(d),
            "day_of_week": get_weekday_zh(d),
            "commits_found": sum(len(c) for c in commits_by_repo.values()),
            "entries": [e.to_dict() for e in entries],
            "extra_notes": existing_report.extra_notes if existing_report else "",
        }
        if as_json:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            report_text = generate_daily_report(
                entries=entries,
                report_date=d,
                extra_notes=result["extra_notes"],
            )
            click.echo(report_text)

    elif vscode_week:
        monday, _ = this_week_range()
        daily_reports = storage.load_week_reports(week_start=monday)
        report_text = generate_weekly_report(daily_reports=daily_reports, week_start=monday)

        if as_json:
            result = {
                "status": "ok",
                "week_start": format_date(monday),
                "week_end": format_date(monday + timedelta(days=6)),
                "report_count": len(daily_reports),
                "markdown": report_text,
            }
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            click.echo(report_text)

    else:
        click.echo("请指定 --today | --week | --history-tree | --report <date> | --catchup", err=True)


def _build_history_tree(storage: Storage, all_dates: list[date]) -> dict:
    """构建年→月→日的日报层级树

    Returns:
        {
            "status": "ok",
            "total": 10,
            "years": [
                {
                    "year": 2026,
                    "months": [
                        {
                            "month": 6,
                            "dates": [
                                {
                                    "date": "2026-06-04",
                                    "day_of_week": "星期四",
                                    "git_count": 3,
                                    "manual_count": 2
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    """
    from collections import defaultdict

    by_year: dict[int, dict[int, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for d in sorted(all_dates, reverse=True):
        report = storage.load_daily_report(d)
        if report is None:
            continue
        git_count = sum(
            1 for e in report.entries if e.source == EntrySource.GIT_COMMIT
        )
        manual_count = sum(
            1 for e in report.entries if e.source == EntrySource.MANUAL
        )
        by_year[d.year][d.month].append({
            "date": format_date(d),
            "day_of_week": get_weekday_zh(d),
            "git_count": git_count,
            "manual_count": manual_count,
        })

    years = []
    for year in sorted(by_year.keys(), reverse=True):
        months_data = []
        for month in sorted(by_year[year].keys(), reverse=True):
            months_data.append({
                "month": month,
                "dates": by_year[year][month],
            })
        years.append({"year": year, "months": months_data})

    return {
        "status": "ok",
        "total": len(all_dates),
        "years": years,
    }


# ─── 入口 ─────────────────────────────────────────

if __name__ == "__main__":
    cli()
