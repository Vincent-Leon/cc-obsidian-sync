# cc-sync — Product Design Document

## Vision

An open-source Claude Code plugin that automatically captures AI conversations
and transforms them into structured knowledge in your note-taking system.

**One-line pitch:** Every Claude Code conversation becomes a searchable, linked
note in your knowledge base — automatically.

---

## Design Principles

### 1. Zero-config start, progressive enhancement

Install the plugin → conversations are saved as local Markdown files. Done.
Want multi-device sync? Add an output adapter. Want AI extraction? Add an LLM
adapter and API key. Want a web dashboard? Add the server adapter. Each layer
is optional.

### 2. Decouple everything

The core plugin knows nothing about FNS, Notion, Anthropic, or OpenAI.
It works with abstract interfaces. Adapters implement those interfaces.
Users mix and match.

### 3. User owns their data

All processing can happen locally. No mandatory cloud services. Even the
LLM extraction can run on a local Ollama model. The plugin never phones
home.

### 4. Convention over configuration, but everything is configurable

Sane defaults (daily note format, folder structure, frontmatter schema) that
work for 80% of users. Power users can override every template, path, and
behavior.

---

## Module Architecture

```
cc-sync/
├── core/              ← The engine (always present)
│   ├── capture        ← CC Stop hook → parse JSONL → ConversationObject
│   ├── process        ← ConversationObject → NoteBundle (frontmatter, body, metadata)
│   └── scheduler      ← Batch processing timer for LLM extraction
│
├── llm/               ← LLM adapter interface (optional)
│   ├── interface      ← Abstract: input=conversation, output=ExtractionResult
│   ├── anthropic      ← Adapter: Claude API (Haiku/Sonnet/Opus)
│   ├── openai         ← Adapter: OpenAI / OpenAI-compatible (Groq, Together, etc)
│   └── ollama         ← Adapter: Local Ollama models
│
├── output/            ← Output adapter interface (at least one required)
│   ├── interface      ← Abstract: write_note(path, content), read_note(path), etc
│   ├── local          ← Adapter: Write .md files to a local directory (DEFAULT)
│   ├── fns            ← Adapter: Fast Note Sync REST API
│   ├── notion         ← Adapter: Notion API (database entries)
│   ├── git            ← Adapter: Git commit + push
│   └── server         ← Adapter: Push to a self-hosted knowledge server
│
├── templates/         ← Note templates (user-overridable)
│   ├── conversation.md.tpl
│   ├── tech-solution.md.tpl
│   ├── concept.md.tpl
│   ├── work-log-entry.tpl
│   ├── prompt-template.md.tpl
│   └── daily-append.tpl
│
└── config/            ← Configuration schema
    └── schema         ← Validates user config, provides defaults
```

---

## Core Data Model

Everything flows through a single data structure:

### ConversationObject (output of capture layer)

```json
{
  "id": "conversation_2026-03-16_14-30-22",
  "source": "claude-code",
  "device": "macbook",
  "project": "my-project",
  "project_path": "/Users/me/code/my-project",
  "date": "2026-03-16",
  "time": "14:30:22",
  "session_id": "abc-123",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "..."},
    {"role": "assistant", "content": "...", "timestamp": "..."}
  ],
  "raw_markdown": "...",
  "word_count": 1500,
  "message_count": 12
}
```

### NoteBundle (output of process layer)

```json
{
  "conversation_note": {
    "path": "AI-Knowledge/conversations/2026-03-16_fix-auth.md",
    "content": "..."
  },
  "project_ref": {
    "path": "AI-Knowledge/projects/my-project/2026-03-16_fix-auth.md",
    "content": "..."
  },
  "daily_append": {
    "path": "Daily/2026-03-16.md",
    "section": "## AI conversations",
    "entry": "- 14:30 **fix-auth** · `my-project` · [[...]]"
  }
}
```

### ExtractionResult (output of LLM layer, optional)

```json
{
  "summary": "Fixed async token refresh race condition",
  "work_log_entry": "Fixed token refresh race condition using asyncio.Lock",
  "tech_solutions": [...],
  "concepts": [...],
  "prompts": [...],
  "atomic_notes": [
    {"path": "AI-Knowledge/atomic/tech/...", "content": "..."},
    {"path": "AI-Knowledge/atomic/concepts/...", "content": "..."}
  ],
  "daily_work_log_append": {
    "path": "Daily/2026-03-16.md",
    "section": "## Work log",
    "entry": "- 14:30 [my-project] Fixed token refresh ..."
  },
  "project_log_append": {
    "path": "AI-Knowledge/projects/my-project/log.md",
    "section": "## 2026-03-16",
    "entry": "- Fixed token refresh race condition [[...]]"
  }
}
```

