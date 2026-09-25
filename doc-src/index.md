# GitNoteLine

以 Git 为后端的本地优先笔记管理工具。

## 特性

- **本地优先** — 数据全部存在本机，不依赖云服务
- **Git 版本管理** — 笔记通过 Git 进行版本控制和多设备同步
- **双模式编辑器** — 支持 Markdown 源码（Monaco）和所见即所得（Quill）两种编辑模式
- **自动同步** — 启动时拉取，保存时推送，无需手动操作
- **轻量部署** — 纯 Python + 前端，零构建工具链

## 架构

```
GitNoteLine-PC/
├── core/           # 共享业务逻辑层
│   ├── config.py       # 运行时配置
│   ├── database.py     # SQLite 操作
│   ├── credentials.py  # 凭证加密存储
│   └── services.py     # 业务服务（Git 操作等）
├── web/            # Flask Web 入口
│   ├── app.py          # Flask 工厂函数
│   ├── routes.py       # 路由 + API
│   └── static/         # 前端（纯 HTML/CSS/JS）
└── docs/           # 项目文档
```
