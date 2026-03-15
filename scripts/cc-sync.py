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
        "prompt_repo_id":    "Repo ID",
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
        "prompt_repo_id":    "仓库 ID",
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
        "prompt_repo_id":    "儲存庫 ID",
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
def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(8192), b""): h.update(c)
    return h.hexdigest()

def san(name):
    return re.sub(r'-+', '-', re.sub(r'[<>:"/\\|?*\s]', '-', name)).strip('-. ')[:80] or "untitled"

# ── FNS API ──────────────────────────────────────────────────
def fns_call(cfg, endpoint, data):
    """POST to FNS REST API. Returns (ok, response_or_error)."""
    api = cfg["fns_api"]
    url = api["url"].rstrip("/") + endpoint
    body = json.dumps(data).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f'Bearer {api["token"]}',
        "token": api["token"],
    }
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return False, str(e)

def fns_upload(cfg, path, content):
    """Upload or update a note via FNS REST API."""
    api = cfg["fns_api"]
    ep = api.get("upload_endpoint", "/api/note/upload")
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

    payload = {
        "repo_id": int(api.get("repo_id", 0)),
        "path": path,
        "content": content_b64,
        "is_base64": True,
    }

    ok, resp = fns_call(cfg, ep, payload)
    if ok:
        return True, resp

    # Fallback: try without base64
    payload_plain = {
        "repo_id": int(api.get("repo_id", 0)),
        "path": path,
        "content": content,
    }
    for alt in ["/api/note/upload", "/api/note/save", "/api/note/create", "/api/file/upload"]:
        if alt == ep:
            continue
        ok2, resp2 = fns_call(cfg, alt, payload_plain)
        if ok2:
            cfg["fns_api"]["upload_endpoint"] = alt
            cfg_save(cfg)
            log(f"Auto-detected working endpoint: {alt}")
            return True, resp2

    return False, resp

# ── Conversation parsing ────────────────────────────────────
def find_latest():
    if not CC_LOGS.exists(): return None
    mds = [f for f in CC_LOGS.glob("conversation_*.md") if not f.is_symlink()]
    return max(mds, key=lambda f: f.stat().st_mtime) if mds else None

def make_title(md):
    """Extract a short title from conversation file."""
    content = md.read_text(encoding="utf-8", errors="replace")
    lines = content.strip().split("\n")
    for ln in lines:
        if ln.startswith("# ") and "Conversation" not in ln:
            return san(ln[2:].strip())
    for i, ln in enumerate(lines):
        if "**User:**" in ln or "\U0001f464" in ln:
            for s in lines[i+1:]:
                s = s.strip()
                if s and not s.startswith(("---", "\U0001f916", "**")):
                    return san(" ".join(re.sub(r'[#*`\[\]]', '', s).split()[:8]))
    return "untitled"

# ── Pipeline ─────────────────────────────────────────────────
def process(cfg, state, echo=False):
    md = find_latest()
    if not md: return 0
    h = md5(str(md))
    if state.get(str(md)) == h: return 0

    content = md.read_text(encoding="utf-8", errors="replace")
    if len(content.strip().split("\n")) < 5: return 0

    ts = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})", md.stem)
    date = ts.group(1) if ts else datetime.now().strftime("%Y-%m-%d")
    title = make_title(md)
    sync_dir = cfg.get("sync_dir", "cc-sync")
    rel_path = f"{sync_dir}/{date}_{title}.md"

    ok, msg = fns_upload(cfg, rel_path, content)
    status = "\u2705" if ok else "\u274c"
    log(f"{status} {rel_path}", echo=echo)

    if ok:
        state[str(md)] = h
        state_save(state)
        return 1
    return 0

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
    """Interactive configuration wizard with FNS JSON quick-config support."""
    cfg = cfg_load() or {
        "lang": "en",
        "device_name": os.uname().nodename.split(".")[0],
        "sync_dir": "cc-sync",
        "fns_api": {"url": "", "token": "", "repo_id": "", "upload_endpoint": "/api/note/upload"},
    }

    # Language selection first
    cfg["lang"] = prompt_lang(cfg)
    cfg_save(cfg)

    title = t("setup_title")
    pad = (38 - len(title)) // 2
    print(f"\n  \u2554{'═'*38}\u2557")
    print(f"  \u2551{' '*pad}{title}{' '*(38 - pad - len(title))}\u2551")
    print(f"  \u255a{'═'*38}\u255d\n")

    # Check for FNS JSON in command-line arguments
    fns_json = None
    args_text = " ".join(sys.argv[2:]).strip()
    if args_text:
        fns_json = parse_fns_json(args_text)

    if fns_json:
        print(f"  \u2705 {t('detected_json')}\n")
        cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
        cfg["fns_api"]["token"] = fns_json["apiToken"]
        print(f"     API:   {cfg['fns_api']['url']}")
        print(f"     Token: {cfg['fns_api']['token'][:12]}...")
        if fns_json.get("vault"):
            print(f"     Vault: {fns_json['vault']}")
    else:
        print(f"  \U0001f4a1 {t('tip_paste')}")
        print(f"     {t('tip_paste_hint')}\n")
        paste = input(f"  {t('prompt_paste')}: ").strip()
        fns_json = parse_fns_json(paste) if paste else None

        if fns_json:
            cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
            cfg["fns_api"]["token"] = fns_json["apiToken"]
            print(f"\n  \u2705 {t('json_loaded')}")
            print(f"     API:   {cfg['fns_api']['url']}")
            print(f"     Token: {cfg['fns_api']['token'][:12]}...")
            if fns_json.get("vault"):
                print(f"     Vault: {fns_json['vault']}")
        else:
            print(f"\n  — {t('fns_api_config')} —")
            print(f"  {t('fns_api_hint')}\n")

            u = input(f"  {t('prompt_url')} [{cfg['fns_api'].get('url', '')}]: ").strip()
            if u: cfg["fns_api"]["url"] = u

            tk = input(f"  {t('prompt_token')} [{cfg['fns_api'].get('token', '')[:8] + '...' if cfg['fns_api'].get('token') else ''}]: ").strip()
            if tk: cfg["fns_api"]["token"] = tk

            r = input(f"  {t('prompt_repo_id')} [{cfg['fns_api'].get('repo_id', '')}]: ").strip()
            if r: cfg["fns_api"]["repo_id"] = r

    # Device name
    dn = input(f"\n  {t('prompt_device')} [{cfg['device_name']}]: ").strip()
    if dn: cfg["device_name"] = dn

    # Sync directory
    sd = input(f"  {t('prompt_sync_dir')} [{cfg.get('sync_dir', 'cc-sync')}]: ").strip()
    if sd: cfg["sync_dir"] = sd

    CC_LOGS.mkdir(parents=True, exist_ok=True)
    cfg_save(cfg)

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
    print(f"  URL:     {api.get('url')}")
    print(f"  Repo ID: {api.get('repo_id')}")
    print(f"  Token:   {api.get('token', '')[:12]}...\n")

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
    print(f"  FNS URL:   {cfg.get('fns_api', {}).get('url')}")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'cc-sync')}")
    print(f"  {t('processed')}  {len(state)} {t('conversations')}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Log:       {LOG_FILE}")

    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        print(f"\n  {t('recent_activity')}")
        for l in lines[-3:]:
            print(f"    {l}")


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
    elif cmd == "test":   cmd_test()
    elif cmd == "status": cmd_status()
    elif cmd == "log":    cmd_log()
    else:
        print("  cc-sync.py — CC → Obsidian via FNS")
        print("  Commands: setup, hook, run, test, status, log")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
