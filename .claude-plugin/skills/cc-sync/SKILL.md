# CC Obsidian Sync Skill

This skill manages the synchronization of Claude Code conversations to Obsidian via Fast Note Sync.

## When to use

Use this skill when the user asks about:
- Syncing conversations to Obsidian
- Checking sync status or logs
- Configuring FNS connection
- Troubleshooting sync issues

## Available commands

- `/cc-sync:web` — Open the web dashboard (the single management entry point)

All configuration, testing, sync operations, and log viewing are done through the dashboard.

## How it works

A Stop hook fires after every Claude Code session ends, calling `scripts/cc-sync.py hook` which:
1. Ingests the latest conversation JSONL into a local SQLite database
2. Formats the conversation into a markdown note
3. Pushes to FNS via REST API (`POST /api/note`)
4. Tracks sync state in the database to avoid duplicates

## Web Dashboard (`/cc-sync:web`)

The dashboard runs on `http://127.0.0.1:8765` and provides three tabs:

- **Conversations** — Search, filter, sort conversations. One-click sync, resync, ignore, unignore. Bulk "Sync All" button.
- **Settings** — Configure FNS connection (URL, token, vault), device name, sync directory, language. Test connectivity with one click.
- **Log** — View recent sync activity log.

## Configuration

Config is stored at `~/.config/cc-sync/config.json`. Database at `~/.config/cc-sync/cc-sync.db`. Configure via the Dashboard Settings tab.
