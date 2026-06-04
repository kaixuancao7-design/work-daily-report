"""数据导出模块

支持导出日报/周报到多种格式：
- 飞书 Markdown (richtext)
- 钉钉 Markdown
- 纯文本
- 通过 Webhook 直接推送
"""

import json
import urllib.request
from datetime import date
from typing import Optional

from cli.models import DailyReport, DailyEntry, EntrySource
from cli.utils import format_date, get_weekday_zh
from cli.storage import Storage
from cli.report_generator import (
    generate_daily_report,
    generate_weekly_report,
)


# ─── 格式转换 ─────────────────────────────────────


def to_feishu_markdown(text: str) -> str:
    """转换为飞书机器人支持的 Markdown 格式

    飞书支持部分 Markdown 语法：
    - 标题 # ## ###
    - 加粗 **text**
    - 列表 -
    - 不支持表格
    """
    # 飞书 Markdown 基本兼容标准 Markdown
    # 主要是去掉不支持的语法（如 HTML）
    lines = text.split("\n")
    filtered = []
    for line in lines:
        # 去除 HTML 标签
        import re
        line = re.sub(r"<[^>]+>", "", line)
        filtered.append(line)
    return "\n".join(filtered)


def to_dingtalk_markdown(text: str) -> str:
    """转换为钉钉机器人支持的 Markdown 格式

    钉钉 Markdown 支持：
    - 标题 # ~ ######
    - 加粗 **text**
    - 链接 [text](url)
    - 列表 -
    - 引用 >
    """
    # 钉钉基本兼容标准 Markdown
    lines = text.split("\n")
    filtered = []
    for line in lines:
        import re
        line = re.sub(r"<[^>]+>", "", line)
        filtered.append(line)
    return "\n".join(filtered)


def to_plain_text(text: str) -> str:
    """转换为纯文本（去除 Markdown 标记）"""
    import re
    # 去标题标记
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 去加粗
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # 去斜体
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text.strip()


# ─── Webhook 推送 ─────────────────────────────────


def send_webhook(webhook_url: str, content: str, msg_type: str = "markdown",
                 title: str = "工作日报") -> bool:
    """推送消息到飞书/钉钉机器人 Webhook

    Args:
        webhook_url: 机器人 Webhook 地址
        content: 消息内容（Markdown 格式）
        msg_type: feishu | dingtalk | markdown
        title: 消息标题

    Returns:
        推送是否成功
    """
    # 判断平台
    if "feishu" in webhook_url or "lark" in webhook_url:
        return _send_feishu(webhook_url, content, title)
    elif "dingtalk" in webhook_url:
        return _send_dingtalk(webhook_url, content, title)
    else:
        # 通用 webhook，尝试标准格式
        return _send_generic(webhook_url, content)


def _send_feishu(webhook_url: str, content: str, title: str) -> bool:
    """推送飞书消息"""
    body = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content,
                }
            ],
        },
    }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return True
            print(f"[Webhook] 飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"[Webhook] 飞书推送异常: {e}")
        return False


def _send_dingtalk(webhook_url: str, content: str, title: str) -> bool:
    """推送钉钉消息"""
    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content,
        },
    }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode") == 0:
                return True
            print(f"[Webhook] 钉钉推送失败: {result}")
            return False
    except Exception as e:
        print(f"[Webhook] 钉钉推送异常: {e}")
        return False


def _send_generic(webhook_url: str, content: str) -> bool:
    """通用 Webhook 推送"""
    body = {"content": content}
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        print(f"[Webhook] 推送异常: {e}")
        return False


# ─── 导出入口 ─────────────────────────────────────


def export_report(
    storage: Storage,
    report_date: Optional[date] = None,
    export_type: str = "daily",      # daily | week
    format: str = "markdown",        # markdown | feishu | dingtalk | text
    webhook_url: str = "",
) -> str:
    """导出报告

    Args:
        storage: 存储实例
        report_date: 日报日期（daily 模式）或周起始日期（week 模式）
        export_type: daily=单天日报, week=周报
        format: 输出格式
        webhook_url: 若不为空则同时推送

    Returns:
        格式化后的报告文本
    """
    from datetime import timedelta

    d = report_date or date.today()

    if export_type == "daily":
        report = storage.load_daily_report(d)
        if report is None:
            text = f"# {format_date(d)} 工作日报\n\n暂无工作记录。"
        else:
            entries = report.entries
            text = generate_daily_report(
                entries=entries,
                report_date=d,
                extra_notes=report.extra_notes,
            )
    else:
        # week
        monday = d - timedelta(days=d.weekday())
        reports = storage.load_week_reports(week_start=monday)
        text = generate_weekly_report(daily_reports=reports, week_start=monday)

    # 格式转换
    if format == "feishu":
        text = to_feishu_markdown(text)
    elif format == "dingtalk":
        text = to_dingtalk_markdown(text)
    elif format == "text":
        text = to_plain_text(text)

    # Webhook 推送
    if webhook_url:
        title = "工作日报" if export_type == "daily" else "工作周报"
        success = send_webhook(webhook_url, text, title=title)
        if success:
            print("✅ Webhook 推送成功")

    return text
