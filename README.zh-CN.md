[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-sync

自动同步 Claude Code 对话到你的知识库。

对话从 JSONL 解析，按会话去重，带有每条消息的时间戳推送到你的笔记系统。支持多种输出适配器：本地文件、FNS、Git 或自部署服务器。

## 安装

### 方式一：pip（推荐）

```bash
pip install git+https://github.com/Vincent-Leon/cc-sync-plugin.git
cc-sync install
```

安装 `cc-sync` 命令行工具并注册 Claude Code 的 Stop hook。安装后重启 Claude Code 生效。

### 方式二：Claude Code 插件

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-sync-plugin.git
/plugin install cc-sync@cc-sync
```

## 更新与卸载

### pip 安装方式

```bash
# 更新
pip install --upgrade git+https://github.com/Vincent-Leon/cc-sync-plugin.git

# 卸载
cc-sync uninstall   # 从 Claude Code 设置中移除 hook
pip uninstall cc-sync-plugin
```

### 插件安装方式

```bash
# 更新
/plugin marketplace update cc-sync
/plugin update cc-sync@cc-sync

# 卸载
/plugin uninstall cc-sync@cc-sync
/plugin marketplace remove cc-sync
```

> **注意：** 更新后需要重启 Claude Code 才能加载新版插件代码。
>
> **已知问题：** `plugin update` 可能只执行了 fetch 而没有 merge。如果更新后仍是旧版本，请手动执行：
>
> ```bash
> cd ~/.claude/plugins/marketplaces/cc-sync/
> git pull
> ```
>
> 然后重新运行 `/plugin update cc-sync@cc-sync`。

## 配置

安装后选择输出适配器：

```bash
# 本地文件（直接写入 Obsidian 笔记库）
cc-sync setup --adapter=local --path=~/Documents/Obsidian/MyVault

# FNS（Fast Note Sync 服务器）
cc-sync setup '{"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}'

# Git（自动提交到 git 仓库）
cc-sync setup --adapter=git --repo-path=~/obsidian-vault

# Server（推送到 cc-sync-server）
cc-sync setup --adapter=server --url=http://localhost:8080 --token=your-token
```

配置完成后重启 Claude Code，即可自动同步每次对话。

## 输出适配器

| 适配器 | 模式 | 说明 |
|--------|------|------|
| `local` | Lite | 直接写 .md 文件到本地目录 |
| `fns` | Lite | 通过 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) REST API 推送 |
| `git` | Lite | 写 .md + 自动 git commit（可选 push） |
| `server` | Server | 推送到 [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) 实现多设备同步 |

## 命令

| 命令 | 说明 |
|------|------|
| `/cc-sync:setup` | 配置输出适配器 |
| `/cc-sync:web` | 打开 Web 管理面板 |
| `/cc-sync:export` | 批量导出所有未同步的对话 |
| `/cc-sync:test` | 测试适配器连通性 |
| `/cc-sync:run` | 手动同步最新对话 |
| `/cc-sync:status` | 查看配置和同步状态 |
| `/cc-sync:log` | 查看最近同步日志 |

## 工作原理

```
CC Stop hook → 解析 JSONL → 按会话去重 → 输出适配器 → 知识库
```

- 从 `.jsonl` 文件解析对话（而非 `.md`），获取结构化数据
- 按 `sessionId` 去重 — 同一会话多次保存只同步一次
- 以对话标题命名文件：`{sync_dir}/{标题}.md`（默认目录：`cc-sync/`）
- 标题冲突自动编号：`标题.md`、`标题 (2).md`、`标题 (3).md`
- 每条消息带时间戳：`### User [14:30]`
- 通过内容哈希追踪变更 — 更新覆盖原文件，不产生重复

插件只负责同步。笔记的整理交给你的笔记工具处理。

## 多设备

**Lite 模式：** 每台设备安装插件，推送到同一个 FNS 服务器或 git 仓库。

**Server 模式：** 每台设备安装插件，全部推送到一个 [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) 实例。服务器负责去重、存储和下游分发。

## 要求

- Python 3.8+
- Jinja2（`pip install jinja2`，pip 安装时自动包含）

## 许可证

MIT
