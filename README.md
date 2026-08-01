# Pleasantries

Pre-hook scripts for AI coding CLIs that block pleasantry-only prompts like "hi", "hello", "ok", "thank you", etc. Send a real task, not a greeting.

## Why?

AI coding assistants are task tools, not chat buddies. Every "hello" wastes a model call, burns tokens, and breaks your flow. This hook intercepts the prompt **before** it reaches the model and rejects it with a nudge.

## How It Works

```
You type "hi" --> Hook reads prompt --> Regex fullmatch --> Blocked
You type "fix auth bug" --> Hook reads prompt --> No match --> Prompt proceeds
```

Each CLI has its own blocking mechanism:

| Block method | CLIs |
|---|---|
| stderr + exit code 2 | Claude, Kiro, Copilot Chat, Copilot CLI, Cursor, Factory Droid, Kimi Code, Devin |
| JSON `{"decision": "block"}` + exit 0 | Codex |
| JSON `{"decision": "deny"}` + exit 0 | Gemini |

The matcher normalizes input (lowercase, strip punctuation, collapse whitespace) and checks if the **entire** prompt is a pleasantry. Prompts that *contain* pleasantry words but include a real task pass through fine:

| Prompt | Result |
|---|---|
| `hi` | Blocked |
| `Hello!!` | Blocked |
| `thank you so much` | Blocked |
| `ok` | Blocked |
| `see ya later` | Blocked |
| `fix the login bug` | Allowed |
| `hello world program in python` | Allowed |
| `please refactor auth.py` | Allowed |

## Supported CLIs

| CLI | Hook Event | Config Location | Blocking |
|---|---|---|---|
| Claude Code | `UserPromptSubmit` | `~/.claude/settings.json` | exit 2 |
| Codex CLI | `UserPromptSubmit` | `~/.codex/hooks.json` | JSON block |
| Gemini CLI | `BeforeAgent` | `~/.gemini/settings.json` | JSON deny |
| Kiro | `UserPromptSubmit` | `.kiro/hooks/*.json` | exit 2 |
| Copilot Chat | `UserPromptSubmit` | `.github/hooks/*.json` | exit 2 |
| Copilot CLI | `userPromptSubmitted` | `.github/hooks/*.json` | exit 2 |
| Cursor | `beforeSubmitPrompt` | `.cursor/hooks.json` | exit 2 |
| Factory Droid | `UserPromptSubmit` | `~/.factory/hooks.json` | exit 2 |
| Kimi Code | `UserPromptSubmit` | `~/.kimi-code/config.toml` | exit 2 |
| Devin CLI | `UserPromptSubmit` | `.devin/hooks.v1.json` | exit 2 |

### Not supported (no hook system)

CodeBuddy, OpenCode (archived), Aider, Kilo Code, Trae, Trae CN (unreleased), Hermes, Pi, OpenClaw, Amp (docs private), Google Antigravity (no prompt access in hooks), Agent Skills (not a specific tool).

## Installation

### Claude Code

`~/.claude/settings.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command",
          "command": "python3 /path/to/block_pleasantries.py claude",
          "timeout": 5 }] }
    ]
  }
}
```

### Codex CLI

**Step 1:** Enable hooks in `~/.codex/config.toml`:
```toml
[features]
hooks = true
```

**Step 2:** Add to `~/.codex/hooks.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command",
          "command": "python3 /path/to/block_pleasantries.py codex",
          "timeout": 5, "statusMessage": "Checking prompt" }] }
    ]
  }
}
```

### Gemini CLI

`~/.gemini/settings.json`:
```json
{
  "hooks": {
    "BeforeAgent": [
      { "matcher": "*", "hooks": [{ "type": "command",
          "command": "python3 /path/to/block_pleasantries.py gemini",
          "timeout": 5000 }] }
    ]
  }
}
```

### Kiro

`.kiro/hooks/block-pleasantries.json` (workspace-level):
```json
{
  "version": "v1",
  "hooks": [{
    "name": "block-pleasantries",
    "trigger": "UserPromptSubmit",
    "action": { "type": "command",
      "command": "python3 /path/to/block_pleasantries.py kiro" },
    "timeout": 30, "enabled": true
  }]
}
```

### Cursor

`.cursor/hooks.json` or `~/.cursor/hooks.json`:
```json
{
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt": [{
      "command": "python3 /path/to/block_pleasantries.py cursor",
      "timeout": 5
    }]
  }
}
```

### VS Code Copilot Chat

`.github/hooks/pleasantries.json` or `~/.copilot/hooks/`:
```json
{
  "version": 1,
  "hooks": {
    "UserPromptSubmit": [{
      "type": "command",
      "command": "python3 /path/to/block_pleasantries.py copilot-chat",
      "timeout": 5
    }]
  }
}
```

### Factory Droid

`~/.factory/hooks.json` or `.factory/hooks.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command",
          "command": "python3 /path/to/block_pleasantries.py factory-droid",
          "timeout": 5 }] }
    ]
  }
}
```

### Kimi Code

`~/.kimi-code/config.toml`:
```toml
[[hooks]]
event = "UserPromptSubmit"
command = "python3 /path/to/block_pleasantries.py kimi-code"
timeout = 5
```

### Devin CLI

`.devin/hooks.v1.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command",
          "command": "python3 /path/to/block_pleasantries.py devin",
          "timeout": 5 }] }
    ]
  }
}
```

Replace `/path/to/` with the actual path to this repo. Use `python` instead of `python3` on Windows.

### Requirements

- Python 3.10+
- No external dependencies (stdlib only: `json`, `re`, `sys`)
- Works on macOS, Linux, and Windows

## Multi-CLI Architecture

```
block_pleasantries.py
+-- Core matcher (CLI-agnostic)
|   +-- PLEASANTRY_PATTERNS      - compiled regex
|   +-- normalize()              - lowercase, strip punctuation
|   +-- is_pleasantry()          - fullmatch check
|
+-- CLI adapters
|   +-- _json_prompt_extract()   - shared JSON stdin parser
|   +-- _exit2_block()           - stderr + exit code 2 (8 CLIs)
|   +-- _codex_block()           - JSON stdout "block" + exit 0
|   +-- _gemini_block()          - JSON stdout "deny" + exit 0
|   +-- ADAPTERS dict            - {name: {extract, block}}
|
+-- main()                       - dispatch via argv[1]
```

Adding a new CLI:

```python
def _newcli_block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)

ADAPTERS["newcli"] = {"extract": _json_prompt_extract, "block": _newcli_block}
```

Then: `python3 block_pleasantries.py newcli`

## Customizing the Blocklist

Edit the `PLEASANTRY_PATTERNS` regex in `block_pleasantries.py`. Patterns are grouped by category:

- **Greetings**: hi, hello, hey, howdy, good morning, ...
- **Acknowledgments**: ok, sure, yeah, got it, ...
- **Thanks**: thank you, thanks, thx, ty, ...
- **Please**: please, pls, plz
- **Farewells**: bye, goodbye, see ya, later, ...

## License

MIT