---

## State Management

All sync and extraction state is persisted in `~/.config/cc-sync/state.json`, keyed by `session_id`.

### state.json schema

```json
{
  "<session_id>": {
    "hash": "md5_of_messages",
    "fns_path": "cc-sync/My Conversation.md",
    "ignored": false,
    "extracted": false,
    "extracted_at": null
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `hash` | string | MD5 of serialized messages — detects content changes |
| `fns_path` | string | Path where the note was written (used for in-place updates) |
| `ignored` | bool | If true, all pipelines skip this session |
| `extracted` | bool | Whether LLM extraction has run (added in v0.3) |
| `extracted_at` | string\|null | ISO timestamp of last extraction |

### Status inference

| State entry | Status |
|-------------|--------|
| No entry | `unsynced` — new conversation, will sync on next hook |
| `ignored: true` | `ignored` — hook, export, and extract all skip |
| Entry exists, hash matches current | `synced` — no action needed |
| Entry exists, hash differs | `modified` — content changed, needs re-sync |

### State evolution

- **v0.1**: `{ "<file_path>": "<md5_hash>" }` — keyed by file, no session awareness
- **v0.2**: `{ "<session_id>": { "hash", "fns_path" } }` — session-keyed, title dedup
- **v0.2+**: adds `ignored` flag and per-session management
- **v0.3**: adds `extracted` / `extracted_at` for LLM pipeline tracking

---

## Interface Definitions

### Output Adapter Interface

```python
class OutputAdapter:
    """All output adapters implement this interface."""

    def write_note(self, path: str, content: str) -> bool:
        """Create or overwrite a note at the given path."""
        raise NotImplementedError

    def append_to_note(self, path: str, section: str, entry: str) -> bool:
        """Append an entry under a specific section heading in an existing note.
        Creates the note and section if they don't exist."""
        raise NotImplementedError

    def read_note(self, path: str) -> str | None:
        """Read note content. Returns None if note doesn't exist."""
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        """Test that the adapter is properly configured."""
        raise NotImplementedError
```

This is intentionally minimal. Every backend (local files, FNS, Notion, Git)
can implement these 4 methods. The core never needs to know which backend
is being used.

**Implementation notes for `append_to_note`:**

This method is more complex than it looks. Implementors must handle:

1. **Note doesn't exist** — call `write_note` first with the section heading, then append the entry
2. **Section doesn't exist** — append `\n## {section}\n\n{entry}` at the end of the file
3. **Idempotency** — prefix each entry with a hash token (e.g., `<!-- cc:{hash8} -->`) and skip if already present; prevents duplicate appends on re-runs

For FNS and Notion adapters, this requires a read-modify-write cycle. The Notion adapter is the most complex: it must traverse the block tree to find a heading block, then append child blocks below it — there is no native "append to section" API.

### LLM Adapter Interface

```python
class LLMAdapter:
    """All LLM adapters implement this interface."""

    def extract(self, conversation: ConversationObject,
                system_prompt: str, user_prompt: str) -> dict:
        """Send conversation to LLM for knowledge extraction.
        Returns parsed JSON dict with extraction results."""
        raise NotImplementedError

    def estimate_cost(self, conversation: ConversationObject) -> float:
        """Estimate cost in USD for processing this conversation."""
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        """Test that the API key / endpoint is working."""
        raise NotImplementedError
```

---

## Configuration Schema

```json
{
  "_comment": "~/.config/cc-sync/config.json",

  "device_name": "macbook",

  "capture": {
    "cc_logs_path": "~/.claude/conversation-logs",
    "min_lines": 5,
    "ignore_patterns": ["test-*", "scratch-*"]
  },

  "output": {
    "adapter": "local",
    "local": {
      "vault_path": "~/Documents/Obsidian/MyVault"
    },
    "fns": {
      "url": "https://fns.example.com:9000",
      "token": "...",
      "repo_id": "1"
    },
    "notion": {
      "token": "secret_...",
      "database_id": "..."
    },
    "git": {
      "repo_path": "~/obsidian-vault",
      "auto_commit": true,
      "auto_push": true,
      "commit_interval": 300
    }
  },

  "llm": {
    "enabled": false,
    "adapter": "anthropic",
    "batch_interval": 1800,
    "max_monthly_cost": 10.0,
    "min_conversation_words": 100,
    "model_upgrade_threshold": 4000,

    "anthropic": {
      "api_key": "sk-ant-...",
      "model": "claude-haiku-4-5-20251001",
      "model_large": "claude-sonnet-4-20250514"
    },
    "openai": {
      "api_key": "sk-...",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o-mini",
      "model_large": "gpt-4o"
    },
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "llama3.2"
    }
  },

  "notes": {
    "ai_dir": "AI-Knowledge",
    "daily_dir": "Daily",
    "daily_format": "%Y-%m-%d",
    "conversation_heading": "## AI conversations",
    "work_log_heading": "## Work log",
    "language": "auto"
  },

  "templates": {
    "custom_dir": null
  }
}
```

