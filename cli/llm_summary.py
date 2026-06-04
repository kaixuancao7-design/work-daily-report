"""LLM 智能总结模块

调用 AI API 对一周工作进行自然语言概括总结。
支持 OpenAI 和 Anthropic API。
"""

import json
import os
import urllib.request
from typing import Optional

from cli.models import DailyReport, Config


def _get_api_config(config: Config) -> tuple[str, str, str]:
    """获取 API 配置，优先环境变量"""
    api_key = config.llm_api_key or os.environ.get("LLM_API_KEY", "")
    api_base = config.llm_api_base or os.environ.get("LLM_API_BASE", "")
    model = config.llm_model or os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    return api_key, api_base, model


def _build_summary_prompt(daily_reports: list[DailyReport]) -> str:
    """构建 LLM 总结提示词"""
    entries_text = []
    for report in daily_reports:
        day_label = f"{report.date} {report.day_of_week}"
        day_entries = "\n".join(f"  - {e.content}" for e in report.entries)
        entries_text.append(f"### {day_label}\n{day_entries}")

    work_log = "\n\n".join(entries_text)

    return f"""你是一个技术团队的周报助手。请根据以下本周工作记录，用中文写一段 3-5 句话的工作总结。

要求：
1. 概括本周主要工作方向和成果
2. 突出重点项目或关键进展
3. 语言简洁、专业
4. 直接输出总结文本，不要加标题或前缀

本周工作记录：

{work_log}

工作总结："""


def generate_weekly_summary(
    daily_reports: list[DailyReport],
    config: Config,
) -> Optional[str]:
    """调用 LLM 生成本周工作总结

    Args:
        daily_reports: 一周日报列表
        config: 全局配置（含 LLM API 信息）

    Returns:
        AI 生成的总结文本，失败返回 None
    """
    api_key, api_base, model = _get_api_config(config)

    if not api_key:
        # 尝试使用 Anthropic SDK 或 OpenAI SDK 的环境变量
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        return None

    prompt = _build_summary_prompt(daily_reports)

    # 判断 API 类型
    if "claude" in model.lower():
        return _call_anthropic(prompt, api_key, api_base, model)
    else:
        return _call_openai(prompt, api_key, api_base, model)


def _call_anthropic(prompt: str, api_key: str, api_base: str, model: str) -> Optional[str]:
    """调用 Anthropic Messages API"""
    base_url = api_base or "https://api.anthropic.com"
    url = f"{base_url}/v1/messages"

    body = {
        "model": model,
        "max_tokens": 500,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", [{}])
            if content:
                return content[0].get("text", "").strip()
    except Exception as e:
        print(f"[LLM] Anthropic API 调用失败: {e}")
        return None

    return None


def _call_openai(prompt: str, api_key: str, api_base: str, model: str) -> Optional[str]:
    """调用 OpenAI Chat Completions API"""
    base_url = api_base or "https://api.openai.com"
    url = f"{base_url}/v1/chat/completions"

    body = {
        "model": model,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": "你是一个技术团队的周报助手。请用中文回答。"},
            {"role": "user", "content": prompt},
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[LLM] OpenAI API 调用失败: {e}")
        return None

    return None
