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
    # Fallback: use first user message
    for i, ln in enumerate(lines):
        if "**User:**" in ln or "\u{1f464}" in ln:
            for s in lines[i+1:]:
                s = s.strip()
                if s and not s.startswith(("---", "\u{1f916}", "**")):
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

    # Build filename: {date}_{title}.md
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


def cmd_setup():
    """Interactive configuration wizard with FNS JSON quick-config support."""
    print("\n  \u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557")
    print("  \u2551   CC Obsidian Sync \u2014 Setup Wizard    \u2551")
    print("  \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\n")

    cfg = cfg_load() or {
        "device_name": os.uname().nodename.split(".")[0],
        "sync_dir": "cc-sync",
        "fns_api": {"url": "", "token": "", "repo_id": "", "upload_endpoint": "/api/note/upload"},
    }

    # Check for FNS JSON in command-line arguments
    fns_json = None
    args_text = " ".join(sys.argv[2:]).strip()
    if args_text:
        fns_json = parse_fns_json(args_text)

    if fns_json:
        print("  \u2705 Detected FNS configuration JSON\n")
        cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
        cfg["fns_api"]["token"] = fns_json["apiToken"]
        print(f"     API:   {cfg['fns_api']['url']}")
        print(f"     Token: {cfg['fns_api']['token'][:12]}...")
        if fns_json.get("vault"):
            print(f"     Vault: {fns_json['vault']}")
    else:
        print("  \U0001f4a1 Tip: paste FNS JSON config for quick setup, or press Enter for manual config")
        print('     (from FNS management panel \u2192 repo \u2192 copy config)\n')
        paste = input("  Paste FNS JSON (or Enter to skip): ").strip()
        fns_json = parse_fns_json(paste) if paste else None

        if fns_json:
            cfg["fns_api"]["url"] = fns_json["api"].rstrip("/")
            cfg["fns_api"]["token"] = fns_json["apiToken"]
            print(f"\n  \u2705 FNS config loaded")
            print(f"     API:   {cfg['fns_api']['url']}")
            print(f"     Token: {cfg['fns_api']['token'][:12]}...")
            if fns_json.get("vault"):
                print(f"     Vault: {fns_json['vault']}")
        else:
            print("\n  \u2014 FNS API Configuration \u2014")
            print("  (Get these from your FNS management panel \u2192 repository \u2192 viewConfig)\n")

            u = input(f"  FNS server URL [{cfg['fns_api'].get('url', '')}]: ").strip()
            if u: cfg["fns_api"]["url"] = u

            t = input(f"  API Token [{cfg['fns_api'].get('token', '')[:8] + '...' if cfg['fns_api'].get('token') else ''}]: ").strip()
            if t: cfg["fns_api"]["token"] = t

            r = input(f"  Repo ID [{cfg['fns_api'].get('repo_id', '')}]: ").strip()
            if r: cfg["fns_api"]["repo_id"] = r

    # Device name
    dn = input(f"\n  Device name [{cfg['device_name']}]: ").strip()
    if dn: cfg["device_name"] = dn

    # Sync directory
    sd = input(f"  Sync directory in vault [{cfg.get('sync_dir', 'cc-sync')}]: ").strip()
    if sd: cfg["sync_dir"] = sd

    CC_LOGS.mkdir(parents=True, exist_ok=True)
    cfg_save(cfg)

    print(f"\n  \u2705 Config saved to {CONFIG_FILE}")
    print(f"\n  Next: restart Claude Code to activate the Stop hook,")
    print(f"  then run /cc-sync:test to verify the FNS connection.\n")


def cmd_hook():
    """Stop hook entry point. Pushes latest conversation to FNS."""
    cfg = cfg_load()
    if not cfg or not cfg.get("fns_api", {}).get("token"):
        log("Not configured \u2014 run /cc-sync:setup"); return 0
    state = state_load()
    n = process(cfg, state)
    if n: log(f"Synced {n} file(s) (device={cfg.get('device_name')})")


def cmd_run():
    cfg = cfg_load()
    if not cfg: print("  Not configured. Run /cc-sync:setup"); return 1
    print(f"  Device: {cfg['device_name']}\n")
    state = state_load()
    n = process(cfg, state, echo=True)
    print(f"\n  {'\u2705 Synced ' + str(n) + ' file(s)' if n else '\U0001f4ed Nothing new'}")


def cmd_test():
    cfg = cfg_load()
    if not cfg: print("  Not configured. Run /cc-sync:setup"); return 1

    api = cfg.get("fns_api", {})
    print(f"  URL:     {api.get('url')}")
    print(f"  Repo ID: {api.get('repo_id')}")
    print(f"  Token:   {api.get('token', '')[:12]}...\n")

    sync_dir = cfg.get("sync_dir", "cc-sync")
    test = f"CC-Sync connectivity test.\nDate: {datetime.now().isoformat()}\nSafe to delete.\n"
    ok, msg = fns_upload(cfg, f"{sync_dir}/.cc-sync-test.md", test)
    print(f"  Upload: {'\u2705 OK' if ok else '\u274c Failed'}")
    if not ok:
        print(f"  Error: {msg}")
        print(f"\n  \U0001f4a1 Check config: {CONFIG_FILE}")
        print(f"     Or try /cc-sync:setup to reconfigure")


def cmd_status():
    cfg = cfg_load()
    if not cfg:
        print("  Not configured. Run /cc-sync:setup"); return 1

    state = state_load()
    print(f"  Device:    {cfg.get('device_name')}")
    print(f"  FNS URL:   {cfg.get('fns_api', {}).get('url')}")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'cc-sync')}")
    print(f"  Processed: {len(state)} conversation(s)")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Log:       {LOG_FILE}")

    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        print(f"\n  Recent activity:")
        for l in lines[-3:]:
            print(f"    {l}")


def cmd_log():
    if not LOG_FILE.exists(): print("  No log yet."); return 0
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
        print("  cc-sync.py \u2014 CC \u2192 Obsidian via FNS")
        print("  Commands: setup, hook, run, test, status, log")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
