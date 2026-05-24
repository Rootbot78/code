#!/usr/bin/env python3
"""
GitHub Terminal Manager (GTM)
Complete GitHub operations in your terminal
"""

import os
import sys
import subprocess
from pathlib import Path

# ================================================================
#  虚拟环境自举 - 兼容 Kali / Debian externally-managed-environment
#  首次运行自动创建 venv 并安装依赖，之后直接复用。
# ================================================================
VENV_DIR = Path.home() / ".github_manager_venv"
REQUIRED = {
    "requests":    "requests",
    "github":      "PyGithub",
    "git":         "gitpython",
    "rich":        "rich",
    "questionary": "questionary",
}

def _in_our_venv():
    return str(VENV_DIR) in sys.executable

def _venv_python():
    return VENV_DIR / "bin" / "python3"

def _ensure_venv():
    if not _venv_python().exists():
        print("  [GTM] 首次运行，正在创建虚拟环境 (约10秒)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        print(f"  [GTM] 虚拟环境已创建: {VENV_DIR}")

def _ensure_pkgs():
    pip = VENV_DIR / "bin" / "pip"
    missing = []
    for mod, pkg in REQUIRED.items():
        r = subprocess.run(
            [str(_venv_python()), "-c", f"import {mod}"],
            capture_output=True
        )
        if r.returncode != 0:
            missing.append(pkg)
    if missing:
        print(f"  [GTM] 正在安装依赖包: {', '.join(missing)}")
        subprocess.check_call(
            [str(pip), "install", "--quiet", "--upgrade"] + missing
        )
        print("  [GTM] 依赖安装完成 OK\n")

def bootstrap():
    if _in_our_venv():
        return
    _ensure_venv()
    _ensure_pkgs()
    python = str(_venv_python())
    script = str(Path(__file__).resolve())
    print("  [GTM] 正在启动...\n")
    os.execv(python, [python, script] + sys.argv[1:])

bootstrap()

import json
import shutil
from datetime import datetime

import requests
import questionary
from github import Github, GithubException, Auth
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
from questionary import Style

console = Console()

Q_STYLE = Style([
    ("qmark",       "fg:#00d7ff bold"),
    ("question",    "fg:#ffffff bold"),
    ("answer",      "fg:#00ff87 bold"),
    ("pointer",     "fg:#ff5f87 bold"),
    ("highlighted", "fg:#ff5f87 bold"),
    ("selected",    "fg:#00ff87"),
    ("separator",   "fg:#6c6c6c"),
    ("instruction", "fg:#6c6c6c italic"),
])

CONFIG_FILE = Path.home() / ".github_manager_config.json"

# ════════════════════════════════════════════════════════
#  配置管理
# ════════════════════════════════════════════════════════
class Config:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                self.data = json.loads(CONFIG_FILE.read_text())
            except Exception:
                self.data = {}

    def save(self):
        CONFIG_FILE.write_text(json.dumps(self.data, indent=2))
        CONFIG_FILE.chmod(0o600)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

# ════════════════════════════════════════════════════════
#  GitHub 会话
# ════════════════════════════════════════════════════════
class GitHubSession:
    def __init__(self, config: Config):
        self.config = config
        self.g = None
        self.user = None
        self.token = None

    def _draw_login_screen(self):
        """绘制全屏登录界面"""
        console.clear()
        # ASCII Logo
        logo_lines = [
            "   ██████╗ ██╗████████╗██╗  ██╗██╗   ██╗██████╗ ",
            "  ██╔════╝ ██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗",
            "  ██║  ███╗██║   ██║   ███████║██║   ██║██████╔╝",
            "  ██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗",
            "  ╚██████╔╝██║   ██║   ██║  ██║╚██████╔╝██████╔╝",
            "   ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ",
            "",
            "      Terminal Manager  ·  Sign in to continue   ",
        ]
        logo = Text()
        colors = ["bold bright_cyan"] * 5 + ["bold cyan", "", "dim white"]
        for line, color in zip(logo_lines, colors):
            logo.append(line + "\n", style=color)
        console.print(Panel(logo, border_style="cyan", padding=(1, 4)))
        console.print()

    def login(self, from_startup=False):
        """登录 GitHub — 账号+密码风格对话框"""
        self._draw_login_screen()

        # ── 如果有已保存的 token，询问是否复用 ──────────
        saved_token = self.config.get("token")
        saved_user  = self.config.get("username")
        if saved_token and not from_startup:
            console.print(Panel(
                f"  检测到已保存的账号 [bold cyan]{saved_user or '(未知)'}[/bold cyan]\n"
                f"  [dim]Token 已加密存储于本地[/dim]",
                border_style="dim", title="[dim]已保存的登录信息[/dim]"
            ))
            use_saved = questionary.confirm(
                "直接使用已保存账号登录?", default=True, style=Q_STYLE
            ).ask()
            if use_saved:
                token = saved_token
                username_hint = saved_user
            else:
                saved_token = None  # 重新输入
                username_hint = None
        else:
            username_hint = None

        # ── 输入用户名 + 密码（Token）───────────────────
        if not saved_token:
            console.print(
                "  [dim]GitHub 已停用密码登录，请使用 Personal Access Token 作为密码。[/dim]\n"
                "  [dim]获取方式: GitHub → Settings → Developer settings → Personal access tokens[/dim]\n"
                "  [dim]建议勾选权限: repo  delete_repo  read:org  gist[/dim]\n"
            )

            username = questionary.text(
                "  用户名 (GitHub username):",
                style=Q_STYLE,
                validate=lambda v: True if v.strip() else "用户名不能为空"
            ).ask()
            if not username: return False

            token = questionary.password(
                "  密码   (Personal Access Token):",
                style=Q_STYLE,
                validate=lambda v: True if v.strip() else "请输入 Token"
            ).ask()
            if not token: return False
            username_hint = username.strip()
            token = token.strip()

        # ── 验证 ────────────────────────────────────────
        console.print()
        with console.status("[cyan]  正在连接 GitHub...  [/cyan]", spinner="dots"):
            try:
                auth = Auth.Token(token)
                g    = Github(auth=auth)
                user = g.get_user()
                _    = user.login          # 实际触发 HTTP 请求
            except GithubException as e:
                msg = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)
                console.print(f"\n  [bold red]❌ 登录失败:[/bold red] {msg}\n")
                console.print("  [dim]请检查 Token 是否正确，或权限是否足够[/dim]\n")
                questionary.press_any_key_to_continue("  按任意键重试...").ask()
                return self.login(from_startup=False)   # 重新弹出登录框
            except Exception as e:
                console.print(f"\n  [bold red]❌ 网络错误:[/bold red] {e}\n")
                questionary.press_any_key_to_continue("  按任意键重试...").ask()
                return self.login(from_startup=False)

        self.g    = g
        self.user = user
        self.token = token

        # ── 保存 ────────────────────────────────────────
        save = questionary.confirm(
            "  记住登录信息（Token 保存到本地）?", default=True, style=Q_STYLE
        ).ask()
        if save:
            self.config.set("token",    token)
            self.config.set("username", user.login)

        # ── 欢迎界面 ─────────────────────────────────────
        console.clear()
        self._draw_login_screen()
        console.print(Panel(
            f"  [bold green]✓  登录成功！欢迎回来[/bold green]\n\n"
            f"  用户名:   [bold cyan]{user.login}[/bold cyan]\n"
            f"  邮箱:     [cyan]{user.email or '未公开'}[/cyan]\n"
            f"  公开仓库: [cyan]{user.public_repos}[/cyan] 个\n"
            f"  粉丝:     [cyan]{user.followers}[/cyan]   关注: [cyan]{user.following}[/cyan]\n"
            f"  主页:     [link={user.html_url}]{user.html_url}[/link]",
            border_style="green", title="[green]  GitHub  [/green]", padding=(1, 2)
        ))
        console.print()
        questionary.press_any_key_to_continue("  按任意键进入主菜单...").ask()
        return True

    def require_login(self):
        if not self.g:
            console.print("[yellow]请先登录[/yellow]")
            return self.login()
        return True

