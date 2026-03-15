#!/usr/bin/env python3
"""
cc-sync.py — Claude Code → Obsidian sync engine (via Fast Note Sync)

Part of the cc-obsidian-sync plugin. Zero external dependencies.

Subcommands:
  setup   Interactive FNS configuration wizard
  hook    Called by CC Stop hook (stdin = hook JSON)
  run     Manual one-shot sync of latest conversation
  test    Test FNS API connectivity
  status  Show current configuration and sync state
  log     Show recent sync log entries
"""

import base64, hashlib, json, os, re, subprocess, sys, time
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
SKILL_DIR    = HOME / ".claude" / "skills" / "conversation-logger"

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
    """Upload or update a note via FNS REST API.

    Tries the configured endpoint first, falls back to common alternatives.
    The content is base64-encoded per the FNS REST API spec.
    """
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
            # Remember working endpoint
            cfg["fns_api"]["upload_endpoint"] = alt
            cfg_save(cfg)
            log(f"Auto-detected working endpoint: {alt}")
            return True, resp2

    return False, resp  # return original error

def fns_get(cfg, path):
    """Get note content from FNS."""
    api = cfg["fns_api"]
    ep = api.get("get_endpoint", "/api/note/get")
    return fns_call(cfg, ep, {"repo_id": int(api.get("repo_id", 0)), "path": path})

# ── Direct file sync ────────────────────────────────────────
def direct_write(cfg, path, content):
    vault = Path(cfg["fns_direct"]["vault_path"])
    target = vault / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True, "written"

def direct_read(cfg, path):
    vault = Path(cfg["fns_direct"]["vault_path"])
    f = vault / path
    if f.exists():
        return True, {"content": f.read_text(encoding="utf-8")}
    return False, "not found"

# ── Unified sync interface ───────────────────────────────────
def push_note(cfg, path, content):
    if cfg.get("sync_method") == "direct":
        return direct_write(cfg, path, content)
    return fns_upload(cfg, path, content)

def get_note(cfg, path):
    if cfg.get("sync_method") == "direct":
        return direct_read(cfg, path)
    return fns_get(cfg, path)

# ── Conversation parsing ────────────────────────────────────
def find_latest():
    if not CC_LOGS.exists(): return None
    mds = [f for f in CC_LOGS.glob("conversation_*.md") if not f.is_symlink()]
    return max(mds, key=lambda f: f.stat().st_mtime) if mds else None

def parse_convo(md):
    content = md.read_text(encoding="utf-8", errors="replace")
    lines = content.strip().split("\n")
    title = first_msg = None
    for i, ln in enumerate(lines):
        if ln.startswith("# ") and not title: title = ln[2:].strip()
        if ("**User:**" in ln or "👤" in ln) and not first_msg:
            for s in lines[i+1:]:
                s = s.strip()
                if s and not s.startswith(("---", "🤖", "**")): first_msg = s[:120]; break
    ts = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})", md.stem)
    return dict(
        title=title, first_msg=first_msg,
        date=ts.group(1) if ts else datetime.now().strftime("%Y-%m-%d"),
        time=(ts.group(2) if ts else datetime.now().strftime("%H-%M-%S")).replace("-", ":"),
        content=content, nlines=len(lines),
    )

def parse_session(md):
    sf = str(md).replace(".md", ".json").replace("conversation_", "session_")
    try:
        with open(sf) as f: return json.load(f)
    except Exception: return {}

def detect_project(meta):
    cwd = meta.get("cwd", "") or meta.get("project_path", "")
    if cwd:
        p = Path(cwd).name
        if p and p not in ("~", ".", ""): return san(p), cwd
    return "_uncategorized", ""

def make_title(info):
    if info.get("title") and "Conversation" not in (info.get("title") or ""):
        return san(info["title"])
    if info.get("first_msg"):
        return san(" ".join(re.sub(r'[#*`\[\]]', '', info["first_msg"]).split()[:8]))
    return "untitled"

# ── Note builders ────────────────────────────────────────────
def build_note(info, proj, proj_path, device, ai):
    t = make_title(info)
    body = re.sub(r'^# Conversation.*?\n+', '', info["content"], count=1)
    body = re.sub(r'^\*\*Session ID:\*\*.*?\n+', '', body, count=1)
    return f"""---
source: claude-code
device: "{device}"
project: "[[{proj}]]"
date: {info['date']}
time: "{info['time']}"
type: ai-conversation
tags: [ai-conversation, claude-code, "{proj}", "device/{device}"]
---

# {t}

> Project: `{proj_path or proj}` | Device: `{device}` | {info['date']} {info['time']}

{body}"""

def build_stub(proj, date, title, ai):
    return f"---\nsource: claude-code\nproject: \"[[{proj}]]\"\ndate: {date}\ntype: ai-conversation-ref\n---\n\n![[{ai}/conversations/{date}_{title}]]\n"

def build_entry(time_, title, proj, device, ai, date):
    return f"- {time_} **{title}** · `{proj}` · `{device}` · [[{ai}/conversations/{date}_{title}|full conversation]]"

