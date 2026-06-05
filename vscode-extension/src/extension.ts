import * as vscode from "vscode";
import { spawn } from "child_process";
import * as path from "path";

// ─── Python CLI 调用 ──────────────────────────────

interface VscodeTodayResult {
  status: string;
  date: string;
  day_of_week: string;
  commits_found: number;
  entries: DailyEntryData[];
  extra_notes: string;
}

interface DailyEntryData {
  id: string;
  content: string;
  source: "git_commit" | "manual";
  repo_name: string;
  branch: string | null;
  commit_hash: string | null;
  created_at: string;
  order: number;
}

function getWorkspaceRoot(): string {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    return folders[0].uri.fsPath;
  }
  return process.cwd();
}

/**
 * 查找扩展自身的安装目录（包含 cli/main.py 和 templates/ 的目录）。
 *
 * 扩展打包时会把 cli/ 和 templates/ 复制到扩展根目录下，
 * 因此优先使用扩展自带的 Python 脚本，而非依赖工作区。
 *
 * __dirname 在运行时是 <extension>/out/，上溯一级即扩展根目录。
 */
function getExtensionDir(): string {
  return path.resolve(__dirname, "..");
}

function getConfig() {
  const wsConfig = vscode.workspace.getConfiguration("dailyReport");
  return {
    pythonCommand: wsConfig.get<string>("pythonCommand") || "python",
    dataDir: wsConfig.get<string>("dataDir") || "",
    outputTarget: wsConfig.get<string>("outputTarget") || "outputChannel",
    templateFormat: wsConfig.get<string>("templateFormat") || "default",
  };
}

function getPythonCliArgs(
  subcommand: string,
  extraArgs: string[] = []
): { args: string[]; cwd: string; env: Record<string, string> } {
  const config = getConfig();
  const extensionDir = getExtensionDir();
  const cliEntry = path.join(extensionDir, "cli", "main.py");

  // 数据目录：优先用户配置，否则用工作区下的 .daily-report-data/
  const workspaceRoot = getWorkspaceRoot();
  const dataDir = config.dataDir || path.join(workspaceRoot, ".daily-report-data");

  // 构建参数: main.py <command> <extraArgs> --data-dir <dir>
  const cmdParts = subcommand.split(" ");
  const args = [cliEntry, ...cmdParts, ...extraArgs, "--data-dir", dataDir];

  // cwd 设为工作区根目录，确保 auto_detect_repos() 扫描用户项目而非扩展目录
  return {
    args,
    cwd: workspaceRoot,
    env: {},
  };
}

async function runPythonCli(
  args: string[],
  cwd: string,
  asJson: boolean = false,
  extraEnv: Record<string, string> = {}
): Promise<string> {
  const config = getConfig();
  const pythonCmd = config.pythonCommand;

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd, args, {
      cwd,
      shell: true,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, ...extraEnv },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout?.on("data", (data: Buffer) => {
      stdout += data.toString("utf-8");
    });

    proc.stderr?.on("data", (data: Buffer) => {
      stderr += data.toString("utf-8");
    });

    proc.on("error", (err) => {
      reject(new Error(`无法启动 Python CLI: ${err.message}。请确认 dailyReport.pythonCommand 配置正确。`));
    });

    proc.on("close", (code) => {
      if (code !== 0) {
        // 检查是否因为用户取消（如 Ctrl+C）
        if (code === 1 && !stderr && !stdout) {
          resolve(""); // 用户取消，静默处理
        }
        reject(new Error(`Python CLI 执行失败 (code=${code}): ${stderr || stdout}`));
        return;
      }
      resolve(stdout);
    });
  });
}

async function runVscodeCommand(
  subcommand: string,
  extraArgs: string[] = [],
  asJson: boolean = false
): Promise<VscodeTodayResult | null> {
  const { args, cwd, env } = getPythonCliArgs(`vscode ${subcommand}`, [
    ...(asJson ? ["--json"] : []),
    ...extraArgs,
  ]);

  const output = await runPythonCli(args, cwd, asJson, env);
  if (!output) return null;

  if (asJson) {
    return JSON.parse(output) as VscodeTodayResult;
  }
  return null;
}

