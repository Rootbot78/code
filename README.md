# GitHub TUI User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Interface Layout](#interface-layout)
4. [Keyboard Shortcuts](#keyboard-shortcuts)
5. [Features](#features)
   - [5.1 Dashboard](#51-dashboard)
   - [5.2 Remote Repos](#52-remote-repos)
   - [5.3 Local Repos](#53-local-repos)
   - [5.4 Branch Management](#54-branch-management)
   - [5.5 Workflows](#55-workflows)
   - [5.6 Issues](#56-issues)
6. [Dialogs Reference](#dialogs-reference)

---

## Introduction

GitHub TUI is a tkinter-based graphical interface for GitHub management, supporting repository management, file operations, Git operations, PR management, and Issue management.

**Prerequisites:**
- `gh` CLI tool installed
- GitHub authentication completed (`gh auth login`)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/gh_tui.git

# 2. Navigate to the directory
cd gh_tui

# 3. Run the program
python3 gh_tui.py
```

**First-time setup - authenticate with GitHub:**
```bash
gh auth login
```

---

## Interface Layout

```
┌──────────────────────────────────────────────────────────────┐
│  GitHub TUI                        ✓ Logged in: username    │
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│  Navigation│              Content Area                       │
│  ──────   │                                                 │
│  D Dashboard│        (Displays current view content)        │
│  R Remote  │                                                 │
│  L Local   │                                                 │
│  B Branches│                                                 │
│  W Workflows│                                                │
│  I Issues  │                                                 │
│            │                                                 │
│  Shortcuts │                                                 │
│  ──────    ├─────────────────────────────────────────────────┤
│  q: Quit   │  Status: Shows current operation status       │
│  r: Refresh│                                                 │
└────────────┴─────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

| Key | Action | Corresponding Menu |
|-----|--------|-------------------|
| `D` | Switch to Dashboard | Dashboard |
| `R` | Switch to Remote Repos | Remote Repos |
| `L` | Switch to Local Repos | Local Repos |
| `B` | Switch to Branch Management | Branches |
| `W` | Switch to Workflows | Workflows |
| `I` | Switch to Issues | Issues |
| `q` / `Ctrl+C` | Exit Program | - |
| `r` | Refresh Current View | - |
| `Esc` | Go Back / Refresh | - |
| `↑` / `k` | Select Previous Item | - |
| `↓` / `j` | Select Next Item | - |
| `Enter` | Confirm Selection | - |
| `n` | New (in dialogs) | - |

---

## Features

### 5.1 Dashboard

Displays an overview of your GitHub account status.

**Displayed Information:**
- **Auth Status** - Whether logged into GitHub
- **Username** - Currently logged-in username
- **Remote Repo Count** - Number of repositories on GitHub
- **Local Repo Count** - Number of Git repos in local `~/github/` directory

**Shortcut Reference** - Lists all available keyboard shortcuts

---

### 5.2 Remote Repos

Manage remote repositories on GitHub.

**Toolbar Buttons:**
| Button | Action |
|--------|--------|
| Search | Search GitHub repositories |
| Refresh (r) | Refresh repository list |
| New (n) | Create new repository |

**Search Box** - Real-time filtering of displayed repositories

**Repository List Action Buttons:**
| Button | Action |
|--------|--------|
| Info | View repository details |
| Clone | Clone to local |
| Upload | Upload file to repository |
| Files | View repository file list |
| Fork | Fork repository |
| Delete | Delete repository |

---

### 5.3 Local Repos

Manage locally cloned Git repositories (stored in `~/github/` directory).

**Toolbar Buttons:**
| Button | Action |
|--------|--------|
| Refresh (r) | Refresh local repository list |

**Repository List Display:**
- Repository name
- Current branch
- Change status (number of modified files)

**Repository List Action Buttons:**
| Button | Action |
|--------|--------|
| Commit | Commit changes |
| Pull | Pull remote updates |
| Push | Push to remote |
| Branch | Branch management |
| Log | View Git commit history |

---

### 5.4 Branch Management

Manage branches in local Git repositories.

**Toolbar:**
- Repository dropdown - Select repository to manage
- Refresh (r) - Refresh branch list
- New (n) - Create new branch

**Branch List Display:**
- Branch name
- Upstream branch (associated remote branch)
- SHA (short hash of latest commit)

**Action Buttons:**
| Button | Action |
|--------|--------|
| Switch | Switch to this branch |
| Delete | Delete this branch (non-current branches only) |

---

### 5.5 Workflows

View and trigger GitHub Actions workflows.

**Prerequisite:** Local repository must have `.github/workflows/` directory with YAML configuration files.

**Toolbar Buttons:**
| Button | Action |
|--------|--------|
| Refresh (r) | Refresh workflow list |
| Run (n) | Manually trigger workflow |

**Workflow List Display:**
- Workflow name
- Recent run status (success/failure/none)
- Run time

**Action Buttons:**
| Button | Action |
|--------|--------|
| Run | Trigger this workflow |

---

### 5.6 Issues

Manage GitHub Issues.

**Toolbar:**
- Status filter - Select `open` / `closed` / `all`
- Refresh (r) - Refresh issue list
- New (n) - Create new issue

**Issue List Display:**
- Number
- Title
- Status
- Labels
- Created time

**Action Buttons:**
| Button | Action |
|--------|--------|
| Close/Reopen | Close or reopen issue |
| Details | View issue full content |

---

## Dialogs Reference

### Search Repository Dialog

**Purpose:** Search for repositories on GitHub

**How to Use:**
1. Enter keywords in the search box (e.g., repo name, topic)
2. Click "Search" button or press Enter
3. Double-click a result to view repository details

---

### Create Repository Dialog

**Purpose:** Create a new repository on GitHub

**Fields:**
| Field | Description | Required |
|-------|-------------|----------|
| Repository Name | Name of the new repository | Yes |
| Description | Repository description | No |
| Private | Check to create private repository | - |
| Initialize README | Check to auto-create README.md | - |
| Add .gitignore | Check to add Python template | - |

---

### Repository Details Dialog

**Purpose:** View detailed repository information

**Displayed Information:**
- Full repo name (owner/repo)
- Description, default branch, language
- Stars, forks, open issues count
- Created time, last updated time, URL

**Action Buttons:**
| Button | Action |
|--------|--------|
| Fork | Fork to your account |
| Star | Star the repository |
| Commits | View commit history |
| PR List | View Pull Requests |
| Close | Close dialog |

---

### Clone Repository Dialog

**Purpose:** Clone a remote repository to local

**Fields:**
| Field | Description | Default |
|-------|-------------|---------|
| Target Path | Local storage path | `~/github/` |

**Action:** Click "Clone" to start cloning

---

### Upload File Dialog

**Purpose:** Upload a file from local to GitHub repository

**Fields:**
| Field | Description | Required |
|-------|-------------|----------|
| Select Local File | Click "Browse" to select file | Yes |
| Repository Path | File path in repo (e.g., `src/main.py`) | Yes |
| Commit Message | Commit message for this upload | Yes |

---

### Delete Repository Dialog

**Purpose:** Delete a repository on GitHub (dangerous operation)

**Confirmation:**
1. Enter repository name to confirm (prevent accidental deletion)
2. Only when the correct name is entered can you click "Delete"

---

### Create PR Dialog

**Purpose:** Create a Pull Request

**Fields:**
| Field | Description | Required |
|-------|-------------|----------|
| Title | PR title | Yes |
| Body | PR detailed description | No |
| Head Branch | Branch to merge from | Yes |
| Base Branch | Branch to merge into | No (default: main) |

---

### Commit Changes Dialog

**Purpose:** Commit changes in local Git repository

**Steps:**
1. **Select Files** - Check the files to commit (only changed files are shown)
2. **Enter Commit Message** - Describe what this commit does
3. **Push Immediately** (optional) - Check to automatically push after commit

---

### Branch Management Dialog

**Purpose:** View and switch branches

**Displayed:**
- Current branch (green marker)
- All branches list

**Actions:**
- Click "Switch" to switch to that branch
- Click "Delete" to delete that branch

---

### Create Branch Dialog

**Purpose:** Create a new branch in local repository

**Fields:**
| Field | Description | Default |
|-------|-------------|---------|
| Branch Name | Name of new branch | - |
| Base Branch | Branch to create from | main |

---

### Run Workflow Dialog

**Purpose:** Manually trigger a GitHub Actions workflow

**Steps:**
1. Select repository from dropdown (if multiple local repos)
2. Click "Run" to trigger the first workflow in that repo

---

### Create Issue Dialog

**Purpose:** Create an Issue on GitHub

**Fields:**
| Field | Description | Required |
|-------|-------------|----------|
| Title | Issue title | Yes |
| Body | Issue content (Markdown supported) | No |
| Labels | Comma-separated label names | No |

---

### View Commits Dialog

**Purpose:** View repository commit history

**Displayed:**
- SHA (7-character hash)
- Commit message
- Author
- Date

---

### View Git Log Dialog

**Purpose:** View local repository Git commit history

**Displayed:**
- SHA (7-character hash)
- Commit message
- Author
- Date

---

## Troubleshooting

### Authentication Failed
```bash
# Check auth status
gh auth status

# Re-login if needed
gh auth logout
gh auth login
```

### Network Error
```
gh command error: Get "https://api.github.com/user": unexpected EOF
```
This is usually a network connection issue. Check:
- Network is working
- Proxy settings are correct
- GitHub is accessible

### Commit Failed
Ensure Git user info is configured:
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### Local Repository Operations Failed
- Ensure local repo path `~/github/` exists with correct permissions
- Ensure `.git` directory is intact

---

## Configuration

**Local Repository Storage:** `~/github/`

To change, edit line 20 in `gh_tui.py`:
```python
LOCAL_REPO_DIR = os.path.expanduser("~/github/")
```
