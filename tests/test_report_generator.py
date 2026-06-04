"""报告生成模块单元测试"""

from datetime import date

from cli.report_generator import (
    generate_daily_report,
    generate_weekly_report,
    entries_from_commits,
    _deduplicate_entries,
    _merge_similar_entries,
)
from cli.models import DailyEntry, DailyReport, CommitInfo, EntrySource
from datetime import datetime


class TestDailyReportGeneration:
    def test_empty_entries(self):
        text = generate_daily_report([], report_date=date(2026, 6, 4))
        assert "2026-06-04" in text
        assert "星期四" in text

    def test_with_git_entries(self):
        entries = [
            DailyEntry(
                content="feat: 添加登录",
                source=EntrySource.GIT_COMMIT,
                repo_name="my-project",
                branch="main",
            ),
        ]
        text = generate_daily_report(entries, report_date=date(2026, 6, 4))
        assert "feat: 添加登录" in text
        assert "my-project" in text
        assert "main" in text

    def test_with_manual_entries(self):
        entries = [
            DailyEntry(
                content="参加需求评审",
                source=EntrySource.MANUAL,
            ),
        ]
        text = generate_daily_report(entries, report_date=date(2026, 6, 4))
        assert "参加需求评审" in text
        assert "其他工作" in text

    def test_with_extra_notes(self):
        text = generate_daily_report(
            [], report_date=date(2026, 6, 4), extra_notes="明天继续联调"
        )
        assert "明天继续联调" in text

    def test_multiple_repos_grouped(self):
        entries = [
            DailyEntry(content="feat A", source=EntrySource.GIT_COMMIT, repo_name="repo-a"),
            DailyEntry(content="feat B", source=EntrySource.GIT_COMMIT, repo_name="repo-b"),
        ]
        text = generate_daily_report(entries, report_date=date(2026, 6, 4))
        assert "repo-a" in text
        assert "repo-b" in text


class TestWeeklyReportGeneration:
    def test_empty_reports(self):
        text = generate_weekly_report([])
        assert "暂无日报记录" in text

    def test_with_reports(self):
        reports = [
            DailyReport(
                date="2026-06-01",
                day_of_week="星期一",
                entries=[
                    DailyEntry(content="feat: 登录", source=EntrySource.GIT_COMMIT,
                               repo_name="repo-a"),
                ],
            ),
            DailyReport(
                date="2026-06-02",
                day_of_week="星期二",
                entries=[
                    DailyEntry(content="feat: 注册", source=EntrySource.GIT_COMMIT,
                               repo_name="repo-a"),
                ],
            ),
        ]
        text = generate_weekly_report(reports)
        assert "feat: 登录" in text
        assert "feat: 注册" in text

    def test_with_summary_and_plan(self):
        reports = [
            DailyReport(
                date="2026-06-01",
                day_of_week="星期一",
                entries=[DailyEntry(content="test", source=EntrySource.MANUAL)],
            ),
        ]
        text = generate_weekly_report(
            reports,
            summary="本周完成了核心模块开发",
            next_week_plan="下周进入测试阶段",
        )
        assert "核心模块开发" in text
        assert "测试阶段" in text


class TestDeduplication:
    def test_dedup_by_commit_hash(self):
        e1 = DailyEntry(
            content="same msg", source=EntrySource.GIT_COMMIT,
            commit_hash="abc123", repo_name="repo",
        )
        e2 = DailyEntry(
            content="same msg", source=EntrySource.GIT_COMMIT,
            commit_hash="abc123", repo_name="repo",
        )
        result = _deduplicate_entries([e1, e2])
        assert len(result) == 1

    def test_no_dedup_different_hashes(self):
        e1 = DailyEntry(
            content="same msg", source=EntrySource.GIT_COMMIT,
            commit_hash="abc", repo_name="repo",
        )
        e2 = DailyEntry(
            content="same msg", source=EntrySource.GIT_COMMIT,
            commit_hash="def", repo_name="repo",
        )
        result = _deduplicate_entries([e1, e2])
        assert len(result) == 2

    def test_dedup_manual_by_content(self):
        e1 = DailyEntry(content="会议", source=EntrySource.MANUAL)
        e2 = DailyEntry(content="会议", source=EntrySource.MANUAL)
        result = _deduplicate_entries([e1, e2])
        assert len(result) == 1


class TestEntriesFromCommits:
    def test_basic_conversion(self):
        commits = [
            CommitInfo(
                hash="abc", message="feat: test", author="u",
                timestamp=datetime.now(), repo_name="repo",
            ),
        ]
        entries = entries_from_commits(commits)
        assert len(entries) == 1
        assert entries[0].content == "feat: test"

    def test_exclude_patterns(self):
        commits = [
            CommitInfo(hash="1", message="feat: good", author="u",
                       timestamp=datetime.now(), repo_name="repo"),
            CommitInfo(hash="2", message="Merge branch x", author="u",
                       timestamp=datetime.now(), repo_name="repo"),
        ]
        entries = entries_from_commits(commits, exclude_patterns=[r"^Merge"])
        assert len(entries) == 1
        assert "good" in entries[0].content
