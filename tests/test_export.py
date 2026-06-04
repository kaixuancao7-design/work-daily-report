"""导出模块单元测试"""

from cli.export import (
    to_feishu_markdown,
    to_dingtalk_markdown,
    to_plain_text,
)


class TestFormatConversion:
    def test_to_feishu_markdown(self):
        text = "# 日报\n## 今日完成\n- feat: test\n- 会议\n"
        result = to_feishu_markdown(text)
        assert "日报" in result
        assert "feat: test" in result
        assert "<p>" not in result  # HTML should be stripped

    def test_to_dingtalk_markdown(self):
        text = "**重要** 工作内容"
        result = to_dingtalk_markdown(text)
        assert "重要" in result
        assert "**" in result  # markdown bold preserved

    def test_to_plain_text(self):
        text = "# 标题\n**加粗**\n- 列表项"
        result = to_plain_text(text)
        assert "#" not in result
        assert "**" not in result
        assert "标题" in result
        assert "加粗" in result
        assert "列表项" in result