// ─── 输出面板 ─────────────────────────────────────

let outputChannel: vscode.OutputChannel;

function getOutputChannel(): vscode.OutputChannel {
  if (!outputChannel) {
    outputChannel = vscode.window.createOutputChannel("工作日报助手");
  }
  return outputChannel;
}

async function showInOutputPanel(content: string) {
  const channel = getOutputChannel();
  channel.clear();
  channel.appendLine(content);
  channel.show(true);
}

async function showInNewEditor(content: string, fileName: string) {
  const doc = await vscode.workspace.openTextDocument({
    content,
    language: "markdown",
  });
  await vscode.window.showTextDocument(doc, { preview: false });
}

async function outputReport(content: string, title: string = "report") {
  const config = getConfig();
  switch (config.outputTarget) {
    case "clipboard":
      await vscode.env.clipboard.writeText(content);
      vscode.window.showInformationMessage("✅ 日报已复制到剪贴板");
      break;
    case "newEditor":
      await showInNewEditor(content, title);
      break;
    case "outputChannel":
    default:
      await showInOutputPanel(content);
      break;
  }
}

// ─── 侧边栏 TreeView ──────────────────────────────

interface TreeEntry {
  id: string;
  label: string;
  source: "git_commit" | "manual" | "section";
  repoName?: string;
  content?: string;
  commitHash?: string;
  branch?: string;
  children?: TreeEntry[];
}

class DailyReportTreeDataProvider
  implements vscode.TreeDataProvider<TreeEntry>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    TreeEntry | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private entries: TreeEntry[] = [];
  private dateLabel: string = "";

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  setData(dateLabel: string, entries: TreeEntry[]) {
    this.dateLabel = dateLabel;
    this.entries = entries;
    this.refresh();
  }

  getTreeItem(element: TreeEntry): vscode.TreeItem {
    if (element.source === "section") {
      const item = new vscode.TreeItem(
        element.label,
        vscode.TreeItemCollapsibleState.Expanded
      );
      item.contextValue = "section";
      if (element.label.startsWith("📦")) {
        item.iconPath = new vscode.ThemeIcon("repo");
      } else {
        item.iconPath = new vscode.ThemeIcon("edit");
      }
      return item;
    }

    const item = new vscode.TreeItem(
      element.label,
      vscode.TreeItemCollapsibleState.None
    );
    item.contextValue = "entry";
    item.tooltip = element.content || element.label;

    if (element.source === "git_commit") {
      item.iconPath = new vscode.ThemeIcon("git-commit");
      item.description = element.branch || element.repoName;
    } else {
      item.iconPath = new vscode.ThemeIcon("pencil");
    }

    return item;
  }

  getChildren(element?: TreeEntry): TreeEntry[] {
    if (element && element.children) {
      return element.children;
    }
    if (!element) {
      return this.entries;
    }
    return [];
  }

  getParent(): undefined {
    return undefined;
  }
}

// ─── 历史日报 TreeView ──────────────────────────

interface HistoryTreeNode {
  type: "year" | "month" | "date" | "empty";
  label: string;
  year?: number;
  month?: number;
  date?: string;
  dayOfWeek?: string;
  gitCount?: number;
  manualCount?: number;
  children?: HistoryTreeNode[];
}

