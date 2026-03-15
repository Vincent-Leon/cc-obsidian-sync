Configure the CC Obsidian Sync plugin.

The user can provide an FNS JSON config block for quick setup, e.g.:

```json
{"api": "https://...", "apiToken": "ey...", "vault": "Documents"}
```

Run the setup script. If the user provided a JSON config, pass it as an argument:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py setup $ARGUMENTS
```

Guide the user through the output. If setup succeeds, remind them to restart Claude Code to activate the Stop hook.