def update_daily(existing, heading, entry):
    if entry.strip() in existing: return existing
    if heading in existing:
        pos = existing.index(heading) + len(heading)
        nxt = re.search(r'\n## ', existing[pos+1:])
        ins = pos + 1 + nxt.start() if nxt else len(existing)
        return existing[:ins].rstrip('\n') + "\n" + entry + "\n\n" + existing[ins:].lstrip('\n')
    return existing.rstrip('\n') + f"\n\n{heading}\n\n{entry}\n"

# ── Pipeline ─────────────────────────────────────────────────
def process(cfg, state, echo=False):
    md = find_latest()
    if not md: return 0
    h = md5(str(md))
    if state.get(str(md)) == h: return 0

    info = parse_convo(md)
    if info["nlines"] < 5: return 0

    meta = parse_session(md)
    proj, pp = detect_project(meta)
    title = make_title(info)
    d, t = info["date"], info["time"]
    dev = cfg.get("device_name", "unknown")
    obs = cfg.get("obsidian", {})
    ai = obs.get("ai_dir", "AI-Knowledge")
    heading = obs.get("daily_heading", "## AI conversations")
    daily_dir = obs.get("daily_dir", "Daily")
    daily_fmt = obs.get("daily_format", "%Y-%m-%d")

    # Build files
    note = build_note(info, proj, pp, dev, ai)
    stub = build_stub(proj, d, title, ai)
    entry = build_entry(t, title, proj, dev, ai, d)

    # Daily note: read → modify → write
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        dfname = dt.strftime(daily_fmt) + ".md"
    except ValueError:
        dfname = d + ".md"
    dpath = f"{daily_dir}/{dfname}"

    ok_d, resp_d = get_note(cfg, dpath)
    if ok_d and isinstance(resp_d, dict):
        daily_content = resp_d.get("content", "") or resp_d.get("data", {}).get("content", "") or f"# {d}\n\n"
        # Handle base64 response
        if resp_d.get("is_base64"):
            try: daily_content = base64.b64decode(daily_content).decode("utf-8")
            except Exception: pass
    else:
        daily_content = f"# {d}\n\n"
    daily_updated = update_daily(daily_content, heading, entry)

    # Push
    files = [
        (f"{ai}/conversations/{d}_{title}.md", note),
        (f"{ai}/projects/{proj}/{d}_{title}.md", stub),
    ]
    if daily_updated != daily_content:
        files.append((dpath, daily_updated))

    synced = 0
    for rel, content in files:
        ok, msg = push_note(cfg, rel, content)
        status = "✅" if ok else "❌"
        log(f"{status} {rel}", echo=echo)
        if ok: synced += 1

    state[str(md)] = h
    state_save(state)
    return synced

# ── Subcommands ──────────────────────────────────────────────

def cmd_setup():
    """Interactive configuration wizard."""
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   CC Obsidian Sync — Setup Wizard    ║")
    print("  ╚══════════════════════════════════════╝\n")

    cfg = cfg_load() or {
        "device_name": os.uname().nodename.split(".")[0],
        "sync_method": "api",
        "fns_api": {"url": "", "token": "", "repo_id": "", "upload_endpoint": "/api/note/upload", "get_endpoint": "/api/note/get"},
        "fns_direct": {"vault_path": ""},
        "obsidian": {"ai_dir": "AI-Knowledge", "daily_dir": "Daily", "daily_format": "%Y-%m-%d", "daily_heading": "## AI conversations"},
    }

    # Device name
    dn = input(f"  Device name [{cfg['device_name']}]: ").strip()
    if dn: cfg["device_name"] = dn

    # Sync method
    # Auto-detect FNS local storage
    fns_local = ""
    for d in ["/data/fast-note-sync/storage", "/opt/fast-note/storage", str(HOME / "fast-note-sync" / "storage")]:
        for vd in Path(d).glob("repos/*/vault") if Path(d).exists() else []:
            fns_local = str(vd); break
        if fns_local: break

    if fns_local:
        print(f"\n  🔍 Detected FNS storage at: {fns_local}")
        m = input("  Use direct file write? (faster, recommended) [Y/n]: ").strip().lower()
        if m != "n":
            cfg["sync_method"] = "direct"
            cfg["fns_direct"]["vault_path"] = fns_local
        else:
            cfg["sync_method"] = "api"
    else:
        cfg["sync_method"] = "api"

    # FNS API config (always collect — useful even in direct mode as fallback)
    print("\n  — FNS API Configuration —")
    print("  (Get these from your FNS management panel → repository → viewConfig)\n")

    u = input(f"  FNS server URL [{cfg['fns_api'].get('url', '')}]: ").strip()
    if u: cfg["fns_api"]["url"] = u

    t = input(f"  API Token [{cfg['fns_api'].get('token', '')[:8] + '...' if cfg['fns_api'].get('token') else ''}]: ").strip()
    if t: cfg["fns_api"]["token"] = t

    r = input(f"  Repo ID [{cfg['fns_api'].get('repo_id', '')}]: ").strip()
    if r: cfg["fns_api"]["repo_id"] = r

    # Obsidian settings
    print("\n  — Obsidian Settings —\n")
    dd = input(f"  Daily notes folder name [{cfg['obsidian']['daily_dir']}]: ").strip()
    if dd: cfg["obsidian"]["daily_dir"] = dd

    df = input(f"  Daily note filename format [{cfg['obsidian']['daily_format']}]: ").strip()
    if df: cfg["obsidian"]["daily_format"] = df

    ad = input(f"  AI knowledge folder [{cfg['obsidian']['ai_dir']}]: ").strip()
    if ad: cfg["obsidian"]["ai_dir"] = ad

    # Install conversation-logger skill
    print("\n  📦 Installing conversation-logger skill...")
    if SKILL_DIR.exists():
        subprocess.run(["git", "pull"], cwd=SKILL_DIR, capture_output=True)
        print("     ✅ Updated")
    else:
        SKILL_DIR.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "https://github.com/sirkitree/conversation-logger.git", str(SKILL_DIR)], capture_output=True)
        print("     ✅ Installed" if r.returncode == 0 else f"     ❌ Failed: {r.stderr.decode()[:100]}")
    for f in SKILL_DIR.glob("scripts/*"): f.chmod(0o755)

    CC_LOGS.mkdir(parents=True, exist_ok=True)
    cfg_save(cfg)

    print(f"\n  ✅ Config saved to {CONFIG_FILE}")
    print(f"  ✅ Sync method: {cfg['sync_method']}")
    print(f"\n  Next: restart Claude Code to activate the Stop hook,")
    print(f"  then run /cc-sync:test to verify the FNS connection.\n")


