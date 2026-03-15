Export all unsynchronized conversations to FNS.

Scans all conversation logs in `~/.claude/conversation-logs/`, skips already synced ones, and uploads the rest.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py export
```

Show the user the export progress output. This is useful for initial setup to bulk-sync all existing conversations.
