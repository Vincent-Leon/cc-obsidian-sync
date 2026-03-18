#!/usr/bin/env python3
"""
cc-sync.py — Claude Code → Obsidian sync engine (via Fast Note Sync)

Part of the cc-obsidian-sync plugin. Zero external dependencies.
Only syncs conversation files — no Obsidian-specific processing.

Subcommands:
  setup   Interactive FNS configuration wizard
  hook    Called by CC Stop hook (stdin = hook JSON)
  run     Manual one-shot sync of latest conversation
  test    Test FNS API connectivity
  status  Show current configuration and sync state
  log     Show recent sync log entries
  export  Bulk export all unsynchronized conversations
  ingest  Manually ingest all JSONL files into the database
  web     Launch the session management dashboard
"""

import base64, hashlib, json, os, re, sqlite3, sys
import urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────
HOME         = Path.home()
CONFIG_DIR   = HOME / ".config" / "cc-sync"
CONFIG_FILE  = CONFIG_DIR / "config.json"
DB_FILE      = CONFIG_DIR / "cc-sync.db"
LOG_FILE     = CONFIG_DIR / "sync.log"
CC_LOGS      = HOME / ".claude" / "conversation-logs"

# ── i18n ─────────────────────────────────────────────────────
STRINGS = {
    "en": {
        "setup_title":       "CC Obsidian Sync — Setup Wizard",
        "detected_json":     "Detected FNS configuration JSON",
        "tip_paste":         "Tip: paste FNS JSON config for quick setup, or press Enter for manual config",
        "tip_paste_hint":    "(from FNS management panel → repo → copy config)",
        "prompt_paste":      "Paste FNS JSON (or Enter to skip)",
        "json_loaded":       "FNS config loaded",
        "fns_api_config":    "FNS API Configuration",
        "fns_api_hint":      "(Get these from your FNS management panel → repository → viewConfig)",
        "prompt_url":        "FNS server URL",
        "prompt_token":      "API Token",
        "prompt_vault":       "Vault",
        "prompt_device":     "Device name",
        "prompt_sync_dir":   "Sync directory in vault",
        "prompt_lang":       "Language / 语言",
        "config_saved":      "Config saved to",
        "next_steps":        "Next: restart Claude Code to activate the Stop hook,\n  then run /cc-sync:test to verify the FNS connection.",
        "not_configured":    "Not configured. Run /cc-sync:setup",
        "synced":            "Synced",
        "files":             "file(s)",
        "nothing_new":       "Nothing new",
        "upload_ok":         "Upload: OK",
        "upload_failed":     "Upload: Failed",
        "check_config":      "Check config",
        "or_reconfigure":    "Or try /cc-sync:setup to reconfigure",
        "processed":         "Processed",
        "conversations":     "conversation(s)",
        "recent_activity":   "Recent activity:",
        "no_log":            "No log yet.",
        "select_lang":       "Select language",
        "export_scanning":   "Scanning conversations...",
        "export_found":      "Found",
        "export_new":        "new",
        "export_skipped":    "already synced",
        "export_progress":   "Exporting",
        "export_done":       "Export complete",
        "export_failed_n":   "failed",
        "export_no_new":     "All conversations already synced.",
    },
    "zh-CN": {
        "setup_title":       "CC Obsidian Sync — 配置向导",
        "detected_json":     "检测到 FNS 配置 JSON",
        "tip_paste":         "提示：粘贴 FNS JSON 配置快速设置，或按 Enter 手动配置",
        "tip_paste_hint":    "（从 FNS 管理面板 → 笔记库 → 复制配置）",
        "prompt_paste":      "粘贴 FNS JSON（或按 Enter 跳过）",
        "json_loaded":       "FNS 配置已加载",
        "fns_api_config":    "FNS API 配置",
        "fns_api_hint":      "（从 FNS 管理面板 → 笔记库 → 查看配置获取）",
        "prompt_url":        "FNS 服务器地址",
        "prompt_token":      "API Token",
        "prompt_vault":       "笔记库名称",
        "prompt_device":     "设备名称",
        "prompt_sync_dir":   "笔记库中的同步目录",
        "prompt_lang":       "Language / 语言",
        "config_saved":      "配置已保存到",
        "next_steps":        "下一步：重启 Claude Code 以激活 Stop hook，\n  然后运行 /cc-sync:test 验证 FNS 连接。",
        "not_configured":    "未配置，请运行 /cc-sync:setup",
        "synced":            "已同步",
        "files":             "个文件",
        "nothing_new":       "没有新内容",
        "upload_ok":         "上传：成功",
        "upload_failed":     "上传：失败",
        "check_config":      "检查配置",
        "or_reconfigure":    "或尝试 /cc-sync:setup 重新配置",
        "processed":         "已处理",
        "conversations":     "个对话",
        "recent_activity":   "最近活动：",
        "no_log":            "暂无日志。",
        "select_lang":       "选择语言",
        "export_scanning":   "正在扫描对话...",
        "export_found":      "发现",
        "export_new":        "条新对话",
        "export_skipped":    "条已同步",
        "export_progress":   "导出中",
        "export_done":       "导出完成",
        "export_failed_n":   "条失败",
        "export_no_new":     "所有对话均已同步。",
    },
    "zh-TW": {
        "setup_title":       "CC Obsidian Sync — 設定精靈",
        "detected_json":     "偵測到 FNS 設定 JSON",
        "tip_paste":         "提示：貼上 FNS JSON 設定快速完成配置，或按 Enter 手動設定",
        "tip_paste_hint":    "（從 FNS 管理面板 → 筆記庫 → 複製設定）",
        "prompt_paste":      "貼上 FNS JSON（或按 Enter 跳過）",
        "json_loaded":       "FNS 設定已載入",
        "fns_api_config":    "FNS API 設定",
        "fns_api_hint":      "（從 FNS 管理面板 → 筆記庫 → 檢視設定取得）",
        "prompt_url":        "FNS 伺服器位址",
        "prompt_token":      "API Token",
        "prompt_vault":       "筆記庫名稱",
        "prompt_device":     "裝置名稱",
        "prompt_sync_dir":   "筆記庫中的同步目錄",
        "prompt_lang":       "Language / 語言",
        "config_saved":      "設定已儲存到",
        "next_steps":        "下一步：重新啟動 Claude Code 以啟用 Stop hook，\n  然後執行 /cc-sync:test 驗證 FNS 連線。",
        "not_configured":    "未設定，請執行 /cc-sync:setup",
        "synced":            "已同步",
        "files":             "個檔案",
        "nothing_new":       "沒有新內容",
        "upload_ok":         "上傳：成功",
        "upload_failed":     "上傳：失敗",
        "check_config":      "檢查設定",
        "or_reconfigure":    "或嘗試 /cc-sync:setup 重新設定",
        "processed":         "已處理",
        "conversations":     "個對話",
        "recent_activity":   "最近活動：",
        "no_log":            "暫無日誌。",
        "select_lang":       "選擇語言",
        "export_scanning":   "正在掃描對話...",
        "export_found":      "發現",
        "export_new":        "筆新對話",
        "export_skipped":    "筆已同步",
        "export_progress":   "匯出中",
        "export_done":       "匯出完成",
        "export_failed_n":   "筆失敗",
        "export_no_new":     "所有對話均已同步。",
    },
}

