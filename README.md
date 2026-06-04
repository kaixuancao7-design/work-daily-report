# work-daily-report

**基于 Git 提交记录自动生成工作日报 / 周报的 CLI 工具 + VSCode 扩展。**

> 每天下班前对着屏幕回忆今天干了什么？写周报时翻遍 git log 拼凑本周内容？这个工具帮你省掉这些重复劳动。
>
> 解析本地 Git 仓库 commit 记录，自动填入「今日完成」，动手补充非代码工作，30 秒生成日报、1 分钟生成周报。

## 功能

| 能力 | 说明 |
|------|------|
| 📦 **Git 自动填充** | 扫描本地仓库，自动提取今天所有 commit 作为工作条目 |
| 🔍 **多仓库发现** | 自动检测工作区下所有 Git 仓库（3 层深度），无需手动配置 |
| ✍️ **手动补充** | 交互式添加会议、文档、沟通等非代码条目 |
| 📋 **周报汇总** | 合并一周日报，按 commit hash 去重 + 同主题归并 |
| 🤖 **LLM 智能总结** | 调用 AI（Anthropic / OpenAI）对本周工作进行自然语言概括 |
| 📄 **多平台模板** | 内置通用 Markdown、飞书、钉钉四套模板，支持自定义 |
| 🔗 **Webhook 推送** | 一键推送日报/周报到飞书或钉钉群聊 |
| 🖥️ **VSCode 深度集成** | 命令面板、状态栏按钮、多视图侧边栏、Webview 预览 |
| 📅 **历史日报浏览** | 侧边栏按 年→月→日 层级展示全部历史日报，点击即看 |
| ⏰ **定时自动总结** | 设定每日/每周自动触发，关机错过自动补全（断点追赶） |

### 解决了什么问题

| 痛点 | 方案 |
|------|------|
| 下班前忘记今天做了什么 | 自动从 Git 提取当日 commit |
| 非代码工作（会议、文档）无法追溯 | 交互式补充，统一存入日报 |
| 写周报时逐天凑内容 | 自动合并一周日报 + AI 总结 |
| 团队要日报还得手动发群 | 导出 + Webhook 推送到飞书/钉钉 |
| VSCode 与外部分工割裂 | 扩展内一键生成、预览、插入 |

## 安装

```bash
# Python CLI
pip install -e .

# VSCode 扩展
code --install-extension vscode-extension/daily-report-0.2.0.vsix
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
daily-report vscode --history-tree       # 输出全部日报 年→月→日 层级 JSON
daily-report vscode --report 2026-06-04  # 输出指定日期 Markdown
daily-report vscode --catchup            # 执行断点追赶，补全缺失日报/周报
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
  "export_format": "markdown",
  "schedule_enabled": true,
  "schedule_daily_time": "18:00",
  "schedule_weekly_day": 5,
  "schedule_weekly_time": "18:30",
  "schedule_auto_save": true,
  "schedule_auto_summary": false
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

### 定时调度配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `schedule_enabled` | `true` | 是否启用自动定时总结 |
| `schedule_daily_time` | `"18:00"` | 每日自动生成日报的时间 |
| `schedule_weekly_day` | `5` | 周报生成日（5=周五） |
| `schedule_weekly_time` | `"18:30"` | 周报生成时间 |
| `schedule_auto_save` | `true` | 是否自动保存到 JSON 存储 |
| `schedule_auto_summary` | `false` | 周报是否自动启用 LLM 总结 |

**断点追赶机制**：VSCode 扩展每次激活时自动检查「上次运行日期」到「今天」之间是否有缺失的日报/周报，如有则自动补全。运行期间每 30 分钟检查一次。调度状态保存在 `data/.schedule_state.json` 中。

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
├── .schedule_state.json          # 定时调度状态
└── daily-reports/
    └── 2026/
        └── 06/
            ├── 2026-06-04.json
            ├── 2026-06-05.json
            └── weekly-2026-06-01.md
```

## VSCode 扩展

### 安装

```bash
code --install-extension vscode-extension/daily-report-0.2.0.vsix
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
| `日报: 查看历史日报` | 点击侧边栏日期 → Webview 查看历史报告 |
| `日报: 刷新今日条目` | 刷新"今日工作"侧边栏 |
| `日报: 刷新历史日报列表` | 刷新"历史日报"侧边栏 |
| `日报: 立即检查并补全缺失日报` | 手动触发断点追赶 |

### UI

- **状态栏**：右下角 `📋 日报` 按钮
- **侧边栏**：活动栏「工作日报」包含两个面板
  - **今日工作**：显示今日 Git 提交和手动条目
  - **历史日报**：按 📅 年 → 📁 月 → 📄 日 层级展示全部日报，点击在 Webview 中查看
- **预览**：Webview 渲染日报 Markdown

### 配置项

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `dailyReport.pythonCommand` | `python` | Python 解释器 |
| `dailyReport.dataDir` | 空 | 数据目录（空=工作区 data/） |
| `dailyReport.outputTarget` | `outputChannel` | 输出目标 |
| `dailyReport.templateFormat` | `default` | 模板格式 |
| `dailyReport.autoCatchup` | `true` | 启动时自动检查并补全缺失日报/周报 |
| `dailyReport.catchupDays` | `7` | 自动补全回溯的最大天数 |

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
│   ├── scheduler.py             # 定时调度 & 断点追赶
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
│   └── daily-report-0.2.0.vsix
├── tests/                       # 47 个单元测试
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
- [x] 多仓库自动发现 + 性能优化
- [x] LLM 智能总结（Anthropic / OpenAI）
- [x] 模板自定义 + 飞书/钉钉模板
- [x] 数据导出 + Webhook 推送
- [x] VSCode 扩展（命令面板、状态栏、多视图侧边栏）
- [x] VSIX 打包
- [x] 历史日报浏览（侧边栏 年→月→日 层级树）
- [x] 定时自动总结 + 断点追赶
