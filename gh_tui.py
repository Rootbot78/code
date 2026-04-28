#!/usr/bin/env python3
"""
GitHub TUI - 交互式 GitHub 管理界面
基于 tkinter 的图形用户界面，实现使用说明.md 中的全部功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import subprocess
import json
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any


# ============================================================
# 配置
# ============================================================
LOCAL_REPO_DIR = os.path.expanduser("~/github/")
GITHUB_TUI_TITLE = "GitHub TUI"
THEME = {
    "bg": "#0d1117",
    "fg": "#c9d1d9",
    "accent": "#238636",
    "accent_hover": "#2ea043",
    "border": "#30363d",
    "selected": "#1f6feb",
    "text_bright": "#ffffff",
    "text_dim": "#8b949e",
    "error": "#f85149",
    "warning": "#d29922",
}


# ============================================================
# 工具函数
# ============================================================
def run_gh_command(args: List[str], capture: bool = True, timeout: int = 30) -> Optional[str]:
    """执行 gh 命令并返回结果"""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout if capture else None
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            if error_msg and error_msg != "EOF":
                print(f"gh command error: {error_msg}", file=sys.stderr)
            return None
    except subprocess.TimeoutExpired:
        print("gh command timeout", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("gh command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error running gh command: {e}", file=sys.stderr)
        return None
        return None


def get_auth_status() -> Dict[str, Any]:
    """获取认证状态"""
    result = run_gh_command(["api", "user"])
    if result:
        try:
            data = json.loads(result)
            return {"authenticated": True, "user": data}
        except json.JSONDecodeError:
            pass
    return {"authenticated": False, "user": {}}


def get_username() -> str:
    """获取当前用户名"""
    result = run_gh_command(["api", "user", "--jq", ".login"])
    return result.strip() if result else "未登录"


def list_remote_repos() -> List[Dict[str, Any]]:
    """获取远程仓库列表"""
    result = run_gh_command(["repo", "list", "--json", "name,owner,description,isPrivate,url", "--limit", "100"])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def clone_repo(repo: str, path: str = LOCAL_REPO_DIR) -> bool:
    """克隆仓库到指定路径"""
    target_path = os.path.join(path, repo.split("/")[-1])

    # 如果目标路径已存在且不为空，提示用户
    if os.path.exists(target_path):
        if os.listdir(target_path):
            return False  # 目录非空

    # 确保父目录存在
    os.makedirs(path, exist_ok=True)

    try:
        # 使用 git clone
        result = subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", target_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Clone error: {e}")
        return False


def create_repo(name: str, description: str = "", private: bool = False,
                init_readme: bool = False, add_gitignore: bool = False) -> bool:
    """创建新仓库"""
    args = ["repo", "create", name]
    if description:
        args.extend(["--description", description])
    if private:
        args.append("--private")
    else:
        args.append("--public")
    if init_readme:
        args.append("--add-readme")
    if add_gitignore:
        args.append("--gitignore-template", "Python")

    result = run_gh_command(args, capture=False)
    return result is not None


def delete_repo(owner: str, repo: str) -> bool:
    """删除仓库"""
    result = run_gh_command(["repo", "delete", f"{owner}/{repo}", "--yes"], capture=False)
    return result is not None


def get_file_sha(owner: str, repo: str, path: str) -> Optional[str]:
    """获取文件的 SHA（用于更新或删除）"""
    result = run_gh_command(["api", f"repos/{owner}/{repo}/contents/{path}", "--jq", ".sha"])
    return result.strip() if result else None


def upload_file(owner: str, repo: str, file_path: str, content: bytes, message: str) -> bool:
    """上传文件到仓库（使用 GitHub API）"""
    import base64
    import json

    # 获取文件 SHA（如果文件已存在）
    sha = get_file_sha(owner, repo, file_path)

    # Base64 编码内容
    encoded = base64.b64encode(content).decode()

    # 构建 JSON 数据
    data = {"message": message, "content": encoded}
    if sha:
        data["sha"] = sha

    json_input = json.dumps(data)

    # 使用 gh api 命令，通过 stdin 传递 JSON
    proc = subprocess.run(
        ["gh", "api", "-X", "PUT", f"repos/{owner}/{repo}/contents/{file_path}",
         "--input", "-"],
        input=json_input,
        capture_output=True,
        text=True
    )
    if proc.returncode != 0:
        print(f"Upload error: {proc.stderr}", file=sys.stderr)
    return proc.returncode == 0


def delete_file(owner: str, repo: str, file_path: str, message: str) -> bool:
    """删除仓库文件（使用 GitHub API）"""
    import json

    sha = get_file_sha(owner, repo, file_path)
    if not sha:
        print(f"File not found: {file_path}")
        return False

    data = {"message": message, "sha": sha}
    json_input = json.dumps(data)

    proc = subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/{owner}/{repo}/contents/{file_path}",
         "--input", "-"],
        input=json_input,
        capture_output=True,
        text=True
    )
    if proc.returncode != 0:
        print(f"Delete error: {proc.stderr}", file=sys.stderr)
    return proc.returncode == 0


def list_repo_files(owner: str, repo: str, path: str = "") -> List[Dict]:
    """列出仓库中的文件"""
    result = run_gh_command(["api", f"repos/{owner}/{repo}/contents/{path}",
                            "--jq", ".[] | {name: .name, type: .type, sha: .sha, size: .size}"])
    if result:
        files = []
        for line in result.strip().split("\n"):
            if line:
                try:
                    files.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return files
    return []


def fork_repo(owner: str, repo: str) -> bool:
    """Fork 仓库"""
    proc = subprocess.run(["gh", "repo", "fork", f"{owner}/{repo}", "--clone=false"],
                         capture_output=True, text=True)
    # 如果已 Fork，gh 返回 0 但 stderr 有消息
    if proc.stderr and "already exists" in proc.stderr:
        return True  # 已存在算成功
    return proc.returncode == 0


def star_repo(owner: str, repo: str) -> bool:
    """Star 仓库"""
    proc = subprocess.run(["gh", "repo", "star", f"{owner}/{repo}"],
                         capture_output=True, text=True)
    return proc.returncode == 0


def unstar_repo(owner: str, repo: str) -> bool:
    """Unstar 仓库"""
    proc = subprocess.run(["gh", "repo", "unstar", f"{owner}/{repo}"],
                         capture_output=True, text=True)
    return proc.returncode == 0


def get_repo_details(owner: str, repo: str) -> Optional[Dict]:
    """获取仓库详细信息"""
    result = run_gh_command(["api", f"repos/{owner}/{repo}",
                            "--jq", "{name:.name,description:.description,default_branch:.default_branch,"
                            "stargazers:.stargazers_count,forks:.forks_count,open_issues:.open_issues_count,"
                            "language:.language,created:.created_at,updated:.pushed_at,url:.html_url}"])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    return None


def list_commits(owner: str, repo: str, limit: int = 20) -> List[Dict]:
    """获取提交历史"""
    result = run_gh_command(["api", f"repos/{owner}/{repo}/commits",
                            "--jq", f".[:{limit}] | .[] | {{sha:.sha[:7],message:.commit.message,author:.commit.author.name,date:.commit.author.date}}"])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def list_pull_requests(owner: str, repo: str, state: str = "open") -> List[Dict]:
    """列出 Pull Requests"""
    result = run_gh_command(["pr", "list", "--repo", f"{owner}/{repo}",
                             "--state", state, "--json", "number,title,state,author,createdAt",
                             "--limit", "30"])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def create_pull_request(owner: str, repo: str, title: str, body: str, head: str, base: str = "main") -> bool:
    """创建 Pull Request"""
    proc = subprocess.run(["gh", "pr", "create", "--repo", f"{owner}/{repo}",
                          "--title", title, "--body", body, "--head", head, "--base", base],
                         capture_output=True, text=True)
    return proc.returncode == 0


def search_repos(query: str, limit: int = 20) -> List[Dict]:
    """搜索仓库"""
    result = run_gh_command(["search", "repos", query, "--json", "name,owner,description,isPrivate,url",
                            "--limit", str(limit)])
    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def get_local_repos() -> List[str]:
    """获取本地仓库列表"""
    if not os.path.exists(LOCAL_REPO_DIR):
        return []
    repos = []
    for item in os.listdir(LOCAL_REPO_DIR):
        path = os.path.join(LOCAL_REPO_DIR, item)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, ".git")):
            repos.append(item)
    return sorted(repos)


def get_git_status(repo: str) -> Dict[str, Any]:
    """获取本地仓库的 git 状态"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    files = result.stdout.strip().split("\n") if result.stdout.strip() else []
    return {"has_changes": len(files) > 0, "files": [f for f in files if f]}


