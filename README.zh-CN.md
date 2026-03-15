[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-obsidian-sync

通过 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) 将 Claude Code 对话自动同步到 Obsidian。

对话从 JSONL 解析，按会话去重，带有每条消息的时间戳推送到你的 Obsidian 笔记库。不做额外处理，不预设目录结构。只做同步。

## 安装

添加插件市场并安装：

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-obsidian-sync.git
/plugin install cc-obsidian-sync@cc-obsidian-sync
```

## 更新与卸载

通过市场安装的插件，更新和卸载都通过插件系统管理：

```bash
# 更新市场目录（拉取最新版本信息）
/plugin marketplace update cc-obsidian-sync

# 更新已安装的插件到最新版本
/plugin update cc-obsidian-sync@cc-obsidian-sync

# 卸载插件
/plugin uninstall cc-obsidian-sync@cc-obsidian-sync

# 移除整个市场（同时卸载其下所有插件）
/plugin marketplace remove cc-obsidian-sync
```

> **注意：** 更新后需要重启 Claude Code 才能加载新版插件代码。

也可以通过 `/plugin` → **Installed** / **Marketplaces** 标签页进行交互式管理。

## 配置

安装后运行：

```
/cc-sync:setup {"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}
```

JSON 可从 FNS 管理面板（笔记库页面）直接复制。

配置完成后重启 Claude Code，即可自动同步每次对话。

## 命令

| 命令 | 说明 |
|------|------|
| `/cc-sync:setup` | 配置 FNS 连接 |
| `/cc-sync:export` | 批量导出所有未同步的对话 |
| `/cc-sync:test` | 测试 API 连通性 |
| `/cc-sync:run` | 手动同步最新对话 |
| `/cc-sync:status` | 查看配置和同步状态 |
| `/cc-sync:log` | 查看最近同步日志 |

## 工作原理

```
CC Stop hook → 解析 JSONL → 按会话去重 → 推送到 FNS → Obsidian 同步
```

- 从 `.jsonl` 文件解析对话（而非 `.md`），获取结构化数据
- 按 `sessionId` 去重 — 同一会话多次保存只同步一次
- 以对话标题命名文件：`{sync_dir}/{标题}.md`（默认目录：`cc-sync/`）
- 标题冲突自动编号：`标题.md`、`标题 (2).md`、`标题 (3).md`
- 每条消息带时间戳：`### User [14:30]`
- 通过内容哈希追踪变更 — 更新覆盖原文件，不产生重复

插件只负责同步。笔记的整理（目录、标签、日记、Dataview 查询等）交给 Obsidian 处理。

## 多设备

在每台设备上安装，所有设备推送到同一个 FNS 服务器。你的 Obsidian 客户端通过 FNS 实时同步接收更新。

## 要求

- Python 3.8+
- 已部署的 [FNS 服务器](https://github.com/haierkeys/fast-note-sync-service) 并配置好 Obsidian 插件

## 许可证

MIT
