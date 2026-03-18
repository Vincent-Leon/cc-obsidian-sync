[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-sync

自動同步 Claude Code 對話到你的知識庫。

對話從 JSONL 解析，按工作階段去重，帶有每則訊息的時間戳推送到你的筆記系統。支援多種輸出適配器：本地檔案、FNS、Git 或自部署伺服器。

## 安裝

### 方式一：pip（推薦）

```bash
pip install git+https://github.com/Vincent-Leon/cc-sync-plugin.git
cc-sync install
```

安裝 `cc-sync` 命令列工具並註冊 Claude Code 的 Stop hook。安裝後重新啟動 Claude Code 生效。

### 方式二：Claude Code 外掛

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-sync-plugin.git
/plugin install cc-sync@cc-sync
```

## 更新與移除

### pip 安裝方式

```bash
# 更新
pip install --upgrade git+https://github.com/Vincent-Leon/cc-sync-plugin.git

# 移除
cc-sync uninstall   # 從 Claude Code 設定中移除 hook
pip uninstall cc-sync-plugin
```

### 外掛安裝方式

```bash
# 更新
/plugin marketplace update cc-sync
/plugin update cc-sync@cc-sync

# 移除
/plugin uninstall cc-sync@cc-sync
/plugin marketplace remove cc-sync
```

> **注意：** 更新後需要重新啟動 Claude Code 才能載入新版外掛程式碼。
>
> **已知問題：** `plugin update` 可能只執行了 fetch 而沒有 merge。如果更新後仍是舊版本，請手動執行：
>
> ```bash
> cd ~/.claude/plugins/marketplaces/cc-sync/
> git pull
> ```
>
> 然後重新執行 `/plugin update cc-sync@cc-sync`。

## 設定

安裝後選擇輸出適配器：

```bash
# 本地檔案（直接寫入 Obsidian 筆記庫）
cc-sync setup --adapter=local --path=~/Documents/Obsidian/MyVault

# FNS（Fast Note Sync 伺服器）
cc-sync setup '{"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}'

# Git（自動提交到 git 倉庫）
cc-sync setup --adapter=git --repo-path=~/obsidian-vault

# Server（推送到 cc-sync-server）
cc-sync setup --adapter=server --url=http://localhost:8080 --token=your-token
```

設定完成後重新啟動 Claude Code，即可自動同步每次對話。

## 輸出適配器

| 適配器 | 模式 | 說明 |
|--------|------|------|
| `local` | Lite | 直接寫 .md 檔案到本地目錄 |
| `fns` | Lite | 透過 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) REST API 推送 |
| `git` | Lite | 寫 .md + 自動 git commit（可選 push） |
| `server` | Server | 推送到 [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) 實現多裝置同步 |

## 命令

| 命令 | 說明 |
|------|------|
| `/cc-sync:setup` | 設定輸出適配器 |
| `/cc-sync:web` | 開啟 Web 管理面板 |
| `/cc-sync:export` | 批次匯出所有未同步的對話 |
| `/cc-sync:test` | 測試適配器連通性 |
| `/cc-sync:run` | 手動同步最新對話 |
| `/cc-sync:status` | 檢視設定和同步狀態 |
| `/cc-sync:log` | 檢視最近同步日誌 |

## 運作原理

```
CC Stop hook → 解析 JSONL → 按工作階段去重 → 輸出適配器 → 知識庫
```

- 從 `.jsonl` 檔案解析對話（而非 `.md`），取得結構化資料
- 按 `sessionId` 去重 — 同一工作階段多次儲存只同步一次
- 以對話標題命名檔案：`{sync_dir}/{標題}.md`（預設目錄：`cc-sync/`）
- 標題衝突自動編號：`標題.md`、`標題 (2).md`、`標題 (3).md`
- 每則訊息帶時間戳：`### User [14:30]`
- 透過內容雜湊追蹤變更 — 更新覆蓋原檔案，不產生重複

外掛只負責同步。筆記的整理交給你的筆記工具處理。

## 多裝置

**Lite 模式：** 每台裝置安裝外掛，推送到同一個 FNS 伺服器或 git 倉庫。

**Server 模式：** 每台裝置安裝外掛，全部推送到一個 [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) 實例。伺服器負責去重、儲存和下游分發。

## 需求

- Python 3.8+
- Jinja2（`pip install jinja2`，pip 安裝時自動包含）

## 授權

MIT
