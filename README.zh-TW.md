[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-obsidian-sync

透過 [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) 將 Claude Code 對話自動同步到 Obsidian。

對話原文直接推送到你的 Obsidian 筆記庫 — 不做額外處理，不預設目錄結構。只做同步。

## 安裝

```
/install github:Vincent-Leon/cc-obsidian-sync
```

或本地安裝：

```
claude --plugin-dir /path/to/cc-obsidian-sync
```

## 設定

安裝後執行：

```
/cc-sync:setup
```

支援直接貼上 FNS JSON 設定快速完成配置：

```
/cc-sync:setup {"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}
```

JSON 可從 FNS 管理面板（筆記庫頁面）直接複製。

也可以不帶參數執行 `/cc-sync:setup` 進入互動式設定。

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
CC Stop hook → 讀取最新對話 → 推送到 FNS → Obsidian 同步
```

對話儲存到 `{sync_dir}/{date}_{title}.md`（預設目錄：`cc-sync/`）。

外掛只負責同步。筆記的整理（目錄、標籤、日記、Dataview 查詢等）交給 Obsidian 處理。

## 多裝置

在每台裝置上安裝，所有裝置推送到同一個 FNS 伺服器。你的 Obsidian 用戶端透過 FNS 即時同步接收更新。

## 需求

- Python 3.8+
- 已部署的 [FNS 伺服器](https://github.com/haierkeys/fast-note-sync-service) 並設定好 Obsidian 外掛

## 授權

MIT
