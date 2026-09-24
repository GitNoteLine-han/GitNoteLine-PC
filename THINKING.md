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
  └─ DB 存在 → 直接进入主页 /
```

**/init/1 重定向规则：**
- DB 不存在 → 显示初始化表单
- DB 已存在 → 302 重定向到 /init/2

### 6. 端口策略

- 默认随机端口（`_find_free_port()`）
- `--port` 指定固定端口
- `--debug` 模式下通过环境变量 `GITNOTELINE_PORT` 保持 reloader 子进程端口一致

---

## 已实现的 API

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/api/hello` | GET | 心跳/连接检测 | 永久保留，不删除 |
| `/api/init/prefill` | GET | 获取身份预填数据 | 读 Git 全局配置 |
| `/api/init/step1` | POST | 提交身份设置 | body: `{name, email, source}` |

---

## 待实现 / 未来路线

### 近期
- [ ] `/init/2` — 仓库路径设置（选择或创建 Git 仓库目录）
- [ ] 笔记 CRUD — 创建、编辑、删除笔记
- [ ] Git 操作封装 — commit、push、pull、diff

### 中期
- [ ] 本地 webview 窗口（可选）
- [ ] 笔记编辑器 — Markdown 编辑 + 实时预览
- [ ] 搜索功能 — 全文搜索笔记内容

### 远期
- [ ] 多仓库支持
- [ ] 冲突处理 UI
- [ ] 笔记标签/分类系统
- [ ] 导出功能（PDF、HTML）

---

## 运行方式

```bash
# 安装依赖（虚拟环境在 ../.env，不在项目目录内）
../.env/bin/pip install -r requirements.txt

# 启动 Web 服务
../.env/bin/python -m web

# 启动（指定端口）
../.env/bin/python -m web --port 8080

# 调试模式（热重载 + Werkzeug debugger）
../.env/bin/python -m web --debug
```

---

## 约束与原则

1. **数据不离开本机** — 所有数据存在用户本机，不依赖云服务
2. **虚拟环境在项目外** — `../.env`，项目目录保持干净
3. **零前端构建** — 不用 npm/webpack，浏览器直接跑
4. **core/ 是共享层** — 业务逻辑与访问方式解耦，未来接入 webview 时无需重写
5. **Git 是真相来源** — 笔记的版本历史由 Git 管理，应用不重复造版本控制