# ════════════════════════════════════════════════════════
#  仓库操作
# ════════════════════════════════════════════════════════
class RepoManager:
    def __init__(self, session: GitHubSession):
        self.s = session

    # ── 列出仓库 ──────────────────────────────────────
    def list_repos(self):
        if not self.s.require_login(): return
        filter_type = questionary.select(
            "显示哪类仓库?",
            choices=["全部", "公开", "私有", "Fork", "Source（非Fork）"],
            style=Q_STYLE
        ).ask()
        type_map = {"全部": "all", "公开": "public", "私有": "private",
                    "Fork": "forks", "Source（非Fork）": "sources"}
        sort_by = questionary.select(
            "排序方式?",
            choices=["最近更新", "创建时间", "名称", "Stars"],
            style=Q_STYLE
        ).ask()
        sort_map = {"最近更新": "updated", "创建时间": "created", "名称": "full_name", "Stars": "stars"}

        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type=type_map[filter_type],
                                               sort=sort_map[sort_by]))

        table = Table(
            title=f"📦 仓库列表 ({len(repos)} 个)",
            box=box.ROUNDED, border_style="cyan", show_lines=True
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("仓库名", style="bold white", min_width=20)
        table.add_column("可见性", width=6)
        table.add_column("⭐", width=6)
        table.add_column("🍴", width=6)
        table.add_column("语言", width=12)
        table.add_column("最近更新", width=12)
        table.add_column("描述", style="dim", min_width=20)

        for i, repo in enumerate(repos, 1):
            vis = "[green]公开[/green]" if not repo.private else "[yellow]私有[/yellow]"
            lang = repo.language or "-"
            updated = repo.updated_at.strftime("%Y-%m-%d") if repo.updated_at else "-"
            desc = (repo.description or "")[:40]
            table.add_row(str(i), repo.name, vis,
                         str(repo.stargazers_count), str(repo.forks_count),
                         lang, updated, desc)

        console.print(table)

    # ── 创建仓库 ──────────────────────────────────────
    def create_repo(self):
        if not self.s.require_login(): return
        console.print(Panel(
            "[bold]创建新仓库[/bold]  [dim](任意步骤按 Ctrl+C 或 ESC 可取消)[/dim]",
            border_style="cyan"
        ))

        name = questionary.text(
            "仓库名称:", validate=lambda x: len(x.strip()) > 0 or "不能为空", style=Q_STYLE
        ).ask()
        if not name: return          # ESC / Ctrl+C → 直接返回

        desc = questionary.text("仓库描述 (可选，直接回车跳过):", style=Q_STYLE).ask()
        if desc is None: return
        desc = desc.strip()

        visibility = questionary.select(
            "仓库可见性:", choices=["公开 (Public)", "私有 (Private)", "← 取消返回"],
            style=Q_STYLE
        ).ask()
        if not visibility or "取消" in visibility: return
        private = "私有" in visibility

        init = questionary.confirm("是否初始化 README.md?", default=True, style=Q_STYLE).ask()
        if init is None: return
        gitignore = None
        license_t = None

        if init:
            add_gi = questionary.confirm("是否添加 .gitignore?", default=False, style=Q_STYLE).ask()
            if add_gi is None: return
            if add_gi:
                langs = ["Python", "Node", "Java", "Go", "Rust", "C++",
                         "Swift", "Kotlin", "Ruby", "← 跳过"]
                choice = questionary.select("选择语言模板:", choices=langs, style=Q_STYLE).ask()
                if choice is None: return
                if "跳过" not in choice:
                    gitignore = choice

            add_lic = questionary.confirm("是否添加开源协议?", default=False, style=Q_STYLE).ask()
            if add_lic is None: return
            if add_lic:
                licenses = ["mit", "apache-2.0", "gpl-3.0", "bsd-3-clause",
                           "lgpl-2.1", "mpl-2.0", "← 跳过"]
                lic = questionary.select("选择协议:", choices=licenses, style=Q_STYLE).ask()
                if lic is None: return
                if "跳过" not in lic:
                    license_t = lic

        # ── 确认摘要 ──────────────────────────────────
        console.print(Panel(
            f"  仓库名: [bold cyan]{name}[/bold cyan]\n"
            f"  描述:   {desc or '(无)'}\n"
            f"  可见性: {'🔒 私有' if private else '🌐 公开'}\n"
            f"  README: {'✓' if init else '✗'}  "
            f"  .gitignore: {gitignore or '✗'}  "
            f"  协议: {license_t or '✗'}",
            title="[cyan]确认信息[/cyan]", border_style="cyan"
        ))
        confirm = questionary.select(
            "确认操作?",
            choices=["✓ 确认创建", "✗ 取消返回"],
            style=Q_STYLE
        ).ask()
        if not confirm or "取消" in confirm:
            console.print("[yellow]已取消[/yellow]"); return

        with console.status("[cyan]正在创建仓库..."):
            try:
                kwargs = dict(name=name, description=desc, private=private, auto_init=init)
                if gitignore: kwargs["gitignore_template"] = gitignore
                if license_t: kwargs["license_template"] = license_t
                repo = self.s.user.create_repo(**kwargs)
            except GithubException as e:
                console.print(f"[red]❌ 创建失败: {e.data.get('message', str(e))}[/red]"); return

        console.print(Panel(
            f"[bold green]✓ 仓库创建成功！[/bold green]\n\n"
            f"名称:  [cyan]{repo.full_name}[/cyan]\n"
            f"URL:   [link={repo.html_url}]{repo.html_url}[/link]\n"
            f"Clone: [dim]git clone {repo.clone_url}[/dim]",
            border_style="green"
        ))
        return repo  # 返回仓库对象供调用方使用

    # ── 删除仓库 ──────────────────────────────────────
    def delete_repo(self):
        if not self.s.require_login(): return
        console.print(Panel(
            "[bold red]⚠ 删除仓库[/bold red]  [dim]此操作不可撤销！[/dim]",
            border_style="red"
        ))

        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))

        if not repos:
            console.print("[yellow]没有可删除的仓库[/yellow]"); return

        # 用方向键选择，避免手动输错名称
        choices = [f"{'🔒' if r.private else '🌐'} {r.full_name}" for r in repos]
        choices.append("← 取消返回")
        chosen = questionary.select(
            "选择要删除的仓库:", choices=choices, style=Q_STYLE
        ).ask()
        if not chosen or "取消" in chosen: return

        repo_full_name = chosen.split(" ", 1)[1]   # 去掉前缀图标

        # 二次确认：用 select 而不是手动输入
        console.print(f"\n  即将删除: [bold red]{repo_full_name}[/bold red]")
        double_check = questionary.select(
            "⚠ 确认永久删除该仓库?",
            choices=[
                "✗ 取消，我不想删除",
                f"✓ 确认删除  {repo_full_name}",
            ],
            style=Q_STYLE
        ).ask()
        if not double_check or "取消" in double_check:
            console.print("[yellow]已取消[/yellow]"); return

        with console.status(f"[red]正在删除 {repo_full_name}..."):
            try:
                repo = self.s.g.get_repo(repo_full_name)
                repo.delete()
            except GithubException as e:
                console.print(f"[red]❌ 删除失败: {e.data.get('message', str(e))}[/red]"); return

        console.print(f"[green]✓ 仓库 [bold]{repo_full_name}[/bold] 已成功删除[/green]")

    # ── 仓库详情 ──────────────────────────────────────
    def repo_info(self):
        if not self.s.require_login(): return
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        names = [r.full_name for r in repos]

        repo_name = questionary.autocomplete(
            "查看哪个仓库?", choices=names, style=Q_STYLE
        ).ask()
        if not repo_name: return

        with console.status("[cyan]获取详情..."):
            try:
                repo = self.s.g.get_repo(repo_name)
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]"); return

        # 基本信息
        table = Table(box=box.MINIMAL, show_header=False)
        table.add_column("", style="dim", width=12)
        table.add_column("", style="white")
        info = [
            ("名称", repo.full_name),
            ("描述", repo.description or "-"),
            ("可见性", "🔒 私有" if repo.private else "🌐 公开"),
            ("Stars", str(repo.stargazers_count)),
            ("Forks", str(repo.forks_count)),
            ("Watchers", str(repo.watchers_count)),
            ("语言", repo.language or "-"),
            ("默认分支", repo.default_branch),
            ("创建时间", str(repo.created_at)[:10]),
            ("最近更新", str(repo.updated_at)[:10]),
            ("URL", repo.html_url),
            ("Clone (HTTPS)", repo.clone_url),
            ("Clone (SSH)", repo.ssh_url),
        ]
        for k, v in info:
            table.add_row(k, v)
        console.print(Panel(table, title=f"[cyan]{repo.full_name}[/cyan]",
                            border_style="cyan"))

        # Topics
        topics = repo.get_topics()
        if topics:
            console.print(f"  🏷  Topics: {' '.join(f'[cyan]{t}[/cyan]' for t in topics)}")

        # 最近 commits
        action = questionary.select(
            "继续操作?",
            choices=["查看最近 Commits", "查看分支列表", "查看 Issues", "查看 PR", "返回"],
            style=Q_STYLE
        ).ask()

        if action == "查看最近 Commits":
            self._show_commits(repo)
        elif action == "查看分支列表":
            self._show_branches(repo)
        elif action == "查看 Issues":
            self._show_issues(repo)
        elif action == "查看 PR":
            self._show_prs(repo)

    def _show_commits(self, repo):
        with console.status("[cyan]获取 Commits..."):
            commits = list(repo.get_commits()[:20])
        t = Table(title="最近 20 条 Commits", box=box.ROUNDED, border_style="cyan")
        t.add_column("SHA", width=8, style="yellow")
        t.add_column("作者", width=16)
        t.add_column("时间", width=12)
        t.add_column("信息")
        for c in commits:
            sha = c.sha[:7]
            author = c.commit.author.name[:14] if c.commit.author else "-"
            date = str(c.commit.author.date)[:10] if c.commit.author else "-"
            msg = (c.commit.message.split("\n")[0])[:60]
            t.add_row(sha, author, date, msg)
        console.print(t)

    def _show_branches(self, repo):
        with console.status("[cyan]获取分支..."):
            branches = list(repo.get_branches())
        t = Table(title="分支列表", box=box.ROUNDED, border_style="cyan")
        t.add_column("分支名")
        t.add_column("最新 Commit SHA", width=10, style="yellow")
        t.add_column("是否受保护", width=8)
        for b in branches:
            t.add_row(b.name, b.commit.sha[:7],
                     "[green]✓[/green]" if b.protected else "-")
        console.print(t)

    def _show_issues(self, repo):
        state = questionary.select("Issues 状态?",
            choices=["open", "closed", "all"], style=Q_STYLE).ask()
        with console.status("[cyan]获取 Issues..."):
            issues = list(repo.get_issues(state=state)[:20])
        t = Table(title=f"Issues ({state})", box=box.ROUNDED, border_style="cyan")
        t.add_column("#", width=6, style="yellow")
        t.add_column("标题")
        t.add_column("状态", width=8)
        t.add_column("创建者", width=14)
        t.add_column("时间", width=12)
        for i in issues:
            if i.pull_request: continue
            status = "[green]open[/green]" if i.state == "open" else "[red]closed[/red]"
            t.add_row(str(i.number), i.title[:60], status,
                     i.user.login if i.user else "-",
                     str(i.created_at)[:10])
        console.print(t)

    def _show_prs(self, repo):
        state = questionary.select("PR 状态?",
            choices=["open", "closed", "all"], style=Q_STYLE).ask()
        with console.status("[cyan]获取 PR..."):
            prs = list(repo.get_pulls(state=state)[:20])
        t = Table(title=f"Pull Requests ({state})", box=box.ROUNDED, border_style="cyan")
        t.add_column("#", width=6, style="yellow")
        t.add_column("标题")
        t.add_column("状态", width=8)
        t.add_column("作者", width=14)
        t.add_column("目标分支", width=12)
        for pr in prs:
            status = "[green]open[/green]" if pr.state == "open" else "[red]closed[/red]"
            t.add_row(str(pr.number), pr.title[:55], status,
                     pr.user.login if pr.user else "-", pr.base.ref)
        console.print(t)

    # ── 修改仓库设置 ──────────────────────────────────
    def edit_repo(self):
        if not self.s.require_login(): return

        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))

        if not repos:
            console.print("[yellow]没有仓库[/yellow]"); return

        # 选择仓库（列表方式，带当前状态）
        choices = [
            f"{'🔒 私有' if r.private else '🌐 公开'}  {r.full_name}"
            for r in repos
        ]
        choices.append("← 取消返回")
        chosen = questionary.select(
            "选择要修改的仓库:", choices=choices, style=Q_STYLE
        ).ask()
        if not chosen or "取消" in chosen: return

        repo_full_name = chosen.split("  ", 1)[1]
        with console.status("[cyan]获取仓库信息..."):
            repo = self.s.g.get_repo(repo_full_name)

        # ── 显示当前所有设置 ─────────────────────────
        cur_vis   = "🔒 私有" if repo.private else "🌐 公开"
        cur_wiki  = "✓ 已开启" if repo.has_wiki else "✗ 已关闭"
        cur_issue = "✓ 已开启" if repo.has_issues else "✗ 已关闭"
        cur_topics = ", ".join(repo.get_topics()) or "(无)"

        info_table = Table(box=box.MINIMAL, show_header=False, padding=(0, 2))
        info_table.add_column("", style="dim", width=14)
        info_table.add_column("")
        info_table.add_row("仓库名",   repo.full_name)
        info_table.add_row("描述",     repo.description or "(无)")
        info_table.add_row("主页 URL", repo.homepage or "(无)")
        info_table.add_row("可见性",   cur_vis)
        info_table.add_row("Wiki",     cur_wiki)
        info_table.add_row("Issues",   cur_issue)
        info_table.add_row("Topics",   cur_topics)
        console.print(Panel(
            info_table,
            title=f"[cyan]当前设置  {repo.full_name}[/cyan]",
            border_style="cyan"
        ))

        # ── 选择要修改哪些项 (空格多选) ──────────────
        what = questionary.checkbox(
            "用空格勾选要修改的项目，回车确认:",
            choices=[
                f"可见性       (当前: {cur_vis})",
                f"描述         (当前: {repo.description or '(无)'})",
                f"主页 URL     (当前: {repo.homepage or '(无)'})",
                f"Wiki         (当前: {cur_wiki})",
                f"Issues       (当前: {cur_issue})",
                f"Topics       (当前: {cur_topics})",
            ],
            style=Q_STYLE
        ).ask()
        if not what: return

        kwargs = {}

        # 可见性
        if any("可见性" in w for w in what):
            new_vis = questionary.select(
                f"可见性  (现在是 {cur_vis}):",
                choices=[
                    "🌐 公开 (Public)  — 所有人可见",
                    "🔒 私有 (Private) — 仅自己可见",
                    "← 跳过不改",
                ],
                style=Q_STYLE
            ).ask()
            if new_vis is None: return
            if "跳过" not in new_vis:
                kwargs["private"] = "私有" in new_vis
                tag = "🔒 私有" if kwargs["private"] else "🌐 公开"
                console.print(f"  → 可见性将改为: [bold]{tag}[/bold]")

        # 描述
        if any("描述" in w for w in what):
            new_desc = questionary.text(
                "新描述 (直接回车保持不变):",
                default=repo.description or "",
                style=Q_STYLE
            ).ask()
            if new_desc is None: return
            kwargs["description"] = new_desc

        # 主页 URL
        if any("主页" in w for w in what):
            new_home = questionary.text(
                "主页 URL (直接回车保持不变):",
                default=repo.homepage or "",
                style=Q_STYLE
            ).ask()
            if new_home is None: return
            kwargs["homepage"] = new_home

        # Wiki
        if any("Wiki" in w for w in what):
            new_wiki = questionary.select(
                f"Wiki  (现在是 {cur_wiki}):",
                choices=["✓ 开启 Wiki", "✗ 关闭 Wiki", "← 跳过不改"],
                style=Q_STYLE
            ).ask()
            if new_wiki is None: return
            if "跳过" not in new_wiki:
                kwargs["has_wiki"] = "开启" in new_wiki

        # Issues
        if any("Issues" in w for w in what):
            new_issue = questionary.select(
                f"Issues  (现在是 {cur_issue}):",
                choices=["✓ 开启 Issues", "✗ 关闭 Issues", "← 跳过不改"],
                style=Q_STYLE
            ).ask()
            if new_issue is None: return
            if "跳过" not in new_issue:
                kwargs["has_issues"] = "开启" in new_issue

        # Topics
        new_topics = None
        if any("Topics" in w for w in what):
            topics_str = questionary.text(
                "Topics (空格分隔，清空则留空，回车确认):",
                default=", ".join(repo.get_topics()),
                style=Q_STYLE
            ).ask()
            if topics_str is None: return
            new_topics = [t.strip() for t in topics_str.replace(",", " ").split() if t.strip()]

        if not kwargs and new_topics is None:
            console.print("[yellow]没有任何修改[/yellow]"); return

        # ── 确认后提交 ────────────────────────────────
        confirm = questionary.select(
            "确认保存以上修改?",
            choices=["✓ 确认保存", "✗ 取消返回"],
            style=Q_STYLE
        ).ask()
        if not confirm or "取消" in confirm:
            console.print("[yellow]已取消[/yellow]"); return

        with console.status("[cyan]正在保存..."):
            try:
                if kwargs:
                    repo.edit(**kwargs)
                if new_topics is not None:
                    repo.replace_topics(new_topics)
            except GithubException as e:
                console.print(f"[red]❌ 更新失败: {e.data.get('message', str(e))}[/red]"); return

        console.print(Panel(
            "[bold green]✓ 仓库设置已更新！[/bold green]\n\n"
            + ("  可见性 → " + ("🔒 私有" if kwargs.get("private") else "🌐 公开") + "\n" if "private" in kwargs else "")
            + (f"  描述   → {kwargs['description']}\n" if "description" in kwargs else "")
            + (f"  Topics → {', '.join(new_topics) or '(已清空)'}\n" if new_topics is not None else ""),
            border_style="green"
        ))

    # ── Fork 仓库 ─────────────────────────────────────
    def fork_repo(self):
        if not self.s.require_login(): return
        repo_url = questionary.text(
            "输入要 Fork 的仓库 (格式: owner/repo):", style=Q_STYLE).ask()
        if not repo_url: return
        try:
            source = self.s.g.get_repo(repo_url)
            with console.status(f"[cyan]正在 Fork {repo_url}..."):
                forked = self.s.user.create_fork(source)
            console.print(f"[green]✓ Fork 成功: {forked.full_name}[/green]")
            console.print(f"  URL: {forked.html_url}")
        except GithubException as e:
            console.print(f"[red]❌ Fork 失败: {e.data.get('message', str(e))}[/red]")

    # ── Star 管理 ─────────────────────────────────────
    def star_manage(self):
        if not self.s.require_login(): return
        action = questionary.select("Star 操作:", choices=["查看我的 Stars", "Star 一个仓库",
                                                           "取消 Star"], style=Q_STYLE).ask()
        if action == "查看我的 Stars":
            with console.status("[cyan]获取 Stars..."):
                starred = list(self.s.user.get_starred()[:30])
            t = Table(title=f"⭐ 我的 Stars (显示前30)", box=box.ROUNDED, border_style="yellow")
            t.add_column("仓库")
            t.add_column("Stars", width=8)
            t.add_column("语言", width=12)
            t.add_column("描述")
            for r in starred:
                t.add_row(r.full_name, str(r.stargazers_count),
                         r.language or "-", (r.description or "")[:50])
            console.print(t)

        elif action == "Star 一个仓库":
            repo_name = questionary.text("输入仓库 (owner/repo):", style=Q_STYLE).ask()
            if repo_name:
                try:
                    repo = self.s.g.get_repo(repo_name)
                    self.s.user.add_to_starred(repo)
                    console.print(f"[green]✓ 已 Star {repo_name}[/green]")
                except GithubException as e:
                    console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]")

        elif action == "取消 Star":
            repo_name = questionary.text("输入仓库 (owner/repo):", style=Q_STYLE).ask()
            if repo_name:
                try:
                    repo = self.s.g.get_repo(repo_name)
                    self.s.user.remove_from_starred(repo)
                    console.print(f"[green]✓ 已取消 Star {repo_name}[/green]")
                except GithubException as e:
                    console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]")

    # ── 删除仓库内容 ──────────────────────────────────
    def delete_repo_contents(self):
        """浏览并删除仓库中的文件/文件夹"""
        if not self.s.require_login(): return

        # 选择仓库
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos:
            console.print("[yellow]没有仓库[/yellow]"); return

        repo_names = [r.full_name for r in repos]
        repo_name = questionary.autocomplete(
            "选择仓库:", choices=repo_names, style=Q_STYLE
        ).ask()
        if not repo_name: return

        with console.status("[cyan]获取仓库信息..."):
            try:
                repo = self.s.g.get_repo(repo_name)
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]"); return

        branch = questionary.text(
            "操作哪个分支:", default=repo.default_branch, style=Q_STYLE
        ).ask() or repo.default_branch

        # 递归浏览目录，选择要删除的条目
        def browse_and_select(path=""):
            """列出指定路径下内容，返回用户选中的 ContentFile 列表（可为文件或整个目录）"""
            with console.status(f"[cyan]读取 {'根目录' if not path else path} ..."):
                try:
                    items = repo.get_contents(path, ref=branch)
                    if not isinstance(items, list):
                        items = [items]
                    items = sorted(items, key=lambda x: (x.type != "dir", x.name))
                except GithubException as e:
                    console.print(f"[red]❌ 无法读取目录: {e.data.get('message', str(e))}[/red]")
                    return []

            if not items:
                console.print("[yellow]此目录为空[/yellow]")
                return []

            # 构造选项列表
            choices = []
            for item in items:
                icon = "📁" if item.type == "dir" else "📄"
                choices.append(f"{icon}  {item.name}")
            choices.append("─── 多选删除 ───────────────")
            choices.append("⬆  返回上层 / 完成选择")

            action = questionary.select(
                f"📂 {'根目录' if not path else path}  ({len(items)} 个条目)  — 选中目录可进入或直接删除整个目录",
                choices=choices,
                style=Q_STYLE,
                instruction="(↑↓ 选择, Enter 确认)"
            ).ask()

            if not action or "返回上层" in action or "完成选择" in action:
                return []

            if "多选删除" in action:
                # 多选模式
                multi_choices = [
                    f"{'📁' if i.type == 'dir' else '📄'}  {i.name}" for i in items
                ]
                selected = questionary.checkbox(
                    "用空格勾选要删除的条目，回车确认:",
                    choices=multi_choices,
                    style=Q_STYLE
                ).ask()
                if not selected:
                    return []
                name_set = {s.split("  ", 1)[1] for s in selected}
                return [i for i in items if i.name in name_set]

            # 单选：判断是文件还是目录
            selected_name = action.split("  ", 1)[1]
            selected_item = next((i for i in items if i.name == selected_name), None)
            if not selected_item: return []

            if selected_item.type == "dir":
                sub_action = questionary.select(
                    f"📁 {selected_item.path}",
                    choices=[
                        "🗑  删除整个目录（含所有子文件）",
                        "📂  进入目录浏览",
                        "← 返回",
                    ],
                    style=Q_STYLE
                ).ask()
                if not sub_action or "返回" in sub_action:
                    return browse_and_select(path)
                if "删除整个目录" in sub_action:
                    return [selected_item]
                # 进入子目录
                return browse_and_select(selected_item.path)
            else:
                return [selected_item]

        targets = browse_and_select()
        if not targets:
            console.print("[yellow]未选择任何内容，已取消[/yellow]"); return

        # 显示删除预览
        console.print()
        preview = Table(title="[red]即将删除以下内容[/red]", box=box.ROUNDED, border_style="red")
        preview.add_column("类型", width=6)
        preview.add_column("路径")
        for t in targets:
            icon = "📁 目录" if t.type == "dir" else "📄 文件"
            preview.add_row(icon, t.path)
        console.print(preview)
        console.print(f"  [dim]分支: {branch}[/dim]\n")

        commit_msg = questionary.text(
            "删除提交信息:", default=f"Delete {', '.join(t.name for t in targets)}", style=Q_STYLE
        ).ask()
        if not commit_msg: return

        confirm = questionary.select(
            "⚠ 确认删除？此操作会产生新的 Commit，内容将从仓库中移除",
            choices=["✗ 取消，我不想删除", "✓ 确认删除"],
            style=Q_STYLE
        ).ask()
        if not confirm or "取消" in confirm:
            console.print("[yellow]已取消[/yellow]"); return

        # 执行删除
        def delete_item(item):
            """递归删除文件或整个目录"""
            if item.type == "dir":
                try:
                    sub_items = repo.get_contents(item.path, ref=branch)
                    if not isinstance(sub_items, list):
                        sub_items = [sub_items]
                except GithubException:
                    sub_items = []
                for sub in sub_items:
                    delete_item(sub)
            else:
                try:
                    repo.delete_file(
                        path=item.path,
                        message=commit_msg,
                        sha=item.sha,
                        branch=branch
                    )
                    console.print(f"  [green]✓ 已删除[/green]  {item.path}")
                except GithubException as e:
                    msg = e.data.get("message", str(e)) if hasattr(e, "data") else str(e)
                    console.print(f"  [red]❌ 删除失败[/red]  {item.path}  ({msg})")

        console.print()
        with Progress(
            SpinnerColumn(), TextColumn("[cyan]{task.description}"),
            console=console, transient=False
        ) as progress:
            task = progress.add_task("正在删除...", total=None)
            for target in targets:
                progress.update(task, description=f"正在删除 {target.path} ...")
                delete_item(target)
            progress.update(task, description="完成！")

        console.print(f"\n[bold green]✓ 删除操作完成[/bold green]")

