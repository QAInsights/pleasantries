#!/usr/bin/env python3
"""Interactive installer for the pleasantries pre-hook across AI coding CLIs.

Usage:
  python install.py              Install hooks (interactive)
  python install.py --uninstall  Remove hooks from all configs
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
INSTALL_DIR = HOME / ".pleasantries"
SCRIPT_NAME = "block_pleasantries.py"
HOOK_MARKER = "block_pleasantries"

# ---------------------------------------------------------------------------
# CLI definitions
# ---------------------------------------------------------------------------
# Each entry:
#   detect_dir  - directory whose existence means the CLI is installed
#   config_path - config file to write the hook into
#   hook_event  - the hook event name used by this CLI
#   install()   - writes the hook into the config
#   uninstall() - removes the hook from the config

SCRIPT_PATH_STR = str(INSTALL_DIR / SCRIPT_NAME)


def _python_cmd() -> str:
    """Return 'python3' on Unix, 'python' on Windows."""
    return "python" if sys.platform == "win32" else "python3"


def _hook_command(cli_name: str) -> str:
    return f"{_python_cmd()} {SCRIPT_PATH_STR} {cli_name}"


# --- JSON config helpers ---


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _json_has_hook(path: Path) -> bool:
    if not path.exists():
        return False
    return HOOK_MARKER in path.read_text(encoding="utf-8")


def _install_json_hook(
    config_path: Path,
    event_name: str,
    cli_name: str,
    *,
    wrapper_key: str = "hooks",
    timeout: int = 5,
    extra_fields: dict | None = None,
) -> None:
    """Add a hook entry to a JSON config file under hooks.<event_name>[].hooks[]."""
    data = _load_json(config_path)

    hooks_root = data.setdefault(wrapper_key, {})
    event_list = hooks_root.setdefault(event_name, [])

    hook_entry = {
        "type": "command",
        "command": _hook_command(cli_name),
        "timeout": timeout,
    }
    if extra_fields:
        hook_entry.update(extra_fields)

    event_list.append({"hooks": [hook_entry]})
    _save_json(config_path, data)


def _uninstall_json_hook(config_path: Path, event_name: str) -> bool:
    """Remove hook entries referencing block_pleasantries. Returns True if changed."""
    if not config_path.exists():
        return False

    data = _load_json(config_path)
    hooks_root = data.get("hooks", {})
    event_list = hooks_root.get(event_name, [])
    if not event_list:
        return False

    cleaned = []
    changed = False
    for group in event_list:
        group_hooks = group.get("hooks", [])
        kept = [
            h
            for h in group_hooks
            if HOOK_MARKER not in h.get("command", "")
        ]
        if len(kept) < len(group_hooks):
            changed = True
        if kept:
            group["hooks"] = kept
            cleaned.append(group)
        elif not any(HOOK_MARKER in h.get("command", "") for h in group_hooks):
            cleaned.append(group)

    if changed:
        if cleaned:
            hooks_root[event_name] = cleaned
        else:
            hooks_root.pop(event_name, None)
        _save_json(config_path, data)
    return changed


# --- TOML helpers (string-based, no full parser needed) ---


def _toml_has_hook(path: Path) -> bool:
    if not path.exists():
        return False
    return HOOK_MARKER in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-CLI install/uninstall
# ---------------------------------------------------------------------------


def install_claude() -> str:
    path = HOME / ".claude" / "settings.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "claude")
    return f"hook added to {path}"


def uninstall_claude() -> bool:
    return _uninstall_json_hook(HOME / ".claude" / "settings.json", "UserPromptSubmit")


def install_codex() -> str:
    hooks_path = HOME / ".codex" / "hooks.json"
    config_path = HOME / ".codex" / "config.toml"

    if _json_has_hook(hooks_path):
        return "already installed, skipped"

    # hooks.json
    data = _load_json(hooks_path)
    hooks_root = data.setdefault("hooks", {})
    event_list = hooks_root.setdefault("UserPromptSubmit", [])
    hook_entry = {
        "type": "command",
        "command": _hook_command("codex"),
        "timeout": 5,
        "statusMessage": "Checking prompt",
    }
    event_list.append({"hooks": [hook_entry]})
    _save_json(hooks_path, data)

    # config.toml: ensure features.hooks = true
    if config_path.exists():
        toml_text = config_path.read_text(encoding="utf-8")
        if "hooks" not in toml_text.split("[features]")[1].split("[")[0] if "[features]" in toml_text else True:
            if "[features]" in toml_text:
                toml_text = toml_text.replace("[features]", "[features]\nhooks = true", 1)
            else:
                toml_text += "\n[features]\nhooks = true\n"
            config_path.write_text(toml_text, encoding="utf-8")

    return f"hook added to {hooks_path}"


def uninstall_codex() -> bool:
    changed = _uninstall_json_hook(HOME / ".codex" / "hooks.json", "UserPromptSubmit")
    # Note: we don't remove features.hooks=true since other hooks may use it
    return changed


def install_gemini() -> str:
    path = HOME / ".gemini" / "settings.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(
        path,
        "BeforeAgent",
        "gemini",
        timeout=5000,
        extra_fields={"name": "block-pleasantries"},
    )
    # Add matcher to the group
    data = _load_json(path)
    groups = data.get("hooks", {}).get("BeforeAgent", [])
    for g in groups:
        for h in g.get("hooks", []):
            if HOOK_MARKER in h.get("command", ""):
                g["matcher"] = "*"
    _save_json(path, data)
    return f"hook added to {path}"


def uninstall_gemini() -> bool:
    return _uninstall_json_hook(HOME / ".gemini" / "settings.json", "BeforeAgent")


def install_cursor() -> str:
    path = HOME / ".cursor" / "hooks.json"
    if _json_has_hook(path):
        return "already installed, skipped"

    data = _load_json(path)
    data.setdefault("version", 1)
    hooks_root = data.setdefault("hooks", {})
    event_list = hooks_root.setdefault("beforeSubmitPrompt", [])
    event_list.append({
        "command": _hook_command("cursor"),
        "timeout": 5,
    })
    _save_json(path, data)
    return f"hook added to {path}"


def uninstall_cursor() -> bool:
    path = HOME / ".cursor" / "hooks.json"
    if not path.exists():
        return False
    data = _load_json(path)
    event_list = data.get("hooks", {}).get("beforeSubmitPrompt", [])
    cleaned = [e for e in event_list if HOOK_MARKER not in e.get("command", "")]
    if len(cleaned) < len(event_list):
        data["hooks"]["beforeSubmitPrompt"] = cleaned
        _save_json(path, data)
        return True
    return False


def install_copilot() -> str:
    hooks_dir = HOME / ".copilot" / "hooks"
    path = hooks_dir / "pleasantries.json"
    if path.exists() and _json_has_hook(path):
        return "already installed, skipped"

    data = {
        "version": 1,
        "hooks": {
            "UserPromptSubmit": [
                {
                    "type": "command",
                    "command": _hook_command("copilot-chat"),
                    "timeout": 5,
                }
            ]
        },
    }
    _save_json(path, data)
    return f"hook created at {path}"


def uninstall_copilot() -> bool:
    path = HOME / ".copilot" / "hooks" / "pleasantries.json"
    if path.exists():
        path.unlink()
        return True
    return False


def install_qwen() -> str:
    path = HOME / ".qwen" / "settings.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "qwen", timeout=5000)
    return f"hook added to {path}"


def uninstall_qwen() -> bool:
    return _uninstall_json_hook(HOME / ".qwen" / "settings.json", "UserPromptSubmit")


def install_junie() -> str:
    path = HOME / ".junie" / "config.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "junie", timeout=10)
    return f"hook added to {path}"


def uninstall_junie() -> bool:
    return _uninstall_json_hook(HOME / ".junie" / "config.json", "UserPromptSubmit")


def install_factory_droid() -> str:
    path = HOME / ".factory" / "hooks.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "factory-droid")
    return f"hook added to {path}"


def uninstall_factory_droid() -> bool:
    return _uninstall_json_hook(HOME / ".factory" / "hooks.json", "UserPromptSubmit")


def install_kimi_code() -> str:
    path = HOME / ".kimi-code" / "config.toml"
    if _toml_has_hook(path):
        return "already installed, skipped"

    block = f"""
