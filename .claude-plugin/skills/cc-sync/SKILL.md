# CC Obsidian Sync Skill

This skill manages the synchronization of Claude Code conversations to Obsidian via Fast Note Sync.

## When to use

Use this skill when the user asks about:
- Syncing conversations to Obsidian
- Checking sync status or logs
- Configuring FNS connection
- Troubleshooting sync issues

## Available commands

- `/cc-sync:setup` — Configure FNS connection (pass FNS JSON config as argument)
- `/cc-sync:status` — Show current config and sync state
- `/cc-sync:test` — Test FNS API connectivity
- `/cc-sync:run` — Manually sync latest conversation
- `/cc-sync:export` — Bulk export all unsynchronized conversations
- `/cc-sync:web` — Open the web dashboard for session management (search, filter, ignore, resync)
- `/cc-sync:log` — View recent sync log

## How it works

A Stop hook fires after every Claude Code session ends, calling `scripts/cc-sync.py hook` which:
1. Ingests the latest conversation JSONL into a local SQLite database
2. Formats the conversation into a markdown note
3. Pushes to FNS via REST API (`POST /api/note`)
4. Tracks sync state in the database to avoid duplicates

Conversations can be managed via the web dashboard (`/cc-sync:web`), which supports:
- Searching by title or project
- Filtering by status (synced / unsynced / ignored)
- One-click sync, resync, ignore, and unignore operations

## Configuration

Config is stored at `~/.config/cc-sync/config.json`. Database at `~/.config/cc-sync/cc-sync.db`. Use `/cc-sync:setup` to configure.
