# work-daily-report

基于 Git 提交记录自动生成工作日报 / 周报的 CLI 工具。

## 功能

- **自动生成日报**: 解析本地 Git 仓库的 commit 记录，自动填充「今日完成」
- **手动补充**: 支持交互式添加非代码类工作条目（会议、文档、沟通等）
- **周报汇总**: 汇总一周日报，按 commit hash 去重 + 同主题合并
- **多仓库**: 支持同时扫描多个 Git 仓库
- **本地存储**: 日报数据以 JSON 格式存储在本地，方便版本管理

## 安装

```bash
pip install -e .
```

依赖：Python 3.10+, click, GitPython, Jinja2, python-dateutil, pyperclip

## 快速开始

```bash
# 1. 查看当前配置（自动检测 git user.name）
daily-report config --show

# 2. 生成今日日报（交互式，可补充手动条目和备注）
daily-report generate today

# 3. 跳过交互，直接输出日报
daily-report generate today --no-manual

# 4. 直接复制到剪贴板
daily-report generate today --output clipboard

# 5. 生成本周周报
daily-report generate week
```

## 命令详解

### `generate today` — 生成今日日报

```
daily-report generate today [OPTIONS]

选项:
  -a, --author TEXT      指定 Git 作者名
  -r, --repo TEXT        指定仓库路径（可多次使用）
  -o, --output [stdout|clipboard|file]  输出方式
  --no-manual            跳过交互式手动补充
  --save / --no-save     是否保存到 JSON 存储（默认保存）
```

执行流程：
1. 扫描 Git 仓库，解析今天的所有 commit
2. 交互式添加手动工作条目（按 Enter 跳过）
3. 交互式输入备注（明日计划、遇到的问题等）
4. 渲染日报 Markdown 并输出
5. 保存到 `data/daily-reports/YYYY/MM/YYYY-MM-DD.json`

### `generate week` — 生成周报

```
daily-report generate week [OPTIONS]

选项:
  --from-date TEXT  周起始日期 (YYYY-MM-DD)，默认本周一
  --to-date TEXT    周结束日期 (YYYY-MM-DD)，默认本周日
  -o, --output [stdout|clipboard|file]
```

执行流程：
1. 加载本周已保存的所有日报
2. 合并条目 → 按 commit hash 去重
3. 汇总统计（总提交数、仓库数、手动条目数）
4. 渲染周报 Markdown 并输出

### `list` — 列出已有日报

```bash
daily-report list              # 最近 14 天
daily-report list --week       # 本周
daily-report list --month      # 本月
```

### `edit` — 编辑日报

```bash
daily-report edit                      # 查看今天日报
daily-report edit 2026-06-04           # 查看指定日期日报
daily-report edit --add                # 交互式添加手动条目
daily-report edit --remove <entry-id>  # 按 ID 删除条目
daily-report edit --notes "备注内容"   # 修改备注
```

### `config` — 配置管理

```bash
daily-report config --show                     # 查看当前配置
daily-report config --set-author "张三"         # 设置 Git 作者
daily-report config --add-repo /path/to/repo   # 添加扫描仓库
```

### `vscode` — VSCode 集成

```bash
daily-report vscode --today        # 输出今日日报 Markdown
daily-report vscode --today --json # 输出今日日报 JSON（供 VSCode 扩展消费）
daily-report vscode --week         # 输出周报 Markdown
```

## 配置

配置文件: `data/config.json`

```json
{
  "git_author": "",              // Git 作者名（空 = 自动检测 git config）
  "git_author_email": "",
  "scan_repos": [],              // 要扫描的仓库路径，空 = 当前目录
  "report_language": "zh",
  "daily_template": "daily.md.j2",
  "weekly_template": "weekly.md.j2",
  "include_branches": ["*"],     // 包含的分支
  "exclude_branches": [],
  "exclude_patterns": [          // 排除的 commit message 正则
    "^(Merge|chore|WIP)",
    "auto-commit"
  ]
}
```

## 数据存储

日报数据存储在 `data/daily-reports/` 目录下，按年/月分层：

```
data/
├── config.json
└── daily-reports/
    └── 2026/
        └── 06/
            ├── 2026-06-04.json
            └── 2026-06-05.json
```

## 项目结构

```
work-daily-report/
├── cli/
│   ├── __init__.py              # 包入口
│   ├── models.py                # 数据模型 (DailyEntry, DailyReport, CommitInfo, Config)
│   ├── utils.py                 # 日期处理 & 工具函数
│   ├── git_parser.py            # Git log 解析模块
│   ├── storage.py               # JSON 持久化存储 + 配置管理
│   ├── report_generator.py      # Jinja2 模板渲染
│   └── main.py                  # Click CLI 入口
├── templates/
│   ├── daily.md.j2              # 日报 Markdown 模板
│   └── weekly.md.j2             # 周报 Markdown 模板
├── tests/                       # 单元测试
│   ├── test_models.py
│   ├── test_storage.py
│   └── test_report_generator.py
├── data/                        # 本地数据存储
│   ├── config.json
│   └── daily-reports/
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v
```

## 路线图

- [x] Python CLI 核心（日报生成、周报汇总、JSON 存储）
- [ ] VSCode 扩展（命令面板、状态栏、侧边栏面板）
- [ ] LLM 智能总结（可选，对周报进行自然语言总结）
- [ ] 团队平台同步（飞书、企业微信等）