class HistoryTreeDataProvider
  implements vscode.TreeDataProvider<HistoryTreeNode>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    HistoryTreeNode | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private rootNodes: HistoryTreeNode[] = [];

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  setData(nodes: HistoryTreeNode[]) {
    this.rootNodes = nodes;
    this.refresh();
  }

  getTreeItem(element: HistoryTreeNode): vscode.TreeItem {
    if (element.type === "year") {
      const item = new vscode.TreeItem(
        element.label,
        vscode.TreeItemCollapsibleState.Collapsed
      );
      item.iconPath = new vscode.ThemeIcon("calendar");
      item.contextValue = "history-year";
      return item;
    }
    if (element.type === "month") {
      const item = new vscode.TreeItem(
        element.label,
        vscode.TreeItemCollapsibleState.Collapsed
      );
      item.iconPath = new vscode.ThemeIcon("folder");
      item.contextValue = "history-month";
      return item;
    }
    if (element.type === "date") {
      const counts = `Git:${element.gitCount ?? 0} 手动:${element.manualCount ?? 0}`;
      const item = new vscode.TreeItem(
        element.label,
        vscode.TreeItemCollapsibleState.None
      );
      item.description = counts;
      item.iconPath = new vscode.ThemeIcon("note");
      item.contextValue = "history-date";
      item.tooltip = `${element.date} ${element.dayOfWeek} — ${counts}`;
      item.command = {
        command: "dailyReport.viewHistoryReport",
        title: "查看日报",
        arguments: [element],
      };
      return item;
    }
    // empty
    return new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
  }

  getChildren(element?: HistoryTreeNode): HistoryTreeNode[] {
    if (element && element.children) {
      return element.children;
    }
    if (!element) {
      return this.rootNodes;
    }
    return [];
  }

  getParent(): undefined {
    return undefined;
  }
}

async function buildHistoryTreeNodes(): Promise<HistoryTreeNode[]> {
  const { args, cwd, env } = getPythonCliArgs("vscode --history-tree", []);
  try {
    const output = await runPythonCli(args, cwd, false, env);
    const data = JSON.parse(output);
    if (data.status !== "ok" || !data.years) {
      return [{ type: "empty", label: "暂无历史日报" }];
    }
    return data.years.map((y: any) => ({
      type: "year" as const,
      label: `📅 ${y.year}年`,
      year: y.year,
      children: y.months.map((m: any) => ({
        type: "month" as const,
        label: `📁 ${String(m.month).padStart(2, "0")}月 (${m.dates.length}天)`,
        month: m.month,
        year: y.year,
        children: m.dates.map((dt: any) => ({
          type: "date" as const,
          label: `📄 ${dt.date.slice(5)} ${dt.day_of_week}`,
          date: dt.date,
          dayOfWeek: dt.day_of_week,
          gitCount: dt.git_count,
          manualCount: dt.manual_count,
        })),
      })),
    }));
  } catch {
    return [{ type: "empty", label: "加载历史日报失败" }];
  }
}

async function handleViewHistoryReport(node: HistoryTreeNode) {
  if (!node.date) return;

  const { args, cwd, env } = getPythonCliArgs("vscode", [
    "--report", node.date,
  ]);
  try {
    const content = await runPythonCli(args, cwd, false, env);
    if (content) {
      const panel = vscode.window.createWebviewPanel(
        "dailyReportHistory",
        `日报 ${node.date}`,
        vscode.ViewColumn.Beside,
        { enableScripts: false }
      );
      panel.webview.html = renderMarkdownAsHtml(content);
    }
  } catch (err: any) {
    vscode.window.showErrorMessage(`加载历史日报失败: ${err.message}`);
  }
}

async function handleRefreshHistoryTree() {
  if (!historyTreeProvider) return;
  const nodes = await buildHistoryTreeNodes();
  historyTreeProvider.setData(nodes);
}


// ─── 条目缓存与刷新 ──────────────────────────────

let treeProvider: DailyReportTreeDataProvider;
let historyTreeProvider: HistoryTreeDataProvider;