[[hooks]]
event = "UserPromptSubmit"
command = "{_hook_command('kimi-code')}"
timeout = 5
"""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing + block, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(block.lstrip(), encoding="utf-8")
    return f"hook appended to {path}"


def uninstall_kimi_code() -> bool:
    path = HOME / ".kimi-code" / "config.toml"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if HOOK_MARKER not in text:
        return False
    # Remove the [[hooks]] block containing our marker
    lines = text.split("\n")
    result = []
    skip = False
    for line in lines:
        if line.strip() == "[[hooks]]":
            # Look ahead to see if this block contains our marker
            idx = lines.index(line)
            block_text = "\n".join(lines[idx : idx + 5])
            if HOOK_MARKER in block_text:
                skip = True
                continue
        if skip:
            if line.strip().startswith("[[") or (line.strip() == "" and result and result[-1].strip() == ""):
                skip = False
                if line.strip().startswith("[["):
                    result.append(line)
                continue
            continue
        result.append(line)
    path.write_text("\n".join(result), encoding="utf-8")
    return True


def install_grok() -> str:
    path = HOME / ".grok" / "user-settings.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "grok", timeout=10)
    return f"hook added to {path}"


def uninstall_grok() -> bool:
    return _uninstall_json_hook(HOME / ".grok" / "user-settings.json", "UserPromptSubmit")


def install_kun() -> str:
    path = HOME / ".kun" / "data" / "config.json"
    if _json_has_hook(path):
        return "already installed, skipped"

    data = _load_json(path)
    hooks_list = data.setdefault("hooks", [])
    hooks_list.append({
        "phase": "UserPromptSubmit",
        "command": _hook_command("kun"),
        "timeoutMs": 5000,
    })
    _save_json(path, data)
    return f"hook added to {path}"


def uninstall_kun() -> bool:
    path = HOME / ".kun" / "data" / "config.json"
    if not path.exists():
        return False
    data = _load_json(path)
    hooks_list = data.get("hooks", [])
    cleaned = [h for h in hooks_list if HOOK_MARKER not in h.get("command", "")]
    if len(cleaned) < len(hooks_list):
        data["hooks"] = cleaned
        _save_json(path, data)
        return True
    return False


def install_open_interpreter() -> str:
    path = HOME / ".openinterpreter" / "hooks.json"
    if _json_has_hook(path):
        return "already installed, skipped"
    _install_json_hook(path, "UserPromptSubmit", "open-interpreter", timeout=10)
    return f"hook added to {path}"


def uninstall_open_interpreter() -> bool:
    return _uninstall_json_hook(
        HOME / ".openinterpreter" / "hooks.json", "UserPromptSubmit"
    )


# ---------------------------------------------------------------------------
# CLI registry
# ---------------------------------------------------------------------------

CLI_REGISTRY = [
    {
        "name": "Claude Code",
        "id": "claude",
        "detect_dir": HOME / ".claude",
        "install": install_claude,
        "uninstall": uninstall_claude,
    },
    {
        "name": "Codex CLI",
        "id": "codex",
        "detect_dir": HOME / ".codex",
        "install": install_codex,
        "uninstall": uninstall_codex,
    },
    {
        "name": "Gemini CLI",
        "id": "gemini",
        "detect_dir": HOME / ".gemini",
        "install": install_gemini,
        "uninstall": uninstall_gemini,
    },
    {
        "name": "Cursor",
        "id": "cursor",
        "detect_dir": HOME / ".cursor",
        "install": install_cursor,
        "uninstall": uninstall_cursor,
    },
    {
        "name": "Copilot Chat",
        "id": "copilot",
        "detect_dir": HOME / ".copilot",
        "install": install_copilot,
        "uninstall": uninstall_copilot,
    },
    {
        "name": "Qwen Code",
        "id": "qwen",
        "detect_dir": HOME / ".qwen",
        "install": install_qwen,
        "uninstall": uninstall_qwen,
    },
    {
        "name": "Junie CLI",
        "id": "junie",
        "detect_dir": HOME / ".junie",
        "install": install_junie,
        "uninstall": uninstall_junie,
    },
    {
        "name": "Factory Droid",
        "id": "factory-droid",
        "detect_dir": HOME / ".factory",
        "install": install_factory_droid,
        "uninstall": uninstall_factory_droid,
    },
    {
        "name": "Kimi Code",
        "id": "kimi-code",
        "detect_dir": HOME / ".kimi-code",
        "install": install_kimi_code,
        "uninstall": uninstall_kimi_code,
    },
    {
        "name": "grok-cli",
        "id": "grok",
        "detect_dir": HOME / ".grok",
        "install": install_grok,
        "uninstall": uninstall_grok,
    },
    {
        "name": "Kun",
        "id": "kun",
        "detect_dir": HOME / ".kun",
        "install": install_kun,
        "uninstall": uninstall_kun,
    },
    {
        "name": "Open Interpreter",
        "id": "open-interpreter",
        "detect_dir": HOME / ".openinterpreter",
        "install": install_open_interpreter,
        "uninstall": uninstall_open_interpreter,
    },
]

# Workspace-only CLIs (detected but not globally installable)
WORKSPACE_ONLY = ["Kiro (.kiro/hooks/)", "Devin (.devin/hooks.v1.json)"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def copy_script() -> None:
    """Copy block_pleasantries.py to ~/.pleasantries/."""
    src = Path(__file__).parent / SCRIPT_NAME
    if not src.exists():
        print(f"Error: {src} not found. Run this from the pleasantries repo.")
        sys.exit(1)

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dst = INSTALL_DIR / SCRIPT_NAME
    shutil.copy2(src, dst)
    print(f"  Script copied to {dst}")


def detect_clis() -> list[dict]:
    """Return list of detected CLIs."""
    return [cli for cli in CLI_REGISTRY if cli["detect_dir"].is_dir()]


def do_install() -> None:
    print()
    print("Pleasantries Hook Installer")
    print("=" * 40)
    print()

    # Step 1: Copy script
    print("[1/3] Installing hook script...")
    copy_script()
    print()

    # Step 2: Detect
    print("[2/3] Scanning for installed AI coding CLIs...")
    print()
    detected = detect_clis()

    if not detected:
        print("  No supported AI coding CLIs detected.")
        print(f"  Looked for config dirs in {HOME}")
        return

    for i, cli in enumerate(detected, 1):
        print(f"  [{i}] {cli['name']:<20} ({cli['detect_dir']})")

    print()
    for ws in WORKSPACE_ONLY:
        print(f"  [-] {ws:<20} (workspace-only, use per-project)")

    print()

    # Step 3: Select
    choice = input("Select CLIs [1-{0}, a=all, q=quit]: ".format(len(detected))).strip()

    if choice.lower() == "q":
        print("Cancelled.")
        return

    if choice.lower() == "a":
        selected = detected
    else:
        indices = []
        for part in choice.replace(",", " ").split():
            try:
                idx = int(part) - 1
                if 0 <= idx < len(detected):
                    indices.append(idx)
            except ValueError:
                print(f"  Invalid selection: {part}")
        selected = [detected[i] for i in indices]

    if not selected:
        print("Nothing selected.")
        return

    # Step 4: Install
    print()
    print("[3/3] Installing hooks...")
    print()

    installed = 0
    skipped = 0
    for cli in selected:
        result = cli["install"]()
        if "skipped" in result:
            print(f"  \u2298 {cli['name']:<20} {result}")
            skipped += 1
        else:
            print(f"  \u2713 {cli['name']:<20} {result}")
            installed += 1

    print()
    print(f"Done! {installed} installed, {skipped} skipped.")
    print()
    print("Restart your CLI sessions for hooks to take effect.")


def do_uninstall() -> None:
    print()
    print("Pleasantries Hook Uninstaller")
    print("=" * 40)
    print()

    removed = 0
    for cli in CLI_REGISTRY:
        try:
            if cli["uninstall"]():
                print(f"  \u2713 {cli['name']:<20} hook removed")
                removed += 1
        except Exception as e:
            print(f"  ! {cli['name']:<20} error: {e}")

    # Optionally remove the script
    script_path = INSTALL_DIR / SCRIPT_NAME
    if script_path.exists():
        answer = input(f"\nRemove {INSTALL_DIR}? [y/N]: ").strip().lower()
        if answer == "y":
            shutil.rmtree(INSTALL_DIR)
            print(f"  Removed {INSTALL_DIR}")

    print()
    if removed:
        print(f"Done! {removed} hooks removed.")
    else:
        print("No hooks found to remove.")


def main() -> None:
    if "--uninstall" in sys.argv:
        do_uninstall()
    else:
        do_install()


if __name__ == "__main__":
    main()
