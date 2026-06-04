"""日期处理与工具函数"""

from datetime import date, datetime, timedelta
from typing import Optional

# 中文本地化星期映射
_WEEKDAY_NAMES_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def get_weekday_zh(d: date) -> str:
    """返回中文星期名"""
    return _WEEKDAY_NAMES_ZH[d.weekday()]


def today() -> date:
    """返回今天的日期"""
    return date.today()


def this_week_range(today_date: Optional[date] = None) -> tuple[date, date]:
    """返回本周一和本周日的日期（周一为一周开始）"""
    d = today_date or date.today()
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def date_range_since(since_days: int) -> list[date]:
    """返回过去 N 天的日期列表"""
    d = date.today()
    return [d - timedelta(days=i) for i in range(since_days)]


def format_date(d: date) -> str:
    """日期转 ISO 字符串"""
    return d.isoformat()


def parse_date(date_str: str) -> date:
    """从 ISO 字符串解析日期"""
    return date.fromisoformat(date_str)


def format_datetime(dt: datetime) -> str:
    """日期时间转 ISO 字符串"""
    return dt.isoformat()


def is_same_day(d1: date, d2: date) -> bool:
    """判断两个日期是否为同一天"""
    return d1 == d2


def get_default_author() -> str:
    """尝试从 git 配置获取默认作者名"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def get_default_author_email() -> str:
    """尝试从 git 配置获取默认邮箱"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""
