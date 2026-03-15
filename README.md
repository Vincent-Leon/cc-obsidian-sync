[简体中文](README.zh-CN.md) / [繁體中文](README.zh-TW.md) / [English](README.md)

# cc-obsidian-sync

Auto-sync Claude Code conversations to Obsidian via [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service).

Raw conversation files are pushed to your Obsidian vault as-is — no extra processing, no opinionated folder structure. Just sync.

## Install

Add the plugin marketplace and install:

```
/plugin marketplace add https://github.com/Vincent-Leon/cc-obsidian-sync.git
/plugin install cc-obsidian-sync@Vincent-Leon/cc-obsidian-sync
```

Or for local development:

```
claude --plugin-dir /path/to/cc-obsidian-sync
```

## Setup

After installing, run:

```
/cc-sync:setup
```

You can paste the FNS JSON config directly for quick setup:

```
/cc-sync:setup {"api": "https://your-fns-server.com", "apiToken": "your-token", "vault": "Documents"}
```

The JSON can be copied from the FNS management panel (repository page).

Or run `/cc-sync:setup` without arguments for interactive mode.

Then restart Claude Code. Every conversation is now auto-synced.

## Commands

| Command | Description |
|---------|-------------|
| `/cc-sync:setup` | Configure FNS connection |
| `/cc-sync:export` | Bulk export all unsynchronized conversations |
| `/cc-sync:test` | Test API connectivity |
| `/cc-sync:run` | Manually sync latest conversation |
| `/cc-sync:status` | Show config and sync state |
| `/cc-sync:log` | View recent sync activity |

## How it works

```
CC Stop hook → read latest conversation → push to FNS → Obsidian syncs
```

Conversations are saved to `{sync_dir}/{date}_{title}.md` (default: `cc-sync/`).

The plugin only handles sync. Organizing notes (folders, tags, daily notes, Dataview queries, etc.) is left to Obsidian.

## Multi-device

Install on every device. Each pushes to the same FNS server. All your Obsidian clients receive updates in real-time via FNS sync.

## Requirements

- Python 3.8+
- A running [FNS server](https://github.com/haierkeys/fast-note-sync-service) with the Obsidian plugin configured

## License

MIT
