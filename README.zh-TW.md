[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-obsidian-sync

透過 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) 將 Claude Code 對話自動同步到 Obsidian。

對話從 JSONL 解析，按工作階段去重，帶有每則訊息的時間戳推送到你的 Obsidian 筆記庫。不做額外處理，不預設目錄結構。只做同步。

## 安裝

新增外掛市場並安裝：

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-obsidian-sync.git
/plugin install cc-obsidian-sync@cc-obsidian-sync
```

## 更新與移除

透過市場安裝的外掛，更新和移除都透過外掛系統管理：

```bash
# 更新市場目錄（拉取最新版本資訊）
/plugin marketplace update cc-obsidian-sync

# 更新已安裝的外掛到最新版本
/plugin update cc-obsidian-sync@cc-obsidian-sync

# 移除外掛
/plugin uninstall cc-obsidian-sync@cc-obsidian-sync

# 移除整個市場（同時移除其下所有外掛）
/plugin marketplace remove cc-obsidian-sync
```

> **注意：** 更新後需要重新啟動 Claude Code 才能載入新版外掛程式碼。

也可以透過 `/plugin` → **Installed** / **Marketplaces** 分頁進行互動式管理。

## 設定

安裝後執行：

```
/cc-sync:setup {"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}
```

JSON 可從 FNS 管理面板（筆記庫頁面）直接複製。

設定完成後重新啟動 Claude Code，即可自動同步每次對話。

## 命令

| 命令 | 說明 |
|------|------|
| `/cc-sync:setup` | 設定 FNS 連線 |
| `/cc-sync:export` | 批次匯出所有未同步的對話 |
| `/cc-sync:test` | 測試 API 連通性 |
| `/cc-sync:run` | 手動同步最新對話 |
| `/cc-sync:status` | 檢視設定和同步狀態 |
| `/cc-sync:log` | 檢視最近同步日誌 |

## 運作原理

```
CC Stop hook → 解析 JSONL → 按工作階段去重 → 推送到 FNS → Obsidian 同步
```

- 從 `.jsonl` 檔案解析對話（而非 `.md`），取得結構化資料
- 按 `sessionId` 去重 — 同一工作階段多次儲存只同步一次
- 以對話標題命名檔案：`{sync_dir}/{標題}.md`（預設目錄：`cc-sync/`）
- 標題衝突自動編號：`標題.md`、`標題 (2).md`、`標題 (3).md`
- 每則訊息帶時間戳：`### User [14:30]`
- 透過內容雜湊追蹤變更 — 更新覆蓋原檔案，不產生重複

外掛只負責同步。筆記的整理（目錄、標籤、日記、Dataview 查詢等）交給 Obsidian 處理。

## 多裝置

在每台裝置上安裝，所有裝置推送到同一個 FNS 伺服器。你的 Obsidian 用戶端透過 FNS 即時同步接收更新。

## 需求

- Python 3.8+
- 已部署的 [FNS 伺服器](https://github.com/haierkeys/fast-note-sync-service) 並設定好 Obsidian 外掛

## 授權

MIT
