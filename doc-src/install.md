# 安装指南

## 环境要求

- Git（必须）

### 检查 Git

打开终端（Windows 为命令提示符或 PowerShell，Linux/macOS 为终端），输入：

```bash
git --version
```

如果显示版本号（如 `git version 2.43.0`），说明已安装。

### 安装 Git

**Windows：**

1. 访问 [Git 官网](https://git-scm.com/download/win)
2. 下载并运行安装程序
3. 安装时保持默认选项即可
4. 安装完成后**重启终端**

**Linux (Debian/Ubuntu)：**

```bash
sudo apt install git
```

**Linux (Fedora)：**

```bash
sudo dnf install git
```

**macOS：**

```bash
xcode-select --install
```

## 下载安装

从 [Releases 页面](https://github.com/your-username/GitNoteLine-PC/releases) 下载对应系统的安装包：

- **Windows** — `GitNoteLine-PC.exe`
- **Linux** — `GitNoteLine-PC.AppImage`

### Windows

双击运行 exe 文件即可。

### Linux

```bash
chmod +x GitNoteLine-PC.AppImage
./GitNoteLine-PC.AppImage
```

启动后会自动打开浏览器访问 `http://gitnoteline.localhost:<port>`。