function buildTreeEntries(data: VscodeTodayResult): TreeEntry[] {
  const treeEntries: TreeEntry[] = [];
  const gitByRepo: Map<string, TreeEntry[]> = new Map();
  const manualEntries: TreeEntry[] = [];

  for (const entry of data.entries) {
    if (entry.source === "git_commit") {
      const repoName = entry.repo_name || "unknown";
      if (!gitByRepo.has(repoName)) {
        gitByRepo.set(repoName, []);
      }
      gitByRepo.get(repoName)!.push({
        id: entry.id,
        label: `  ${entry.content}`,
        source: "git_commit",
        repoName: entry.repo_name,
        content: entry.content,
        commitHash: entry.commit_hash || undefined,
        branch: entry.branch || undefined,
      });
    } else {
      manualEntries.push({
        id: entry.id,
        label: `  ${entry.content}`,
        source: "manual",
        content: entry.content,
      });
    }
  }

  // 按仓库分组
  for (const [repo, entries] of gitByRepo) {
    treeEntries.push({
      id: `section-git-${repo}`,
      label: `📦 ${repo} (${entries.length} 条提交)`,
      source: "section",
      repoName: repo,
      children: entries,
    });
  }

  if (manualEntries.length > 0) {
    treeEntries.push({
      id: "section-manual",
      label: `✍️ 其他工作 (${manualEntries.length} 条)`,
      source: "section",
      children: manualEntries,
    });
  }

  return treeEntries;
}

async function refreshTreeView() {
  if (!treeProvider) return;

  try {
    const data = await runVscodeCommand("--today", [], true);
    if (data && data.entries && data.entries.length > 0) {
      const treeEntries = buildTreeEntries(data);
      treeProvider.setData(data.date, treeEntries);
    } else if (data) {
      treeProvider.setData(data.date, [
        {
          id: "empty",
          label: "今日暂无工作记录",
          source: "section",
          children: [
            {
              id: "empty-hint",
              label: "点击状态栏 📋 生成今日日报",
              source: "manual",
            },
          ],
        },
      ]);
    }
  } catch (err: any) {
    // 静默失败，可能是还没有日报数据
    treeProvider.setData("", [
      {
        id: "error",
        label: `加载失败: ${err.message}`,
        source: "section",
        children: [],
      },
    ]);
  }
}

// ─── 命令处理器 ───────────────────────────────────

async function handleGenerateToday() {
  const config = getConfig();
  const templateArgs = config.templateFormat !== "default"
    ? ["--template", config.templateFormat === "feishu" ? "daily-feishu.md.j2"
      : config.templateFormat === "dingtalk" ? "daily-dingtalk.md.j2"
      : "daily.md.j2"]
    : [];
  const { args, cwd, env } = getPythonCliArgs("generate today", [
    "--no-manual",
    "--output", "stdout",
    ...templateArgs,
  ]);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "正在生成今日日报...",
      cancellable: false,
    },
    async (progress) => {
      try {
        const content = await runPythonCli(args, cwd, false, env);
        if (content) {
          await outputReport(content, "今日日报");
        } else {
          vscode.window.showInformationMessage("📭 今日暂无工作记录");
        }
        // 刷新侧边栏
        await refreshTreeView();
      } catch (err: any) {
        vscode.window.showErrorMessage(`生成日报失败: ${err.message}`);
      }
    }
  );
}

async function handleGenerateWeek() {
  const { args, cwd, env } = getPythonCliArgs("generate week", [
    "--output",
    "stdout",
  ]);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "正在生成本周周报...",
      cancellable: false,
    },
    async (progress) => {
      try {
        const content = await runPythonCli(args, cwd, false, env);
        if (content) {
          await outputReport(content, "本周周报");
        }
      } catch (err: any) {
        vscode.window.showErrorMessage(`生成周报失败: ${err.message}`);
      }
    }
  );
}

async function handleInsertAtCursor() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("请先打开一个编辑器文件，将光标定位到要插入日报的位置。");
    return;
  }

  const { args, cwd, env } = getPythonCliArgs("generate today", [
    "--no-manual",
    "--output",
    "stdout",
  ]);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "正在生成日报并插入...",
      cancellable: false,
    },
    async (progress) => {
      try {
        const content = await runPythonCli(args, cwd, false, env);
        if (content) {
          await editor.edit((editBuilder) => {
            editBuilder.insert(editor.selection.active, content);
          });
          vscode.window.showInformationMessage("✅ 日报已插入到光标位置");
        } else {
          vscode.window.showInformationMessage("📭 今日暂无工作记录");
        }
        await refreshTreeView();
      } catch (err: any) {
        vscode.window.showErrorMessage(`插入日报失败: ${err.message}`);
      }
    }
  );
}

