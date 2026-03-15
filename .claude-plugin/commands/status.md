---
allowed-tools: Bash(python3:*)
description: Show current CC Obsidian Sync config and state
---

## Your task

Run the following command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cc-sync.py status
```

Present the output to the user. If there are errors, suggest running `/cc-sync:setup` to fix configuration. You MUST execute this bash command immediately. Do not use any other tools or do anything else.
