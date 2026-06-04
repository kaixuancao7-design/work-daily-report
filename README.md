# work-daily-report

基于 Git 提交记录自动生成工作日报 / 周报的 CLI 工具，附带 VSCode 扩展。

## 功能

- **自动生成日报**: 解析本地 Git 仓库的 commit 记录，自动填充「今日完成」
- **多仓库自动发现**: 自动扫描工作区下所有 Git 仓库（3 层深度），无需手动配置
- **手动补充**: 交互式添加非代码类工作条目（会议、文档、沟通等）
- **周报汇总**: 汇总一周日报，按 commit hash 去重 + 同主题合并
- **LLM 智能总结**: 可选调用 AI 对本周工作进行自然语言概括
- **多模板导出**: 内置默认 / 飞书 / 钉钉模板，支持自定义模板目录
- **Webhook 推送**: 支持飞书、钉钉机器人 Webhook 一键推送
- **VSCode 扩展**: 命令面板、状态栏、侧边栏、Webview 预览等编辑器内体验

## 安装

```bash
# Python CLI
pip install -e .

# VSCode 扩展
code --install-extension vscode-extension/daily-report-0.1.0.vsix
```

依赖：Python 3.10+, click, GitPython, Jinja2, python-dateutil, pyperclip

## 快速开始

```bash
# 查看配置
daily-report config --show

# 生成今日日报（自动发现仓库，交互式补充手动条目）
daily-report generate today

# 跳过交互，复制到剪贴板
daily-report generate today --no-manual --output clipboard

# 飞书格式日报
daily-report generate today --template daily-feishu.md.j2

# 生成本周周报 + AI 智能总结
daily-report generate week --summary

# 导出并推送到飞书机器人
daily-report export today --format feishu --webhook https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

## 命令详解

### `generate today` — 生成今日日报

```
daily-report generate today [OPTIONS]

选项:
  -a, --author TEXT      指定 Git 作者名
  -r, --repo TEXT        指定仓库路径（可多次使用，为空 = 自动发现）
  -o, --output [stdout|clipboard|file]  输出方式
  -t, --template TEXT    模板名称（daily.md.j2 / daily-feishu.md.j2 / daily-dingtalk.md.j2）
  --no-manual            跳过交互式手动补充
  --save / --no-save     是否保存到 JSON 存储（默认保存）
```

执行流程：
1. 自动发现或手动指定 Git 仓库
2. 解析今天的所有 commit，排除 Merge / chore / WIP 等
3. 交互式添加手动工作条目（按 Enter 跳过）
4. 交互式输入备注
5. 用指定模板渲染 Markdown 并输出
6. 保存到 `data/daily-reports/YYYY/MM/YYYY-MM-DD.json`

### `generate week` — 生成周报

```
daily-report generate week [OPTIONS]

选项:
  --from-date TEXT  周起始日期 (YYYY-MM-DD)，默认本周一
  --to-date TEXT    周结束日期 (YYYY-MM-DD)，默认本周日
  --summary         使用 LLM 对本周工作进行智能总结
  -t, --template TEXT  模板名称
  -o, --output [stdout|clipboard|file]
```

### `export` — 导出 & 推送

```
daily-report export [today|week] [OPTIONS]

选项:
  -f, --format [markdown|feishu|dingtalk|text]  导出格式
  -w, --webhook TEXT    Webhook 地址，推送后自动发送到目标群
  -o, --output [stdout|clipboard|file]
```

### `list` — 列出已有日报

```bash
daily-report list              # 最近 14 天
daily-report list --week       # 本周
daily-report list --month      # 本月
```

### `edit` — 编辑日报

```bash
daily-report edit                      # 查看今天日报
daily-report edit 2026-06-04           # 查看指定日期
daily-report edit --add                # 交互式添加条目
daily-report edit --remove <entry-id>  # 按 ID 删除
daily-report edit --notes "备注内容"   # 修改备注
```

### `config` — 配置管理

```bash
daily-report config --show                     # 查看当前配置
daily-report config --set-author "张三"         # 设置 Git 作者
daily-report config --add-repo /path/to/repo   # 添加扫描仓库
```

### `vscode` — VSCode 扩展专用

```bash
daily-report vscode --today              # 输出今日日报 Markdown
daily-report vscode --today --json       # 输出 JSON（供扩展消费）
daily-report vscode --week               # 输出周报 Markdown
```

## 配置

配置文件: `data/config.json`

```json
{
  "git_author": "",
  "git_author_email": "",
  "scan_repos": [],
  "auto_detect_repos": true,
  "scan_max_depth": 3,
  "include_branches": ["*"],
  "exclude_branches": [],
  "exclude_patterns": ["^(Merge|chore|WIP)", "auto-commit"],
  "report_language": "zh",
  "daily_template": "daily.md.j2",
  "weekly_template": "weekly.md.j2",
  "custom_template_dir": "",
  "llm_api_key": "",
  "llm_api_base": "",
  "llm_model": "claude-sonnet-4-6",
  "export_webhook_url": "",
  "export_format": "markdown"
}
```

### LLM 配置

支持 Anthropic 和 OpenAI API：

```bash
# 环境变量方式（推荐）
export LLM_API_KEY=sk-xxx
export LLM_MODEL=claude-sonnet-4-6

