#!/usr/bin/env python3
"""Multi-CLI pre-hook that blocks pleasantry-only prompts.

Usage: python block_pleasantries.py <cli-name>

Supported CLIs and their hook config:

  claude  - ~/.claude/settings.json (JSON)
    {
      "hooks": {
        "UserPromptSubmit": [
          { "hooks": [{ "type": "command",
              "command": "python block_pleasantries.py claude" }] }
        ]
      }
    }

  codex  - ~/.codex/hooks.json (JSON) + features.hooks = true in config.toml
    {
      "hooks": {
        "UserPromptSubmit": [
          { "hooks": [{ "type": "command",
              "command": "python block_pleasantries.py codex",
              "timeout": 5 }] }
        ]
      }
    }

Adding a new CLI:
  1. Write an extract function: _<cli>_extract(raw_stdin) -> prompt string
  2. Add an entry to ADAPTERS with the extract fn and the exit code that
     signals "block" for that CLI's hook system.
"""

import json
import re
import sys

# ---------------------------------------------------------------------------
# Core matcher (CLI-agnostic)
# ---------------------------------------------------------------------------

PLEASANTRY_PATTERNS = re.compile(
    "|".join(
        rf"(?:{p})"
        for p in [
            # Greetings: hi, hello, hey there, good morning, ...
            r"(?:hi|hello|hey|howdy|greetings|yo)(?:\s+(?:there|everyone|all|folks))?",
            r"good\s+(?:morning|afternoon|evening|day|night)",
            # Acknowledgments: ok, sure, yeah, got it, ...
            r"(?:ok(?:ay)?|k|sure|yes|no|yep|nope|yeah|nah|alright|fine|cool|nice|great|awesome|understood)",
            r"got\s+it",
            # Thanks: thank you, thanks a lot, thx, ty, ...
            r"(?:thank\s+(?:you|u)|thanks|thx|ty|appreciate\s+it)(?:\s+(?:so\s+much|a\s+lot|very\s+much))?",
            # Please
            r"(?:please|pls|plz)",
            # Farewells: bye, see ya later, ...
            r"(?:bye|goodbye|cya|later)(?:\s+(?:all|everyone|later))?",
            r"see\s+(?:you|ya)(?:\s+(?:later|soon|around))?",
        ]
    ),
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_pleasantry(text: str) -> bool:
    """True if the entire prompt is nothing but a pleasantry."""
    normalized = normalize(text)
    if not normalized:
        return False
    return PLEASANTRY_PATTERNS.fullmatch(normalized) is not None


# ---------------------------------------------------------------------------
# CLI adapters
# ---------------------------------------------------------------------------
# Each adapter provides:
#   extract(raw) -> str   : pull the user prompt out of raw stdin
#   block(msg)   -> None  : signal "block this prompt" to the CLI
#
# Blocking mechanisms differ per CLI:
#   claude - exit code 2 + stderr message
#   codex  - JSON stdout {"decision": "block", "reason": ...} + exit code 0


def _json_prompt_extract(raw: str) -> str:
    """Extract prompt from JSON stdin. Used by Claude Code and Codex CLI."""
    return json.loads(raw).get("prompt", "")


def _claude_block(msg: str) -> None:
    """Claude Code: stderr message + exit code 2."""
    print(msg, file=sys.stderr)
    sys.exit(2)


def _codex_block(msg: str) -> None:
    """Codex CLI: JSON decision on stdout + exit code 0."""
    json.dump({"decision": "block", "reason": msg}, sys.stdout)
    sys.exit(0)


ADAPTERS: dict[str, dict] = {
    "claude": {
        "extract": _json_prompt_extract,
        "block": _claude_block,
    },
    "codex": {
        "extract": _json_prompt_extract,
        "block": _codex_block,
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    cli = sys.argv[1] if len(sys.argv) > 1 else "claude"

    adapter = ADAPTERS.get(cli)
    if adapter is None:
        supported = ", ".join(sorted(ADAPTERS))
        print(
            f"Unknown CLI '{cli}'. Supported: {supported}",
            file=sys.stderr,
        )
        sys.exit(1)

    raw = sys.stdin.read()

    try:
        prompt = adapter["extract"](raw)
    except Exception:
        # Can't parse the payload; let the prompt through rather than
        # breaking the user's session.
        sys.exit(0)

    if is_pleasantry(prompt):
        msg = (
            f'Blocked: "{prompt.strip()}" is a pleasantry, not a task. '
            "Send a real prompt with something for the AI to do."
        )
        adapter["block"](msg)

    sys.exit(0)


if __name__ == "__main__":
    main()
