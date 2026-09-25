# THINKING — GitNoteLine-PC 架构与实现路线

## 项目定位

GitNoteLine 是一个以 Git 为后端的笔记管理工具。PC 端是本地优先的桌面/本地 Web 应用，数据全部存在本机，通过 Git 进行版本管理和同步。

---

## 整体架构

```
GitNoteLine-PC/
├── core/           # 共享业务逻辑层
│   ├── config.py       # 运行时配置单例
│   ├── database.py     # 数据目录解析 + SQLite 操作
│   └── services.py     # 业务服务（身份、Git 操作等）
├── web/            # Flask Web 入口
│   ├── __main__.py     # CLI 入口：python -m web
│   ├── app.py          # Flask 工厂函数
│   ├── routes.py       # 路由 + API
│   └── static/         # 前端（纯 HTML/CSS/JS，无框架）
└── requirements.txt
```

### 访问方式

当前通过浏览器访问本地 Flask 服务（`http://gitnoteline.localhost:<port>`），未来可能支持本地 webview 窗口。

`core/` 作为共享业务逻辑层，无论哪种访问方式都复用同一套代码。

---

## 关键设计决策

### 1. 数据存储：SQLite + Git

```
~/.gitnoteline/          # 平台数据目录
├── userdata.db          # SQLite — 应用配置和用户数据
└── (future) notes/      # Git 仓库 — 笔记内容
```

**为什么用 SQLite 而不是 JSON/TOML 配置文件：**
- 需要存储结构化数据（设置、元数据、未来可能的索引）
- SQLite 单文件、零依赖、Python 标准库自带
- 比手动管理 JSON 文件的读写锁和迁移更可靠

**平台数据目录：**
| 平台 | 路径 |
|---|---|
| Linux | `~/.gitnoteline/` |
| macOS | `~/Library/Application Support/GitNoteLine/` |
| Windows | `%APPDATA%\GitNoteLine\` |

### 2. 网络绑定：IPv6 双栈 loopback

```python
run_simple("::1", port, app, ...)
```

绑定 `::1`（IPv6 loopback），Linux 默认 `IPV6_V6ONLY=0`，同时接受 IPv4 和 IPv6 连接。配合 `gitnoteline.localhost` 域名使用。

**为什么不用 127.0.0.1：** 单绑 IPv4 会丢失 IPv6 连接；双栈 `::1` 一个地址覆盖两种协议。

**为什么用 localhost 域名而不是 IP：** 浏览器对 `*.localhost` 有特殊处理（不经过 DNS 解析、不发送 HSTS 预加载等），更安全。

### 3. 前端：零框架，纯 HTML/CSS/JS

**为什么不用 React/Vue：**
- 这是一个本地应用，页面少、交互简单
- 不需要构建工具链（no webpack, no npm, no node_modules）
- 纯静态文件由 Flask 直接 serve，开发即部署
- 用户偏好轻量方案

**前端文件结构：**
```
static/
├── css/style.css          # 设计系统（psyScale 风格，白灰色调）
├── js/api-adapter.js      # API 桥接层（预留 webview 检测）
├── js/app.js              # 主页逻辑
└── js/init.js             # 初始化流程逻辑
```

**设计系统：** 参考 psyScale 项目的视觉风格——渐变背景、白色卡片 + 阴影、hover 上浮、fadeIn 动画。使用 CSS 变量统一管理颜色、圆角、阴影。

### 4. 本地 webview（未来可能）

如果将来需要原生窗口体验，可能的方案：

- **方案 A：嵌入式 Flask** — webview 内启动 Flask，通过 HTTP 通信。优点是完全复用现有路由，缺点是端口管理。
- **方案 B：js_api 直调** — webview 直接调用 Python 函数，无 HTTP 开销。但需要额外维护一套暴露的 API 类。

当前 `api-adapter.js` 已预留了环境检测逻辑，未来接入 webview 时只需补充对应 transport。

### 5. 初始化流程

```
首次启动
  │
  ├─ DB 不存在 → 重定向 /init/1
  │   │
  │   ├─ 检测到 Git 全局配置 → 显示确认卡片
  │   │   ├─ "使用" → 写入 DB（identity_source=git）→ /init/2
  │   │   └─ "手动填写" → 显示表单（预填 Git 数据）
  │   │
  │   └─ 无 Git 配置 → 直接显示表单
  │       └─ 提交 → 写入 DB（identity_source=manual）→ /init/2
  │
  ├─ DB 存在但无仓库 → /init/2（仓库设置选择页）
  │   │
  │   ├─ /init/2/1 — 创建在线仓库（推荐）
  │   │   │
  │   │   ├─ 填写远程 URL、本地路径、凭证信息
  │   │   ├─ 自动从 URL 提取域名作为平台标签
  │   │   ├─ 自动从 URL 提取仓库名，默认路径：~/.gitnoteline/repos/<仓库名>
  │   │   ├─ GitHub + 通用密钥 → 红色警告（GitHub 不支持密码认证）
  │   │   └─ 提交后验证流程：
  │   │       ├─ git ls-remote 检测远程状态
  │   │       ├─ 非空仓库 → git pull（同步已有内容）
  │   │       ├─ 写入 .gitnoteline.yaml（设备注册表）
  │   │       ├─ git add + commit + push（验证凭证）
  │   │       └─ 失败时自动回滚（删除目录 + 数据库记录）
  │   │
  │   ├─ /init/2/2 — 同步已有云仓库（待实现）
  │   ├─ /init/2/3 — 选择已有本地仓库（待实现）
  │   └─ /init/2/4 — 创建本地仓库，暂不同步（待实现）
  │
  └─ DB 存在且有仓库 → 直接进入主页 /