# 或写入配置文件
daily-report config  # 手动编辑 data/config.json
```

## 模板

| 模板文件 | 用途 | 适用平台 |
|---------|------|---------|
| `daily.md.j2` | 标准日报 | 通用 Markdown |
| `weekly.md.j2` | 标准周报 | 通用 Markdown |
| `daily-feishu.md.j2` | 飞书日报 | 飞书消息 |
| `daily-dingtalk.md.j2` | 钉钉日报 | 钉钉消息 |

自定义模板：将 `.j2` 文件放到 `templates/custom/` 目录，然后设置：

```bash
daily-report config --set custom_template_dir templates/custom
```

## 数据存储

```
data/
├── config.json
└── daily-reports/
    └── 2026/
        └── 06/
            ├── 2026-06-04.json
            └── 2026-06-05.json
```

## VSCode 扩展

### 安装

```bash
code --install-extension vscode-extension/daily-report-0.1.0.vsix
```

或在 VSCode 中：`Ctrl+Shift+P` → `Extensions: Install from VSIX`

### 命令

| 命令 | 功能 |
|------|------|
| `日报: 生成今日日报` | 解析 Git 提交，生成日报 |
| `日报: 生成本周周报` | 汇总一周日报 |
| `日报: 在光标处插入今日日报` | 直接插入到编辑器 |
| `日报: 预览今日日报` | Webview 面板预览 |
| `日报: 添加手动工作条目` | 快速添加条目 |
| `日报: 导出日报` | 按格式导出 |
| `日报: 刷新今日条目` | 刷新侧边栏 |

### UI

- **状态栏**：右下角 `📋 日报` 按钮
- **侧边栏**：活动栏「工作日报」→「今日工作」面板
- **预览**：Webview 渲染日报 Markdown

### 配置项

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `dailyReport.pythonCommand` | `python` | Python 解释器 |
| `dailyReport.dataDir` | 空 | 数据目录（空=工作区 data/） |
| `dailyReport.outputTarget` | `outputChannel` | 输出目标 |
| `dailyReport.templateFormat` | `default` | 模板格式 |

## 项目结构

```
work-daily-report/
├── cli/
│   ├── __init__.py
│   ├── models.py                # 数据模型
│   ├── utils.py                 # 工具函数
│   ├── git_parser.py            # Git 日志解析
│   ├── storage.py               # JSON 持久化存储
│   ├── report_generator.py      # Jinja2 模板渲染
│   ├── llm_summary.py           # LLM API 调用
│   ├── export.py                # 导出 & Webhook 推送
│   └── main.py                  # Click CLI 入口
├── templates/                   # Jinja2 报告模板
│   ├── daily.md.j2
│   ├── weekly.md.j2
│   ├── daily-feishu.md.j2
│   └── daily-dingtalk.md.j2
├── vscode-extension/            # VSCode 扩展
│   ├── package.json
│   ├── src/extension.ts
│   ├── out/extension.js
│   └── daily-report-0.1.0.vsix
├── tests/                       # 40 个单元测试
├── data/                        # 本地数据（gitignore）
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 开发

```bash
# Python
pip install -e ".[dev]"
pytest tests/ -v

# VSCode 扩展
cd vscode-extension
npm install
npm run compile
npm run package      # 打包 .vsix
```

## 路线图

- [x] Python CLI 核心（日报、周报、JSON 存储）
- [x] 多仓库自动发现
- [x] LLM 智能总结（Anthropic / OpenAI）
- [x] 模板自定义 + 飞书/钉钉模板
- [x] 数据导出 + Webhook 推送
- [x] VSCode 扩展（命令面板、状态栏、侧边栏）
- [x] VSIX 打包
