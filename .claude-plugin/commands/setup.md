Configure the CC Obsidian Sync plugin. This command is NON-INTERACTIVE — all config is passed via arguments.

## Quick setup with FNS JSON

If the user provides FNS JSON config (from the FNS management panel), pass it directly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py setup '$ARGUMENTS'
```

Example: `/cc-sync:setup {"api": "https://...", "apiToken": "ey...", "vault": "Documents"}`

## Setup with individual options

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py setup --url=URL --token=TOKEN --vault=VAULT
```

Optional flags: `--lang=en|zh-CN|zh-TW`, `--device=NAME`, `--sync-dir=DIR`

## Important

- Ask the user for their FNS JSON config if they don't provide one.
- Do NOT run this script without arguments — it requires at least the FNS connection info.
- After setup succeeds, remind the user to restart Claude Code to activate the Stop hook.