def cmd_hook():
    """Stop hook entry point. Saves locally + pushes to FNS."""
    try: stdin = sys.stdin.read()
    except: stdin = ""

    # Local save
    try: hook = json.loads(stdin) if stdin.strip() else {}
    except: hook = {}
    tp, sid = hook.get("transcript_path", ""), hook.get("session_id", "unknown")
    ss = SKILL_DIR / "scripts" / "save-conversation.sh"
    if ss.exists() and tp:
        subprocess.Popen(["bash", str(ss), tp, sid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    # FNS push
    cfg = cfg_load()
    if not cfg or not cfg.get("fns_api", {}).get("token"):
        log("Not configured — run /cc-sync:setup"); return 0
    state = state_load()
    n = process(cfg, state)
    if n: log(f"Synced {n} file(s) → {cfg.get('sync_method')} (device={cfg.get('device_name')})")


def cmd_run():
    cfg = cfg_load()
    if not cfg: print("  Not configured. Run /cc-sync:setup"); return 1
    print(f"  Device: {cfg['device_name']} | Method: {cfg['sync_method']}\n")
    state = state_load()
    n = process(cfg, state, echo=True)
    print(f"\n  {'✅ Synced ' + str(n) + ' file(s)' if n else '📭 Nothing new'}")


def cmd_test():
    cfg = cfg_load()
    if not cfg: print("  Not configured. Run /cc-sync:setup"); return 1
    m = cfg.get("sync_method", "api")
    print(f"  Method: {m}\n")

    if m == "direct":
        vp = cfg.get("fns_direct", {}).get("vault_path", "")
        e = Path(vp).exists() if vp else False
        print(f"  Vault: {vp}")
        print(f"  Status: {'✅ OK' if e else '❌ Path not found'}")
    else:
        api = cfg.get("fns_api", {})
        print(f"  URL:     {api.get('url')}")
        print(f"  Repo ID: {api.get('repo_id')}")
        print(f"  Token:   {api.get('token', '')[:12]}...\n")

        # Upload test note
        test = f"---\ntest: true\ndate: {datetime.now().isoformat()}\n---\n\nCC-Sync connectivity test. Safe to delete.\n"
        ok, msg = push_note(cfg, f"{cfg.get('obsidian',{}).get('ai_dir','AI-Knowledge')}/.cc-sync-test.md", test)
        print(f"  Upload: {'✅ OK' if ok else '❌ Failed'}")
        if not ok:
            print(f"  Error: {msg}")
            print(f"\n  💡 Check config: {CONFIG_FILE}")
            print(f"     Or try /cc-sync:setup to reconfigure")


def cmd_status():
    cfg = cfg_load()
    if not cfg:
        print("  Not configured. Run /cc-sync:setup"); return 1

    state = state_load()
    print(f"  Device:      {cfg.get('device_name')}")
    print(f"  Method:      {cfg.get('sync_method')}")
    if cfg.get("sync_method") == "direct":
        print(f"  Vault path:  {cfg.get('fns_direct', {}).get('vault_path')}")
    else:
        print(f"  FNS URL:     {cfg.get('fns_api', {}).get('url')}")
    print(f"  AI dir:      {cfg.get('obsidian', {}).get('ai_dir')}")
    print(f"  Daily dir:   {cfg.get('obsidian', {}).get('daily_dir')}")
    print(f"  Processed:   {len(state)} conversation(s)")
    print(f"  Config:      {CONFIG_FILE}")
    print(f"  Log:         {LOG_FILE}")

    # Show last 3 log entries
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
        print("  cc-sync.py — CC → Obsidian via FNS")
        print("  Commands: setup, hook, run, test, status, log")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
