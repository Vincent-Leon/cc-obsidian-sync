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
"""

import base64, hashlib, json, os, re, sys
import urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────
HOME         = Path.home()
CONFIG_DIR   = HOME / ".config" / "cc-sync"
CONFIG_FILE  = CONFIG_DIR / "config.json"
STATE_FILE   = CONFIG_DIR / "state.json"
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

# ── Config / State ───────────────────────────────────────────
def cfg_load():
    return json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else None

def cfg_save(c):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(c, indent=2, ensure_ascii=False))

def state_load():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

def state_save(s):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False))

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
            # FNS returns HTTP 200 but uses code/status in body for errors
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
        messages: list of {role, content, time_str}
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

        # Skip non-message types
        msg_type = obj.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        # Extract session metadata from first message
        if session_id is None:
            session_id = obj.get("sessionId", "")
        if project is None:
            project = obj.get("cwd", "")

        # Skip meta messages (system injected)
        if obj.get("isMeta"):
            continue

        msg = obj.get("message", {})
        content_parts = msg.get("content", "")
        role = msg.get("role", msg_type)

        # Extract text content
        if isinstance(content_parts, list):
            texts = [p.get("text", "") for p in content_parts if isinstance(p, dict) and p.get("type") == "text"]
            text = "\n".join(t for t in texts if t)
        elif isinstance(content_parts, str):
            text = content_parts
        else:
            continue

        # Skip empty and system-injected messages
        if not text.strip():
            continue
        stripped_text = text.strip()
        if re.match(r'^<(local-command-|command-name>|command-message>)', stripped_text):
            continue

        # Tag messages that are IDE/system context (not real user input)
        is_context = bool(re.match(r'^<(ide_selection|system-reminder)', stripped_text))

        # Parse timestamp
        ts_str = obj.get("timestamp", "")
        time_str = ""
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                # Convert UTC to local time
                local_dt = dt.astimezone()
                time_str = local_dt.strftime("%H:%M")
                if first_date is None:
                    first_date = local_dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass

        messages.append({"role": role, "content": text, "time_str": time_str, "is_context": is_context})

    if not messages or not session_id:
        return None

    # Extract title from first real user message (skip context-only messages)
    title = "untitled"
    for m in messages:
        if m["role"] == "user" and not m.get("is_context"):
            raw = re.sub(r'[#*`\[\]]', '', m["content"]).strip()
            raw = raw.split("\n")[0].strip()  # first line only
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
        # Skip IDE selection / system context messages from output
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


def resolve_path(sync_dir, title, session_id, state):
    """Determine FNS path for a session, handling title conflicts with numbering."""
    # If this session was already synced, reuse its path
    entry = state.get(session_id)
    if isinstance(entry, dict) and "fns_path" in entry:
        return entry["fns_path"]

    # Collect all paths already used by other sessions
    used_paths = set()
    for sid, val in state.items():
        if isinstance(val, dict) and "fns_path" in val:
            used_paths.add(val["fns_path"])

    base = f"{sync_dir}/{title}.md"
    if base not in used_paths:
        return base

    for i in range(2, 10000):
        candidate = f"{sync_dir}/{title} ({i}).md"
        if candidate not in used_paths:
            return candidate
    return f"{sync_dir}/{title} ({session_id[:8]}).md"


def sync_one(cfg, state, jsonl_path, echo=False):
    """Sync a single conversation. Returns True on success, None if skipped, False on failure."""
    # Parse JSONL
    parsed = parse_jsonl(jsonl_path)
    if not parsed or len(parsed["messages"]) < 2:
        return None  # empty or trivial conversation

    session_id = parsed["session_id"]
    content_hash = md5_str(json.dumps(parsed["messages"], ensure_ascii=False))

    # Check if already synced with same content
    entry = state.get(session_id)
    if isinstance(entry, dict) and entry.get("hash") == content_hash:
        return None  # already synced, no changes

    # Generate formatted content and resolve path
    content = format_conversation(parsed)
    sync_dir = cfg.get("sync_dir", "cc-sync")
    rel_path = resolve_path(sync_dir, parsed["title"], session_id, state)

    ok, msg = fns_upload(cfg, rel_path, content)
    icon = "\u2705" if ok else "\u274c"
    log(f"{icon} {rel_path}", echo=echo)

    if ok:
        state[session_id] = {"hash": content_hash, "fns_path": rel_path}
        state_save(state)
        return True
    return False


def process(cfg, state, echo=False):
    """Sync the latest conversation."""
    jsonl = find_latest_jsonl()
    if not jsonl:
        return 0
    result = sync_one(cfg, state, jsonl, echo=echo)
    return 1 if result is True else 0

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
    """Non-interactive setup. Accepts FNS JSON or individual --key=value args.

    Usage:
      setup '{"api":"...","apiToken":"...","vault":"..."}'
      setup --url=... --token=... --vault=...
      setup --lang=zh-CN
      setup --device=MyMac
      setup --sync-dir=cc-sync
    """
    cfg = cfg_load() or {
        "lang": "en",
        "device_name": os.uname().nodename.split(".")[0],
        "sync_dir": "cc-sync",
        "fns_api": {"url": "", "token": "", "vault": ""},
    }

    args = sys.argv[2:]
    args_text = " ".join(args).strip()

    # Try FNS JSON first
    fns_json = parse_fns_json(args_text) if args_text else None
    if fns_json:
        cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
        cfg["fns_api"]["token"] = fns_json["apiToken"]
        cfg["fns_api"]["vault"] = fns_json.get("vault", "")

    # Parse --key=value args
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

    # Print result
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
    state = state_load()
    n = process(cfg, state)
    if n: log(f"Synced {n} file(s) (device={cfg.get('device_name')})")


def cmd_run():
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1
    print(f"  Device: {cfg['device_name']}\n")
    state = state_load()
    n = process(cfg, state, echo=True)
    if n:
        print(f"\n  \u2705 {t('synced')} {n} {t('files')}")
    else:
        print(f"\n  \U0001f4ed {t('nothing_new')}")


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

    state = state_load()
    lang_name = LANG_NAMES.get(cfg.get("lang", "en"), "English")
    print(f"  Language:  {lang_name}")
    print(f"  Device:    {cfg.get('device_name')}")
    api = cfg.get("fns_api", {})
    print(f"  FNS URL:   {api.get('url')}")
    print(f"  Vault:     {api.get('vault')}")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'cc-sync')}")
    print(f"  {t('processed')}  {len(state)} {t('conversations')}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Log:       {LOG_FILE}")

    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        print(f"\n  {t('recent_activity')}")
        for l in lines[-3:]:
            print(f"    {l}")


def dedupe_by_session(jsonl_files):
    """Group JSONL files by session_id, keep only the latest (most complete) per session.
    Returns list of (jsonl_path, parsed_data) tuples sorted by date."""
    sessions = {}  # session_id -> (jsonl_path, parsed_data, mtime)
    for jf in jsonl_files:
        parsed = parse_jsonl(jf)
        if not parsed or len(parsed["messages"]) < 2:
            continue
        sid = parsed["session_id"]
        mtime = jf.stat().st_mtime
        if sid not in sessions or mtime > sessions[sid][2]:
            sessions[sid] = (jf, parsed, mtime)
    return [(jf, parsed) for jf, parsed, _ in sorted(sessions.values(), key=lambda x: x[2])]


def cmd_export():
    """Scan all conversations and sync any that haven't been uploaded yet."""
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1

    state = state_load()
    all_jsonl = find_all_jsonl()

    print(f"  {t('export_scanning')}")

    # Deduplicate: keep only the latest file per session
    unique = dedupe_by_session(all_jsonl)

    # Partition into new vs already synced
    new, skipped = [], 0
    for jf, parsed in unique:
        sid = parsed["session_id"]
        content_hash = md5_str(json.dumps(parsed["messages"], ensure_ascii=False))
        entry = state.get(sid)
        if isinstance(entry, dict) and entry.get("hash") == content_hash:
            skipped += 1
        else:
            new.append(jf)

    print(f"  {t('export_found')} {len(new)} {t('export_new')}, {skipped} {t('export_skipped')}\n")

    if not new:
        print(f"  {t('export_no_new')}")
        return 0

    ok_count, fail_count = 0, 0
    for i, jf in enumerate(new, 1):
        print(f"  [{i}/{len(new)}] {t('export_progress')} {jf.name}...", end="", flush=True)
        result = sync_one(cfg, state, jf)
        if result is True:
            ok_count += 1
            print(" \u2705")
        elif result is None:
            skipped += 1
            print(" -")
        else:
            fail_count += 1
            print(" \u274c")

    print(f"\n  {t('export_done')}: {ok_count} {t('files')}", end="")
    if fail_count:
        print(f", {fail_count} {t('export_failed_n')}", end="")
    print()


def cmd_log():
    if not LOG_FILE.exists(): print(f"  {t('no_log')}"); return 0
    for l in LOG_FILE.read_text().strip().split("\n")[-30:]:
        print(l)


# ── Entry ────────────────────────────────────────────────────
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if   cmd == "setup":  cmd_setup()
    elif cmd == "hook":   cmd_hook()
    elif cmd == "run":    cmd_run()
    elif cmd == "export": cmd_export()
    elif cmd == "test":   cmd_test()
    elif cmd == "status": cmd_status()
    elif cmd == "log":    cmd_log()
    else:
        print("  cc-sync.py — CC → Obsidian via FNS")
        print("  Commands: setup, hook, run, export, test, status, log")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
