"""数据模型单元测试"""

from datetime import datetime

from cli.models import DailyEntry, DailyReport, CommitInfo, Config, EntrySource


class TestDailyEntry:
    def test_create_git_entry(self):
        entry = DailyEntry(
            content="feat: 添加登录",
            source=EntrySource.GIT_COMMIT,
            repo_name="my-repo",
            branch="feature/login",
            commit_hash="abc123",
        )
        assert entry.source == EntrySource.GIT_COMMIT
        assert entry.repo_name == "my-repo"
        assert entry.id  # auto-generated

    def test_create_manual_entry(self):
        entry = DailyEntry(
            content="参加评审会议",
            source=EntrySource.MANUAL,
        )
        assert entry.repo_name == "manual"
        assert entry.commit_hash is None

    def test_to_dict_and_from_dict(self):
        entry = DailyEntry(
            content="feat: 添加登录",
            source=EntrySource.GIT_COMMIT,
            repo_name="my-repo",
            branch="main",
            commit_hash="abc123",
        )
        d = entry.to_dict()
        restored = DailyEntry.from_dict(d)
        assert restored.content == entry.content
        assert restored.source == entry.source
        assert restored.branch == "main"

    def test_from_dict_defaults(self):
        d = {"content": "test", "source": "manual"}
        entry = DailyEntry.from_dict(d)
        assert entry.content == "test"
        assert entry.source == EntrySource.MANUAL
        assert entry.repo_name == "manual"


class TestDailyReport:
    def test_create_empty(self):
        report = DailyReport(date="2026-06-04", day_of_week="星期四")
        assert report.entries == []
        assert report.extra_notes == ""

    def test_to_dict_and_from_dict(self):
        entry = DailyEntry(content="test", source=EntrySource.MANUAL)
        report = DailyReport(
            date="2026-06-04",
            day_of_week="星期四",
            entries=[entry],
            extra_notes="明天继续",
        )
        d = report.to_dict()
        restored = DailyReport.from_dict(d)
        assert len(restored.entries) == 1
        assert restored.extra_notes == "明天继续"


class TestCommitInfo:
    def test_to_daily_entry(self):
        ci = CommitInfo(
            hash="abc123",
            message="feat: 新功能",
            author="test",
            timestamp=datetime(2026, 6, 4, 10, 0),
            repo_name="my-repo",
            branch="main",
        )
        entry = ci.to_daily_entry()
        assert entry.content == "feat: 新功能"
        assert entry.source == EntrySource.GIT_COMMIT
        assert entry.commit_hash == "abc123"
        assert entry.repo_name == "my-repo"


class TestConfig:
    def test_default_config(self):
        config = Config()
        assert config.scan_repos == []
        assert config.report_language == "zh"

    def test_roundtrip(self):
        config = Config(
            git_author="张三",
            scan_repos=["/path/to/repo"],
            exclude_patterns=["^WIP"],
        )
        d = config.to_dict()
        restored = Config.from_dict(d)
        assert restored.git_author == "张三"
        assert restored.scan_repos == ["/path/to/repo"]
        assert restored.exclude_patterns == ["^WIP"]
