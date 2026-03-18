[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-sync

Auto-sync Claude Code conversations to your knowledge base.

Conversations are parsed from JSONL, deduplicated by session, and pushed to your note system with per-message timestamps. Supports multiple output adapters: local files, FNS, Git, or a self-hosted server.

## Install

### Option A: pip (recommended)

```bash
pip install git+https://github.com/Vincent-Leon/cc-sync-plugin.git
cc-sync install
```

This installs the `cc-sync` CLI and registers the Stop hook in Claude Code settings. Restart Claude Code to activate.

### Option B: Claude Code Plugin

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-sync-plugin.git
/plugin install cc-sync@cc-sync
```

## Update & Uninstall

### If installed via pip

```bash
# Update
pip install --upgrade git+https://github.com/Vincent-Leon/cc-sync-plugin.git

# Uninstall
cc-sync uninstall   # remove hook from Claude Code settings
pip uninstall cc-sync-plugin
```

### If installed via plugin

```bash
# Update
/plugin marketplace update cc-sync
/plugin update cc-sync@cc-sync

# Uninstall
/plugin uninstall cc-sync@cc-sync
/plugin marketplace remove cc-sync
```

> **Note:** After updating, restart Claude Code to load the new plugin code.
>
> **Known issue:** `plugin update` may only fetch without merging. If you're stuck on an old version, run:
>
> ```bash
> cd ~/.claude/plugins/marketplaces/cc-sync/
> git pull
> ```
>
> Then run `/plugin update cc-sync@cc-sync` again.

## Setup

Choose an output adapter during setup:

```bash
# Local files (write directly to Obsidian vault)
cc-sync setup --adapter=local --path=~/Documents/Obsidian/MyVault

# FNS (Fast Note Sync server)
cc-sync setup '{"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}'

# Git (auto-commit to a git repo)
cc-sync setup --adapter=git --repo-path=~/obsidian-vault

# Server (push to cc-sync-server)
cc-sync setup --adapter=server --url=http://localhost:8080 --token=your-token
```

Then restart Claude Code. Every conversation is now auto-synced.

## Output Adapters

| Adapter | Mode | Description |
|---------|------|-------------|
| `local` | Lite | Write .md files directly to a local directory |
| `fns` | Lite | Push via [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service) REST API |
| `git` | Lite | Write .md + auto git commit (optional push) |
| `server` | Server | POST to [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) for multi-device sync |

## Commands

| Command | Description |
|---------|-------------|
| `/cc-sync:setup` | Configure output adapter |
| `/cc-sync:web` | Open web dashboard |
| `/cc-sync:export` | Bulk export all unsynchronized conversations |
| `/cc-sync:test` | Test adapter connectivity |
| `/cc-sync:run` | Manually sync latest conversation |
| `/cc-sync:status` | Show config and sync state |
| `/cc-sync:log` | View recent sync activity |

## How it works

```
CC Stop hook → parse JSONL → deduplicate by session → output adapter → knowledge base
```

- Conversations are parsed from `.jsonl` files (not `.md`) for structured data
- Deduplicated by `sessionId` — same session saved multiple times only syncs once
- Files are named by conversation title: `{sync_dir}/{title}.md` (default dir: `cc-sync/`)
- Title conflicts are auto-numbered: `title.md`, `title (2).md`, `title (3).md`
- Each message includes a timestamp: `### User [14:30]`
- Content changes are tracked by hash — updates overwrite in place, no duplicates

The plugin only handles sync. Organizing notes is left to your note app.

## Multi-device

**Lite mode:** Install on every device, each pushes to the same FNS server or git repo.

**Server mode:** Install the plugin on every device, all push to one [cc-sync-server](https://github.com/Vincent-Leon/cc-sync-server) instance. The server handles dedup, storage, and downstream distribution.

## Requirements

- Python 3.8+
- Jinja2 (`pip install jinja2`, auto-installed with pip)

## License

MIT