LANG_NAMES = {"en": "English", "zh-CN": "简体中文", "zh-TW": "繁體中文"}

def get_lang():
    cfg = cfg_load()
    return (cfg or {}).get("lang", "en")

def t(key):
    lang = get_lang()
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))

# ── Logging ──────────────────────────────────────────────────
def log(msg, echo=False):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    if echo:
        print(f"  {msg}")

# ── Config ───────────────────────────────────────────────────
def cfg_load():
    return json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else None

def cfg_save(c):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(c, indent=2, ensure_ascii=False))

# ── Database ─────────────────────────────────────────────────
def db_connect():
    """Open (or create) the SQLite database. Returns a connection."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_FILE), timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    db_init_schema(db)
    return db

def db_init_schema(db):
    """Create tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            session_id    TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            date          TEXT NOT NULL,
            project       TEXT DEFAULT '',
            project_path  TEXT DEFAULT '',
            message_count INTEGER DEFAULT 0,
            word_count    INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'unsynced'
                          CHECK(status IN ('unsynced','synced','ignored')),
            content_hash  TEXT,
            synced_path   TEXT,
            synced_at     TEXT,
            source_file   TEXT,
            source_mtime  REAL,
            created_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
            updated_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_conv_status ON conversations(status);
        CREATE INDEX IF NOT EXISTS idx_conv_date   ON conversations(date DESC);

        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE,
            seq        INTEGER NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            time_str   TEXT DEFAULT '',
            is_context INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, seq);

        CREATE TABLE IF NOT EXISTS extractions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE,
            summary      TEXT,
            result_json  TEXT,
            llm_model    TEXT,
            cost_usd     REAL DEFAULT 0,
            created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_extractions_session ON extractions(session_id);

        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);
    """)
    # FTS5 for dashboard search (title + project)
    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                session_id UNINDEXED, title, project,
                content='conversations', content_rowid='rowid'
            )
        """)
        db.executescript("""
            CREATE TRIGGER IF NOT EXISTS conv_fts_ai AFTER INSERT ON conversations BEGIN
                INSERT INTO conversations_fts(rowid, session_id, title, project)
                VALUES (new.rowid, new.session_id, new.title, new.project);
            END;
            CREATE TRIGGER IF NOT EXISTS conv_fts_ad AFTER DELETE ON conversations BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, session_id, title, project)
                VALUES ('delete', old.rowid, old.session_id, old.title, old.project);
            END;
            CREATE TRIGGER IF NOT EXISTS conv_fts_au AFTER UPDATE ON conversations BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, session_id, title, project)
                VALUES ('delete', old.rowid, old.session_id, old.title, old.project);
                INSERT INTO conversations_fts(rowid, session_id, title, project)
                VALUES (new.rowid, new.session_id, new.title, new.project);
            END;
        """)
    except Exception:
        pass  # FTS5 not available on this build; search falls back to LIKE
    db.commit()