def get_git_branch(repo: str) -> str:
    """获取当前分支"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout.strip()


def get_git_branches(repo: str) -> List[Dict[str, str]]:
    """获取所有分支"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(
        ["git", "branch", "-a", "--format", "%(refname:short)|%(upstream:short)|%(objectname:short)"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    branches = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|")
            branches.append({
                "name": parts[0] if len(parts) > 0 else "",
                "upstream": parts[1] if len(parts) > 1 else "",
                "sha": parts[2] if len(parts) > 2 else ""
            })
    return branches


def git_commit(repo: str, message: str, files: List[str]) -> tuple:
    """提交更改，返回 (success: bool, error_msg: str)"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    try:
        # Stage files
        for f in files:
            result = subprocess.run(["git", "add", f], cwd=repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                return False, result.stderr or "git add 失败"
        # Commit
        result = subprocess.run(["git", "commit", "-m", message], cwd=repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            return False, result.stderr or "git commit 失败"
        return True, ""
    except Exception as e:
        return False, str(e)


def git_push(repo: str) -> bool:
    """推送更改"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(["git", "push"], cwd=repo_path, capture_output=False)
    return result.returncode == 0


def git_pull(repo: str) -> bool:
    """拉取更新"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(["git", "pull"], cwd=repo_path, capture_output=False)
    return result.returncode == 0


def create_branch(repo: str, branch_name: str, base_branch: str = "main") -> bool:
    """创建分支"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    try:
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def switch_branch(repo: str, branch_name: str) -> bool:
    """切换分支"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    try:
        subprocess.run(["git", "checkout", branch_name], cwd=repo_path, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def delete_branch(repo: str, branch_name: str) -> bool:
    """删除分支"""
    repo_path = os.path.join(LOCAL_REPO_DIR, repo)
    result = subprocess.run(["git", "branch", "-d", branch_name], cwd=repo_path, capture_output=False)
    return result.returncode == 0


def list_workflows(repo_path: str) -> List[Dict[str, Any]]:
    """获取工作流列表"""
    workflow_dir = os.path.join(repo_path, ".github", "workflows")
    if not os.path.exists(workflow_dir):
        return []
    workflows = []
    for f in os.listdir(workflow_dir):
        if f.endswith((".yml", ".yaml")):
            workflows.append({"name": f.replace(".yml", "").replace(".yaml", ""), "file": f})
    return workflows


def run_workflow(repo: str, workflow_name: str) -> bool:
    """触发工作流"""
    result = run_gh_command(["workflow", "run", workflow_name], capture=False)
    return result is not None


def get_workflow_runs(repo: str, workflow_name: str = "") -> List[Dict[str, Any]]:
    """获取工作流运行记录"""
    if workflow_name:
        result = run_gh_command(["run", "list", "--workflow", workflow_name, "--json", "name,status,conclusion,createdAt,number", "-L", "20"])
    else:
        result = run_gh_command(["run", "list", "--json", "name,status,conclusion,createdAt,number", "-L", "20"])

    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def list_issues(repo: str = "", state: str = "open") -> List[Dict[str, Any]]:
    """获取议题列表"""
    if repo:
        result = run_gh_command(["issue", "list", "--repo", repo, "--state", state, "--json", "number,title,body,labels,state,createdAt", "-L", "50"])
    else:
        result = run_gh_command(["issue", "list", "--state", state, "--json", "number,title,body,labels,state,createdAt", "-L", "50"])

    if result:
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
    return []


def create_issue(title: str, body: str = "", labels: List[str] = None) -> bool:
    """创建议题"""
    args = ["issue", "create", "--title", title]
    if body:
        args.extend(["--body", body])
    if labels:
        for label in labels:
            args.extend(["--label", label])

    result = run_gh_command(args, capture=False)
    return result is not None


def close_issue(issue_number: int) -> bool:
    """关闭议题"""
    result = run_gh_command(["issue", "close", str(issue_number)], capture=False)
    return result is not None


def reopen_issue(issue_number: int) -> bool:
    """重新打开议题"""
    result = run_gh_command(["issue", "reopen", str(issue_number)], capture=False)
    return result is not None


# ============================================================
# 主应用类
# ============================================================
class GitHubTUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(GITHUB_TUI_TITLE)
        self.geometry("1200x700")
        self.configure(bg=THEME["bg"])
        self.minsize(900, 500)

        # 状态变量
        self.current_view = tk.StringVar(value="dashboard")
        self.username = tk.StringVar(value="")
        self.authenticated = tk.BooleanVar(value=False)
        self.selected_repo = tk.StringVar(value="")
        self.selected_local_repo = tk.StringVar(value="")
        self.search_query = tk.StringVar(value="")
        self.issue_state = tk.StringVar(value="open")

        # 初始化认证
        self.check_auth()

        # 创建界面
        self.create_layout()

        # 绑定快捷键
        self.bind_shortcuts()

        # 刷新数据
        self.refresh_current_view()

    def check_auth(self):
        """检查认证状态"""
        auth_info = get_auth_status()
        self.authenticated.set(auth_info.get("authenticated", False))
        if self.authenticated.get():
            user = auth_info.get("user", {})
            self.username.set(user.get("login", ""))
        else:
            self.username.set("未登录")

    def create_layout(self):
        """创建界面布局"""
        # 顶部栏
        self.create_top_bar()

        # 主区域
        main_frame = tk.Frame(self, bg=THEME["bg"])
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 侧边栏
        self.create_sidebar(main_frame)

        # 内容区域
        self.create_content_area(main_frame)

        # 底部栏
        self.create_bottom_bar()

    def create_top_bar(self):
        """创建顶部栏"""
        top_bar = tk.Frame(self, bg=THEME["border"], height=40)
        top_bar.pack(side=tk.TOP, fill=tk.X)

        title_label = tk.Label(
            top_bar,
            text=" GitHub TUI ",
            bg=THEME["border"],
            fg=THEME["text_bright"],
            font=("Arial", 12, "bold")
        )
        title_label.pack(side=tk.LEFT, padx=10)

        self.auth_label = tk.Label(
            top_bar,
            text="",
            bg=THEME["border"],
            fg=THEME["text_dim"],
            font=("Arial", 10)
        )
        self.auth_label.pack(side=tk.LEFT, padx=20)

        self.repo_label = tk.Label(
            top_bar,
            text="",
            bg=THEME["border"],
            fg=THEME["text_dim"],
            font=("Arial", 10)
        )
        self.repo_label.pack(side=tk.RIGHT, padx=10)

    def create_sidebar(self, parent):
        """创建侧边栏"""
        sidebar = tk.Frame(parent, bg=THEME["bg"], width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 标题
        nav_label = tk.Label(
            sidebar,
            text=" 导航 ",
            bg=THEME["bg"],
            fg=THEME["text_dim"],
            font=("Arial", 10)
        )
        nav_label.pack(anchor="w", pady=(10, 5), padx=10)

        # 导航菜单
        nav_items = [
            ("仪表盘", "dashboard", "D"),
            ("远程仓库", "repos", "R"),
            ("本地仓库", "local", "L"),
            ("分支管理", "branches", "B"),
            ("工作流", "workflows", "W"),
            ("议题", "issues", "I"),
        ]

        self.nav_buttons = {}
        for text, view_key, key in nav_items:
            btn = tk.Button(
                sidebar,
                text=f"{text}  ({key})",
                bg=THEME["bg"],
                fg=THEME["fg"],
                font=("Arial", 10),
                anchor="w",
                padx=10,
                pady=8,
                bd=0,
                cursor="hand2",
                command=lambda v=view_key: self.navigate_to(v)
            )
            btn.pack(fill="x", padx=5, pady=2)
            self.nav_buttons[view_key] = btn

        # 分隔线
        sep = tk.Frame(sidebar, bg=THEME["border"], height=1)
        sep.pack(fill="x", padx=10, pady=15)

        # 操作提示
        help_label = tk.Label(
            sidebar,
            text=" 快捷键\n ──────\n q: 退出\n r: 刷新\n Esc: 返回",
            bg=THEME["bg"],
            fg=THEME["text_dim"],
            font=("Arial", 9),
            justify="left"
        )
        help_label.pack(anchor="w", padx=10)

    def create_content_area(self, parent):
        """创建内容区域"""
        self.content_frame = tk.Frame(parent, bg=THEME["bg"])
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 内容将动态加载
        self.load_content("dashboard")

    def create_bottom_bar(self):
        """创建底部栏"""
        bottom_bar = tk.Frame(self, bg=THEME["border"], height=30)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = tk.Label(
            bottom_bar,
            text="就绪",
            bg=THEME["border"],
            fg=THEME["text_dim"],
            font=("Arial", 9),
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.shortcut_label = tk.Label(
            bottom_bar,
            text="↑↓: 选择 | Enter: 确认 | q: 退出 | r: 刷新",
            bg=THEME["border"],
            fg=THEME["text_dim"],
            font=("Arial", 9)
        )
        self.shortcut_label.pack(side=tk.RIGHT, padx=10)

    def bind_shortcuts(self):
        """绑定快捷键"""
        self.bind("q", lambda e: self.quit_app())
        self.bind("<Control-c>", lambda e: self.quit_app())
        self.bind("<Escape>", lambda e: self.go_back())
        self.bind("r", lambda e: self.refresh_current_view())
        self.bind("D", lambda e: self.navigate_to("dashboard"))
        self.bind("R", lambda e: self.navigate_to("repos"))
        self.bind("L", lambda e: self.navigate_to("local"))
        self.bind("B", lambda e: self.navigate_to("branches"))
        self.bind("W", lambda e: self.navigate_to("workflows"))
        self.bind("I", lambda e: self.navigate_to("issues"))
        self.bind("<Up>", lambda e: self.select_prev())
        self.bind("k", lambda e: self.select_prev())
        self.bind("<Down>", lambda e: self.select_next())
        self.bind("j", lambda e: self.select_next())
        self.bind("<Return>", lambda e: self.confirm_selection())

    def navigate_to(self, view: str):
        """导航到指定视图"""
        self.current_view.set(view)
        # 更新侧边栏高亮
        for key, btn in self.nav_buttons.items():
            if key == view:
                btn.configure(bg=THEME["selected"], fg=THEME["text_bright"])
            else:
                btn.configure(bg=THEME["bg"], fg=THEME["fg"])
        self.load_content(view)

    def load_content(self, view: str):
        """加载内容"""
        # 清除现有内容
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if view == "dashboard":
            self.load_dashboard()
        elif view == "repos":
            self.load_repos()
        elif view == "local":
            self.load_local_repos()
        elif view == "branches":
            self.load_branches()
        elif view == "workflows":
            self.load_workflows()
        elif view == "issues":
            self.load_issues()

        self.update_top_bar()

    def update_top_bar(self):
        """更新顶部栏"""
        if self.authenticated.get():
            self.auth_label.config(text=f"✓ 已登录: {self.username.get()}")
        else:
            self.auth_label.config(text="✗ 未登录")

        if self.selected_repo.get():
            self.repo_label.config(text=f"仓库: {self.selected_repo.get()}")
        else:
            self.repo_label.config(text="")

    def load_dashboard(self):
        """加载仪表盘"""
        # 标题
        title = tk.Label(
            self.content_frame,
            text="仪表盘",
            bg=THEME["bg"],
            fg=THEME["text_bright"],
            font=("Arial", 18, "bold")
        )
        title.pack(anchor="w", padx=20, pady=(20, 10))

        # 信息卡片
        info_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        info_frame.pack(fill="both", expand=True, padx=20)

        # 认证状态卡片
        self.create_dashboard_card(info_frame, "认证状态",
                                  "✓ 已认证" if self.authenticated.get() else "✗ 未认证", 0, 0)

        # 用户名卡片
        self.create_dashboard_card(info_frame, "用户名",
                                  self.username.get() or "未登录", 0, 1)

        # 远程仓库数量
        repo_count = len(list_remote_repos())
        self.create_dashboard_card(info_frame, "远程仓库总数",
                                  str(repo_count), 1, 0)

        # 本地仓库数量
        local_count = len(get_local_repos())
        self.create_dashboard_card(info_frame, "本地仓库总数",
                                  str(local_count), 1, 1)

        # 快捷键说明
        help_frame = tk.LabelFrame(
            self.content_frame,
            text="快捷键",
            bg=THEME["bg"],
            fg=THEME["fg"],
            bd=1,
            relief="solid"
        )
        help_frame.pack(fill="x", padx=20, pady=20)

        shortcuts = [
            ("D", "仪表盘"), ("R", "远程仓库"), ("L", "本地仓库"),
            ("B", "分支管理"), ("W", "工作流"), ("I", "议题"),
            ("q", "退出"), ("r", "刷新"), ("Esc", "返回")
        ]

        for i, (key, desc) in enumerate(shortcuts):
            tk.Label(
                help_frame,
                text=f"{key}: {desc}",
                bg=THEME["bg"],
                fg=THEME["text_dim"],
                font=("Arial", 9)
            ).pack(anchor="w", padx=20, pady=2)

    def create_dashboard_card(self, parent, title: str, value: str, row: int, col: int):
        """创建仪表盘卡片"""
        card = tk.Frame(parent, bg=THEME["border"], bd=1, relief="solid")
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        tk.Label(
            card,
            text=title,
            bg=THEME["border"],
            fg=THEME["text_dim"],
            font=("Arial", 10)
        ).pack(padx=15, pady=(15, 5))

        tk.Label(
            card,
            text=value,
            bg=THEME["border"],
            fg=THEME["text_bright"],
            font=("Arial", 20, "bold")
        ).pack(padx=15, pady=(5, 15))

        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(col, weight=1)

    def load_repos(self):
        """加载远程仓库视图"""
        # 工具栏
        toolbar = tk.Frame(self.content_frame, bg=THEME["bg"])
        toolbar.pack(fill="x", padx=10, pady=5)

        tk.Label(toolbar, text="远程仓库", bg=THEME["bg"],
                fg=THEME["text_bright"], font=("Arial", 14, "bold")).pack(side="left")

        # 搜索框
        search_frame = tk.Frame(toolbar, bg=THEME["border"], bd=1)
        search_frame.pack(side="right", padx=5)
        tk.Label(search_frame, text="搜索:", bg=THEME["border"],
                fg=THEME["fg"]).pack(side="left", padx=5)
        self.repo_search = tk.Entry(search_frame, width=20, bg=THEME["bg"],
                                    fg=THEME["fg"], insertbackground=THEME["fg"],
                                    relief="flat", bd=0)
        self.repo_search.pack(side="left", padx=5)
        self.repo_search.bind("<KeyRelease>", lambda e: self.filter_repos())

        # 按钮
        tk.Button(toolbar, text="搜索", command=self.show_search_repos_dialog,
                 bg="#1f6feb", fg="white", relief="flat",
                 cursor="hand2").pack(side="left", padx=5)
        tk.Button(toolbar, text="刷新 (r)", command=self.load_repos,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)
        tk.Button(toolbar, text="新建 (n)", command=self.show_create_repo_dialog,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)

        # 仓库列表
        list_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 表头
        headers = ["名称", "所有者", "描述", "私有", "操作"]
        widths = [20, 12, 25, 6, 55]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 数据
        self.repo_list = list_remote_repos()
        self.repo_widgets = []

        for idx, repo in enumerate(self.repo_list):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            name = repo.get("name", "")
            owner = repo.get("owner", {}).get("login", "")
            desc = repo.get("description", "")[:50] or "-"
            is_private = "是" if repo.get("isPrivate") else "否"

            widgets = []
            for col, (text, w) in enumerate(zip([name, owner, desc, is_private], widths[:4])):
                lbl = tk.Label(list_frame, text=text, bg=bg, fg=THEME["fg"],
                              width=w, anchor="w", bd=1, relief="solid")
                lbl.grid(row=row, column=col, sticky="ew")
                widgets.append(lbl)

            # 操作按钮
            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=4, sticky="ew")

            info_btn = tk.Button(btn_frame, text="Info",
                                bg=THEME["text_dim"], fg="white", relief="flat",
                                cursor="hand2", command=lambda r=repo: self.show_repo_detail_dialog(r))
            info_btn.pack(side="left", padx=2, pady=2)

            clone_btn = tk.Button(btn_frame, text="Clone",
                                 bg=THEME["accent"], fg="white", relief="flat",
                                 cursor="hand2", command=lambda r=repo: self.clone_repo_dialog(r))
            clone_btn.pack(side="left", padx=2, pady=2)

            upload_btn = tk.Button(btn_frame, text="Upload",
                                  bg="#1f6feb", fg="white", relief="flat",
                                  cursor="hand2", command=lambda r=repo: self.upload_file_dialog(r))
            upload_btn.pack(side="left", padx=2, pady=2)

            files_btn = tk.Button(btn_frame, text="Files",
                                 bg="#8957e5", fg="white", relief="flat",
                                 cursor="hand2", command=lambda r=repo: self.show_repo_files(r))
            files_btn.pack(side="left", padx=2, pady=2)

            fork_btn = tk.Button(btn_frame, text="Fork",
                                bg=THEME["warning"], fg="white", relief="flat",
                                cursor="hand2", command=lambda r=repo: self.fork_repo_action(
                                    r.get("owner", {}).get("login", ""), r.get("name", "")))
            fork_btn.pack(side="left", padx=2, pady=2)

            delete_btn = tk.Button(btn_frame, text="Delete",
                                  bg=THEME["error"], fg="white", relief="flat",
                                  cursor="hand2", command=lambda r=repo: self.delete_repo_dialog(r))
            delete_btn.pack(side="left", padx=2, pady=2)

            widgets.append(btn_frame)
            self.repo_widgets.append(widgets)

    def filter_repos(self):
        """过滤仓库列表"""
        query = self.repo_search.get().lower()
        for idx, widgets in enumerate(self.repo_widgets):
            repo = self.repo_list[idx]
            name = repo.get("name", "").lower()
            visible = query in name if query else True

            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]
            for w in widgets[:-1]:  # 不包括按钮frame
                w.grid_remove() if not visible else w.grid()
                w.configure(bg=bg if visible else THEME["bg"])

    def load_local_repos(self):
        """加载本地仓库视图"""
        # 工具栏
        toolbar = tk.Frame(self.content_frame, bg=THEME["bg"])
        toolbar.pack(fill="x", padx=10, pady=5)

        tk.Label(toolbar, text="本地仓库", bg=THEME["bg"],
                fg=THEME["text_bright"], font=("Arial", 14, "bold")).pack(side="left")

        tk.Button(toolbar, text="刷新 (r)", command=self.load_local_repos,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)

        # 仓库列表
        list_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 表头
        headers = ["仓库名", "当前分支", "状态", "操作"]
        widths = [25, 15, 15, 40]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 数据
        repos = get_local_repos()

        for idx, repo in enumerate(repos):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            branch = get_git_branch(repo)
            status_info = get_git_status(repo)
            status = f"{len(status_info['files'])} 个文件更改" if status_info["has_changes"] else "无更改"

            for col, (text, w) in enumerate(zip([repo, branch, status], widths[:3])):
                tk.Label(list_frame, text=text, bg=bg, fg=THEME["fg"],
                        width=w, anchor="w", bd=1, relief="solid").grid(row=row, column=col, sticky="ew")

            # 操作按钮
            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=3, sticky="ew")

            tk.Button(btn_frame, text="Commit",
                     bg=THEME["accent"], fg="white", relief="flat",
                     cursor="hand2", command=lambda r=repo: self.show_commit_dialog(r)).pack(side="left", padx=2, pady=2)

            tk.Button(btn_frame, text="Pull",
                     bg="#1f6feb", fg="white", relief="flat",
                     cursor="hand2", command=lambda r=repo: self.pull_repo(r)).pack(side="left", padx=2, pady=2)

            tk.Button(btn_frame, text="Push",
                     bg=THEME["accent"], fg="white", relief="flat",
                     cursor="hand2", command=lambda r=repo: self.push_repo(r)).pack(side="left", padx=2, pady=2)

            tk.Button(btn_frame, text="Branch",
                     bg="#8957e5", fg="white", relief="flat",
                     cursor="hand2", command=lambda r=repo: self.show_branch_dialog(r)).pack(side="left", padx=2, pady=2)

            tk.Button(btn_frame, text="Log",
                     bg=THEME["text_dim"], fg="white", relief="flat",
                     cursor="hand2", command=lambda r=repo: self.show_git_log(r)).pack(side="left", padx=2, pady=2)

        if not repos:
            tk.Label(list_frame, text="暂无本地仓库，请先克隆远程仓库",
                    bg=THEME["bg"], fg=THEME["text_dim"],
                    font=("Arial", 11)).grid(row=1, column=0, columnspan=4, pady=20)

    def load_branches(self):
        """加载分支管理视图"""
        # 工具栏
        toolbar = tk.Frame(self.content_frame, bg=THEME["bg"])
        toolbar.pack(fill="x", padx=10, pady=5)

        tk.Label(toolbar, text="分支管理", bg=THEME["bg"],
                fg=THEME["text_bright"], font=("Arial", 14, "bold")).pack(side="left")

        # 仓库选择
        tk.Label(toolbar, text="仓库:", bg=THEME["bg"], fg=THEME["fg"]).pack(side="left", padx=(10, 5))
        repos = get_local_repos()
        self.branch_repo_var = tk.StringVar()
        if repos:
            self.branch_repo_var.set(repos[0])
        repo_combo = ttk.Combobox(toolbar, textvariable=self.branch_repo_var,
                                  values=repos, state="readonly", width=20)
        repo_combo.pack(side="left", padx=5)
        repo_combo.bind("<<ComboboxSelected>>", lambda e: self.load_branches())

        tk.Button(toolbar, text="刷新 (r)", command=self.load_branches,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)
        tk.Button(toolbar, text="新建 (n)", command=self.show_create_branch_dialog,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)

        # 分支列表
        list_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 表头
        headers = ["分支名", "上游", "SHA", "操作"]
        widths = [25, 20, 12, 35]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 数据
        repo = self.branch_repo_var.get()
        branches = get_git_branches(repo) if repo else []
        current_branch = get_git_branch(repo) if repo else ""

        for idx, branch in enumerate(branches):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            name = branch.get("name", "")
            upstream = branch.get("upstream", "-") or "-"
            sha = branch.get("sha", "")[:7]

            for col, (text, w) in enumerate(zip([name, upstream, sha], widths[:3])):
                tk.Label(list_frame, text=text, bg=bg, fg=THEME["fg"],
                        width=w, anchor="w", bd=1, relief="solid").grid(row=row, column=col, sticky="ew")

            # 操作按钮
            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=3, sticky="ew")

            if name != current_branch:
                tk.Button(btn_frame, text="切换",
                         bg=THEME["accent"], fg="white", relief="flat",
                         cursor="hand2", command=lambda r=repo, b=name: self.switch_branch(r, b)).pack(side="left", padx=2, pady=2)

                tk.Button(btn_frame, text="删除",
                         bg=THEME["error"], fg="white", relief="flat",
                         cursor="hand2", command=lambda r=repo, b=name: self.delete_branch(r, b)).pack(side="left", padx=2, pady=2)

        if not branches:
            tk.Label(list_frame, text="请先选择本地仓库",
                    bg=THEME["bg"], fg=THEME["text_dim"],
                    font=("Arial", 11)).grid(row=1, column=0, columnspan=4, pady=20)

    def load_workflows(self):
        """加载工作流视图"""
        # 工具栏
        toolbar = tk.Frame(self.content_frame, bg=THEME["bg"])
        toolbar.pack(fill="x", padx=10, pady=5)

        tk.Label(toolbar, text="工作流", bg=THEME["bg"],
                fg=THEME["text_bright"], font=("Arial", 14, "bold")).pack(side="left")

        tk.Button(toolbar, text="刷新 (r)", command=self.load_workflows,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)
        tk.Button(toolbar, text="运行 (n)", command=self.show_run_workflow_dialog,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)

        # 工作流列表
        list_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 表头
        headers = ["工作流名称", "最近运行状态", "运行时间", "操作"]
        widths = [25, 15, 20, 30]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 获取所有本地仓库的工作流
        repos = get_local_repos()
        all_workflows = []
        for repo in repos:
            repo_path = os.path.join(LOCAL_REPO_DIR, repo)
            workflows = list_workflows(repo_path)
            for wf in workflows:
                wf["repo"] = repo
                all_workflows.append(wf)

        for idx, wf in enumerate(all_workflows):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            name = wf.get("name", "")
            runs = get_workflow_runs(wf.get("repo", ""), name)
            status = runs[0].get("conclusion", "无") if runs else "无"
            created = runs[0].get("createdAt", "")[:19] if runs else "-"

            for col, (text, w) in enumerate(zip([name, status, created], widths[:3])):
                tk.Label(list_frame, text=text, bg=bg, fg=THEME["fg"],
                        width=w, anchor="w", bd=1, relief="solid").grid(row=row, column=col, sticky="ew")

            # 操作按钮
            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=3, sticky="ew")

            tk.Button(btn_frame, text="运行",
                     bg=THEME["accent"], fg="white", relief="flat",
                     cursor="hand2", command=lambda r=wf.get("repo", ""), w=name: self.run_workflow(r, w)).pack(side="left", padx=2, pady=2)

        if not all_workflows:
            tk.Label(list_frame, text="暂无工作流，请在 .github/workflows/ 目录下创建",
                    bg=THEME["bg"], fg=THEME["text_dim"],
                    font=("Arial", 11)).grid(row=1, column=0, columnspan=4, pady=20)

    def load_issues(self):
        """加载议题视图"""
        # 工具栏
        toolbar = tk.Frame(self.content_frame, bg=THEME["bg"])
        toolbar.pack(fill="x", padx=10, pady=5)

        tk.Label(toolbar, text="议题", bg=THEME["bg"],
                fg=THEME["text_bright"], font=("Arial", 14, "bold")).pack(side="left")

        # 状态筛选
        tk.Label(toolbar, text="状态:", bg=THEME["bg"], fg=THEME["fg"]).pack(side="left", padx=(10, 5))
        state_combo = ttk.Combobox(toolbar, textvariable=self.issue_state,
                                   values=["open", "closed", "all"],
                                   state="readonly", width=10)
        state_combo.pack(side="left", padx=5)
        state_combo.bind("<<ComboboxSelected>>", lambda e: self.load_issues())

        tk.Button(toolbar, text="刷新 (r)", command=self.load_issues,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)
        tk.Button(toolbar, text="新建 (n)", command=self.show_create_issue_dialog,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right", padx=5)

        # 议题列表
        list_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 表头
        headers = ["编号", "标题", "状态", "标签", "创建时间", "操作"]
        widths = [8, 35, 10, 20, 18, 20]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 数据
        issues = list_issues(state=self.issue_state.get())

        for idx, issue in enumerate(issues):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            number = issue.get("number", "")
            title = issue.get("title", "")[:40] or "-"
            state = issue.get("state", "")
            labels = ", ".join([l.get("name", "") for l in issue.get("labels", [])[:3]]) or "-"
            created = issue.get("createdAt", "")[:10] if issue.get("createdAt") else "-"

            for col, (text, w) in enumerate(zip([number, title, state, labels, created], widths[:5])):
                tk.Label(list_frame, text=str(text), bg=bg, fg=THEME["fg"],
                        width=w, anchor="w", bd=1, relief="solid").grid(row=row, column=col, sticky="ew")

            # 操作按钮
            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=5, sticky="ew")

            if state == "open":
                tk.Button(btn_frame, text="关闭",
                         bg=THEME["warning"], fg="white", relief="flat",
                         cursor="hand2", command=lambda n=number: self.close_issue(n)).pack(side="left", padx=2, pady=2)
            else:
                tk.Button(btn_frame, text="打开",
                         bg=THEME["accent"], fg="white", relief="flat",
                         cursor="hand2", command=lambda n=number: self.reopen_issue(n)).pack(side="left", padx=2, pady=2)

            tk.Button(btn_frame, text="详情",
                     bg="#1f6feb", fg="white", relief="flat",
                     cursor="hand2", command=lambda i=issue: self.show_issue_detail(i)).pack(side="left", padx=2, pady=2)

        if not issues:
            tk.Label(list_frame, text="暂无议题",
                    bg=THEME["bg"], fg=THEME["text_dim"],
                    font=("Arial", 11)).grid(row=1, column=0, columnspan=6, pady=20)

    # ============================================================
    # 对话框方法
    # ============================================================

    def show_search_repos_dialog(self):
        """搜索仓库对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("搜索仓库")
        dialog.geometry("500x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="搜索 GitHub 仓库",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(dialog, text="搜索关键词:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        search_var = tk.StringVar()
        search_entry = tk.Entry(dialog, textvariable=search_var, width=40,
                               bg=THEME["border"], fg=THEME["fg"])
        search_entry.pack(pady=5)
        search_entry.focus()

        # 结果列表
        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.search_results = tk.Listbox(list_frame, bg=THEME["bg"], fg=THEME["fg"],
                                          yscrollcommand=scrollbar.set, selectbackground=THEME["selected"])
        self.search_results.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.search_results.yview)

        self.search_data = []

        def do_search():
            query = search_var.get().strip()
            if not query:
                return

            self.search_results.delete(0, tk.END)
            self.search_data = search_repos(query)

            for r in self.search_data:
                name = r.get("name", "")
                owner = r.get("owner", {}).get("login", "")
                desc = r.get("description", "")[:40] or ""
                self.search_results.insert(tk.END, f"{owner}/{name} - {desc}")

        def on_double_click(e):
            sel = self.search_results.curselection()
            if sel:
                idx = sel[0]
                if idx < len(self.search_data):
                    repo = self.search_data[idx]
                    dialog.destroy()
                    self.show_repo_detail_dialog(repo)

        self.search_results.bind("<Double-Button-1>", on_double_click)

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="搜索", command=do_search,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

        search_entry.bind("<Return>", lambda e: do_search())

    def show_repo_detail_dialog(self, repo: Dict):
        """显示仓库详情对话框"""
        repo_name = repo.get("name", "")
        owner = repo.get("owner", {}).get("login", "")

        details = get_repo_details(owner, repo_name)

        dialog = tk.Toplevel(self)
        dialog.title(f"仓库详情 - {owner}/{repo_name}")
        dialog.geometry("500x450")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"{owner}/{repo_name}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 16, "bold")).pack(pady=10)

        if details:
            info_text = f"""描述: {details.get('description', '无') or '无'}
默认分支: {details.get('default_branch', 'unknown')}
语言: {details.get('language', '未知')}
星标: {details.get('stargazers', 0)}
Fork: {details.get('forks', 0)}
开放议题: {details.get('open_issues', 0)}
创建时间: {details.get('created', '')[:10]}
最后更新: {details.get('updated', '')[:10]}
URL: {details.get('url', '')}"""
        else:
            info_text = "无法获取仓库详情"

        info_label = tk.Label(dialog, text=info_text, bg=THEME["bg"],
                             fg=THEME["fg"], justify="left", anchor="nw",
                             font=("Arial", 10))
        info_label.pack(fill="both", expand=True, padx=20, pady=10)

        # 操作按钮
        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="Fork", command=lambda: self.fork_repo_action(owner, repo_name),
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Star", command=lambda: self.star_repo_action(owner, repo_name),
                 bg=THEME["warning"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="提交记录", command=lambda: self.show_commits_dialog(owner, repo_name),
                 bg="#1f6feb", fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="PR 列表", command=lambda: self.show_prs_dialog(owner, repo_name),
                 bg="#8957e5", fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def fork_repo_action(self, owner: str, repo: str):
        """Fork 仓库"""
        self.status_label.config(text=f"Forking {owner}/{repo}...")
        self.update()
        if fork_repo(owner, repo):
            self.status_label.config(text=f"已 Fork {owner}/{repo}")
            messagebox.showinfo("成功", f"已成功 Fork {owner}/{repo}")
        else:
            self.status_label.config(text="Fork 失败")
            messagebox.showerror("错误", "Fork 失败，可能已 Fork 或无权限")

    def star_repo_action(self, owner: str, repo: str):
        """Star 仓库"""
        if star_repo(owner, repo):
            self.status_label.config(text=f"已 Star {owner}/{repo}")
            messagebox.showinfo("成功", f"已 Star {owner}/{repo}")
        else:
            self.status_label.config(text="Star 失败")
            messagebox.showerror("错误", "Star 失败")

    def show_commits_dialog(self, owner: str, repo: str):
        """显示提交记录"""
        dialog = tk.Toplevel(self)
        dialog.title(f"提交记录 - {owner}/{repo}")
        dialog.geometry("650x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"提交记录: {owner}/{repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        headers = ["SHA", "信息", "作者", "日期"]
        widths = [10, 40, 15, 18]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        commits = list_commits(owner, repo)
        for idx, c in enumerate(commits):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            sha = c.get("sha", "")[:7]
            msg = c.get("message", "")[:50] or "-"
            author = c.get("author", "")[:15]
            date = c.get("date", "")[:19]

            tk.Label(list_frame, text=sha, bg=bg, fg=THEME["accent"],
                    width=widths[0], anchor="w", bd=1, relief="solid").grid(row=row, column=0, sticky="ew")
            tk.Label(list_frame, text=msg, bg=bg, fg=THEME["fg"],
                    width=widths[1], anchor="w", bd=1, relief="solid").grid(row=row, column=1, sticky="ew")
            tk.Label(list_frame, text=author, bg=bg, fg=THEME["fg"],
                    width=widths[2], anchor="w", bd=1, relief="solid").grid(row=row, column=2, sticky="ew")
            tk.Label(list_frame, text=date, bg=bg, fg=THEME["fg"],
                    width=widths[3], anchor="w", bd=1, relief="solid").grid(row=row, column=3, sticky="ew")

        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(pady=10)

    def show_prs_dialog(self, owner: str, repo: str):
        """显示 PR 列表"""
        dialog = tk.Toplevel(self)
        dialog.title(f"Pull Requests - {owner}/{repo}")
        dialog.geometry("600x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"Pull Requests: {owner}/{repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 状态筛选
        state_frame = tk.Frame(dialog, bg=THEME["bg"])
        state_frame.pack(fill="x", padx=20)
        tk.Label(state_frame, text="状态:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(side="left")
        pr_state = tk.StringVar(value="open")
        ttk.Combobox(state_frame, textvariable=pr_state, values=["open", "closed", "all"],
                    state="readonly", width=10).pack(side="left", padx=5)

        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        headers = ["#", "标题", "状态", "作者", "创建时间"]
        widths = [6, 35, 10, 15, 18]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        def load_prs():
            for widget in list_frame.winfo_children():
                if int(widget.grid_info().get("row", 0)) > 0:
                    widget.destroy()

            prs = list_pull_requests(owner, repo, pr_state.get())
            for idx, pr in enumerate(prs):
                row = idx + 1
                bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

                num = pr.get("number", "")
                title = pr.get("title", "")[:40] or "-"
                state = pr.get("state", "")
                author = pr.get("author", {}).get("login", "")[:15] if isinstance(pr.get("author"), dict) else str(pr.get("author", ""))[:15]
                created = pr.get("createdAt", "")[:10]

                tk.Label(list_frame, text=str(num), bg=bg, fg=THEME["fg"],
                        width=widths[0], anchor="w", bd=1, relief="solid").grid(row=row, column=0, sticky="ew")
                tk.Label(list_frame, text=title, bg=bg, fg=THEME["fg"],
                        width=widths[1], anchor="w", bd=1, relief="solid").grid(row=row, column=1, sticky="ew")
                tk.Label(list_frame, text=state, bg=bg, fg=THEME["fg"],
                        width=widths[2], anchor="w", bd=1, relief="solid").grid(row=row, column=2, sticky="ew")
                tk.Label(list_frame, text=author, bg=bg, fg=THEME["fg"],
                        width=widths[3], anchor="w", bd=1, relief="solid").grid(row=row, column=3, sticky="ew")
                tk.Label(list_frame, text=created, bg=bg, fg=THEME["fg"],
                        width=widths[4], anchor="w", bd=1, relief="solid").grid(row=row, column=4, sticky="ew")

        tk.Button(state_frame, text="刷新", command=load_prs,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="right")
        tk.Button(dialog, text="新建 PR", command=lambda: self.show_create_pr_dialog(owner, repo),
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(pady=10)
        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(pady=5)

        load_prs()

    def show_create_pr_dialog(self, owner: str, repo: str):
        """创建 PR 对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("创建 Pull Request")
        dialog.geometry("450x300")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"创建 PR - {owner}/{repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(dialog, text="标题:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        title_var = tk.StringVar()
        tk.Entry(dialog, textvariable=title_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        tk.Label(dialog, text="描述:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        body_var = tk.StringVar()
        tk.Entry(dialog, textvariable=body_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        tk.Label(dialog, text="源分支:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        head_var = tk.StringVar()
        tk.Entry(dialog, textvariable=head_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        tk.Label(dialog, text="目标分支 (默认 main):", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        base_var = tk.StringVar(value="main")
        tk.Entry(dialog, textvariable=base_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_create():
            if not title_var.get().strip():
                messagebox.showerror("错误", "请输入标题")
                return
            if not head_var.get().strip():
                messagebox.showerror("错误", "请输入源分支")
                return

            if create_pull_request(owner, repo, title_var.get(), body_var.get(),
                                 head_var.get(), base_var.get()):
                self.status_label.config(text="PR 创建成功")
                messagebox.showinfo("成功", "Pull Request 创建成功")
                dialog.destroy()
            else:
                self.status_label.config(text="PR 创建失败")
                messagebox.showerror("错误", "创建 PR 失败")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="创建", command=do_create,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def clone_repo_dialog(self, repo: Dict):
        """克隆仓库对话框"""
        owner = repo.get("owner", {}).get("login", "")
        repo_name = repo.get("name", "")
        full_name = f"{owner}/{repo_name}"
        dialog = tk.Toplevel(self)
        dialog.title("克隆仓库")
        dialog.geometry("400x200")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"克隆仓库: {full_name}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 11)).pack(pady=10)

        tk.Label(dialog, text="目标路径:", bg=THEME["bg"],
                fg=THEME["fg"]).pack()
        path_var = tk.StringVar(value=LOCAL_REPO_DIR)
        tk.Entry(dialog, textvariable=path_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_clone():
            path = path_var.get()
            os.makedirs(path, exist_ok=True)
            self.status_label.config(text=f"正在克隆 {full_name}...")
            dialog.update()

            if clone_repo(full_name, path):
                self.status_label.config(text=f"成功克隆仓库: {full_name}")
                messagebox.showinfo("成功", f"仓库 {full_name} 已克隆到 {path}")
            else:
                target_path = os.path.join(path, full_name.split("/")[-1])
                if os.path.exists(target_path) and os.listdir(target_path):
                    self.status_label.config(text=f"克隆失败：目标目录已存在")
                    messagebox.showerror("错误", f"目标目录 {target_path} 已存在且不为空，请先删除或移动")
                else:
                    self.status_label.config(text=f"克隆失败")
                    messagebox.showerror("错误", "克隆仓库失败，请检查网络和仓库地址")

            dialog.destroy()
            self.load_repos()

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="克隆", command=do_clone,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def delete_repo_dialog(self, repo: Dict):
        """删除仓库对话框"""
        repo_name = repo.get("name", "")
        owner = repo.get("owner", {}).get("login", "")

        dialog = tk.Toplevel(self)
        dialog.title("删除仓库")
        dialog.geometry("450x220")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="⚠️ 警告：此操作不可撤销！",
                bg=THEME["bg"], fg=THEME["error"],
                font=("Arial", 12, "bold")).pack(pady=10)

        tk.Label(dialog, text=f"确定要删除仓库 {owner}/{repo_name} 吗？",
                bg=THEME["bg"], fg=THEME["fg"]).pack()
        tk.Label(dialog, text="请输入仓库名称以确认:",
                bg=THEME["bg"], fg=THEME["fg"]).pack(pady=(10, 5))

        confirm_var = tk.StringVar()
        tk.Entry(dialog, textvariable=confirm_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_delete():
            if confirm_var.get() == repo_name:
                self.status_label.config(text=f"正在删除 {repo_name}...")
                dialog.update()

                if delete_repo(owner, repo_name):
                    self.status_label.config(text=f"已删除仓库: {repo_name}")
                    messagebox.showinfo("成功", f"仓库 {repo_name} 已删除")
                else:
                    self.status_label.config(text=f"删除失败")
                    messagebox.showerror("错误", "删除仓库失败")

                dialog.destroy()
                self.load_repos()
            else:
                messagebox.showerror("错误", "仓库名称不匹配")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="删除", command=do_delete,
                 bg=THEME["error"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def upload_file_dialog(self, repo: Dict):
        """上传文件到仓库对话框"""
        repo_name = repo.get("name", "")
        owner = repo.get("owner", {}).get("login", "")

        dialog = tk.Toplevel(self)
        dialog.title(f"上传文件 - {owner}/{repo_name}")
        dialog.geometry("450x380")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"上传文件到 {owner}/{repo_name}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 选择文件
        tk.Label(dialog, text="选择本地文件:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        file_path_var = tk.StringVar()
        tk.Entry(dialog, textvariable=file_path_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)
        tk.Button(dialog, text="浏览...", command=lambda: file_path_var.set(
            filedialog.askopenfilename() or file_path_var.get()),
                 bg=THEME["border"], fg=THEME["fg"], relief="flat").pack()

        # 仓库内路径
        tk.Label(dialog, text="仓库内路径 (如: folder/file.txt):", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        dest_var = tk.StringVar()
        tk.Entry(dialog, textvariable=dest_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        # 提交信息
        tk.Label(dialog, text="提交信息:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        msg_var = tk.StringVar(value="Upload file")
        tk.Entry(dialog, textvariable=msg_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_upload():
            local_path = file_path_var.get().strip()
            dest_path = dest_var.get().strip()

            if not local_path or not os.path.exists(local_path):
                messagebox.showerror("错误", "请选择有效的本地文件")
                return

            if not dest_path:
                messagebox.showerror("错误", "请输入仓库内路径")
                return

            try:
                with open(local_path, "rb") as f:
                    content = f.read()

                self.status_label.config(text=f"正在上传文件...")
                dialog.update()

                if upload_file(owner, repo_name, dest_path, content, msg_var.get()):
                    self.status_label.config(text="上传成功")
                    messagebox.showinfo("成功", "文件上传成功")
                else:
                    self.status_label.config(text="上传失败")
                    messagebox.showerror("错误", "文件上传失败")

                dialog.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败: {e}")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="上传", command=do_upload,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def show_repo_files(self, repo: Dict):
        """显示仓库文件列表"""
        repo_name = repo.get("name", "")
        owner = repo.get("owner", {}).get("login", "")

        dialog = tk.Toplevel(self)
        dialog.title(f"仓库文件 - {owner}/{repo_name}")
        dialog.geometry("600x450")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"仓库文件: {owner}/{repo_name}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 使用 Canvas + Scrollbar 实现可滚动列表
        canvas = tk.Canvas(dialog, bg=THEME["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        list_frame = tk.Frame(canvas, bg=THEME["bg"])

        list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 打包
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=10)

        # 表头
        headers = ["名称", "类型", "大小", "操作"]
        widths = [25, 10, 10, 20]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        # 获取文件列表
        files = list_repo_files(owner, repo_name)

        if not files:
            tk.Label(list_frame, text="仓库为空或无法访问",
                    bg=THEME["bg"], fg=THEME["text_dim"]).grid(row=1, column=0, columnspan=4, pady=20)
        else:
            for idx, f in enumerate(files):
                row = idx + 1
                bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

                name = f.get("name", "")
                ftype = f.get("type", "")
                size = f"{f.get('size', 0)}" if ftype == "file" else "-"

                tk.Label(list_frame, text=name, bg=bg, fg=THEME["fg"],
                        width=widths[0], anchor="w", bd=1, relief="solid").grid(row=row, column=0, sticky="ew")
                tk.Label(list_frame, text=ftype, bg=bg, fg=THEME["fg"],
                        width=widths[1], anchor="w", bd=1, relief="solid").grid(row=row, column=1, sticky="ew")
                tk.Label(list_frame, text=size, bg=bg, fg=THEME["fg"],
                        width=widths[2], anchor="w", bd=1, relief="solid").grid(row=row, column=2, sticky="ew")

                btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
                btn_frame.grid(row=row, column=3, sticky="ew")

                if ftype == "file":
                    tk.Button(btn_frame, text="删除",
                             bg=THEME["error"], fg="white", relief="flat",
                             cursor="hand2", command=lambda n=name: self.delete_file_dialog(owner, repo_name, n, dialog)
                             ).pack(side="left", padx=2, pady=2)

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="刷新", command=lambda: self.refresh_repo_files(dialog, owner, repo_name, canvas, scrollbar),
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(side="left", padx=5)

    def refresh_repo_files(self, dialog, owner: str, repo_name: str, canvas, scrollbar):
        """刷新仓库文件列表"""
        # 销毁旧列表帧
        for widget in dialog.winfo_children():
            if isinstance(widget, tk.Canvas):
                widget.destroy()
            elif isinstance(widget, tk.Scrollbar):
                widget.destroy()

        # 重新创建 Canvas + Scrollbar
        canvas = tk.Canvas(dialog, bg=THEME["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        list_frame = tk.Frame(canvas, bg=THEME["bg"])

        list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=10)

        headers = ["名称", "类型", "大小", "操作"]
        widths = [25, 10, 10, 20]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        files = list_repo_files(owner, repo_name)

        for idx, f in enumerate(files):
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]

            name = f.get("name", "")
            ftype = f.get("type", "")
            size = f"{f.get('size', 0)}" if ftype == "file" else "-"

            tk.Label(list_frame, text=name, bg=bg, fg=THEME["fg"],
                    width=widths[0], anchor="w", bd=1, relief="solid").grid(row=row, column=0, sticky="ew")
            tk.Label(list_frame, text=ftype, bg=bg, fg=THEME["fg"],
                    width=widths[1], anchor="w", bd=1, relief="solid").grid(row=row, column=1, sticky="ew")
            tk.Label(list_frame, text=size, bg=bg, fg=THEME["fg"],
                    width=widths[2], anchor="w", bd=1, relief="solid").grid(row=row, column=2, sticky="ew")

            btn_frame = tk.Frame(list_frame, bg=bg, bd=1, relief="solid")
            btn_frame.grid(row=row, column=3, sticky="ew")

            if ftype == "file":
                tk.Button(btn_frame, text="删除",
                         bg=THEME["error"], fg="white", relief="flat",
                         cursor="hand2", command=lambda n=name: self.delete_file_dialog(owner, repo_name, n, dialog)
                         ).pack(side="left", padx=2, pady=2)

    def delete_file_dialog(self, owner: str, repo: str, file_path: str, parent_dialog):
        """删除仓库文件对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("删除文件")
        dialog.geometry("400x180")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="⚠️ 警告：此操作不可撤销！",
                bg=THEME["bg"], fg=THEME["error"],
                font=("Arial", 11, "bold")).pack(pady=10)

        tk.Label(dialog, text=f"确定要删除文件 {file_path} 吗？",
                bg=THEME["bg"], fg=THEME["fg"]).pack()

        tk.Label(dialog, text="提交信息:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(pady=(10, 0))
        msg_var = tk.StringVar(value="Delete file")
        tk.Entry(dialog, textvariable=msg_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_delete():
            if delete_file(owner, repo, file_path, msg_var.get()):
                self.status_label.config(text="文件已删除")
                messagebox.showinfo("成功", "文件删除成功")
                dialog.destroy()
                parent_dialog.destroy()
                self.show_repo_files({"name": repo, "owner": {"login": owner}})
            else:
                self.status_label.config(text="删除失败")
                messagebox.showerror("错误", "删除文件失败")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="删除", command=do_delete,
                 bg=THEME["error"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def show_create_repo_dialog(self):
        """创建仓库对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("创建新仓库")
        dialog.geometry("400x350")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="创建新仓库",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 仓库名称
        tk.Label(dialog, text="仓库名称 *:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=40, pady=(10, 0))
        name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=name_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        # 描述
        tk.Label(dialog, text="描述:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=40, pady=(10, 0))
        desc_var = tk.StringVar()
        tk.Entry(dialog, textvariable=desc_var, width=40,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        # 私有
        private_var = tk.BooleanVar()
        tk.Checkbutton(dialog, text="私有仓库", variable=private_var,
                      bg=THEME["bg"], fg=THEME["fg"],
                      selectcolor=THEME["border"]).pack(anchor="w", padx=40, pady=5)

        # 初始化README
        readme_var = tk.BooleanVar()
        tk.Checkbutton(dialog, text="初始化 README", variable=readme_var,
                      bg=THEME["bg"], fg=THEME["fg"],
                      selectcolor=THEME["border"]).pack(anchor="w", padx=40, pady=5)

        # 添加.gitignore
        gitignore_var = tk.BooleanVar()
        tk.Checkbutton(dialog, text="添加 .gitignore (Python)", variable=gitignore_var,
                      bg=THEME["bg"], fg=THEME["fg"],
                      selectcolor=THEME["border"]).pack(anchor="w", padx=40, pady=5)

        def do_create():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("错误", "请输入仓库名称")
                return

            self.status_label.config(text=f"正在创建仓库 {name}...")
            dialog.update()

            if create_repo(name, desc_var.get(), private_var.get(),
                          readme_var.get(), gitignore_var.get()):
                self.status_label.config(text=f"已创建仓库: {name}")
                messagebox.showinfo("成功", f"仓库 {name} 创建成功")
                dialog.destroy()
                self.load_repos()
            else:
                self.status_label.config(text="创建失败")
                messagebox.showerror("错误", "创建仓库失败")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="创建", command=do_create,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def show_commit_dialog(self, repo: str):
        """提交更改对话框"""
        dialog = tk.Toplevel(self)
        dialog.title(f"提交更改 - {repo}")
        dialog.geometry("500x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        status_info = get_git_status(repo)
        files = status_info.get("files", [])

        tk.Label(dialog, text=f"提交更改 - {repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 文件列表
        tk.Label(dialog, text="选择要提交的文件:",
                bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w", padx=20, pady=(10, 5))

        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        file_vars = []
        for f in files:
            var = tk.BooleanVar()
            cb = tk.Checkbutton(list_frame, text=f[3:] if len(f) > 3 else f,
                              variable=var, bg=THEME["border"],
                              fg=THEME["fg"], selectcolor=THEME["selected"],
                              anchor="w")
            cb.pack(anchor="w", padx=10)
            file_vars.append((var, f[3:] if len(f) > 3 else f))

        scrollbar.config(command=lambda *args: None)

        # 提交信息
        tk.Label(dialog, text="提交信息:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=20, pady=(10, 5))
        msg_var = tk.StringVar()
        tk.Entry(dialog, textvariable=msg_var, width=50,
                bg=THEME["border"], fg=THEME["fg"]).pack(padx=20, pady=5)

        # 立即推送
        push_var = tk.BooleanVar()
        tk.Checkbutton(dialog, text="立即推送到远程", variable=push_var,
                      bg=THEME["bg"], fg=THEME["fg"],
                      selectcolor=THEME["border"]).pack(anchor="w", padx=20, pady=5)

        def do_commit():
            selected = [f for var, f in file_vars if var.get()]
            if not selected:
                messagebox.showerror("错误", "请选择要提交的文件")
                return

            message = msg_var.get().strip()
            if not message:
                messagebox.showerror("错误", "请输入提交信息")
                return

            self.status_label.config(text=f"正在提交 {repo}...")
            dialog.update()

            success, err_msg = git_commit(repo, message, selected)
            if success:
                if push_var.get():
                    if git_push(repo):
                        self.status_label.config(text="提交并推送成功")
                        messagebox.showinfo("成功", "更改已提交并推送")
                    else:
                        self.status_label.config(text="提交成功但推送失败")
                        messagebox.showwarning("警告", "提交成功但推送失败")
                else:
                    self.status_label.config(text="提交成功")
                    messagebox.showinfo("成功", "更改已提交（未推送）")
                dialog.destroy()
                self.load_local_repos()
            else:
                self.status_label.config(text="提交失败")
                messagebox.showerror("错误", f"提交失败\n\n{err_msg}")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="提交", command=do_commit,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def pull_repo(self, repo: str):
        """拉取仓库更新"""
        self.status_label.config(text=f"正在拉取 {repo}...")
        self.update()

        if git_pull(repo):
            self.status_label.config(text=f"拉取成功: {repo}")
            messagebox.showinfo("成功", f"仓库 {repo} 已更新")
        else:
            self.status_label.config(text=f"拉取失败: {repo}")
            messagebox.showerror("错误", f"拉取 {repo} 失败，可能有冲突")

        self.load_local_repos()

    def push_repo(self, repo: str):
        """推送仓库更新"""
        self.status_label.config(text=f"正在推送 {repo}...")
        self.update()

        if git_push(repo):
            self.status_label.config(text=f"推送成功: {repo}")
            messagebox.showinfo("成功", f"仓库 {repo} 已推送")
        else:
            self.status_label.config(text=f"推送失败: {repo}")
            messagebox.showerror("错误", f"推送 {repo} 失败，请检查网络或权限")

        self.load_local_repos()

    def show_git_log(self, repo: str):
        """显示 Git 提交历史"""
        dialog = tk.Toplevel(self)
        dialog.title(f"提交历史 - {repo}")
        dialog.geometry("650x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"Git 提交历史: {repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        headers = ["SHA", "提交信息", "作者", "日期"]
        widths = [10, 40, 15, 18]
        for i, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(list_frame, text=h, bg=THEME["border"],
                    fg=THEME["text_bright"], font=("Arial", 10, "bold"),
                    width=w, anchor="w", bd=1, relief="solid").grid(row=0, column=i, sticky="ew")

        repo_path = os.path.join(LOCAL_REPO_DIR, repo)
        result = subprocess.run(
            ["git", "log", "--oneline", "-20", "--format=%H|%s|%an|%ad", "--date=iso"],
            cwd=repo_path, capture_output=True, text=True
        )

        for idx, line in enumerate(result.stdout.strip().split("\n")):
            if not line:
                continue
            row = idx + 1
            bg = THEME["bg"] if idx % 2 == 0 else THEME["border"]
            parts = line.split("|")
            if len(parts) >= 4:
                sha = parts[0][:7]
                msg = parts[1][:50]
                author = parts[2][:15]
                date = parts[3][:19]

                tk.Label(list_frame, text=sha, bg=bg, fg=THEME["accent"],
                        width=widths[0], anchor="w", bd=1, relief="solid").grid(row=row, column=0, sticky="ew")
                tk.Label(list_frame, text=msg, bg=bg, fg=THEME["fg"],
                        width=widths[1], anchor="w", bd=1, relief="solid").grid(row=row, column=1, sticky="ew")
                tk.Label(list_frame, text=author, bg=bg, fg=THEME["fg"],
                        width=widths[2], anchor="w", bd=1, relief="solid").grid(row=row, column=2, sticky="ew")
                tk.Label(list_frame, text=date, bg=bg, fg=THEME["fg"],
                        width=widths[3], anchor="w", bd=1, relief="solid").grid(row=row, column=3, sticky="ew")

        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(pady=10)

    def show_branch_dialog(self, repo: str):
        """分支管理对话框"""
        dialog = tk.Toplevel(self)
        dialog.title(f"分支管理 - {repo}")
        dialog.geometry("400x300")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"分支管理 - {repo}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        branches = get_git_branches(repo)
        current = get_git_branch(repo)

        tk.Label(dialog, text=f"当前分支: {current}",
                bg=THEME["bg"], fg=THEME["accent"]).pack()

        list_frame = tk.Frame(dialog, bg=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        for branch in branches:
            name = branch.get("name", "")
            is_current = name == current
            color = THEME["accent"] if is_current else THEME["fg"]

            frame = tk.Frame(list_frame, bg=THEME["border"])
            frame.pack(fill="x", pady=1)

            tk.Label(frame, text=f"{'* ' if is_current else '  '}{name}",
                    bg=THEME["border"], fg=color, anchor="w").pack(side="left", padx=10, pady=5)

            if not is_current:
                tk.Button(frame, text="切换",
                         bg=THEME["accent"], fg="white", relief="flat",
                         cursor="hand2", command=lambda r=repo, b=name: (
                             switch_branch(r, b), dialog.destroy(), self.load_local_repos()
                         )).pack(side="right", padx=5, pady=2)

                tk.Button(frame, text="删除",
                         bg=THEME["error"], fg="white", relief="flat",
                         cursor="hand2", command=lambda r=repo, b=name: (
                             delete_branch(r, b), dialog.destroy(), self.load_local_repos()
                         )).pack(side="right", padx=5, pady=2)

        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(pady=10)

    def show_create_branch_dialog(self):
        """创建分支对话框"""
        repo = self.branch_repo_var.get() if hasattr(self, 'branch_repo_var') else ""
        if not repo:
            messagebox.showwarning("警告", "请先选择本地仓库")
            return

        dialog = tk.Toplevel(self)
        dialog.title("创建分支")
        dialog.geometry("350x200")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="创建新分支",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        tk.Label(dialog, text="分支名称:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=40, pady=(10, 0))
        name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=name_var, width=30,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        tk.Label(dialog, text="基础分支:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=40, pady=(10, 0))
        base_var = tk.StringVar(value="main")
        tk.Entry(dialog, textvariable=base_var, width=30,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_create():
            name = name_var.get().strip()
            base = base_var.get().strip() or "main"

            if not name:
                messagebox.showerror("错误", "请输入分支名称")
                return

            self.status_label.config(text=f"正在创建分支 {name}...")
            dialog.update()

            if create_branch(repo, name, base):
                self.status_label.config(text=f"已创建分支: {name}")
                messagebox.showinfo("成功", f"分支 {name} 创建成功")
                dialog.destroy()
                self.load_branches()
            else:
                self.status_label.config(text="创建分支失败")
                messagebox.showerror("错误", "创建分支失败")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="创建", command=do_create,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def switch_branch(self, repo: str, branch: str):
        """切换分支"""
        if switch_branch(repo, branch):
            self.status_label.config(text=f"已切换到分支: {branch}")
            messagebox.showinfo("成功", f"已切换到分支 {branch}")
            self.load_branches()
        else:
            messagebox.showerror("错误", "切换分支失败")

    def delete_branch(self, repo: str, branch: str):
        """删除分支"""
        result = messagebox.askyesno("确认", f"确定要删除分支 {branch} 吗？")
        if result:
            if delete_branch(repo, branch):
                self.status_label.config(text=f"已删除分支: {branch}")
                self.load_branches()
            else:
                messagebox.showerror("错误", "删除分支失败")

    def show_run_workflow_dialog(self):
        """运行工作流对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("运行工作流")
        dialog.geometry("400x150")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="运行工作流",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        repos = get_local_repos()
        if not repos:
            tk.Label(dialog, text="没有可用的本地仓库",
                    bg=THEME["bg"], fg=THEME["error"]).pack()
            tk.Button(dialog, text="关闭", command=dialog.destroy,
                     bg=THEME["border"], fg=THEME["fg"], relief="flat").pack(pady=10)
            return

        tk.Label(dialog, text="选择仓库:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=40, pady=(10, 0))
        repo_var = tk.StringVar(value=repos[0])
        ttk.Combobox(dialog, textvariable=repo_var, values=repos,
                    state="readonly").pack(pady=5)

        def do_run():
            repo = repo_var.get()
            repo_path = os.path.join(LOCAL_REPO_DIR, repo)
            workflows = list_workflows(repo_path)

            if not workflows:
                messagebox.showwarning("警告", "该仓库没有工作流")
                return

            workflow_name = workflows[0]["name"]
            self.status_label.config(text=f"正在运行工作流 {workflow_name}...")
            dialog.update()

            if run_workflow(repo, workflow_name):
                self.status_label.config(text=f"已触发工作流: {workflow_name}")
                messagebox.showinfo("成功", f"工作流 {workflow_name} 已触发")
            else:
                self.status_label.config(text="触发工作流失败")
                messagebox.showerror("错误", "触发工作流失败")

            dialog.destroy()
            self.load_workflows()

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="运行", command=do_run,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def run_workflow(self, repo: str, workflow_name: str):
        """运行工作流"""
        self.status_label.config(text=f"正在运行工作流 {workflow_name}...")
        self.update()

        if run_workflow(repo, workflow_name):
            self.status_label.config(text=f"已触发工作流: {workflow_name}")
            messagebox.showinfo("成功", f"工作流 {workflow_name} 已触发")
        else:
            self.status_label.config(text="触发工作流失败")
            messagebox.showerror("错误", "触发工作流失败")

        self.load_workflows()

    def show_create_issue_dialog(self):
        """创建议题对话框"""
        dialog = tk.Toplevel(self)
        dialog.title("创建议题")
        dialog.geometry("450x350")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="创建新议题",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(pady=10)

        # 标题
        tk.Label(dialog, text="标题 *:", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        title_var = tk.StringVar()
        tk.Entry(dialog, textvariable=title_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        # 描述
        tk.Label(dialog, text="描述 (支持 Markdown):", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))

        desc_text = tk.Text(dialog, width=45, height=10,
                           bg=THEME["border"], fg=THEME["fg"],
                           insertbackground=THEME["fg"])
        desc_text.pack(pady=5)

        # 标签
        tk.Label(dialog, text="标签 (用逗号分隔):", bg=THEME["bg"],
                fg=THEME["fg"]).pack(anchor="w", padx=30, pady=(10, 0))
        labels_var = tk.StringVar()
        tk.Entry(dialog, textvariable=labels_var, width=45,
                bg=THEME["border"], fg=THEME["fg"]).pack(pady=5)

        def do_create():
            title = title_var.get().strip()
            if not title:
                messagebox.showerror("错误", "请输入标题")
                return

            body = desc_text.get("1.0", "end").strip()
            labels = [l.strip() for l in labels_var.get().split(",") if l.strip()]

            self.status_label.config(text="正在创建议题...")
            dialog.update()

            if create_issue(title, body, labels):
                self.status_label.config(text="已创建议题")
                messagebox.showinfo("成功", "议题创建成功")
                dialog.destroy()
                self.load_issues()
            else:
                self.status_label.config(text="创建议题失败")
                messagebox.showerror("错误", "创建议题失败")

        btn_frame = tk.Frame(dialog, bg=THEME["bg"])
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="创建", command=do_create,
                 bg=THEME["accent"], fg="white", relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="取消", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2", width=10).pack(side="left", padx=5)

    def close_issue(self, issue_number: int):
        """关闭议题"""
        if close_issue(issue_number):
            self.status_label.config(text=f"已关闭议题 #{issue_number}")
            self.load_issues()
        else:
            messagebox.showerror("错误", "关闭议题失败")

    def reopen_issue(self, issue_number: int):
        """重新打开议题"""
        if reopen_issue(issue_number):
            self.status_label.config(text=f"已重新打开议题 #{issue_number}")
            self.load_issues()
        else:
            messagebox.showerror("错误", "重新打开议题失败")

    def show_issue_detail(self, issue: Dict):
        """显示议题详情"""
        dialog = tk.Toplevel(self)
        dialog.title(f"议题 #{issue.get('number', '')}")
        dialog.geometry("500x400")
        dialog.configure(bg=THEME["bg"])
        dialog.transient(self)

        tk.Label(dialog, text=f"议题 #{issue.get('number', '')}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 14, "bold")).pack(anchor="w", padx=20, pady=10)

        tk.Label(dialog, text=f"标题: {issue.get('title', '')}",
                bg=THEME["bg"], fg=THEME["text_bright"],
                font=("Arial", 11)).pack(anchor="w", padx=20)

        tk.Label(dialog, text=f"状态: {issue.get('state', '')}",
                bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w", padx=20, pady=2)

        labels = ", ".join([l.get("name", "") for l in issue.get("labels", [])]) or "无"
        tk.Label(dialog, text=f"标签: {labels}",
                bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w", padx=20, pady=2)

        created = issue.get("createdAt", "")[:19] if issue.get("createdAt") else "-"
        tk.Label(dialog, text=f"创建时间: {created}",
                bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w", padx=20, pady=2)

        tk.Label(dialog, text="描述:",
                bg=THEME["bg"], fg=THEME["fg"]).pack(anchor="w", padx=20, pady=(10, 5))

        desc_frame = tk.Frame(dialog, bg=THEME["border"], bd=1)
        desc_frame.pack(fill="both", expand=True, padx=20, pady=5)

        desc_label = tk.Label(desc_frame, text=issue.get("body", "无描述") or "无描述",
                             bg=THEME["border"], fg=THEME["fg"],
                             justify="left", anchor="nw", wraplength=450)
        desc_label.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg=THEME["border"], fg=THEME["fg"], relief="flat",
                 cursor="hand2").pack(pady=10)

    # ============================================================
    # 导航和快捷键方法
    # ============================================================

    def refresh_current_view(self):
        """刷新当前视图"""
        self.check_auth()
        view = self.current_view.get()
        self.load_content(view)

    def go_back(self):
        """返回上一级（当前实现为刷新）"""
        self.refresh_current_view()

    def quit_app(self):
        """退出应用"""
        result = messagebox.askquestion("退出", "确定要退出 GitHub TUI 吗？")
        if result == "yes":
            self.destroy()

    def select_prev(self):
        """选择上一个（子类可重写）"""
        pass

    def select_next(self):
        """选择下一个（子类可重写）"""
        pass

    def confirm_selection(self):
        """确认选择（子类可重写）"""
        pass


# ============================================================
# 主程序入口
# ============================================================
if __name__ == "__main__":
    try:
        app = GitHubTUI()
        app.mainloop()
    except KeyboardInterrupt:
        pass
