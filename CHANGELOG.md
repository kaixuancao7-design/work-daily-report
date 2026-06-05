# Changelog

## v0.2.1 (2026-06-05)

### 🔧 重要修复

**v0.2.0 版本存在以下已知问题，v0.2.1 已全部修复：**

1. **VSIX 在其他项目中无法使用** (`can't open file 'cli/main.py': No such file or directory`)
   - 原因：VSIX 未包含 Python 文件；`findProjectRoot()` 仅在开发工作区有效
   - 修复：通过 `copy-python` 脚本将 `cli/` 和 `templates/` 打包进 VSIX；使用 `getExtensionDir()` 基于 `__dirname` 定位扩展安装目录

2. **其他项目中无法识别 Git 提交记录**
   - 原因：`cwd` 设为扩展安装目录，`auto_detect_repos()` 扫描了错误的目录
   - 修复：将 `cwd` 改为 `workspaceRoot`

3. **日报生成为空，无诊断信息**
   - 原因：Python CLI 的诊断信息写入 stderr，但扩展在成功时静默丢弃 stderr，用户无法看到扫描结果
   - 修复：`runPythonCli` 始终将 stderr 输出到 VSCode 输出频道；输出面板改为追加模式

4. **Windows GBK 编码错误** (`UnicodeDecodeError: 'gbk' codec can't decode byte 0xaa`)
   - 原因：`subprocess.run(text=True)` 默认使用系统编码（GBK），Git 输出含 UTF-8 emoji
   - 修复：所有 `subprocess.run` 调用显式指定 `encoding="utf-8"`

5. **`auto_detect_repos()` 扫描缓慢**
   - 原因：扫描数百个目录，每个都启动 `git rev-parse` 子进程
   - 修复：添加 25 个常见非仓库目录跳过列表，先用纯文件系统检查 `.git` 目录再启动子进程

### ✨ 改进

- VSCode 输出频道现在显示完整的 CLI 诊断信息（扫描进度、仓库数、提交数）
- `main.py` 通过 `sys.path.insert()` 自解析导入路径，无需外部 PYTHONPATH
- `.gitignore` 和 `.vscodeignore` 优化

---

## v0.2.0 (2026-06-04)

> ⚠️ **此版本存在上述已知问题，请使用 v0.2.1+**

### 功能

- 多仓库自动发现与 Git 提交解析
- 日报/周报生成（Markdown 模板）
- LLM 智能总结（周报）
- 多平台模板导出（飞书、钉钉）
- VSCode 扩展：侧边栏、状态栏、命令面板
- 历史日报浏览器（年→月→日 树形层级）
- 定时调度 + 断点追赶
- 手动工作条目补充
- 剪贴板/文件/编辑器 多种输出方式

---

## v0.1.0

### 初始版本

- Python CLI 核心：日报生成、周报汇总
- Git 提交解析
- JSON 文件存储
- Jinja2 模板渲染
- VSCode 扩展基础集成