# ── Helpers ──────────────────────────────────────────────────
def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(8192), b""): h.update(c)
    return h.hexdigest()

def md5_str(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def san(name):
    """Sanitize a string for use as a filename. Keeps CJK chars, replaces illegal chars with -."""
    s = re.sub(r'[<>:"/\\|?*]', '-', name)       # illegal filename chars
    s = re.sub(r'[\n\r\t]', ' ', s)                # newlines to space
    s = re.sub(r'\s+', ' ', s).strip()             # collapse whitespace
    s = s.strip('-. ')
    return s[:50] or "untitled"

# ── FNS API ──────────────────────────────────────────────────
def fns_call(cfg, endpoint, data, method="POST"):
    """Call FNS REST API. Returns (ok, response_or_error)."""
    api = cfg["fns_api"]
    url = api["url"].rstrip("/") + endpoint
    body = json.dumps(data).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f'Bearer {api["token"]}',
        "token": api["token"],
    }
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
            if isinstance(resp, dict) and resp.get("status") is False:
                return False, f"FNS error {resp.get('code')}: {resp.get('message', '')}"
            return True, resp
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return False, str(e)

def fns_upload(cfg, path, content):
    """Create or update a note via FNS REST API (POST /api/note)."""
    api = cfg["fns_api"]
    vault = api.get("vault", "")
    payload = {
        "vault": vault,
        "path": path,
        "content": content,
    }
    return fns_call(cfg, "/api/note", payload)

# ── JSONL Parsing ───────────────────────────────────────────
def parse_jsonl(jsonl_path):
    """Parse a conversation JSONL file into structured data.

    Returns dict with keys:
        session_id: str
        date: str (YYYY-MM-DD)
        project: str (cwd from first message)
        messages: list of {role, content, time_str, is_context}
        title: str (sanitized first real user message)
    Returns None if file is empty or has no real messages.
    """
    messages = []
    session_id = None
    project = None
    first_date = None

    for line in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        if session_id is None:
            session_id = obj.get("sessionId", "")
        if project is None:
            project = obj.get("cwd", "")

        if obj.get("isMeta"):
            continue

        msg = obj.get("message", {})
        content_parts = msg.get("content", "")
        role = msg.get("role", msg_type)

        if isinstance(content_parts, list):
            texts = [p.get("text", "") for p in content_parts if isinstance(p, dict) and p.get("type") == "text"]
            text = "\n".join(t for t in texts if t)
        elif isinstance(content_parts, str):
            text = content_parts
        else:
            continue

        if not text.strip():
            continue
        stripped_text = text.strip()
        if re.match(r'^<(local-command-|command-name>|command-message>)', stripped_text):
            continue

        is_context = bool(re.match(r'^<(ide_selection|system-reminder)', stripped_text))

        ts_str = obj.get("timestamp", "")
        time_str = ""
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                local_dt = dt.astimezone()
                time_str = local_dt.strftime("%H:%M")
                if first_date is None:
                    first_date = local_dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass

        messages.append({"role": role, "content": text, "time_str": time_str, "is_context": is_context})

    if not messages or not session_id:
        return None

    title = "untitled"
    for m in messages:
        if m["role"] == "user" and not m.get("is_context"):
            raw = re.sub(r'[#*`\[\]]', '', m["content"]).strip()
            raw = raw.split("\n")[0].strip()
            if raw:
                title = san(raw)
                break

    return {
        "session_id": session_id,
        "date": first_date or datetime.now().strftime("%Y-%m-%d"),
        "project": project or "",
        "messages": messages,
        "title": title,
    }


