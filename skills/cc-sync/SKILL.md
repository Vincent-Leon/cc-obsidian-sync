# CC Obsidian Sync Skill

This skill manages the synchronization of Claude Code conversations to Obsidian via Fast Note Sync.

## When to use

Use this skill when the user asks about:
- Syncing conversations to Obsidian
- Checking sync status or logs
- Configuring FNS connection
- Troubleshooting sync issues

## Available commands

- `/cc-sync:setup` — Interactive configuration wizard
- `/cc-sync:status` — Show current config and sync state
- `/cc-sync:test` — Test FNS API connectivity
- `/cc-sync:run` — Manually sync latest conversation
- `/cc-sync:log` — View recent sync log

## How it works

A Stop hook fires after every Claude Code response, calling `scripts/cc-sync.py hook` which:
1. Saves the conversation locally via conversation-logger
2. Parses the conversation into an Obsidian note with YAML frontmatter
3. Detects the project from the working directory
4. Pushes to FNS (API mode or direct file write)
5. Updates the daily note with a conversation entry

## Configuration

Config is stored at `~/.config/cc-sync/config.json`. Use `/cc-sync:setup` to configure interactively.
