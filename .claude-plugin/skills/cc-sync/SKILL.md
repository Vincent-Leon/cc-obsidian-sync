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
- `/cc-sync:log` — View recent sync log

## How it works

A Stop hook fires after every Claude Code session ends, calling `scripts/cc-sync.py hook` which:
1. Finds the latest conversation from `~/.claude/conversation-logs/`
2. Parses the conversation into a markdown note
3. Pushes to FNS via REST API (`POST /api/note`)
4. Tracks sync state to avoid duplicates

## Configuration

Config is stored at `~/.config/cc-sync/config.json`. Use `/cc-sync:setup` to configure.