# ════════════════════════════════════════════════════════
#  Git 本地操作
# ════════════════════════════════════════════════════════
class GitLocalManager:
    def __init__(self, session: GitHubSession):
        self.s = session

    def _run(self, cmd, cwd=None):
        """运行 git 命令并显示输出"""
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True
        )
        if result.stdout:
            console.print(f"[dim]{result.stdout.strip()}[/dim]")
        if result.stderr:
            console.print(f"[yellow]{result.stderr.strip()}[/yellow]")
        return result.returncode == 0

    def clone_repo(self):
        if not self.s.require_login(): return
        source = questionary.select(
            "克隆哪里的仓库?",
            choices=["我的仓库", "输入任意 URL/路径"],
            style=Q_STYLE
        ).ask()

        if source == "我的仓库":
            with console.status("[cyan]获取仓库列表..."):
                repos = list(self.s.user.get_repos(type="all"))
            names = [r.full_name for r in repos]
            repo_name = questionary.autocomplete("选择仓库:", choices=names, style=Q_STYLE).ask()
            if not repo_name: return
            repo = self.s.g.get_repo(repo_name)
            use_ssh = questionary.confirm(
                "使用 SSH 克隆? (否则用 HTTPS)", default=True, style=Q_STYLE).ask()
            if use_ssh is None: return
            url = repo.ssh_url if use_ssh else repo.clone_url
        else:
            url = questionary.text("输入仓库 URL:", style=Q_STYLE).ask()
            if not url: return

        target = questionary.text(
            "克隆到哪个目录? (留空=当前目录):", style=Q_STYLE).ask() or "."

        console.print(f"\n[cyan]▶ git clone {url}[/cyan]\n")
        self._run(f'git clone "{url}"', cwd=target)

    def _inject_token(self, url: str) -> str:
        """如果是 HTTPS URL 且有 token，则自动嵌入 token 避免输入凭据"""
        token = self.s.token
        if token and url.startswith("https://") and "@" not in url:
            # https://github.com/... → https://<token>@github.com/...
            url = url.replace("https://", f"https://{token}@", 1)
        return url

    def _run_seq(self, cmds, cwd):
        """依次执行命令列表，任一失败则中止并返回 False"""
        for cmd in cmds:
            console.print(f"\n[cyan]▶ {cmd}[/cyan]")
            if not self._run(cmd, cwd=cwd):
                console.print("[red]❌ 命令执行失败，已中止后续步骤[/red]")
                return False
        return True

    def push_project(self):
        """上传本地项目到 GitHub"""
        if not self.s.require_login(): return
        console.print(Panel("[bold]上传本地项目到 GitHub[/bold]", border_style="cyan"))

        local_path = questionary.path(
            "选择本地项目目录:", only_directories=True,
            default=str(Path.cwd()), style=Q_STYLE
        ).ask()
        if not local_path or not Path(local_path).exists():
            console.print("[red]目录不存在[/red]"); return

        local_path = Path(local_path)
        git_dir = local_path / ".git"

        action = questionary.select(
            "操作类型?",
            choices=[
                "初始化新仓库并推送 (全新项目)",
                "推送到已有远程仓库",
                "添加远程地址并推送",
            ],
            style=Q_STYLE
        ).ask()
        if not action: return

        # ── Bug2修复：新仓库流程自动获取 URL，无需手动输入 ──
        if action == "初始化新仓库并推送 (全新项目)":
            console.print("\n[cyan]第一步：在 GitHub 创建仓库[/cyan]")
            rm = RepoManager(self.s)
            new_repo = rm.create_repo()
            if not new_repo:
                console.print("[yellow]未创建仓库，已取消[/yellow]"); return

            # 自动填充 URL，让用户选择 SSH 或 HTTPS
            use_ssh = questionary.confirm(
                "使用 SSH 推送? (否则用 HTTPS)", default=True, style=Q_STYLE).ask()
            if use_ssh is None: return
            remote_url = new_repo.ssh_url if use_ssh else self._inject_token(new_repo.clone_url)
            console.print(f"  [dim]远程地址已自动填充: {new_repo.ssh_url if use_ssh else new_repo.clone_url}[/dim]")

            # 初始化本地 git
            if not git_dir.exists():
                console.print(f"\n[cyan]▶ 初始化 git[/cyan]")
                if not self._run("git init", cwd=local_path): return

            branch = questionary.text("分支名:", default="main", style=Q_STYLE).ask() or "main"
            commit_msg = questionary.text("Commit 信息:", default="Initial commit", style=Q_STYLE).ask()
            if not commit_msg: return

            # Bug3修复：_run_seq 任一失败即中止
            self._run_seq([
                f'git remote add origin "{remote_url}"',
                "git add .",
                f'git commit -m "{commit_msg}"',
                f"git branch -M {branch}",
                f"git push -u origin {branch}",
            ], cwd=local_path)

        # ── Bug1修复：推送已有远程仓库时先检测/选择 remote ──
        elif action == "推送到已有远程仓库":
            # 检查当前目录是否已有 remote
            check = subprocess.run(
                "git remote -v", cwd=local_path,
                shell=True, capture_output=True, text=True
            )
            if not check.stdout.strip():
                console.print("[yellow]⚠ 当前目录尚未绑定远程仓库，请从账号中选择一个：[/yellow]")
                with console.status("[cyan]获取仓库列表..."):
                    repos = list(self.s.user.get_repos(type="all"))
                if not repos:
                    console.print("[red]账号下没有仓库，请先创建[/red]"); return

                use_ssh = questionary.confirm(
                    "使用 SSH? (否则用 HTTPS)", default=True, style=Q_STYLE).ask()
                if use_ssh is None: return
                repo_choices = [
                    (r.ssh_url if use_ssh else self._inject_token(r.clone_url), r.full_name) for r in repos
                ]
                chosen_name = questionary.select(
                    "选择目标仓库:",
                    choices=[name for _, name in repo_choices],
                    style=Q_STYLE
                ).ask()
                if not chosen_name: return
                remote_url = next(url for url, name in repo_choices if name == chosen_name)

                if not git_dir.exists():
                    if not self._run("git init", cwd=local_path): return
                if not self._run(f'git remote add origin "{remote_url}"', cwd=local_path): return

            branch = questionary.text("推送哪个分支:", default="main", style=Q_STYLE).ask() or "main"
            commit_msg = questionary.text("Commit 信息 (留空则跳过 commit):", style=Q_STYLE).ask()
            force = questionary.confirm("是否 force push?", default=False, style=Q_STYLE).ask()
            if force is None: return

            cmds = ["git add ."]
            if commit_msg:
                cmds.append(f'git commit -m "{commit_msg}"')
            cmds.append(f"git push {'--force' if force else ''} origin {branch}".strip())
            self._run_seq(cmds, cwd=local_path)

        # ── Bug5修复：允许自定义 commit message，空则中止 ──
        elif action == "添加远程地址并推送":
            remote_url = questionary.text("远程仓库 URL:", style=Q_STYLE).ask()
            if not remote_url: return
            remote_url = self._inject_token(remote_url)
            remote_name = questionary.text("远程名称:", default="origin", style=Q_STYLE).ask() or "origin"
            branch = questionary.text("分支:", default="main", style=Q_STYLE).ask() or "main"
            commit_msg = questionary.text("Commit 信息:", default="Initial commit", style=Q_STYLE).ask()
            if not commit_msg: return

            if not git_dir.exists():
                if not self._run("git init", cwd=local_path): return

            self._run_seq([
                f'git remote add {remote_name} "{remote_url}"',
                "git add .",
                f'git commit -m "{commit_msg}"',
                f"git push -u {remote_name} {branch}",
            ], cwd=local_path)

    def pull_project(self):
        """拉取更新"""
        local_path = questionary.path(
            "项目目录:", only_directories=True,
            default=str(Path.cwd()), style=Q_STYLE
        ).ask()
        if not local_path: return

        branch = questionary.text("分支 (留空=当前分支):", style=Q_STYLE).ask()
        rebase = questionary.confirm("使用 rebase?", default=False, style=Q_STYLE).ask()

        cmd = f"git pull {'--rebase' if rebase else ''} {('origin ' + branch) if branch else ''}".strip()
        console.print(f"\n[cyan]▶ {cmd}[/cyan]\n")
        self._run(cmd, cwd=local_path)

    def git_status(self):
        """查看 Git 状态"""
        local_path = questionary.path(
            "项目目录:", only_directories=True,
            default=str(Path.cwd()), style=Q_STYLE
        ).ask()
        if not local_path: return
        console.print(f"\n[cyan]▶ git status[/cyan]")
        self._run("git status", cwd=local_path)
        console.print(f"\n[cyan]▶ git log --oneline -10[/cyan]")
        self._run("git log --oneline -10", cwd=local_path)

    def branch_manage(self):
        """分支管理"""
        local_path = questionary.path(
            "项目目录:", only_directories=True,
            default=str(Path.cwd()), style=Q_STYLE
        ).ask()
        if not local_path: return

        action = questionary.select(
            "分支操作:",
            choices=["查看所有分支", "创建新分支", "切换分支", "合并分支",
                     "删除分支", "推送分支到远程"],
            style=Q_STYLE
        ).ask()

        if action == "查看所有分支":
            self._run("git branch -a", cwd=local_path)
        elif action == "创建新分支":
            name = questionary.text("新分支名:", style=Q_STYLE).ask()
            checkout = questionary.confirm("创建后立即切换?", default=True, style=Q_STYLE).ask()
            self._run(f"git checkout -b {name}" if checkout else f"git branch {name}", cwd=local_path)
        elif action == "切换分支":
            name = questionary.text("目标分支名:", style=Q_STYLE).ask()
            self._run(f"git checkout {name}", cwd=local_path)
        elif action == "合并分支":
            src = questionary.text("要合并的分支名:", style=Q_STYLE).ask()
            self._run(f"git merge {src}", cwd=local_path)
        elif action == "删除分支":
            name = questionary.text("要删除的分支名:", style=Q_STYLE).ask()
            force = questionary.confirm("强制删除?", default=False, style=Q_STYLE).ask()
            self._run(f"git branch {'-D' if force else '-d'} {name}", cwd=local_path)
        elif action == "推送分支到远程":
            name = questionary.text("分支名:", style=Q_STYLE).ask()
            self._run(f"git push origin {name}", cwd=local_path)

