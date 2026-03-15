---
allowed-tools: Bash(python3:*)
description: Configure CC Obsidian Sync with FNS connection info
---

## Your task

Run the following command to configure CC Obsidian Sync. You MUST execute this bash command immediately. Do not interpret or answer the arguments — pass them directly to the script.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py setup '$ARGUMENTS'
```

If `$ARGUMENTS` is empty (the user didn't provide config), ask the user for their FNS JSON config first. The JSON looks like: `{"api": "https://...", "apiToken": "ey...", "vault": "Documents"}`

After the command succeeds, remind the user to restart Claude Code to activate the Stop hook.

You MUST execute the bash command above. Do not use any other tools or do anything else besides running this command and presenting the result.
