# cc-obsidian-sync

Auto-sync Claude Code conversations to Obsidian via [Fast Note Sync](https://github.com/haierkeys/fast-note-sync-service).

Every CC response is automatically saved, tagged by project, and pushed to your Obsidian vault — with entries in your daily notes.

## Install

```
/plugin marketplace add https://github.com/YOUR_USER/cc-obsidian-sync
```

Or local install:

```
claude --plugin-dir /path/to/cc-obsidian-sync
```

## Setup

After installing, run:

```
/cc-sync:setup
```

This interactive wizard asks for your FNS server URL, API token, and repo ID (all available from the FNS management panel). On the FNS server itself, it auto-detects the local vault path for direct file writing.

Then restart Claude Code. That's it — every conversation is now auto-synced.

## Commands

| Command | Description |
|---------|-------------|
| `/cc-sync:setup` | Configure FNS connection |
| `/cc-sync:test` | Test API connectivity |
| `/cc-sync:run` | Manually sync latest conversation |
| `/cc-sync:status` | Show config and sync state |
| `/cc-sync:log` | View recent sync activity |

## How it works

```
CC Stop hook → save locally → parse conversation → push to FNS → Obsidian syncs
```

Each conversation generates:
- **Full archive** → `AI-Knowledge/conversations/YYYY-MM-DD_title.md`
- **Project reference** → `AI-Knowledge/projects/<project>/YYYY-MM-DD_title.md`
- **Daily entry** → `Daily/YYYY-MM-DD.md` → `## AI conversations` section

Notes include YAML frontmatter with device, project, date, time, and tags — compatible with Dataview queries.

## Multi-device

Install on every device (MacBook, servers). Each pushes to the same FNS server. All your Obsidian clients receive updates in real-time via FNS WebSocket sync.

## Sync methods

- **API mode** (default): HTTP push to FNS REST API. Works from any network.
- **Direct mode** (auto-detected on FNS server): Writes files directly to FNS storage. Fastest, zero network overhead.

## Requirements

- Python 3.8+
- `git`, `jq` (for conversation-logger skill)
- A running [FNS server](https://github.com/haierkeys/fast-note-sync-service) with the Obsidian plugin configured

## License

MIT
