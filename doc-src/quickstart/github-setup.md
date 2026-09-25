# 准备 GitHub 仓库

## 创建仓库

1. 登录 [GitHub](https://github.com)，点击右上角 **"+"** → **"New repository"**
2. 填写仓库名称（例如 `my-notes`）
3. 选择仓库可见性：
    - **Public（公开）** — 任何人都能看到仓库内容。适合不介意公开的笔记，也可以用来展示你的笔记习惯
    - **Private（私有）** — 只有你自己能看到。推荐用于个人笔记
4. **不要勾选** "Add a README file" 等初始化选项（保持空仓库）
5. 点击 **"Create repository"**
6. 创建完成后，复制页面上显示的仓库地址，格式类似：
   ```
   https://github.com/你的用户名/my-notes.git
   ```

## 创建密钥（Personal Access Token）

GitHub 不允许用账号密码进行 Git 操作，需要创建一个 Token 作为替代密码。

1. 打开 [GitHub Token 设置页](https://github.com/settings/tokens?type=beta)
2. 你会看到两种类型：

    **Fine-grained token（精细化密钥）**
    
    看起来权限控制更精细，但配置复杂，需要选择具体的仓库和权限范围。说实话，作者自己都没成功用这个跑通过 Git 同步，所以**不推荐**，除非你非常熟悉 GitHub 的权限系统。

    **Tokens (classic)（经典密钥）** ← 推荐
    
    简单粗暴，勾选权限就能用。点击 **"Generate new token"** → **"Generate new token (classic)"**：
    
    - **Note**：随便填个名字，比如 `gitnoteline`
    - **Expiration**：选择有效期（建议 No expiration，一劳永逸）
    - **Select scopes**：勾选 **`repo`**（整个 repo 组）
    - 点击 **"Generate token"**
    - **立即复制生成的 token**（以 `ghp_` 开头），页面刷新后就看不到了

## 准备初始化信息

| 信息 | 说明 | 示例 |
|------|------|------|
| 远程仓库 URL | 刚才创建的仓库地址 | `https://github.com/用户名/my-notes.git` |
| 本地路径 | 笔记存放在电脑上的位置 | `~/.gitnoteline/repos/my-notes`（默认即可） |
| 密钥名称 | 给这个密钥起个名字 | `GitHub Token` |
| 密钥类型 | 选择 classic 还是 fine-grained | `Fine-grained Token`（实际填 classic 的 token 也选这个） |
| 密钥 | 刚才生成的 token | `ghp_xxxxxxxxxxxx` |