async function handleAddManualEntry() {
  const content = await vscode.window.showInputBox({
    prompt: "请输入工作条目内容",
    placeHolder: "例：参加需求评审会议，确认 V2 迭代范围",
    validateInput: (value) => {
      if (!value || value.trim().length === 0) {
        return "内容不能为空";
      }
      return undefined;
    },
  });

  if (!content) return;

  // 获取今天的日期
  const today = new Date();
  const dateStr = today.toISOString().split("T")[0];

  const { args, cwd, env } = getPythonCliArgs(`edit ${dateStr}`, ["--add"]);

  // 需要通过 stdin 输入内容，然后发送空行结束
  try {
    const config = getConfig();
    const proc = spawn(config.pythonCommand, args, {
      cwd,
      shell: true,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, ...env },
    });

    proc.stdin?.write(content + "\n\n");
    proc.stdin?.end();

    let stdout = "";
    proc.stdout?.on("data", (data: Buffer) => {
      stdout += data.toString("utf-8");
    });

    await new Promise<void>((resolve, reject) => {
      proc.on("close", (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`exit code ${code}: ${stdout}`));
        }
      });
      proc.on("error", reject);
    });

    vscode.window.showInformationMessage(`✅ 已添加条目: ${content}`);
    await refreshTreeView();
  } catch (err: any) {
    vscode.window.showErrorMessage(`添加条目失败: ${err.message}`);
  }
}

async function handlePreviewToday() {
  const panel = vscode.window.createWebviewPanel(
    "dailyReportPreview",
    "今日工作日报",
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "正在加载日报...",
      cancellable: false,
    },
    async (progress) => {
      try {
        const { args, cwd, env } = getPythonCliArgs("generate", [
          "today",
          "--no-manual",
          "--output",
          "stdout",
        ]);
        const content = await runPythonCli(args, cwd, false, env);
        if (content) {
          panel.webview.html = renderMarkdownAsHtml(content);
        } else {
          panel.webview.html = "<p>今日暂无工作记录</p>";
        }
      } catch (err: any) {
        panel.webview.html = `<p style="color:red">加载失败: ${err.message}</p>`;
      }
    }
  );
}

function renderMarkdownAsHtml(markdown: string): string {
  // 简单的 Markdown → HTML 转换（生产环境可用 marked 库）
  const escaped = markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  let html = escaped
    // 标题
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    // 列表
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    // 引用
    .replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>")
    // 段落（连续空行分隔）
    .replace(/\n\n/g, "</p><p>")
    // 包裹 li
    .replace(
      /((?:<li>.*<\/li>\n?)+)/g,
      "<ul>\n$1</ul>"
    );

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      padding: 20px;
      line-height: 1.8;
      color: var(--vscode-editor-foreground);
      background: var(--vscode-editor-background);
    }
    h1 { font-size: 1.5em; border-bottom: 2px solid var(--vscode-panel-border); padding-bottom: 8px; }
    h2 { font-size: 1.2em; margin-top: 24px; }
    h3 { font-size: 1.1em; color: var(--vscode-textLink-foreground); }
    ul { padding-left: 20px; }
    li { margin: 6px 0; }
    blockquote {
      border-left: 3px solid var(--vscode-textBlockQuote-border);
      background: var(--vscode-textBlockQuote-background);
      padding: 8px 16px;
      margin: 12px 0;
    }
  </style>
</head>
<body>
  <p>${html}</p>