Key design points:
- `output.adapter` selects which output adapter to use
- `llm.enabled` defaults to false — works without any LLM
- `llm.adapter` selects which LLM backend to use
- Each adapter has its own config section
- Templates can be overridden by placing files in custom_dir
- `notes.language: "auto"` detects from conversation content

---

## Template System

Templates use [Jinja2](https://jinja.palletsprojects.com/) syntax — the only external dependency.
Users can override any template by placing a file with the same name in their `custom_dir`.

Simple variables: `{{ variable }}`. Conditional sections: `{% if var %}...{% endif %}`.
Loops: `{% for item in list %}...{% endfor %}`.

### conversation.md.tpl (default)

```jinja
---
source: {{ source }}
device: "{{ device }}"
project: "[[{{ project }}]]"
date: {{ date }}
time: "{{ time }}"
type: ai-conversation
tags: [ai-conversation, {{ source }}, "{{ project }}", "device/{{ device }}"]
---

# {{ title }}

> Project: `{{ project_path }}` | Device: `{{ device }}` | {{ date }} {{ time }}

{{ body }}
```

### tech-solution.md.tpl (default)

```jinja
---
type: tech-solution
date: {{ date }}
project: "[[{{ project }}]]"
tags: [tech-solution, {{ tags | join(', ') }}]
source: "[[{{ source_note }}]]"
---

# {{ title }}

## Problem

{{ problem }}

## Solution

{{ solution }}

{% if code %}
## Key code

{{ code }}
{% endif %}

{% if gotchas %}
## Gotchas

{% for item in gotchas %}
- {{ item }}
{% endfor %}
{% endif %}

{% if related %}
## Related

{% for item in related %}
- [[{{ item }}]]
{% endfor %}
{% endif %}
```

Users who prefer different frontmatter fields, different section names, or
a completely different structure can swap templates without touching core code.

---

## Session Management

Every conversation has a lifecycle. Users need control over which conversations sync and when.

### Session states

| Status | Meaning | Stored as |
|--------|---------|-----------|
| `unsynced` | New conversation, not yet synced | No entry in state.json |
| `synced` | Successfully synced, content unchanged | `{ hash, fns_path }` |
| `modified` | Previously synced, content has changed | Entry exists but hash differs |
| `ignored` | User explicitly excluded | `{ ..., ignored: true }` |

### Two levels of filtering

**`capture.ignore_patterns`** (config-level, batch): regex patterns matched against conversation titles at capture time. Use this for projects or conversation types you *never* want to sync — e.g., `["scratch-*", "test-*"]`. Evaluated on every hook run; no UI needed.

**Session-level ignore** (per-session, after the fact): marks a specific session as ignored in state.json. Persists across hook runs. Use this when a conversation already exists but you decide you don't want it synced. Requires the Dashboard to manage effectively.

### Per-session operations

| Operation | Effect |
|-----------|--------|
| `ignore` | Sets `ignored: true`; hook, export, and extract all skip this session |
| `unignore` | Removes `ignored` flag; session returns to its previous status |
| `resync` | Clears `hash` from state entry; forces re-upload on next sync even if content unchanged |
| `delete-state` | Removes the entire state entry; session becomes `unsynced` again |

### Dashboard (`/cc-sync:web`)

A localhost web UI for managing sessions visually. Runs at `http://127.0.0.1:8765`. Features: search by title, filter by status, sort by date or project, one-click ignore/sync/resync per session. Without the Dashboard, session-level ignore has no practical UI — that's why it ships together (v0.2+).

---

## Plugin Slash Commands

| Command | Description |
|---------|-------------|
| `/cc-sync:setup` | Interactive config wizard (picks adapter, enters credentials) |
| `/cc-sync:test` | Tests output adapter and LLM adapter connectivity |
| `/cc-sync:run` | Manually sync latest conversation |
| `/cc-sync:web` | Open the web dashboard for session management |
| `/cc-sync:extract` | Manually run LLM extraction on unprocessed conversations |
| `/cc-sync:status` | Shows config, adapter status, processed count, cost spent |
| `/cc-sync:log` | Recent sync and extraction activity |
| `/cc-sync:reset` | Reset processed state (re-sync/re-extract everything) |

---

## Implementation Roadmap

### v0.1 — MVP ✓ released

- [x] CC Stop hook capture
- [x] Conversation parsing (JSONL → structured object)
- [x] FNS output adapter
- [x] Project detection from cwd

### v0.2 — Session management & Dashboard (current)

- [x] Session deduplication (same session across multiple JSONL files)
- [x] Title-based filenames + per-message timestamps
- [ ] Ignore mechanism (per-session state flag)
- [ ] Web Dashboard (`/cc-sync:web`, localhost:8765)
- [ ] Adapter interface refactor (OutputAdapter / LLMAdapter base classes)
- [ ] Jinja2 template system

### v0.3 — LLM extraction

- [ ] LLM adapter interface
- [ ] Anthropic adapter (Haiku for most, Sonnet for long conversations)
- [ ] OpenAI-compatible adapter (Groq, Together, etc.)
- [ ] Extraction prompt with structured JSON output
- [ ] Batch scheduler (process unextracted sessions in background)
- [ ] Cost tracking and monthly budget cap
- [ ] Tech solution / concept / prompt template output

### v0.4 — More output adapters

- [ ] Local file output adapter (write directly to Obsidian vault path)
- [ ] Notion adapter
- [ ] Git adapter (auto commit + push)
- [ ] Work log: dual-dimension (daily note + project log)
- [ ] Weekly summary generation

### v0.5 — Polish

- [ ] Multi-language support (auto-detect conversation language)
- [ ] Ollama / local LLM adapter
- [ ] Dataview query examples bundled
- [ ] Community template gallery

### v1.0 — Stable release

- [ ] Comprehensive docs
- [ ] Published to CC plugin marketplace
- [ ] 3+ output adapters tested in production
- [ ] 2+ LLM adapters tested
- [ ] Community template gallery

### Future (if demand exists)

- [ ] Self-hosted knowledge server (web UI for browsing/searching)
- [ ] ChatGPT / browser conversation capture (separate plugins)
- [ ] Cross-reference between conversations (AI-powered linking)
- [ ] Team knowledge base features

---

## Why NOT build the server first

The server can always be added as an output adapter later. But building it
first means:

1. **Higher adoption barrier** — "install plugin + deploy server" vs "install plugin"
2. **Duplicated effort** — FNS already does sync + storage + web UI well
3. **Maintenance burden** — a server needs auth, security updates, backup, monitoring
4. **Wrong abstraction** — the hard problem is capture + extraction, not storage

If the plugin gains traction and users demand a centralized dashboard,
build it then — as a standalone project that consumes the same adapter
interface. The plugin stays clean.

---

## For the self-hosted server scenario (future)

If you do build a server later, it would look like:

```
cc-sync-server/
├── API endpoints    ← Receives notes from plugin's "server" adapter
├── Web UI           ← Browse conversations, search, manage
├── Storage          ← SQLite or Postgres
├── Output plugins   ← Server-side output to FNS, Notion, Git, etc
└── LLM integration  ← Server-side extraction (offloads from client)
```

The plugin's "server" adapter would simply POST conversation data to the
server's API. The server then handles all downstream distribution. This
is the architecture you described — but it's an optional add-on, not the
foundation.

---

## Repository Structure (proposed)

```
cc-sync/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── setup.md
│   ├── test.md
│   ├── run.md
│   ├── extract.md
│   ├── status.md
│   └── log.md
├── hooks/
│   └── hooks.json
├── skills/
│   └── cc-sync/
│       └── SKILL.md
├── scripts/
│   └── cc-sync.py          ← Single-file engine (all logic)
├── templates/
│   ├── conversation.md.tpl
│   ├── tech-solution.md.tpl
│   ├── concept.md.tpl
│   ├── prompt-template.md.tpl
│   └── daily-append.tpl
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

All logic stays in one `cc-sync.py` for simplicity. Adapters are classes
within the file, not separate modules — keeps the "single file, zero deps"
advantage for plugin distribution. If the project grows large enough to
warrant splitting, that's a v2 concern.