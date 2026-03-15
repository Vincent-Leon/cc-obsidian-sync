[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-obsidian-sync

通过 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) 将 Claude Code 对话自动同步到 Obsidian。

对话原文直接推送到你的 Obsidian 笔记库 — 不做额外处理，不预设目录结构。只做同步。

## 安装

添加插件市场并安装：

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-obsidian-sync.git
/plugin install cc-obsidian-sync@Vincent-Leon/cc-obsidian-sync
```

或本地开发模式：

```
claude --plugin-dir /path/to/cc-obsidian-sync
```

## 配置

安装后运行：

```
/cc-sync:setup
```

支持直接粘贴 FNS JSON 配置快速完成设置：

```
/cc-sync:setup {"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}
```

JSON 可从 FNS 管理面板（笔记库页面）直接复制。

也可以不带参数运行 `/cc-sync:setup` 进入交互式配置。

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
CC Stop hook → 读取最新对话 → 推送到 FNS → Obsidian 同步
```

对话保存到 `{sync_dir}/{date}_{title}.md`（默认目录：`cc-sync/`）。

插件只负责同步。笔记的整理（目录、标签、日记、Dataview 查询等）交给 Obsidian 处理。

## 多设备

在每台设备上安装，所有设备推送到同一个 FNS 服务器。你的 Obsidian 客户端通过 FNS 实时同步接收更新。

## 要求

- Python 3.8+
- 已部署的 [FNS 服务器](https://github.com/haierkeys/fast-note-sync-service) 并配置好 Obsidian 插件

## 许可证

MIT