</body>
</html>`;
}

async function handleExport() {
  const config = getConfig();
  const format = config.templateFormat || "markdown";
  const { args, cwd, env } = getPythonCliArgs("export today", [
    "--format", format,
    "--output", "stdout",
  ]);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "正在导出日报...",
      cancellable: false,
    },
    async (progress) => {
      try {
        const content = await runPythonCli(args, cwd, false, env);
        if (content) {
          await outputReport(content, "日报导出");
        }
      } catch (err: any) {
        vscode.window.showErrorMessage(`导出失败: ${err.message}`);
      }
    }
  );
}

// ─── 定时调度服务 ───────────────────────────────

const CATCHUP_INTERVAL_MS = 30 * 60 * 1000; // 30 分钟

class SchedulerService {
  private intervalId: NodeJS.Timeout | null = null;

  async runCatchup() {
    const { args, cwd, env } = getPythonCliArgs("vscode --catchup", []);
    try {
      const output = await runPythonCli(args, cwd, false, env);
      const result = JSON.parse(output);
      if (result.status === "ok") {
        const dailyCount = (result.daily_generated as string[]).length;
        const weeklyInfo = result.weekly_generated as string;
        if (dailyCount > 0 || weeklyInfo) {
          const parts: string[] = [];
          if (dailyCount > 0) {
            parts.push(`${dailyCount} 天日报`);
          }
          if (weeklyInfo) {
            parts.push(`周报 (${weeklyInfo})`);
          }
          vscode.window.showInformationMessage(
            `📋 已自动补全: ${parts.join(" + ")}`
          );
        }
      }
    } catch {
      // 静默处理，不影响正常使用
    }
  }

  start(context: vscode.ExtensionContext) {
    // 启动时执行追赶
    this.runCatchup();

    // 定时检查
    this.intervalId = setInterval(() => {
      this.runCatchup();
    }, CATCHUP_INTERVAL_MS);

    context.subscriptions.push({
      dispose: () => this.stop(),
    });
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}


// ─── 激活 & 停用 ──────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
  console.log("工作日报助手 已激活");

  // 侧边栏 TreeView — 今日工作
  treeProvider = new DailyReportTreeDataProvider();
  const treeView = vscode.window.createTreeView("dailyReport.todayEntries", {
    treeDataProvider: treeProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(treeView);

  // 侧边栏 TreeView — 历史日报
  historyTreeProvider = new HistoryTreeDataProvider();
  const historyTreeView = vscode.window.createTreeView(
    "dailyReport.historyTree",
    {
      treeDataProvider: historyTreeProvider,
      showCollapseAll: true,
    }
  );
  context.subscriptions.push(historyTreeView);

  // 状态栏按钮
  const statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.text = "$(notebook) 日报";
  statusBarItem.tooltip = "工作日报助手";
  statusBarItem.command = "dailyReport.generateToday";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // 注册命令
  const commands = [
    vscode.commands.registerCommand("dailyReport.generateToday", handleGenerateToday),
    vscode.commands.registerCommand("dailyReport.generateWeek", handleGenerateWeek),
    vscode.commands.registerCommand("dailyReport.insertAtCursor", handleInsertAtCursor),
    vscode.commands.registerCommand("dailyReport.addManualEntry", handleAddManualEntry),
    vscode.commands.registerCommand("dailyReport.previewToday", handlePreviewToday),
    vscode.commands.registerCommand("dailyReport.refreshEntries", () => refreshTreeView()),
    vscode.commands.registerCommand("dailyReport.export", handleExport),
    vscode.commands.registerCommand("dailyReport.viewHistoryReport", handleViewHistoryReport),
    vscode.commands.registerCommand("dailyReport.refreshHistoryTree", () => handleRefreshHistoryTree()),
    vscode.commands.registerCommand("dailyReport.catchupNow", () => {
      const scheduler = new SchedulerService();
      scheduler.runCatchup();
    }),
  ];
  context.subscriptions.push(...commands);

  // 启动定时调度（追赶 + 定时检查）
  const scheduler = new SchedulerService();
  scheduler.start(context);

  // 刷新两个侧边栏
  refreshTreeView();
  handleRefreshHistoryTree();
}

export function deactivate() {
  if (outputChannel) {
    outputChannel.dispose();
  }
  console.log("工作日报助手 已停用");
}
