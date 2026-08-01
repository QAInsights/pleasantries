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

| CLI | Block method |
|---|---|
| Claude Code | stderr message + exit code 2 |
| Codex CLI | JSON stdout `{"decision": "block", "reason": "..."}` + exit code 0 |

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

| CLI | Hook Type | Config File | Status |
|---|---|---|---|
| Claude Code | `UserPromptSubmit` | `~/.claude/settings.json` | Supported |
| Codex CLI | `UserPromptSubmit` | `~/.codex/hooks.json` + `config.toml` | Supported |
| More coming | - | - | Planned |

## Installation

### Claude Code

Add to `~/.claude/settings.json` (global) or `.claude/settings.json` (project-level):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/block_pleasantries.py claude",
            "timeout": 5
          }
        ]
      }
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
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/block_pleasantries.py codex",
            "timeout": 5,
            "statusMessage": "Checking prompt"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/` with the actual path to this repo.

**Windows note:** Use `python` instead of `python3`, and add a `commandWindows` field with the full path to `python.exe`:

```json
"command": "python C:/Users/you/gits/pleasantries/block_pleasantries.py codex",
"commandWindows": "C:\\Users\\you\\scoop\\apps\\python\\current\\python.exe C:\\Users\\you\\gits\\pleasantries\\block_pleasantries.py codex"
```

### Requirements

- Python 3.10+
- No external dependencies (stdlib only: `json`, `re`, `sys`)
- Works on macOS, Linux, and Windows

## Multi-CLI Architecture

The script separates core matching logic from CLI-specific I/O:

```
block_pleasantries.py
+-- Core matcher (CLI-agnostic)
|   +-- PLEASANTRY_PATTERNS      - compiled regex
|   +-- normalize()              - lowercase, strip punctuation
|   +-- is_pleasantry()          - fullmatch check
|
+-- CLI adapters
|   +-- _json_prompt_extract()   - shared JSON stdin parser
|   +-- _claude_block()          - stderr + exit code 2
|   +-- _codex_block()           - JSON stdout decision + exit code 0
|   +-- ADAPTERS dict            - {name: {extract, block}}
|
+-- main()                       - dispatch via argv[1]
```

Adding a new CLI takes two steps:

```python
def _newcli_extract(raw: str) -> str:
    return json.loads(raw).get("prompt", "")

def _newcli_block(msg: str) -> None:
    # Use whatever blocking mechanism the CLI supports
    print(msg, file=sys.stderr)
    sys.exit(2)

ADAPTERS["newcli"] = {"extract": _newcli_extract, "block": _newcli_block}
```

Then pass the CLI name: `python3 block_pleasantries.py newcli`

## Customizing the Blocklist

Edit the `PLEASANTRY_PATTERNS` regex in `block_pleasantries.py`. Patterns are grouped by category:

- **Greetings**: hi, hello, hey, howdy, good morning, ...
- **Acknowledgments**: ok, sure, yeah, got it, ...
- **Thanks**: thank you, thanks, thx, ty, ...
- **Please**: please, pls, plz
- **Farewells**: bye, goodbye, see ya, later, ...

## License

MIT
