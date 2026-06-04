"""Git 日志解析模块

负责从 Git 仓库中提取提交记录，支持：
- 解析今日 / 指定日期 / 本周的提交
- 多仓库扫描
- 按分支 / commit message 模式过滤
"""

import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from cli.models import CommitInfo
from cli.utils import is_same_day


class GitParser:
    """Git 提交解析器"""

    def __init__(
        self,
        repo_path: str = ".",
        author: str = "",
        author_email: str = "",
    ):
        repo = Path(repo_path).resolve()
        # 支持仓库根目录和子目录
        self.repo_path = self._find_repo_root(repo)
        self.author = author
        self.author_email = author_email
        self.repo_name = self.repo_path.name

    @staticmethod
    def _find_repo_root(path: Path) -> Path:
        """向上查找 Git 仓库根目录"""
        for parent in [path, *path.parents]:
            if (parent / ".git").exists():
                return parent
        # 如果找不到 .git，回退到传入的路径
        return path

    @staticmethod
    def _is_git_repo(path: Path) -> bool:
        """检查路径是否在 Git 仓库中"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True, text=True, timeout=5,
                cwd=str(path),
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_git_log(self, since: str, until: str = "", branch: str = "") -> list[str]:
        """执行 git log 命令，返回原始输出行列表

        Args:
            since: 起始时间，如 "2026-06-04 00:00:00"
            until: 截止时间，如 "2026-06-05 00:00:00"
            branch: 分支名，空 = 所有分支
        """
        cmd = [
            "git", "log",
            f"--since={since}",
            "--format=%H|%s|%an|%ai|%D",
            "--no-merges",
        ]

        if until:
            cmd.append(f"--until={until}")
        if self.author:
            cmd.append(f"--author={self.author}")
        if branch:
            cmd.append(branch)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10,
                cwd=str(self.repo_path),
            )
            if result.returncode != 0:
                return []
            return [line for line in result.stdout.strip().split("\n") if line]
        except Exception:
            return []

    def _parse_log_line(self, line: str, commit_date: date) -> Optional[CommitInfo]:
        """解析单行 git log 输出

        格式: %H|%s|%an|%ai|%D
        示例: a1b2c3d|feat: 添加登录模块|张三|2026-06-04 10:30:00 +0800|feature/login
        """
        parts = line.split("|", 4)
        if len(parts) < 5:
            return None

        commit_hash = parts[0]
        message = parts[1].strip()
        author = parts[2]
        timestamp_str = parts[3].strip()
        refs_str = parts[4].strip()

        # 解析时间戳
        try:
            timestamp = datetime.strptime(timestamp_str[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

        # 解析分支名
        branch = self._parse_branch_from_refs(refs_str)

        return CommitInfo(
            hash=commit_hash,
            message=message,
            author=author,
            timestamp=timestamp,
            repo_name=self.repo_name,
            branch=branch,
        )

    @staticmethod
    def _parse_branch_from_refs(refs_str: str) -> str:
        """从 git refs 字符串中提取分支名

        refs 格式: "HEAD -> main, origin/main" 或 "feature/login" 或 "tag: v1.0"
        """
        if not refs_str:
            return ""
        # 优先取 HEAD -> xxx
        match = re.search(r"HEAD -> ([^,]+)", refs_str)
        if match:
            return match.group(1).strip()
        # 否则取第一个 ref
        first_ref = refs_str.split(",")[0].strip()
        if first_ref and not first_ref.startswith("tag:"):
            return first_ref
        return ""

    def get_commits_by_date(self, target_date: date) -> list[CommitInfo]:
        """获取指定日期的提交记录"""
        since = f"{target_date.isoformat()} 00:00:00"
        until = f"{(target_date + timedelta(days=1)).isoformat()} 00:00:00"
        lines = self._run_git_log(since=since, until=until)
        commits = []
        for line in lines:
            ci = self._parse_log_line(line, target_date)
            if ci is not None:
                commits.append(ci)
        return commits

    def get_today_commits(self) -> list[CommitInfo]:
        """获取今天的所有提交"""
        return self.get_commits_by_date(date.today())

    def get_week_commits(self) -> dict[date, list[CommitInfo]]:
        """获取本周所有提交，按日期分组"""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        result: dict[date, list[CommitInfo]] = {}

        for i in range(7):
            d = monday + timedelta(days=i)
            commits = self.get_commits_by_date(d)
            if commits:
                result[d] = commits

        return result

    def scan_multiple_repos(self, repo_paths: list[str]) -> dict[str, list[CommitInfo]]:
        """扫描多个仓库，返回按仓库分组的提交"""
        today_date = date.today()
        result: dict[str, list[CommitInfo]] = {}

        for rp in repo_paths:
            parser = GitParser(repo_path=rp, author=self.author)
            commits = parser.get_commits_by_date(today_date)
            if commits:
                result[parser.repo_name] = commits

        return result

    def is_available(self) -> bool:
        """检查是否可以正常使用 Git"""
        return self._is_git_repo(self.repo_path)


# 自动发现时跳过的高频非仓库目录
_SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".svn", ".hg",
    "venv", ".venv", "env", ".env", ".tox",
    "dist", "build", ".eggs", "eggs",
    ".vscode", ".idea", ".claude",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "site-packages", "__pypackages__",
    "bower_components", ".next", ".nuxt",
}

# 自动发现时跳过的路径前缀模式
_SKIP_PATTERNS = [
    r"\.(git|svn|hg)$",
    r"node_modules",
    r"__pycache__",
    r"(venv|\.venv|\.tox)$",
    r"site-packages",
    r"\.(vscode|idea|claude)$",
]


def _should_skip_dir(dir_path: Path) -> bool:
    """快速判断目录是否应该跳过（纯文件系统检查，不启动子进程）"""
    name = dir_path.name
    if name in _SKIP_DIRS:
        return True
    # 跳过隐藏目录（除了 . 和 ..）
    if name.startswith(".") and name not in (".", ".."):
        return True
    return False


def _has_git_dir(path: Path) -> bool:
    """快速检查路径是否包含 .git 目录（纯文件系统检查，不启动子进程）"""
    return (path / ".git").is_dir()


def auto_detect_repos(base_path: str = ".", max_depth: int = 2) -> list[str]:
    """自动检测指定路径下的 Git 仓库列表

    优化策略：
    1. 先用纯文件系统检查 .git 目录，确认后再用 git rev-parse 验证
    2. 跳过 node_modules、__pycache__ 等高频非仓库目录
    3. 跳过所有隐藏目录

    Args:
        base_path: 扫描起点
        max_depth: 最大扫描深度
    """
    repos = []
    base = Path(base_path).resolve()

    # 首先检查 base_path 自身
    if _has_git_dir(base) and GitParser._is_git_repo(base):
        repos.append(str(base))

    # 扫描子目录
    for depth in range(1, max_depth + 1):
        pattern = "/".join(["*"] * depth)
        for p in base.glob(pattern):
            if not p.is_dir():
                continue
            if _should_skip_dir(p):
                continue
            if str(p) in repos:
                continue
            # 快速过滤：没有 .git 目录的直接跳过
            if not _has_git_dir(p):
                continue
            # 最终用 git rev-parse 确认
            if GitParser._is_git_repo(p):
                repos.append(str(p))

    return repos