def format_conversation(parsed):
    """Generate markdown with per-message timestamps from parsed JSONL data."""
    lines = []
    lines.append(f"# {parsed['title']}")
    lines.append("")
    lines.append(f"> Session: {parsed['session_id']}")
    lines.append(f"> Date: {parsed['date']}")
    if parsed["project"]:
        lines.append(f"> Project: {parsed['project']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in parsed["messages"]:
        if msg.get("is_context"):
            continue
        role_label = "User" if msg["role"] == "user" else "Assistant"
        ts = f" [{msg['time_str']}]" if msg["time_str"] else ""
        lines.append(f"### {role_label}{ts}")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")

    return "\n".join(lines)


def make_title_from_md(md_path):
    """Fallback: extract title from .md file when JSONL is unavailable."""
    content = md_path.read_text(encoding="utf-8", errors="replace")
    in_user = False
    for ln in content.strip().split("\n"):
        stripped = ln.strip()
        if re.match(r'^##\s+USER\s*$', stripped, re.IGNORECASE) or "**User:**" in stripped:
            in_user = True
            continue
        if in_user:
            if stripped and not stripped.startswith(("---", "##", "**")):
                return san(re.sub(r'[#*`\[\]]', '', stripped).strip())
    return "untitled"


# ── Pipeline ─────────────────────────────────────────────────
def find_all_jsonl():
    """Return all conversation .jsonl files sorted by mtime (oldest first)."""
    if not CC_LOGS.exists():
        return []
    files = [f for f in CC_LOGS.glob("conversation_*.jsonl") if not f.is_symlink()]
    return sorted(files, key=lambda f: f.stat().st_mtime)


def find_latest_jsonl():
    """Return the most recently modified conversation .jsonl file."""
    if not CC_LOGS.exists():
        return None
    files = [f for f in CC_LOGS.glob("conversation_*.jsonl") if not f.is_symlink()]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


# ── Ingest (JSONL → DB) ─────────────────────────────────────
def ingest_jsonl(db, jsonl_path):
    """Parse a JSONL file and upsert into the database. Returns session_id or None."""
    fname = jsonl_path.name
    mtime = jsonl_path.stat().st_mtime

    # Fast path: already ingested this exact file version
    row = db.execute(
        "SELECT session_id FROM conversations WHERE source_file = ? AND source_mtime = ?",
        (fname, mtime)
    ).fetchone()
    if row:
        return row["session_id"]

    parsed = parse_jsonl(jsonl_path)
    if not parsed or len(parsed["messages"]) < 2:
        return None

    sid = parsed["session_id"]
    msgs = parsed["messages"]
    content_hash = md5_str(json.dumps(msgs, ensure_ascii=False))
    word_count = sum(len(m["content"].split()) for m in msgs)
    project_name = parsed["project"].split("/")[-1] if parsed["project"] else ""
    now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    existing = db.execute(
        "SELECT content_hash, status, source_mtime FROM conversations WHERE session_id = ?",
        (sid,)
    ).fetchone()

    if existing:
        # Only update if this file is newer
        if existing["source_mtime"] and mtime <= existing["source_mtime"]:
            return sid
        new_status = existing["status"]
        if existing["status"] != "ignored" and existing["content_hash"] != content_hash:
            new_status = "unsynced"
        db.execute("""
            UPDATE conversations SET
                title=?, date=?, project=?, project_path=?,
                message_count=?, word_count=?, content_hash=?,
                source_file=?, source_mtime=?, updated_at=?, status=?
            WHERE session_id=?
        """, (parsed["title"], parsed["date"], project_name,
              parsed["project"], len(msgs), word_count, content_hash,
              fname, mtime, now_ts, new_status, sid))
    else:
        db.execute("""
            INSERT INTO conversations
            (session_id, title, date, project, project_path, message_count, word_count,
             content_hash, source_file, source_mtime, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, parsed["title"], parsed["date"], project_name,
              parsed["project"], len(msgs), word_count, content_hash,
              fname, mtime, now_ts, now_ts))

    # Replace messages for this session
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    db.executemany(
        "INSERT INTO messages (session_id, seq, role, content, time_str, is_context) VALUES (?,?,?,?,?,?)",
        [(sid, i, m["role"], m["content"], m["time_str"], int(m.get("is_context", False)))
         for i, m in enumerate(msgs)]
    )
    db.commit()
    return sid


def ingest_all(db):
    """Ingest all JSONL files into the database. Returns count of processed sessions."""
    count = 0
    for jf in find_all_jsonl():
        if ingest_jsonl(db, jf):
            count += 1
    return count


def ingest_latest(db):
    """Ingest only the most recent JSONL file. Returns session_id or None."""
    jf = find_latest_jsonl()
    return ingest_jsonl(db, jf) if jf else None


# ── Sync (DB → FNS) ─────────────────────────────────────────
def resolve_path_db(db, sync_dir, title, session_id):
    """Determine FNS path for a session, using DB for conflict detection."""
    # Reuse existing path if already synced
    row = db.execute(
        "SELECT synced_path FROM conversations WHERE session_id = ? AND synced_path IS NOT NULL",
        (session_id,)
    ).fetchone()
    if row:
        return row["synced_path"]

    # Collect all paths in use
    used = {r["synced_path"] for r in db.execute(
        "SELECT synced_path FROM conversations WHERE synced_path IS NOT NULL"
    ).fetchall()}

    base = f"{sync_dir}/{title}.md"
    if base not in used:
        return base
    for i in range(2, 10000):
        candidate = f"{sync_dir}/{title} ({i}).md"
        if candidate not in used:
            return candidate
    return f"{sync_dir}/{title} ({session_id[:8]}).md"


def sync_session(cfg, db, session_id, echo=False):
    """Sync a single session from DB to FNS. Returns True/None/False."""
    row = db.execute(
        "SELECT * FROM conversations WHERE session_id = ? AND status = 'unsynced'",
        (session_id,)
    ).fetchone()
    if not row:
        return None  # already synced or ignored

    # Reconstruct parsed dict from DB for format_conversation()
    msgs = db.execute(
        "SELECT role, content, time_str, is_context FROM messages WHERE session_id = ? ORDER BY seq",
        (session_id,)
    ).fetchall()
    parsed = {
        "session_id": session_id,
        "date": row["date"],
        "project": row["project_path"] or row["project"],
        "title": row["title"],
        "messages": [{"role": m["role"], "content": m["content"],
                      "time_str": m["time_str"], "is_context": bool(m["is_context"])} for m in msgs],
    }

    content = format_conversation(parsed)
    sync_dir = cfg.get("sync_dir", "cc-sync")
    rel_path = resolve_path_db(db, sync_dir, row["title"], session_id)

    ok, msg = fns_upload(cfg, rel_path, content)
    icon = "\u2705" if ok else "\u274c"
    log(f"{icon} {rel_path}", echo=echo)

    if ok:
        now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        db.execute("""
            UPDATE conversations SET status='synced', synced_path=?, synced_at=?, updated_at=?
            WHERE session_id=?
        """, (rel_path, now_ts, now_ts, session_id))
        db.commit()
        return True
    return False


# ── Subcommands ──────────────────────────────────────────────

def parse_fns_json(text):
    """Parse FNS JSON config block: {"api": "...", "apiToken": "...", "vault": "..."}"""
    try:
        obj = json.loads(text)
        if "api" in obj and "apiToken" in obj:
            return obj
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def prompt_lang(cfg):
    """Prompt user to select language. Returns chosen lang code."""
    print(f"\n  — {t('select_lang')} —\n")
    langs = list(LANG_NAMES.items())
    for i, (code, name) in enumerate(langs, 1):
        cur = " *" if code == cfg.get("lang", "en") else ""
        print(f"    {i}. {name}{cur}")
    choice = input(f"\n  [{cfg.get('lang', 'en')}]: ").strip()
    if choice in ("1", "2", "3"):
        return langs[int(choice) - 1][0]
    if choice in LANG_NAMES:
        return choice
    return cfg.get("lang", "en")


def cmd_setup():
    """Non-interactive setup. Accepts FNS JSON or individual --key=value args."""
    cfg = cfg_load() or {
        "lang": "en",
        "device_name": os.uname().nodename.split(".")[0],
        "sync_dir": "cc-sync",
        "fns_api": {"url": "", "token": "", "vault": ""},
    }

    args = sys.argv[2:]
    args_text = " ".join(args).strip()

    fns_json = parse_fns_json(args_text) if args_text else None
    if fns_json:
        cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
        cfg["fns_api"]["token"] = fns_json["apiToken"]
        cfg["fns_api"]["vault"] = fns_json.get("vault", "")

    for arg in args:
        if arg.startswith("--"):
            k, _, v = arg[2:].partition("=")
            if k == "url":       cfg["fns_api"]["url"] = v
            elif k == "token":   cfg["fns_api"]["token"] = v
            elif k == "vault":   cfg["fns_api"]["vault"] = v
            elif k == "lang":    cfg["lang"] = v
            elif k == "device":  cfg["device_name"] = v
            elif k == "sync-dir": cfg["sync_dir"] = v

    CC_LOGS.mkdir(parents=True, exist_ok=True)
    cfg_save(cfg)

    api = cfg["fns_api"]
    print(f"\n  CC Obsidian Sync — Config\n")
    print(f"  Language:  {LANG_NAMES.get(cfg.get('lang', 'en'), 'English')}")
    print(f"  Device:    {cfg['device_name']}")
    print(f"  API:       {api.get('url')}")
    print(f"  Vault:     {api.get('vault')}")
    print(f"  Token:     {api['token'][:12]}..." if api.get('token') else "  Token:     (not set)")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'cc-sync')}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"\n  \u2705 {t('config_saved')} {CONFIG_FILE}")
    print(f"\n  {t('next_steps')}\n")


def cmd_hook():
    """Stop hook entry point. Pushes latest conversation to FNS."""
    cfg = cfg_load()
    if not cfg or not cfg.get("fns_api", {}).get("token"):
        log("Not configured — run /cc-sync:setup"); return 0
    db = db_connect()
    sid = ingest_latest(db)
    if sid:
        result = sync_session(cfg, db, sid)
        if result:
            log(f"Synced 1 file(s) (device={cfg.get('device_name')})")
    db.close()


def cmd_run():
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1
    print(f"  Device: {cfg['device_name']}\n")
    db = db_connect()
    sid = ingest_latest(db)
    if sid:
        result = sync_session(cfg, db, sid, echo=True)
        if result is True:
            print(f"\n  \u2705 {t('synced')} 1 {t('files')}")
        elif result is None:
            print(f"\n  \U0001f4ed {t('nothing_new')}")
        else:
            print(f"\n  \u274c {t('upload_failed')}")
    else:
        print(f"\n  \U0001f4ed {t('nothing_new')}")
    db.close()


def cmd_test():
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1

    api = cfg.get("fns_api", {})
    print(f"  URL:   {api.get('url')}")
    print(f"  Vault: {api.get('vault')}")
    print(f"  Token: {api.get('token', '')[:12]}...\n")

    sync_dir = cfg.get("sync_dir", "cc-sync")
    test = f"CC-Sync connectivity test.\nDate: {datetime.now().isoformat()}\nSafe to delete.\n"
    ok, msg = fns_upload(cfg, f"{sync_dir}/.cc-sync-test.md", test)
    if ok:
        print(f"  \u2705 {t('upload_ok')}")
    else:
        print(f"  \u274c {t('upload_failed')}")
        print(f"  Error: {msg}")
        print(f"\n  \U0001f4a1 {t('check_config')}: {CONFIG_FILE}")
        print(f"     {t('or_reconfigure')}")


def cmd_status():
    cfg = cfg_load()
    if not cfg:
        print(f"  {t('not_configured')}"); return 1

    db = db_connect()
    stats = {}
    for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
        stats[row["status"]] = row["n"]
    total = sum(stats.values())
    db.close()

    lang_name = LANG_NAMES.get(cfg.get("lang", "en"), "English")
    print(f"  Language:  {lang_name}")
    print(f"  Device:    {cfg.get('device_name')}")
    api = cfg.get("fns_api", {})
    print(f"  FNS URL:   {api.get('url')}")
    print(f"  Vault:     {api.get('vault')}")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'cc-sync')}")
    print(f"  {t('processed')}  {total} {t('conversations')}")
    if stats:
        parts = []
        if stats.get("synced"):    parts.append(f"synced: {stats['synced']}")
        if stats.get("unsynced"):  parts.append(f"unsynced: {stats['unsynced']}")
        if stats.get("ignored"):   parts.append(f"ignored: {stats['ignored']}")
        print(f"  Status:    {', '.join(parts)}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Database:  {DB_FILE}")
    print(f"  Log:       {LOG_FILE}")

    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        print(f"\n  {t('recent_activity')}")
        for l in lines[-3:]:
            print(f"    {l}")


def cmd_export():
    """Scan all conversations and sync any that haven't been uploaded yet."""
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1

    print(f"  {t('export_scanning')}")
    db = db_connect()
    ingest_all(db)

    rows = db.execute(
        "SELECT session_id, title FROM conversations WHERE status = 'unsynced' ORDER BY date"
    ).fetchall()
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    synced = total - len(rows)

    print(f"  {t('export_found')} {len(rows)} {t('export_new')}, {synced} {t('export_skipped')}\n")

    if not rows:
        print(f"  {t('export_no_new')}")
        db.close()
        return 0

    ok_count, fail_count = 0, 0
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {t('export_progress')} {row['title']}...", end="", flush=True)
        result = sync_session(cfg, db, row["session_id"])
        if result is True:
            ok_count += 1
            print(" \u2705")
        elif result is None:
            print(" -")
        else:
            fail_count += 1
            print(" \u274c")

    print(f"\n  {t('export_done')}: {ok_count} {t('files')}", end="")
    if fail_count:
        print(f", {fail_count} {t('export_failed_n')}", end="")
    print()
    db.close()


def cmd_ingest():
    """Manually ingest all JSONL files into the database."""
    db = db_connect()
    ingest_all(db)
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    stats = {}
    for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
        stats[row["status"]] = row["n"]
    print(f"  Database: {DB_FILE}")
    print(f"  Total conversations: {total}")
    if stats:
        parts = []
        if stats.get("synced"):    parts.append(f"synced: {stats['synced']}")
        if stats.get("unsynced"):  parts.append(f"unsynced: {stats['unsynced']}")
        if stats.get("ignored"):   parts.append(f"ignored: {stats['ignored']}")
        print(f"  Status: {', '.join(parts)}")
    db.close()


def cmd_log():
    if not LOG_FILE.exists(): print(f"  {t('no_log')}"); return 0
    for l in LOG_FILE.read_text().strip().split("\n")[-30:]:
        print(l)


# ── Web Dashboard ────────────────────────────────────────────
def cmd_web():
    """Launch the session management dashboard on localhost."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    # Parse --port and --no-browser
    port = 8765
    open_browser = True
    for arg in sys.argv[2:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--no-browser":
            open_browser = False

    db = db_connect()
    print(f"  Ingesting conversations...")
    ingest_all(db)
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    print(f"  {total} conversations in database.\n")

    html_path = Path(__file__).parent / "dashboard.html"

    def json_response(handler, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(body)

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/dashboard":
                if not html_path.exists():
                    self.send_error(404, "dashboard.html not found")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_path.read_bytes())

            elif self.path.startswith("/api/conversations"):
                # Parse query params
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                status_filter = qs.get("status", [None])[0]
                query = qs.get("q", [None])[0]
                sort = qs.get("sort", ["date"])[0]
                order = qs.get("order", ["desc"])[0]
                limit = int(qs.get("limit", [200])[0])
                offset = int(qs.get("offset", [0])[0])

                if query:
                    # FTS5 search
                    try:
                        rows = db.execute("""
                            SELECT c.* FROM conversations c
                            JOIN conversations_fts f ON c.session_id = f.session_id
                            WHERE conversations_fts MATCH ?
                            ORDER BY c.date DESC LIMIT ? OFFSET ?
                        """, (query, limit, offset)).fetchall()
                    except Exception:
                        # FTS5 not available, fall back to LIKE
                        rows = db.execute("""
                            SELECT * FROM conversations
                            WHERE title LIKE ? OR project LIKE ?
                            ORDER BY date DESC LIMIT ? OFFSET ?
                        """, (f"%{query}%", f"%{query}%", limit, offset)).fetchall()
                elif status_filter:
                    rows = db.execute(f"""
                        SELECT * FROM conversations WHERE status = ?
                        ORDER BY {sort} {'ASC' if order == 'asc' else 'DESC'}
                        LIMIT ? OFFSET ?
                    """, (status_filter, limit, offset)).fetchall()
                else:
                    rows = db.execute(f"""
                        SELECT * FROM conversations
                        ORDER BY {sort} {'ASC' if order == 'asc' else 'DESC'}
                        LIMIT ? OFFSET ?
                    """, (limit, offset)).fetchall()

                json_response(self, [dict(r) for r in rows])

            elif self.path == "/api/stats":
                stats = {}
                for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
                    stats[row["status"]] = row["n"]
                stats["total"] = sum(stats.values())
                json_response(self, stats)

            elif self.path == "/api/config":
                c = cfg_load() or {}
                api = c.get("fns_api", {})
                token = api.get("token", "")
                json_response(self, {
                    "lang": c.get("lang", "en"),
                    "device_name": c.get("device_name", ""),
                    "sync_dir": c.get("sync_dir", "cc-sync"),
                    "fns_api": {
                        "url": api.get("url", ""),
                        "token_preview": (token[:12] + "...") if len(token) > 12 else token,
                        "token_set": bool(token),
                        "vault": api.get("vault", ""),
                    }
                })

            elif self.path.startswith("/api/log"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                limit = int(qs.get("limit", [100])[0])
                lines = []
                if LOG_FILE.exists():
                    all_lines = LOG_FILE.read_text().strip().split("\n")
                    if all_lines != [""]:
                        lines = all_lines[-limit:]
                json_response(self, {"lines": list(reversed(lines)), "total": len(lines)})

            elif self.path == "/api/info":
                json_response(self, {
                    "version": "0.3.0",
                    "db_path": str(DB_FILE),
                    "config_path": str(CONFIG_FILE),
                    "log_path": str(LOG_FILE),
                })

            else:
                self.send_error(404)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}
            except (json.JSONDecodeError, ValueError):
                json_response(self, {"error": "Invalid JSON"}, 400)
                return

            sid = body.get("session_id", "")
            now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            if self.path == "/api/sync":
                cfg = cfg_load()
                if not cfg or not cfg.get("fns_api", {}).get("token"):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                result = sync_session(cfg, db, sid)
                if result is True:
                    json_response(self, {"ok": True, "message": "Synced"})
                elif result is None:
                    json_response(self, {"ok": False, "message": "Not unsynced"}, 400)
                else:
                    json_response(self, {"ok": False, "message": "Upload failed"}, 500)

            elif self.path == "/api/resync":
                cfg = cfg_load()
                if not cfg or not cfg.get("fns_api", {}).get("token"):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                db.execute(
                    "UPDATE conversations SET status='unsynced', updated_at=? WHERE session_id=?",
                    (now_ts, sid))
                db.commit()
                result = sync_session(cfg, db, sid)
                ok = result is True
                json_response(self, {"ok": ok, "message": "Resynced" if ok else "Failed"})

            elif self.path == "/api/ignore":
                db.execute(
                    "UPDATE conversations SET status='ignored', updated_at=? WHERE session_id=?",
                    (now_ts, sid))
                db.commit()
                json_response(self, {"ok": True, "message": "Ignored"})

            elif self.path == "/api/unignore":
                db.execute(
                    "UPDATE conversations SET status='unsynced', updated_at=? WHERE session_id=? AND status='ignored'",
                    (now_ts, sid))
                db.commit()
                json_response(self, {"ok": True, "message": "Unignored"})

            elif self.path == "/api/ingest":
                ingest_all(db)
                total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
                json_response(self, {"ok": True, "total": total})

            elif self.path == "/api/config":
                new_cfg = {
                    "lang": body.get("lang", "en"),
                    "device_name": body.get("device_name", ""),
                    "sync_dir": body.get("sync_dir", "cc-sync"),
                    "fns_api": {
                        "url": body.get("fns_api", {}).get("url", ""),
                        "token": body.get("fns_api", {}).get("token", ""),
                        "vault": body.get("fns_api", {}).get("vault", ""),
                    }
                }
                # If token is empty string, keep the old one
                if not new_cfg["fns_api"]["token"]:
                    old = cfg_load() or {}
                    new_cfg["fns_api"]["token"] = old.get("fns_api", {}).get("token", "")
                cfg_save(new_cfg)
                json_response(self, {"ok": True, "message": "Config saved"})

            elif self.path == "/api/test":
                import time
                cfg = cfg_load()
                if not cfg or not cfg.get("fns_api", {}).get("token"):
                    json_response(self, {"ok": False, "message": "Not configured", "latency_ms": 0}, 400); return
                sync_dir = cfg.get("sync_dir", "cc-sync")
                test_content = f"CC-Sync connectivity test.\nDate: {datetime.now().isoformat()}\nSafe to delete.\n"
                t0 = time.time()
                ok, msg = fns_upload(cfg, f"{sync_dir}/.cc-sync-test.md", test_content)
                latency = int((time.time() - t0) * 1000)
                json_response(self, {"ok": ok, "message": "OK" if ok else str(msg), "latency_ms": latency})

            elif self.path == "/api/sync-all":
                cfg = cfg_load()
                if not cfg or not cfg.get("fns_api", {}).get("token"):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                rows = db.execute("SELECT session_id FROM conversations WHERE status='unsynced'").fetchall()
                synced, failed = 0, 0
                for row in rows:
                    result = sync_session(cfg, db, row["session_id"])
                    if result is True: synced += 1
                    elif result is False: failed += 1
                json_response(self, {"ok": True, "synced": synced, "failed": failed, "total_unsynced": len(rows)})

            else:
                self.send_error(404)

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format, *args):
            pass  # suppress noisy access logs

    try:
        server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    except OSError as e:
        print(f"  \u274c Cannot bind to port {port}: {e}")
        print(f"  Try: python3 cc-sync.py web --port=8766")
        db.close()
        return 1

    url = f"http://127.0.0.1:{port}"
    print(f"  \u2705 Dashboard: {url}")
    print(f"  Press Ctrl+C to stop.\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    db.close()


# ── Hook Install/Uninstall ────────────────────────────────────
def _get_settings_path():
    """Get Claude Code user settings path."""
    return HOME / ".claude" / "settings.json"

def _hook_entry():
    """Return the hook configuration for Claude Code settings."""
    return {
        "type": "command",
        "command": "cc-sync hook",
        "timeout": 30
    }

def cmd_install():
    """Install cc-sync as a Claude Code Stop hook."""
    settings_path = _get_settings_path()
    settings = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    entry = _hook_entry()
    # Check if already installed
    for hook in stop_hooks:
        if hook.get("command", "").startswith("cc-sync "):
            print("  ✅ cc-sync hook is already installed.")
            return

    stop_hooks.append(entry)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("  ✅ Installed cc-sync Stop hook in Claude Code settings.")
    print(f"  Settings: {settings_path}")
    print("  Restart Claude Code to activate.")

def cmd_uninstall():
    """Remove cc-sync hook from Claude Code settings."""
    settings_path = _get_settings_path()
    if not settings_path.exists():
        print("  No Claude Code settings found.")
        return

    settings = json.loads(settings_path.read_text())
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    original_len = len(stop_hooks)
    stop_hooks[:] = [h for h in stop_hooks if not h.get("command", "").startswith("cc-sync ")]

    if len(stop_hooks) == original_len:
        print("  cc-sync hook not found in settings.")
        return

    # Clean up empty structures
    if not stop_hooks:
        settings.get("hooks", {}).pop("Stop", None)
    if not settings.get("hooks"):
        settings.pop("hooks", None)

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("  ✅ Removed cc-sync hook from Claude Code settings.")
    print("  Restart Claude Code to apply.")


# ── Entry ────────────────────────────────────────────────────
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if   cmd == "setup":     cmd_setup()
    elif cmd == "hook":      cmd_hook()
    elif cmd == "run":       cmd_run()
    elif cmd == "export":    cmd_export()
    elif cmd == "test":      cmd_test()
    elif cmd == "status":    cmd_status()
    elif cmd == "log":       cmd_log()
    elif cmd == "ingest":    cmd_ingest()
    elif cmd == "web":       cmd_web()
    elif cmd == "install":   cmd_install()
    elif cmd == "uninstall": cmd_uninstall()
    else:
        print("  cc-sync — CC → Obsidian via FNS")
        print("  Commands: setup, hook, run, export, test, status, log, ingest, web")
        print("           install, uninstall")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
