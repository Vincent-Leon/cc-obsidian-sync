# CC-Sync Plugin

Claude Code conversation capture plugin. Hooks into Claude Code's Stop event, parses JSONL conversation logs, and syncs to configurable output adapters.

## Project Structure

```
.claude-plugin/           # Claude Code plugin distribution
  plugin.json             # Plugin metadata (v0.5.0)
  marketplace.json        # Marketplace config
  hooks/hooks.json        # Stop hook registration
  scripts/cc-sync.py      # Main engine (single file, ~1400 lines, stdlib only)
  scripts/dashboard.html  # Web UI (single-file HTML, vanilla JS, no framework)
  commands/web.md         # /cc-sync:web command definition
  skills/cc-sync/SKILL.md # Skill definition

src/cc_sync/              # pip distribution (mirrors .claude-plugin/scripts/)
  __init__.py             # Package version
  core.py                 # Same as cc-sync.py + install/uninstall commands
  dashboard.html          # Same as scripts/dashboard.html

pyproject.toml            # pip install config, entry point: cc-sync → cc_sync.core:main
```

**Important:** `cc-sync.py` and `core.py` must stay in sync. `core.py` is a copy of `cc-sync.py` with added `cmd_install()` and `cmd_uninstall()` functions at the bottom.

## Build & Test

```bash
# Syntax check
python3 -c "import ast; ast.parse(open('.claude-plugin/scripts/cc-sync.py').read())"

# Run commands directly
python3 .claude-plugin/scripts/cc-sync.py status
python3 .claude-plugin/scripts/cc-sync.py test

# pip install (editable)
pip install -e .
cc-sync status
```

No external dependencies in the main script. Everything uses Python stdlib (urllib, sqlite3, json, pathlib, hashlib, http.server).

## Architecture

### Commands
`setup`, `hook`, `run`, `export`, `test`, `status`, `log`, `ingest`, `web`, `install`, `uninstall`

### Output Adapters
All inherit from `OutputAdapter` base class with `write_note(path, content)` and `test_connection()`:
- **FNSAdapter** — POST to Fast Note Sync API
- **LocalAdapter** — Write .md files to local directory
- **GitAdapter** — Write + git add/commit/push
- **ServerAdapter** — POST ConversationObject to cc-sync-server (uses `send_conversation()` instead of `write_note()`)

### Data Flow
```
Stop hook → parse_jsonl() → ingest to SQLite → sync_session() → adapter.write_note()
```

### Database (SQLite, WAL mode)
- Schema version tracked in `schema_version` table. Current: v2.
- Tables: `conversations`, `messages`, `extractions`, `conversations_fts` (FTS5)
- Status values: `unsynced`, `synced`, `ignored`

### Config
Location: `~/.config/cc-sync/config.json`
```json
{
  "lang": "en",
  "device_name": "hostname",
  "sync_dir": "cc-sync",
  "output": {
    "adapter": "fns",
    "fns": {"url": "...", "token": "...", "vault": "..."}
  }
}
```

## Coding Conventions

- **Zero external deps** in cc-sync.py. Stdlib only. Jinja2 is listed in pyproject.toml but not used yet.
- **Section headers**: `# ── Section Name ──` with dashes to ~80 chars
- **Function prefixes**: `cmd_`, `db_`, `cfg_`, `parse_`, `format_`, `sync_`, `ingest_`, `find_`
- **Error handling**: Broad try/except, log error message, return False/None on failure. Never crash the hook.
- **Logging**: `log(msg)` appends timestamped line to `~/.config/cc-sync/sync.log`
- **i18n**: `STRINGS` dict with en/zh-CN/zh-TW, access via `t(key)`
- **SQL**: Always use `?` placeholders, never f-string interpolation for values
- **Config migration**: `cfg_load()` auto-migrates old formats (v0.4 flat → v0.5 nested output)

## ConversationObject Protocol

The transport format between plugin and server:
```json
{
  "version": 1,
  "source": "claude-code",
  "device": "...",
  "session_id": "...",
  "title": "...",
  "date": "YYYY-MM-DD",
  "project": "project-name",
  "project_path": "/full/path",
  "message_count": 12,
  "word_count": 1500,
  "content_hash": "md5",
  "messages": [{"role": "user", "content": "...", "time_str": "14:30", "is_context": false, "seq": 0}]
}
```

The `source` field is parameterized — other AI tools can produce the same format with a different source value.

## Ecosystem

This plugin is the first "source" implementation. The server (cc-sync-server) accepts ConversationObjects from any source. See cc-sync-server repo for server-side details.