# ════════════════════════════════════════════════════════
#  Gist 操作
# ════════════════════════════════════════════════════════
class GistManager:
    def __init__(self, session: GitHubSession):
        self.s = session

    def list_gists(self):
        if not self.s.require_login(): return
        with console.status("[cyan]获取 Gists..."):
            gists = list(self.s.user.get_gists()[:20])
        t = Table(title="📝 我的 Gists", box=box.ROUNDED, border_style="cyan")
        t.add_column("ID", width=10, style="yellow")
        t.add_column("描述")
        t.add_column("文件数", width=6)
        t.add_column("可见性", width=8)
        t.add_column("创建时间", width=12)
        for g in gists:
            vis = "[green]公开[/green]" if g.public else "[yellow]私有[/yellow]"
            t.add_row(g.id[:8], g.description or "-", str(len(g.files)),
                     vis, str(g.created_at)[:10])
        console.print(t)

    def create_gist(self):
        if not self.s.require_login(): return
        desc = questionary.text("Gist 描述:", style=Q_STYLE).ask() or ""
        filename = questionary.text("文件名 (如 hello.py):", style=Q_STYLE).ask()
        if not filename: return

        console.print("[dim]输入文件内容 (输入 END 结束):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END": break
                lines.append(line)
            except EOFError:
                break
        content = "\n".join(lines)
        public = questionary.confirm("公开 Gist?", default=True, style=Q_STYLE).ask()

        from github import InputFileContent
        try:
            gist = self.s.user.create_gist(
                public=public,
                files={filename: InputFileContent(content)},
                description=desc
            )
            console.print(f"[green]✓ Gist 创建成功: {gist.html_url}[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]")

# ════════════════════════════════════════════════════════
#  用户/搜索操作
# ════════════════════════════════════════════════════════
class SearchManager:
    def __init__(self, session: GitHubSession):
        self.s = session

    def search_repos(self):
        if not self.s.require_login(): return
        query = questionary.text("搜索仓库 (关键词):", style=Q_STYLE).ask()
        if not query: return

        sort = questionary.select("排序:", choices=["stars", "forks", "updated"], style=Q_STYLE).ask()
        order = questionary.select("顺序:", choices=["desc", "asc"], style=Q_STYLE).ask()

        with console.status("[cyan]搜索中..."):
            results = list(self.s.g.search_repositories(query, sort=sort, order=order)[:20])

        t = Table(title=f"🔍 搜索结果: {query}", box=box.ROUNDED, border_style="cyan")
        t.add_column("仓库", min_width=25)
        t.add_column("⭐", width=8)
        t.add_column("语言", width=12)
        t.add_column("描述")
        for r in results:
            t.add_row(r.full_name, str(r.stargazers_count),
                     r.language or "-", (r.description or "")[:50])
        console.print(t)

    def search_users(self):
        if not self.s.require_login(): return
        query = questionary.text("搜索用户:", style=Q_STYLE).ask()
        if not query: return
        with console.status("[cyan]搜索中..."):
            results = list(self.s.g.search_users(query)[:15])
        t = Table(title=f"👤 用户搜索: {query}", box=box.ROUNDED, border_style="cyan")
        t.add_column("用户名")
        t.add_column("类型", width=10)
        t.add_column("URL")
        for u in results:
            t.add_row(u.login, u.type, u.html_url)
        console.print(t)

    def my_profile(self):
        if not self.s.require_login(): return
        u = self.s.user
        table = Table(box=box.MINIMAL, show_header=False)
        table.add_column("", style="dim", width=14)
        table.add_column("")
        info = [
            ("登录名", u.login), ("姓名", u.name or "-"),
            ("邮箱", u.email or "未公开"), ("公司", u.company or "-"),
            ("地点", u.location or "-"), ("博客", u.blog or "-"),
            ("Bio", u.bio or "-"),
            ("公开仓库", str(u.public_repos)),
            ("粉丝", str(u.followers)), ("关注", str(u.following)),
            ("加入时间", str(u.created_at)[:10]),
            ("GitHub URL", u.html_url),
        ]
        for k, v in info:
            table.add_row(k, v)
        console.print(Panel(table, title="[cyan]👤 我的 GitHub 个人资料[/cyan]",
                            border_style="cyan"))

    def follow_manage(self):
        if not self.s.require_login(): return
        action = questionary.select(
            "操作:", choices=["查看我关注的人", "查看粉丝", "关注用户", "取消关注"],
            style=Q_STYLE
        ).ask()

        if action == "查看我关注的人":
            with console.status("[cyan]获取..."):
                following = list(self.s.user.get_following()[:30])
            console.print("[cyan]我关注的用户:[/cyan] " + ", ".join(u.login for u in following))
        elif action == "查看粉丝":
            with console.status("[cyan]获取..."):
                followers = list(self.s.user.get_followers()[:30])
            console.print("[cyan]粉丝:[/cyan] " + ", ".join(u.login for u in followers))
        elif action == "关注用户":
            login = questionary.text("输入用户名:", style=Q_STYLE).ask()
            if login:
                try:
                    target = self.s.g.get_user(login)
                    self.s.user.add_to_following(target)
                    console.print(f"[green]✓ 已关注 {login}[/green]")
                except GithubException as e:
                    console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]")
        elif action == "取消关注":
            login = questionary.text("输入用户名:", style=Q_STYLE).ask()
            if login:
                try:
                    target = self.s.g.get_user(login)
                    self.s.user.remove_from_following(target)
                    console.print(f"[green]✓ 已取消关注 {login}[/green]")
                except GithubException as e:
                    console.print(f"[red]❌ {e.data.get('message', str(e))}[/red]")