```

**/init/1 重定向规则：**
- DB 不存在 → 显示初始化表单
- DB 已存在 → 302 重定向到 /init/2

**/init/2/1 验证流程：**
1. `git ls-remote` 检测远程仓库状态
2. 空仓库：跳过 pull，直接写 YAML + push
3. 非空仓库：pull → 写 YAML → push
4. 失败时回滚：删除本地目录 + 数据库凭证/仓库记录
5. 错误处理：
   - 认证失败 → "认证失败，请检查凭证是否正确"
   - 网络错误 → "网络错误，无法连接远程仓库"
   - 使用 `GIT_TERMINAL_PROMPT=0` 禁用交互式密码提示

### 6. 凭证加密存储

**不使用 keyring，改用 Fernet 对称加密存储在数据库：**

```python
# core/credentials.py
from cryptography.fernet import Fernet

# 密钥派生：machine-id + username → PBKDF2 → Fernet key
# 加密存储：encrypted_secret 字段存储在 credentials 表
```

**为什么不用 keyring：**
- 容器化部署时可能没有 keyring daemon
- 数据库加密更便携，备份/迁移只需复制 userdata.db
- 密钥从 machine-id 派生，同一台机器自动解密

**加密流程：**
1. 获取 machine-id（Linux: `/etc/machine-id`）+ 用户名
2. PBKDF2 派生 32 字节密钥（100000 次迭代）
3. Fernet 加密凭证（AES-128-CBC + HMAC）
4. 存储到 `credentials.encrypted_secret` 字段

### 7. .gitnoteline.yaml 配置文件

每个仓库根目录的 `.gitnoteline.yaml` 记录设备注册表：

```yaml
version: 1
devices:
  - name: G36113          # 设备名（hostname）
    joined: 2026-09-25    # 首次加入时间
    last_sync: 2026-09-25 # 最后同步时间
```

**设计原则：**
- 信息最小化，适合公开仓库
- 新设备加入时追加一条记录
- 每次同步更新 `last_sync`
- `version` 字段用于未来格式迁移

### 8. 端口策略

- 默认随机端口（`_find_free_port()`）
- `--port` 指定固定端口
- `--debug` 模式下通过环境变量 `GITNOTELINE_PORT` 保持 reloader 子进程端口一致
- `--only-server` 模式：监听 `0.0.0.0:8080`，适合容器化/远程部署

---

## 已实现的 API

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/api/hello` | GET | 心跳/连接检测 | 永久保留，不删除 |
| `/api/init/prefill` | GET | 获取身份预填数据 | 读 Git 全局配置 |
| `/api/init/step1` | POST | 提交身份设置 | body: `{name, email, source}` |
| `/api/init/step2/1/default-path` | GET | 获取默认本地路径 | query: `remote_url`，自动提取仓库名 |
| `/api/init/step2/1` | POST | 创建在线仓库 | body: `{remote_url, local_path, credential_name, credential_type, credential_secret}` |

---

## 待实现 / 未来路线

### 近期
- [ ] `/init/2/2` — 同步已有云仓库（clone 远程仓库到本地）
- [ ] `/init/2/3` — 选择已有本地仓库（关联已存在的 Git 仓库）
- [ ] `/init/2/4` — 创建本地仓库，暂不同步（纯本地模式）
- [ ] 笔记 CRUD — 创建、编辑、删除笔记
- [ ] Git 操作封装 — commit、push、pull、diff

### 中期
- [ ] 本地 webview 窗口（可选）
- [ ] 笔记编辑器 — Markdown 编辑 + 实时预览
- [ ] 搜索功能 — 全文搜索笔记内容
- [ ] 多设备同步 UI — 查看设备列表、同步状态

### 远期
- [ ] 冲突处理 UI
- [ ] 笔记标签/分类系统
- [ ] 导出功能（PDF、HTML）

---

## 运行方式

```bash
# 安装依赖（虚拟环境在 ../.env，不在项目目录内）
../.env/bin/pip install -r requirements.txt

# 启动 Web 服务（本地开发）
../.env/bin/python -m web

# 启动（指定端口）
../.env/bin/python -m web --port 8080

# 服务器模式（容器化/远程部署）
../.env/bin/python -m web --only-server

# 调试模式（热重载 + Werkzeug debugger）
../.env/bin/python -m web --debug
```

**依赖说明：**
- `flask>=3.0` — Web 框架
- `werkzeug>=3.0` — WSGI 工具库
- `cryptography>=41.0` — 凭证加密（Fernet）
- `pyyaml>=6.0` — YAML 配置文件读写

---

## 约束与原则

1. **数据不离开本机** — 所有数据存在用户本机，不依赖云服务
2. **虚拟环境在项目外** — `../.env`，项目目录保持干净
3. **零前端构建** — 不用 npm/webpack，浏览器直接跑
4. **core/ 是共享层** — 业务逻辑与访问方式解耦，未来接入 webview 时无需重写
5. **Git 是真相来源** — 笔记的版本历史由 Git 管理，应用不重复造版本控制
