# GitHub Token 更换详细教程

## 为什么要更换 Token

- Token 过期了
- Token 被撤销
- 权限不足
- 安全原因（泄露）

---

## 步骤一：生成新 Token

### 1. 进入 Token 设置页面

打开：https://github.com/settings/tokens

### 2. 创建新 Token

1. 点击 **Generate new token (Classic)**
2. 填写 Token 名称（如 `Git CLI 2026`）
3. 设置过期时间（建议 30-90 天）
4. 勾选所需权限：

| 权限 | 用途 |
|------|------|
| `repo` | 读写仓库 |
| `workflow` | 管理 GitHub Actions |
| `read:user` | 读取用户信息 |

### 3. 生成并复制

- 点击 **Generate token**
- **立即复制**（只会显示一次）

---

## 步骤二：更新本地仓库的 Token

### 方式 A：修改 remote URL（推荐）

```bash
# 进入仓库目录
cd /path/to/your/repo

# 更新 remote URL
git remote set-url origin https://用户名:新Token@github.com/用户名/仓库名.git

# 验证是否成功
git remote -v

# 测试推送
git push
```

### 方式 B：使用 Credential Helper

```bash
# 设置凭据存储
git config --global credential.helper store

# 下次 push 时会提示输入用户名和 Token
git push
# Username: 你的GitHub用户名
# Password: 新Token
```

### 方式 C：手动编辑配置文件

```bash
# 编辑 .git/config 文件
nano .git/config

# 或使用 vim
vim .git/config
```

找到：
```
[remote "origin"]
    url = https://用户名:旧Token@github.com/用户名/仓库名.git
```

改为：
```
[remote "origin"]
    url = https://用户名:新Token@github.com/用户名/仓库名.git
```

---

## 步骤三：验证 Token 是否有效

### 测试 API 请求
```bash
curl -s -u 用户名:新Token https://api.github.com/user
```

如果返回用户信息，说明 Token 有效。

### 测试仓库访问
```bash
git fetch origin
```

如果没有报错，说明 Token 正常工作。

---

## 多仓库 Token 管理

如果多个仓库使用不同 Token，可以使用：

### 1. 每个仓库单独设置
```bash
git remote set-url origin https://用户名:Token@github.com/用户名/仓库名.git
```

### 2. 使用 .gitconfig 多个凭据
```bash
# 编辑 ~/.gitconfig
[credential "https://github.com"]
    username = 你的用户名
```

### 3. 使用 GitHub CLI（如果可用）
```bash
gh auth login
gh auth git credential
```

---

## 常见问题

### Q: 推送时报 `403 Forbidden`
A: Token 无效或权限不足，重新生成并更新。

### Q: Token 过期有什么预兆？
A: 会收到 GitHub 邮件通知，建议提前更换。

### Q: 可以同时使用多个 Token 吗？
A: 可以，不同仓库使用不同的 remote URL。

### Q: Token 泄露了怎么办？
A: 立即在 https://github.com/settings/tokens 撤销该 Token。

---

## 快速参考命令

```bash
# 查看当前 remote
git remote -v

# 更新 Token
git remote set-url origin https://用户名:新Token@github.com/用户名/仓库名.git

# 验证连接
git fetch

# 查看所有仓库的 remote
git remote -v
```

---

## 安全建议

1. **不要**把 Token 提交到代码中
2. **不要**在公开场合分享 Token
3. **定期**更换 Token
4. **设置**短期过期时间
5. **使用**最小权限原则