# ════════════════════════════════════════════════════════
#  SSH Key 管理
# ════════════════════════════════════════════════════════
class SSHManager:
    def __init__(self, session: GitHubSession):
        self.s = session

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select(
            "SSH Key 操作:",
            choices=["查看已添加的 SSH Keys", "添加新 SSH Key",
                     "生成新 SSH Key 对", "删除 SSH Key"],
            style=Q_STYLE
        ).ask()

        if action == "查看已添加的 SSH Keys":
            with console.status("[cyan]获取..."):
                keys = list(self.s.user.get_keys())
            t = Table(title="🔑 SSH Keys", box=box.ROUNDED, border_style="cyan")
            t.add_column("ID", width=10)
            t.add_column("标题")
            t.add_column("Key 类型", width=12)
            t.add_column("创建时间", width=12)
            for k in keys:
                key_type = k.key.split()[0] if k.key else "-"
                t.add_row(str(k.id), k.title, key_type, str(k.created_at)[:10] if hasattr(k, 'created_at') else "-")
            console.print(t)

        elif action == "添加新 SSH Key":
            title = questionary.text("Key 标题:", style=Q_STYLE).ask()
            key_path = questionary.path(
                "SSH 公钥文件路径:", default=str(Path.home() / ".ssh" / "id_rsa.pub"),
                style=Q_STYLE
            ).ask()
            try:
                key_content = Path(key_path).read_text().strip()
                self.s.user.create_key(title=title, key=key_content)
                console.print(f"[green]✓ SSH Key 添加成功[/green]")
            except Exception as e:
                console.print(f"[red]❌ 失败: {e}[/red]")

        elif action == "生成新 SSH Key 对":
            key_name = questionary.text("Key 文件名:", default="id_rsa_github", style=Q_STYLE).ask()
            email = questionary.text("邮箱:", style=Q_STYLE).ask()
            ssh_dir = Path.home() / ".ssh"
            key_path = ssh_dir / key_name
            console.print(f"\n[cyan]▶ 生成 SSH Key...[/cyan]")
            result = subprocess.run(
                f'ssh-keygen -t rsa -b 4096 -C "{email}" -f "{key_path}" -N ""',
                shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                pub_key = (key_path.with_suffix(".pub")).read_text()
                console.print(f"[green]✓ Key 已生成: {key_path}[/green]")
                console.print(Panel(pub_key, title="[cyan]公钥内容 (已复制路径)[/cyan]"))
                if questionary.confirm("立即添加到 GitHub?", default=True, style=Q_STYLE).ask():
                    title = questionary.text("Key 标题:", style=Q_STYLE).ask() or key_name
                    self.s.user.create_key(title=title, key=pub_key.strip())
                    console.print("[green]✓ SSH Key 已添加到 GitHub[/green]")
            else:
                console.print(f"[red]❌ 生成失败: {result.stderr}[/red]")

        elif action == "删除 SSH Key":
            with console.status("[cyan]获取 Keys..."):
                keys = list(self.s.user.get_keys())
            choices = [f"{k.title} (ID: {k.id})" for k in keys]
            if not choices:
                console.print("[yellow]没有 SSH Keys[/yellow]"); return
            chosen = questionary.select("选择要删除的 Key:", choices=choices, style=Q_STYLE).ask()
            idx = choices.index(chosen)
            if questionary.confirm("确认删除?", default=False, style=Q_STYLE).ask():
                keys[idx].delete()
                console.print("[green]✓ 已删除[/green]")


# ════════════════════════════════════════════════════════
#  文件浏览器（在线查看 / 编辑 / 上传）
# ════════════════════════════════════════════════════════
class FileManager:
    def __init__(self, session):
        self.s = session

    def _pick_repo(self):
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: console.print("[yellow]没有仓库[/yellow]"); return None
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return None
        try:
            return self.s.g.get_repo(name)
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return None

    def browse_files(self):
        if not self.s.require_login(): return
        repo = self._pick_repo()
        if not repo: return
        branch = questionary.text("分支:", default=repo.default_branch, style=Q_STYLE).ask() or repo.default_branch
        self._browse(repo, branch, "")

    def _browse(self, repo, branch, path):
        while True:
            with console.status(f"[cyan]读取 {path or '/'}..."):
                try:
                    items = repo.get_contents(path or "", ref=branch)
                    if not isinstance(items, list): items = [items]
                    items = sorted(items, key=lambda x: (x.type != "dir", x.name))
                except GithubException as e:
                    console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
            choices = []
            for it in items:
                icon = "📁" if it.type == "dir" else "📄"
                size = f" ({it.size}B)" if it.type == "file" else ""
                choices.append(f"{icon}  {it.name}{size}")
            choices.append("⬆  返回上层")
            chosen = questionary.select(
                f"📂 {repo.full_name} / {path or '(根目录)'}  [{branch}]",
                choices=choices, style=Q_STYLE
            ).ask()
            if not chosen or "返回上层" in chosen: return
            name = chosen.split("  ", 1)[1].split(" (")[0]
            item = next((i for i in items if i.name == name), None)
            if not item: continue
            if item.type == "dir":
                self._browse(repo, branch, item.path)
            else:
                self._file_menu(repo, branch, item)

    def _file_menu(self, repo, branch, item):
        action = questionary.select(
            f"📄 {item.path}  ({item.size}B)",
            choices=["👁  查看内容", "✏️  在线编辑", "💾  下载到本地", "← 返回"],
            style=Q_STYLE
        ).ask()
        if not action or "返回" in action: return
        if "查看" in action:
            try:
                content = item.decoded_content.decode("utf-8", errors="replace")
                lines = content.split("\n")
                console.print(Panel(
                    "\n".join(lines[:200]) + ("\n[dim]...(仅显示前200行)[/dim]" if len(lines) > 200 else ""),
                    title=f"[cyan]{item.path}[/cyan]", border_style="cyan"
                ))
            except Exception as e:
                console.print(f"[red]❌ 无法解码: {e}[/red]")
        elif "编辑" in action:
            self._edit_file(repo, branch, item)
        elif "下载" in action:
            save_path = questionary.text("保存路径:", default=item.name, style=Q_STYLE).ask()
            if save_path:
                try:
                    Path(save_path).write_bytes(item.decoded_content)
                    console.print(f"[green]✓ 已保存到 {save_path}[/green]")
                except Exception as e:
                    console.print(f"[red]❌ 保存失败: {e}[/red]")

    def _edit_file(self, repo, branch, item):
        try:
            original = item.decoded_content.decode("utf-8", errors="replace")
        except Exception:
            console.print("[red]❌ 该文件为二进制文件，无法在线编辑[/red]"); return
        console.print(Panel(original[:2000] + ("\n[dim]...[/dim]" if len(original) > 2000 else ""),
                            title=f"[cyan]当前内容: {item.path}[/cyan]", border_style="dim"))
        console.print("[dim]请输入新内容 (输入END单独一行结束):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        new_content = "\n".join(lines)
        if not new_content.strip(): console.print("[yellow]内容为空，已取消[/yellow]"); return
        commit_msg = questionary.text("Commit 信息:", default=f"Update {item.name}", style=Q_STYLE).ask()
        if not commit_msg: return
        try:
            with console.status("[cyan]保存中..."):
                repo.update_file(item.path, commit_msg, new_content, item.sha, branch=branch)
            console.print(f"[green]✓ 文件已更新: {item.path}[/green]")
        except GithubException as e:
            console.print(f"[red]❌ 更新失败: {e.data.get('message',str(e))}[/red]")

    def edit_file(self):
        if not self.s.require_login(): return
        repo = self._pick_repo()
        if not repo: return
        branch = questionary.text("分支:", default=repo.default_branch, style=Q_STYLE).ask() or repo.default_branch
        file_path = questionary.text("文件路径 (如 README.md):", style=Q_STYLE).ask()
        if not file_path: return
        try:
            with console.status("[cyan]读取文件..."):
                item = repo.get_contents(file_path, ref=branch)
        except GithubException as e:
            console.print(f"[red]❌ 文件不存在: {e.data.get('message',str(e))}[/red]"); return
        self._edit_file(repo, branch, item)

    def upload_file(self):
        if not self.s.require_login(): return
        repo = self._pick_repo()
        if not repo: return
        branch = questionary.text("分支:", default=repo.default_branch, style=Q_STYLE).ask() or repo.default_branch
        local_file = questionary.path("选择本地文件:", style=Q_STYLE).ask()
        if not local_file or not Path(local_file).is_file():
            console.print("[red]❌ 文件不存在[/red]"); return
        dest_path = questionary.text("上传到仓库中的路径:", default=Path(local_file).name, style=Q_STYLE).ask()
        if not dest_path: return
        commit_msg = questionary.text("Commit 信息:", default=f"Add {Path(local_file).name}", style=Q_STYLE).ask()
        if not commit_msg: return
        content = Path(local_file).read_bytes()
        existing_sha = None
        try:
            existing = repo.get_contents(dest_path, ref=branch)
            existing_sha = existing.sha
        except GithubException:
            pass
        try:
            with console.status("[cyan]上传中..."):
                if existing_sha:
                    repo.update_file(dest_path, commit_msg, content, existing_sha, branch=branch)
                    console.print(f"[green]✓ 文件已更新: {dest_path}[/green]")
                else:
                    repo.create_file(dest_path, commit_msg, content, branch=branch)
                    console.print(f"[green]✓ 文件已上传: {dest_path}[/green]")
        except GithubException as e:
            console.print(f"[red]❌ 上传失败: {e.data.get('message',str(e))}[/red]")


# ════════════════════════════════════════════════════════
#  Issue 管理
# ════════════════════════════════════════════════════════
class IssueManager:
    def __init__(self, session):
        self.s = session

    def _pick_repo(self):
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: console.print("[yellow]没有仓库[/yellow]"); return None
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return None
        try:
            return self.s.g.get_repo(name)
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return None

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select("Issue 操作:", choices=[
            "📋  查看 Issues", "➕  创建 Issue", "✏️  编辑 / 关闭 Issue",
            "💬  评论 Issue", "🏷️  管理 Labels", "🎯  管理 Milestones"
        ], style=Q_STYLE).ask()
        if not action: return
        if "查看" in action: self.list_issues()
        elif "创建" in action: self.create_issue()
        elif "编辑" in action: self.edit_issue()
        elif "评论" in action: self.comment_issue()
        elif "Labels" in action: self.manage_labels()
        elif "Milestones" in action: self.manage_milestones()

    def list_issues(self):
        repo = self._pick_repo()
        if not repo: return
        state = questionary.select("状态:", choices=["open", "closed", "all"], style=Q_STYLE).ask() or "open"
        with console.status("[cyan]获取 Issues..."):
            issues = [i for i in repo.get_issues(state=state)[:30] if not i.pull_request]
        if not issues: console.print(f"[yellow]没有 {state} Issues[/yellow]"); return
        t = Table(title=f"Issues ({state}) — {repo.full_name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("#", width=6, style="yellow"); t.add_column("标题", min_width=30)
        t.add_column("状态", width=8); t.add_column("标签", width=20)
        t.add_column("创建者", width=14); t.add_column("时间", width=12)
        for i in issues:
            status = "[green]open[/green]" if i.state == "open" else "[red]closed[/red]"
            labels = ", ".join(lb.name for lb in i.labels) or "-"
            t.add_row(str(i.number), i.title[:50], status, labels[:20],
                     i.user.login if i.user else "-", str(i.created_at)[:10])
        console.print(t)

    def create_issue(self):
        repo = self._pick_repo()
        if not repo: return
        title = questionary.text("Issue 标题:", validate=lambda v: True if v.strip() else "不能为空", style=Q_STYLE).ask()
        if not title: return
        console.print("[dim]Issue 正文 (输入END结束，可直接END跳过):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        body = "\n".join(lines)
        try:
            all_labels = [lb.name for lb in repo.get_labels()]
        except Exception:
            all_labels = []
        label_names = []
        if all_labels:
            chosen_labels = questionary.checkbox("选择标签 (可选):", choices=all_labels, style=Q_STYLE).ask()
            label_names = chosen_labels or []
        assignees = []
        if questionary.confirm("是否指派给某人?", default=False, style=Q_STYLE).ask():
            assignee = questionary.text("GitHub 用户名:", style=Q_STYLE).ask()
            if assignee: assignees = [assignee]
        try:
            with console.status("[cyan]创建 Issue..."):
                issue = repo.create_issue(title=title.strip(), body=body or None,
                                          labels=label_names, assignees=assignees)
            console.print(Panel(
                f"[bold green]✓ Issue 创建成功！[/bold green]\n\n"
                f"  编号:  [cyan]#{issue.number}[/cyan]\n"
                f"  标题:  {issue.title}\n"
                f"  URL:   [link={issue.html_url}]{issue.html_url}[/link]",
                border_style="green"
            ))
        except GithubException as e:
            console.print(f"[red]❌ 创建失败: {e.data.get('message',str(e))}[/red]")

    def edit_issue(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("Issue 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            issue = repo.get_issue(int(num_str))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        console.print(Panel(
            f"标题: {issue.title}\n状态: {issue.state}\n正文: {(issue.body or '')[:200]}",
            title=f"[cyan]#{issue.number}[/cyan]", border_style="cyan"
        ))
        action = questionary.select("操作:", choices=[
            "修改标题", "修改正文", "关闭 Issue", "重新打开 Issue", "← 返回"
        ], style=Q_STYLE).ask()
        if not action or "返回" in action: return
        try:
            if "标题" in action:
                new_title = questionary.text("新标题:", default=issue.title, style=Q_STYLE).ask()
                if new_title: issue.edit(title=new_title); console.print("[green]✓ 已更新标题[/green]")
            elif "正文" in action:
                console.print("[dim]输入新正文 (END结束):[/dim]")
                lines = []
                while True:
                    try:
                        line = input()
                        if line == "END": break
                        lines.append(line)
                    except EOFError: break
                issue.edit(body="\n".join(lines)); console.print("[green]✓ 已更新正文[/green]")
            elif "关闭" in action:
                issue.edit(state="closed"); console.print(f"[green]✓ Issue #{issue.number} 已关闭[/green]")
            elif "重新打开" in action:
                issue.edit(state="open"); console.print(f"[green]✓ Issue #{issue.number} 已重新打开[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def comment_issue(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("Issue 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            issue = repo.get_issue(int(num_str))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        with console.status("[cyan]获取评论..."):
            comments = list(issue.get_comments()[:5])
        for c in comments:
            console.print(Panel(c.body[:300], title=f"[cyan]{c.user.login}[/cyan]  {str(c.created_at)[:10]}", border_style="dim"))
        console.print("[dim]输入评论内容 (END结束):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        body = "\n".join(lines)
        if not body.strip(): console.print("[yellow]已取消[/yellow]"); return
        try:
            issue.create_comment(body); console.print("[green]✓ 评论已发布[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def manage_labels(self):
        repo = self._pick_repo()
        if not repo: return
        action = questionary.select("Label 操作:", choices=["查看所有 Labels", "创建 Label", "删除 Label"], style=Q_STYLE).ask()
        if not action: return
        if "查看" in action:
            with console.status("[cyan]获取 Labels..."):
                labels = list(repo.get_labels())
            t = Table(title="Labels", box=box.ROUNDED, border_style="cyan")
            t.add_column("名称"); t.add_column("颜色", width=10); t.add_column("描述")
            for lb in labels:
                t.add_row(f"[bold]{lb.name}[/bold]", f"#{lb.color}", lb.description or "-")
            console.print(t)
        elif "创建" in action:
            name = questionary.text("Label 名称:", style=Q_STYLE).ask()
            if not name: return
            color = questionary.text("颜色 (6位十六进制，不含#):", default="0075ca", style=Q_STYLE).ask() or "0075ca"
            desc = questionary.text("描述 (可选):", style=Q_STYLE).ask() or ""
            try:
                repo.create_label(name=name, color=color, description=desc)
                console.print(f"[green]✓ Label created[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")
        elif "删除" in action:
            with console.status("[cyan]获取 Labels..."):
                labels = list(repo.get_labels())
            if not labels: console.print("[yellow]没有 Labels[/yellow]"); return
            chosen = questionary.select("选择:", choices=[lb.name for lb in labels], style=Q_STYLE).ask()
            if chosen and questionary.confirm(f"确认删除 '{chosen}'?", default=False, style=Q_STYLE).ask():
                next(l for l in labels if l.name == chosen).delete()
                console.print(f"[green]✓ 已删除[/green]")

    def manage_milestones(self):
        repo = self._pick_repo()
        if not repo: return
        action = questionary.select("Milestone 操作:", choices=["查看 Milestones", "创建 Milestone", "关闭 Milestone"], style=Q_STYLE).ask()
        if not action: return
        if "查看" in action:
            with console.status("[cyan]..."):
                ms = list(repo.get_milestones(state="all")[:20])
            t = Table(title="Milestones", box=box.ROUNDED, border_style="cyan")
            t.add_column("编号", width=6); t.add_column("标题"); t.add_column("状态", width=8)
            t.add_column("进度", width=10); t.add_column("截止日期", width=12)
            for m in ms:
                total = m.open_issues + m.closed_issues
                pct = f"{int(m.closed_issues/total*100)}%" if total else "-"
                due = str(m.due_on)[:10] if m.due_on else "-"
                status = "[green]open[/green]" if m.state == "open" else "[red]closed[/red]"
                t.add_row(str(m.number), m.title, status, pct, due)
            console.print(t)
        elif "创建" in action:
            title = questionary.text("Milestone 标题:", style=Q_STYLE).ask()
            if not title: return
            desc = questionary.text("描述 (可选):", style=Q_STYLE).ask() or ""
            try:
                ms = repo.create_milestone(title=title, description=desc)
                console.print(f"[green]✓ Milestone created #{ms.number}[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")
        elif "关闭" in action:
            with console.status("[cyan]..."):
                ms_list = list(repo.get_milestones(state="open"))
            if not ms_list: console.print("[yellow]没有 open Milestones[/yellow]"); return
            chosen = questionary.select("选择:", choices=[m.title for m in ms_list], style=Q_STYLE).ask()
            if chosen:
                next(m for m in ms_list if m.title == chosen).edit(state="closed")
                console.print("[green]✓ 已关闭[/green]")


# ════════════════════════════════════════════════════════
#  Pull Request 管理
# ════════════════════════════════════════════════════════
class PRManager:
    def __init__(self, session):
        self.s = session

    def _pick_repo(self):
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: console.print("[yellow]没有仓库[/yellow]"); return None
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return None
        try:
            return self.s.g.get_repo(name)
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return None

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select("Pull Request 操作:", choices=[
            "📋  查看 PR 列表", "➕  创建 PR", "🔀  合并 PR",
            "🔍  查看 PR Diff", "💬  评论 PR", "✖️  关闭 / 重新打开 PR"
        ], style=Q_STYLE).ask()
        if not action: return
        if "查看 PR 列表" in action: self.list_prs()
        elif "创建" in action: self.create_pr()
        elif "合并" in action: self.merge_pr()
        elif "Diff" in action: self.view_diff()
        elif "评论" in action: self.comment_pr()
        elif "关闭" in action: self.toggle_pr()

    def list_prs(self):
        repo = self._pick_repo()
        if not repo: return
        state = questionary.select("状态:", choices=["open", "closed", "all"], style=Q_STYLE).ask() or "open"
        with console.status("[cyan]获取 PRs..."):
            prs = list(repo.get_pulls(state=state)[:20])
        if not prs: console.print(f"[yellow]没有 {state} PRs[/yellow]"); return
        t = Table(title=f"Pull Requests — {repo.full_name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("#", width=6, style="yellow"); t.add_column("标题", min_width=30)
        t.add_column("状态", width=8); t.add_column("来源", width=18)
        t.add_column("目标", width=14); t.add_column("作者", width=14); t.add_column("时间", width=12)
        for pr in prs:
            status = "[green]open[/green]" if pr.state == "open" else "[red]closed[/red]"
            t.add_row(str(pr.number), pr.title[:45], status, pr.head.ref[:16],
                     pr.base.ref, pr.user.login if pr.user else "-", str(pr.created_at)[:10])
        console.print(t)

    def create_pr(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取分支..."):
            branches = [b.name for b in repo.get_branches()]
        if len(branches) < 2:
            console.print("[yellow]⚠ 至少需要2个分支[/yellow]"); return
        head = questionary.select("来源分支 (你的修改):", choices=branches, style=Q_STYLE).ask()
        if not head: return
        base = questionary.select("目标分支 (合并到):", choices=[b for b in branches if b != head], style=Q_STYLE).ask()
        if not base: return
        title = questionary.text("PR 标题:", validate=lambda v: True if v.strip() else "不能为空", style=Q_STYLE).ask()
        if not title: return
        console.print("[dim]PR 描述 (END结束，可直接END跳过):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        body = "\n".join(lines)
        draft = questionary.confirm("创建为草稿 PR?", default=False, style=Q_STYLE).ask()
        try:
            with console.status("[cyan]创建 PR..."):
                pr = repo.create_pull(title=title.strip(), body=body or "", head=head, base=base, draft=draft or False)
            console.print(Panel(
                f"[bold green]✓ PR #{pr.number} 创建成功！[/bold green]\n\n"
                f"  {head} → {base}\n"
                f"  URL: [link={pr.html_url}]{pr.html_url}[/link]",
                border_style="green"
            ))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def merge_pr(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("PR 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            pr = repo.get_pull(int(num_str))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        console.print(Panel(f"[bold]{pr.title}[/bold]\n{pr.head.ref} → {pr.base.ref}\n可合并: {'✓' if pr.mergeable else '✗'}",
                            title=f"[cyan]PR #{pr.number}[/cyan]", border_style="cyan"))
        if not pr.mergeable:
            console.print("[yellow]⚠ 该 PR 当前无法合并（可能存在冲突）[/yellow]"); return
        method = questionary.select("合并方式:", choices=["merge (保留所有 commits)", "squash (压缩为1个 commit)", "rebase (变基合并)"], style=Q_STYLE).ask()
        if not method: return
        merge_method = method.split(" ")[0]
        commit_title = questionary.text("合并 commit 标题:", default=pr.title, style=Q_STYLE).ask() or pr.title
        if not questionary.confirm(f"确认合并 PR #{pr.number}?", default=False, style=Q_STYLE).ask(): return
        try:
            with console.status("[cyan]合并中..."):
                result = pr.merge(commit_title=commit_title, merge_method=merge_method)
            if result.merged:
                console.print(f"[bold green]✓ PR #{pr.number} 合并成功！[/bold green]\n  SHA: {result.sha}")
            else:
                console.print(f"[red]❌ 合并失败: {result.message}[/red]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def view_diff(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("PR 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            pr = repo.get_pull(int(num_str))
            with console.status("[cyan]获取文件变更..."):
                files = list(pr.get_files())
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        t = Table(title=f"PR #{pr.number} 文件变更", box=box.ROUNDED, border_style="cyan")
        t.add_column("状态", width=10); t.add_column("文件路径")
        t.add_column("+", width=8, style="green"); t.add_column("-", width=8, style="red")
        status_map = {"added": "[green]新增[/green]", "removed": "[red]删除[/red]",
                     "modified": "[yellow]修改[/yellow]", "renamed": "[cyan]重命名[/cyan]"}
        for f in files:
            t.add_row(status_map.get(f.status, f.status), f.filename, str(f.additions), str(f.deletions))
        console.print(t)
        console.print(f"  总计: [green]+{pr.additions}[/green]  [red]-{pr.deletions}[/red]  {pr.changed_files} 个文件")
        if files and questionary.confirm("查看某个文件的 patch?", default=False, style=Q_STYLE).ask():
            chosen = questionary.select("选择文件:", choices=[f.filename for f in files], style=Q_STYLE).ask()
            if chosen:
                f = next(fi for fi in files if fi.filename == chosen)
                if f.patch:
                    console.print(Syntax(f.patch, "diff", theme="monokai", line_numbers=True))
                else:
                    console.print("[yellow]该文件无 patch 数据[/yellow]")

    def comment_pr(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("PR 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            pr = repo.get_pull(int(num_str))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        console.print("[dim]输入评论内容 (END结束):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        body = "\n".join(lines)
        if not body.strip(): console.print("[yellow]已取消[/yellow]"); return
        try:
            pr.create_issue_comment(body); console.print("[green]✓ 评论已发布[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def toggle_pr(self):
        repo = self._pick_repo()
        if not repo: return
        num_str = questionary.text("PR 编号:", validate=lambda v: v.strip().isdigit() or "请输入数字", style=Q_STYLE).ask()
        if not num_str: return
        try:
            pr = repo.get_pull(int(num_str))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        new_state = "closed" if pr.state == "open" else "open"
        label = "关闭" if new_state == "closed" else "重新打开"
        if questionary.confirm(f"确认{label} PR #{pr.number}?", default=False, style=Q_STYLE).ask():
            try:
                pr.edit(state=new_state); console.print(f"[green]✓ PR #{pr.number} 已{label}[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")


# ════════════════════════════════════════════════════════
#  Release & Tag 管理
# ════════════════════════════════════════════════════════
class ReleaseManager:
    def __init__(self, session):
        self.s = session

    def _pick_repo(self):
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: console.print("[yellow]没有仓库[/yellow]"); return None
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return None
        try:
            return self.s.g.get_repo(name)
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return None

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select("Release / Tag 操作:", choices=[
            "📋  查看 Releases", "➕  创建 Release", "🗑️  删除 Release",
            "🏷️  查看 Tags", "➕  创建 Tag", "🗑️  删除 Tag"
        ], style=Q_STYLE).ask()
        if not action: return
        if "查看 Releases" in action: self.list_releases()
        elif "创建 Release" in action: self.create_release()
        elif "删除 Release" in action: self.delete_release()
        elif "查看 Tags" in action: self.list_tags()
        elif "创建 Tag" in action: self.create_tag()
        elif "删除 Tag" in action: self.delete_tag()

    def list_releases(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取 Releases..."):
            releases = list(repo.get_releases()[:15])
        if not releases: console.print("[yellow]没有 Releases[/yellow]"); return
        t = Table(title=f"Releases — {repo.full_name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("Tag", width=16); t.add_column("名称", min_width=20)
        t.add_column("草稿", width=6); t.add_column("预发布", width=8)
        t.add_column("发布时间", width=12); t.add_column("下载", width=8)
        for r in releases:
            downloads = sum(a.download_count for a in r.get_assets())
            t.add_row(r.tag_name, r.title or "-", "✓" if r.draft else "-",
                     "✓" if r.prerelease else "-",
                     str(r.published_at)[:10] if r.published_at else "-", str(downloads))
        console.print(t)

    def create_release(self):
        repo = self._pick_repo()
        if not repo: return
        tag_name = questionary.text("Tag 名称 (如 v1.0.0):", validate=lambda v: True if v.strip() else "不能为空", style=Q_STYLE).ask()
        if not tag_name: return
        name = questionary.text("Release 标题:", default=tag_name, style=Q_STYLE).ask() or tag_name
        console.print("[dim]Release Notes (END结束，可直接END跳过):[/dim]")
        lines = []
        while True:
            try:
                line = input()
                if line == "END": break
                lines.append(line)
            except EOFError: break
        body = "\n".join(lines)
        is_draft = questionary.confirm("保存为草稿?", default=False, style=Q_STYLE).ask()
        is_pre = questionary.confirm("标记为预发布?", default=False, style=Q_STYLE).ask()
        target = questionary.text("基于哪个分支/commit (留空=默认分支):", style=Q_STYLE).ask() or repo.default_branch
        try:
            with console.status("[cyan]创建 Release..."):
                release = repo.create_git_release(
                    tag=tag_name.strip(), name=name, message=body or "",
                    draft=is_draft or False, prerelease=is_pre or False, target_commitish=target
                )
            console.print(Panel(
                f"[bold green]✓ Release 创建成功！[/bold green]\n\n"
                f"  Tag: [cyan]{release.tag_name}[/cyan]\n"
                f"  URL: [link={release.html_url}]{release.html_url}[/link]",
                border_style="green"
            ))
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def delete_release(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取 Releases..."):
            releases = list(repo.get_releases()[:15])
        if not releases: console.print("[yellow]没有 Releases[/yellow]"); return
        choices = [f"{r.tag_name}  {r.title or ''}" for r in releases]
        chosen = questionary.select("选择要删除的 Release:", choices=choices, style=Q_STYLE).ask()
        if not chosen: return
        idx = choices.index(chosen)
        if questionary.confirm(f"确认删除?", default=False, style=Q_STYLE).ask():
            try:
                releases[idx].delete_release()
                console.print("[green]✓ 已删除[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def list_tags(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取 Tags..."):
            tags = list(repo.get_tags()[:20])
        if not tags: console.print("[yellow]没有 Tags[/yellow]"); return
        t = Table(title=f"Tags — {repo.full_name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("Tag 名称"); t.add_column("Commit SHA", width=12)
        for tag in tags:
            t.add_row(tag.name, tag.commit.sha[:8])
        console.print(t)

    def create_tag(self):
        repo = self._pick_repo()
        if not repo: return
        tag_name = questionary.text("Tag 名称:", validate=lambda v: True if v.strip() else "不能为空", style=Q_STYLE).ask()
        if not tag_name: return
        msg = questionary.text("Tag 信息:", default=tag_name, style=Q_STYLE).ask() or tag_name
        sha = questionary.text("基于哪个 commit SHA (留空=最新):", style=Q_STYLE).ask()
        if not sha:
            with console.status("[cyan]获取最新 commit..."):
                sha = repo.get_branch(repo.default_branch).commit.sha
        try:
            with console.status("[cyan]创建 Tag..."):
                tag_obj = repo.create_git_tag(tag=tag_name.strip(), message=msg, object=sha, type="commit")
                repo.create_git_ref(f"refs/tags/{tag_name.strip()}", tag_obj.sha)
            console.print(f"[green]✓ Tag created[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def delete_tag(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取 Tags..."):
            tags = list(repo.get_tags()[:20])
        if not tags: console.print("[yellow]没有 Tags[/yellow]"); return
        chosen = questionary.select("选择:", choices=[t.name for t in tags], style=Q_STYLE).ask()
        if chosen and questionary.confirm(f"确认删除 '{chosen}'?", default=False, style=Q_STYLE).ask():
            try:
                repo.get_git_ref(f"tags/{chosen}").delete()
                console.print("[green]✓ 已删除[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")


# ════════════════════════════════════════════════════════
#  协作者 & 仓库高级操作
# ════════════════════════════════════════════════════════
class CollabManager:
    def __init__(self, session):
        self.s = session

    def _pick_repo(self):
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: console.print("[yellow]没有仓库[/yellow]"); return None
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return None
        try:
            return self.s.g.get_repo(name)
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return None

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select("协作者 & 高级仓库操作:", choices=[
            "👥  查看协作者", "➕  添加协作者", "➖  移除协作者",
            "✏️  重命名仓库", "📦  归档 / 取消归档", "🔁  转让仓库", "👁️  Watch / Unwatch"
        ], style=Q_STYLE).ask()
        if not action: return
        if "查看协作者" in action: self.list_collabs()
        elif "添加协作者" in action: self.add_collab()
        elif "移除协作者" in action: self.remove_collab()
        elif "重命名" in action: self.rename_repo()
        elif "归档" in action: self.archive_repo()
        elif "转让" in action: self.transfer_repo()
        elif "Watch" in action: self.watch_repo()

    def list_collabs(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取协作者..."):
            collabs = list(repo.get_collaborators())
        t = Table(title=f"协作者 — {repo.full_name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("用户名"); t.add_column("权限", width=12); t.add_column("GitHub URL")
        for c in collabs:
            perm = repo.get_collaborator_permission(c)
            t.add_row(c.login, perm, c.html_url)
        console.print(t)

    def add_collab(self):
        repo = self._pick_repo()
        if not repo: return
        login = questionary.text("GitHub 用户名:", style=Q_STYLE).ask()
        if not login: return
        perm = questionary.select("权限:", choices=["pull (只读)", "push (读写)", "admin (管理员)", "maintain", "triage"], style=Q_STYLE).ask()
        if not perm: return
        perm_key = perm.split(" ")[0]
        try:
            repo.add_to_collaborators(login, perm_key)
            console.print(f"[green]✓ 已邀请 {login}（对方需接受邀请后生效）[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def remove_collab(self):
        repo = self._pick_repo()
        if not repo: return
        with console.status("[cyan]获取协作者..."):
            collabs = [c for c in repo.get_collaborators() if c.login != self.s.user.login]
        if not collabs: console.print("[yellow]没有其他协作者[/yellow]"); return
        chosen = questionary.select("选择要移除的协作者:", choices=[c.login for c in collabs], style=Q_STYLE).ask()
        if chosen and questionary.confirm(f"确认移除 {chosen}?", default=False, style=Q_STYLE).ask():
            try:
                repo.remove_from_collaborators(chosen)
                console.print(f"[green]✓ 已移除 {chosen}[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def rename_repo(self):
        repo = self._pick_repo()
        if not repo: return
        new_name = questionary.text(f"新仓库名 (当前: {repo.name}):", validate=lambda v: True if v.strip() else "不能为空", style=Q_STYLE).ask()
        if not new_name: return
        if questionary.confirm(f"确认重命名为 {new_name}?", default=False, style=Q_STYLE).ask():
            try:
                repo.edit(name=new_name.strip())
                console.print(f"[green]✓ 已重命名为 {new_name}[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def archive_repo(self):
        repo = self._pick_repo()
        if not repo: return
        action = "取消归档" if repo.archived else "归档"
        if questionary.confirm(f"当前: {'已归档' if repo.archived else '正常'}。确认{action}?", default=False, style=Q_STYLE).ask():
            try:
                repo.edit(archived=not repo.archived)
                console.print(f"[green]✓ 已{action}[/green]")
            except GithubException as e:
                console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def transfer_repo(self):
        repo = self._pick_repo()
        if not repo: return
        console.print(Panel(f"[bold yellow]⚠ 转让仓库后将失去所有权！[/bold yellow]\n仓库: [bold]{repo.full_name}[/bold]", border_style="yellow"))
        new_owner = questionary.text("转让给 (用户名或组织名):", style=Q_STYLE).ask()
        if not new_owner: return
        if not questionary.confirm(f"确认转让给 {new_owner}?", default=False, style=Q_STYLE).ask(): return
        confirm2 = questionary.text(f"输入仓库名 '{repo.name}' 以确认:", style=Q_STYLE).ask()
        if confirm2 != repo.name:
            console.print("[yellow]仓库名不匹配，已取消[/yellow]"); return
        try:
            repo.transfer(new_owner)
            console.print(f"[green]✓ 转让请求已发送给 {new_owner}[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def watch_repo(self):
        if not self.s.require_login(): return
        repo_name = questionary.text("仓库 (owner/repo):", style=Q_STYLE).ask()
        if not repo_name: return
        try:
            repo = self.s.g.get_repo(repo_name)
            action = questionary.select("操作:", choices=["Watch (订阅通知)", "Unwatch (取消订阅)"], style=Q_STYLE).ask()
            if not action: return
            if "Unwatch" not in action:
                self.s.user.add_to_watched(repo)
                console.print(f"[green]✓ 已 Watch {repo_name}[/green]")
            else:
                self.s.user.remove_from_watched(repo)
                console.print(f"[green]✓ 已 Unwatch {repo_name}[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")


# ════════════════════════════════════════════════════════
#  通知 & 个人资料 & Actions
# ════════════════════════════════════════════════════════
class NotificationManager:
    def __init__(self, session):
        self.s = session

    def manage(self):
        if not self.s.require_login(): return
        action = questionary.select("通知 & 个人资料:", choices=[
            "🔔  查看通知", "✅  标记全部已读", "✏️  编辑个人资料", "⚙️  查看 GitHub Actions"
        ], style=Q_STYLE).ask()
        if not action: return
        if "查看通知" in action: self.list_notifications()
        elif "标记全部已读" in action: self.mark_all_read()
        elif "编辑个人资料" in action: self.edit_profile()
        elif "Actions" in action: self.view_actions()

    def list_notifications(self):
        with console.status("[cyan]获取通知..."):
            notifs = list(self.s.user.get_notifications()[:20])
        if not notifs:
            console.print("[green]✓ 没有未读通知[/green]"); return
        t = Table(title=f"通知 ({len(notifs)} 条)", box=box.ROUNDED, border_style="cyan")
        t.add_column("仓库", width=25); t.add_column("类型", width=12)
        t.add_column("标题", min_width=30); t.add_column("原因", width=14); t.add_column("时间", width=12)
        reason_map = {"assign": "指派", "comment": "评论", "mention": "@提及",
                     "review_requested": "请求Review", "subscribed": "订阅", "author": "作者"}
        for n in notifs:
            t.add_row(n.repository.full_name[:23], n.subject.type,
                     n.subject.title[:40], reason_map.get(n.reason, n.reason), str(n.updated_at)[:10])
        console.print(t)
        if questionary.confirm("标记全部已读?", default=False, style=Q_STYLE).ask():
            self.mark_all_read()

    def mark_all_read(self):
        try:
            with console.status("[cyan]标记已读..."):
                self.s.user.mark_notifications_as_read()
            console.print("[green]✓ 全部通知已标记为已读[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def edit_profile(self):
        u = self.s.user
        console.print(Panel(
            f"姓名: {u.name or '-'}\nBio: {u.bio or '-'}\n公司: {u.company or '-'}\n地点: {u.location or '-'}\n博客: {u.blog or '-'}",
            title="[cyan]当前个人资料[/cyan]", border_style="cyan"
        ))
        what = questionary.checkbox("选择要修改的项目:", choices=["姓名", "Bio", "公司", "地点", "博客/网站"], style=Q_STYLE).ask()
        if not what: return
        kwargs = {}
        if "姓名" in what:
            v = questionary.text("新姓名:", default=u.name or "", style=Q_STYLE).ask()
            if v is not None: kwargs["name"] = v
        if "Bio" in what:
            v = questionary.text("新 Bio:", default=u.bio or "", style=Q_STYLE).ask()
            if v is not None: kwargs["bio"] = v
        if "公司" in what:
            v = questionary.text("公司:", default=u.company or "", style=Q_STYLE).ask()
            if v is not None: kwargs["company"] = v
        if "地点" in what:
            v = questionary.text("地点:", default=u.location or "", style=Q_STYLE).ask()
            if v is not None: kwargs["location"] = v
        if "博客" in what:
            v = questionary.text("博客/网站 URL:", default=u.blog or "", style=Q_STYLE).ask()
            if v is not None: kwargs["blog"] = v
        if not kwargs: return
        try:
            u.edit(**kwargs); console.print("[green]✓ 个人资料已更新[/green]")
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]")

    def view_actions(self):
        if not self.s.require_login(): return
        with console.status("[cyan]获取仓库列表..."):
            repos = list(self.s.user.get_repos(type="all"))
        if not repos: return
        name = questionary.autocomplete("选择仓库:", choices=[r.full_name for r in repos], style=Q_STYLE).ask()
        if not name: return
        try:
            repo = self.s.g.get_repo(name)
            with console.status("[cyan]获取 Workflows..."):
                workflows = list(repo.get_workflows())
        except GithubException as e:
            console.print(f"[red]❌ {e.data.get('message',str(e))}[/red]"); return
        if not workflows:
            console.print("[yellow]该仓库没有 GitHub Actions Workflows[/yellow]"); return
        t = Table(title=f"Workflows — {name}", box=box.ROUNDED, border_style="cyan")
        t.add_column("ID", width=10); t.add_column("名称"); t.add_column("状态", width=12); t.add_column("文件路径")
        for w in workflows:
            t.add_row(str(w.id), w.name, w.state, w.path)
        console.print(t)
        if questionary.confirm("查看某个 Workflow 的最近运行?", default=False, style=Q_STYLE).ask():
            chosen = questionary.select("选择 Workflow:", choices=[w.name for w in workflows], style=Q_STYLE).ask()
            if chosen:
                wf = next(w for w in workflows if w.name == chosen)
                with console.status("[cyan]获取运行记录..."):
                    runs = list(wf.get_runs()[:10])
                t2 = Table(title=f"最近运行 — {chosen}", box=box.ROUNDED, border_style="cyan")
                t2.add_column("Run #", width=8); t2.add_column("状态", width=12)
                t2.add_column("结论", width=10); t2.add_column("分支", width=14)
                t2.add_column("触发", width=12); t2.add_column("时间", width=12)
                status_map = {"completed": "[green]完成[/green]", "in_progress": "[yellow]运行中[/yellow]", "queued": "[cyan]排队[/cyan]"}
                conclusion_map = {"success": "[green]成功[/green]", "failure": "[red]失败[/red]", "cancelled": "[yellow]已取消[/yellow]"}
                for r in runs:
                    t2.add_row(str(r.run_number), status_map.get(r.status, r.status or "-"),
                              conclusion_map.get(r.conclusion, r.conclusion or "-"),
                              (r.head_branch or "-")[:12], r.event or "-", str(r.created_at)[:10])
                console.print(t2)


# ════════════════════════════════════════════════════════
#  主菜单
# ════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.config = Config()
        self.session = GitHubSession(self.config)
        self.repo_mgr = RepoManager(self.session)
        self.git_local = GitLocalManager(self.session)
        self.gist_mgr = GistManager(self.session)
        self.search_mgr = SearchManager(self.session)
        self.ssh_mgr = SSHManager(self.session)
        self.file_mgr = FileManager(self.session)
        self.issue_mgr = IssueManager(self.session)
        self.pr_mgr = PRManager(self.session)
        self.release_mgr = ReleaseManager(self.session)
        self.collab_mgr = CollabManager(self.session)
        self.notif_mgr = NotificationManager(self.session)

    def banner(self):
        banner_text = Text()
        banner_text.append("  ██████╗ ████████╗███╗   ███╗\n", style="bold cyan")
        banner_text.append("  ██╔════╝╚══██╔══╝████╗ ████║\n", style="bold cyan")
        banner_text.append("  ██║  ███╗  ██║   ██╔████╔██║\n", style="bold blue")
        banner_text.append("  ██║   ██║  ██║   ██║╚██╔╝██║\n", style="bold blue")
        banner_text.append("  ╚██████╔╝  ██║   ██║ ╚═╝ ██║\n", style="bold magenta")
        banner_text.append("   ╚═════╝   ╚═╝   ╚═╝     ╚═╝\n", style="bold magenta")
        banner_text.append("\n  GitHub Terminal Manager  v1.0\n", style="bold white")
        if self.session.user:
            banner_text.append(f"  已登录: {self.session.user.login}", style="green")
        else:
            banner_text.append("  [未登录]", style="dim")
        console.print(Panel(banner_text, border_style="cyan", padding=(0, 2)))

    def main_menu(self):
        MENUS = {
            "🔐  登录 / 切换账号": self.session.login,
            "─── 仓库操作 ───────────────": None,
            "📦  查看我的仓库列表": self.repo_mgr.list_repos,
            "➕  创建新仓库": self.repo_mgr.create_repo,
            "🔍  查看仓库详情 / Commits / Issues": self.repo_mgr.repo_info,
            "✏️  修改仓库设置": self.repo_mgr.edit_repo,
            "🗂️  删除仓库内容 (文件/目录)": self.repo_mgr.delete_repo_contents,
            "🍴  Fork 仓库": self.repo_mgr.fork_repo,
            "⭐  Star 管理": self.repo_mgr.star_manage,
            "🗑️  删除仓库": self.repo_mgr.delete_repo,
            "─── 文件管理 ───────────────": None,
            "📁  浏览 / 查看仓库文件": self.file_mgr.browse_files,
            "✏️  在线编辑文件": self.file_mgr.edit_file,
            "⬆️  上传本地文件到仓库": self.file_mgr.upload_file,
            "─── Issue 管理 ─────────────": None,
            "🐛  Issue 操作": self.issue_mgr.manage,
            "─── Pull Request ───────────": None,
            "🔀  Pull Request 操作": self.pr_mgr.manage,
            "─── Release & Tag ──────────": None,
            "🚀  Release / Tag 操作": self.release_mgr.manage,
            "─── 协作 & 高级管理 ─────────": None,
            "👥  协作者 & 仓库高级操作": self.collab_mgr.manage,
            "─── Git 本地操作 ────────────": None,
            "⬇️  克隆仓库 (git clone)": self.git_local.clone_repo,
            "⬆️  上传项目 (git push)": self.git_local.push_project,
            "🔄  拉取更新 (git pull)": self.git_local.pull_project,
            "📊  查看项目状态 (git status/log)": self.git_local.git_status,
            "🌿  分支管理": self.git_local.branch_manage,
            "─── 其他功能 ───────────────": None,
            "📝  Gist 管理": self._gist_menu,
            "🔑  SSH Key 管理": self.ssh_mgr.manage,
            "🔔  通知 & 个人资料 & Actions": self.notif_mgr.manage,
            "👤  个人资料 (查看)": self.search_mgr.my_profile,
            "👥  关注/粉丝管理": self.search_mgr.follow_manage,
            "🔍  搜索仓库": self.search_mgr.search_repos,
            "👤  搜索用户": self.search_mgr.search_users,
            "─────────────────────────────": None,
            "🚪  退出": "exit",
        }

        while True:
            console.clear()
            self.banner()

            choices = [k for k in MENUS.keys()]
            action = questionary.select(
                "选择操作:",
                choices=choices,
                style=Q_STYLE,
                instruction="(↑↓ 选择, Enter 确认)"
            ).ask()

            if action is None or MENUS.get(action) == "exit":
                console.print("\n[cyan]再见! 👋[/cyan]\n")
                break

            handler = MENUS.get(action)
            if handler is None:
                continue  # 分隔线

            console.print()
            try:
                handler()
            except KeyboardInterrupt:
                console.print("\n[yellow]↩ 已取消，返回主菜单[/yellow]")
            except Exception as e:
                console.print(f"\n[red]错误: {e}[/red]")

            console.print()
            questionary.press_any_key_to_continue("按任意键返回主菜单 (或 Ctrl+C 直接退出)...").ask()

    def _gist_menu(self):
        action = questionary.select(
            "Gist 操作:", choices=["查看我的 Gists", "创建新 Gist"], style=Q_STYLE
        ).ask()
        if action == "查看我的 Gists":
            self.gist_mgr.list_gists()
        elif action == "创建新 Gist":
            self.gist_mgr.create_gist()

# ════════════════════════════════════════════════════════
#  入口
# ════════════════════════════════════════════════════════
def main():
    # 检查 git 是否安装
    if not shutil.which("git"):
        console.print("[red]❌ 未检测到 git，请先安装 git[/red]")
        sys.exit(1)

    app = App()

    # ── 启动时始终弹出登录对话框 ──────────────────────────
    saved_token    = app.config.get("token")
    saved_username = app.config.get("username")

    if saved_token:
        # 有保存的 token → 先画登录画面，静默验证，再问是否使用
        app.session._draw_login_screen()
        console.print(Panel(
            f"  欢迎回来！检测到已保存的账号 [bold cyan]{saved_username or '(未知)'}[/bold cyan]\n"
            f"  [dim]Token 已安全存储在本地配置中[/dim]",
            border_style="cyan", title="[cyan]  GitHub 登录  [/cyan]", padding=(1, 2)
        ))
        console.print()
        use_saved = questionary.select(
            "  请选择登录方式:",
            choices=[
                f"✓  使用已保存账号  [{saved_username or 'token'}]",
                "→  切换账号 / 重新登录",
                "✗  退出",
            ],
            style=Q_STYLE
        ).ask()

        if use_saved is None or "退出" in use_saved:
            console.print("\n[cyan]再见! 👋[/cyan]\n")
            return

        if "使用已保存账号" in use_saved:
            # 静默验证保存的 token
            with console.status("[cyan]  正在验证登录状态...[/cyan]", spinner="dots"):
                try:
                    auth = Auth.Token(saved_token)
                    g    = Github(auth=auth)
                    user = g.get_user()
                    _    = user.login
                    app.session.g     = g
                    app.session.user  = user
                    app.session.token = saved_token
                except Exception:
                    app.config.set("token", None)
                    console.print("\n  [yellow]⚠ 已保存的 Token 已失效，请重新登录[/yellow]\n")
                    questionary.press_any_key_to_continue("  按任意键继续...").ask()
                    if not app.session.login(from_startup=False):
                        return

            # 验证成功 → 简短欢迎
            console.clear()
            app.session._draw_login_screen()
            console.print(Panel(
                f"  [bold green]✓  验证成功[/bold green]\n\n"
                f"  用户名:   [bold cyan]{user.login}[/bold cyan]\n"
                f"  邮箱:     [cyan]{user.email or '未公开'}[/cyan]\n"
                f"  公开仓库: [cyan]{user.public_repos}[/cyan] 个\n"
                f"  粉丝:     [cyan]{user.followers}[/cyan]   关注: [cyan]{user.following}[/cyan]",
                border_style="green", title="[green]  欢迎回来  [/green]", padding=(1, 2)
            ))
            console.print()
            questionary.press_any_key_to_continue("  按任意键进入主菜单...").ask()
        else:
            # 切换账号
            if not app.session.login(from_startup=False):
                return
    else:
        # 没有保存的 token → 直接弹出登录框
        if not app.session.login(from_startup=True):
            return

    app.main_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[cyan]再见! 👋[/cyan]\n")
