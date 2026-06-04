"""LLM 总结模块单元测试"""

from cli.llm_summary import _build_summary_prompt
from cli.models import DailyReport, DailyEntry, EntrySource


class TestSummaryPrompt:
    def test_build_prompt_basic(self):
        reports = [
            DailyReport(
                date="2026-06-01",
                day_of_week="星期一",
                entries=[
                    DailyEntry(content="feat: 登录模块", source=EntrySource.GIT_COMMIT),
                    DailyEntry(content="参加需求评审", source=EntrySource.MANUAL),
                ],
            ),
        ]
        prompt = _build_summary_prompt(reports)
        assert "2026-06-01" in prompt
        assert "feat: 登录模块" in prompt
        assert "参加需求评审" in prompt
        assert "工作总结" in prompt

    def test_build_prompt_multiple_days(self):
        reports = [
            DailyReport(
                date="2026-06-01",
                day_of_week="星期一",
                entries=[DailyEntry(content="feat: A", source=EntrySource.GIT_COMMIT)],
            ),
            DailyReport(
                date="2026-06-02",
                day_of_week="星期二",
                entries=[DailyEntry(content="feat: B", source=EntrySource.GIT_COMMIT)],
            ),
        ]
        prompt = _build_summary_prompt(reports)
        assert "2026-06-01" in prompt
        assert "2026-06-02" in prompt
        assert "feat: A" in prompt
        assert "feat: B" in prompt
