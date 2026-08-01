#!/usr/bin/env python3
"""Interactive installer for the pleasantries pre-hook across AI coding CLIs.

Usage:
  python install.py              Install hooks (interactive TUI)
  python install.py --uninstall  Remove hooks from all configs

Dependencies: pip install rich InquirerPy
"""

import json
import shutil
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
except ImportError:
    print("Missing dependencies. Run: pip install rich InquirerPy")
    sys.exit(1)

HOME = Path.home()
INSTALL_DIR = HOME / ".pleasantries"
SCRIPT_NAME = "block_pleasantries.py"
HOOK_MARKER = "block_pleasantries"
SCRIPT_PATH_STR = str(INSTALL_DIR / SCRIPT_NAME)

console = Console()


def _python_cmd() -> str:
    return "python" if sys.platform == "win32" else "python3"


def _hook_command(cli_name: str) -> str:
    # Forward slashes work on all platforms and avoid TOML escape issues
    return f"{_python_cmd()} {SCRIPT_PATH_STR.replace(chr(92), '/')} {cli_name}"


# ---------------------------------------------------------------------------
# JSON config helpers
# ---------------------------------------------------------------------------


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
        kept = [h for h in group_hooks if HOOK_MARKER not in h.get("command", "")]
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
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "claude")
    return str(path)


def uninstall_claude() -> bool:
    return _uninstall_json_hook(HOME / ".claude" / "settings.json", "UserPromptSubmit")


def install_codex() -> str:
    hooks_path = HOME / ".codex" / "hooks.json"
    config_path = HOME / ".codex" / "config.toml"
    if _json_has_hook(hooks_path):
        return "skip"
    data = _load_json(hooks_path)
    hooks_root = data.setdefault("hooks", {})
    event_list = hooks_root.setdefault("UserPromptSubmit", [])
    event_list.append({"hooks": [{
        "type": "command",
        "command": _hook_command("codex"),
        "timeout": 5,
        "statusMessage": "Checking prompt",
    }]})
    _save_json(hooks_path, data)
    if config_path.exists():
        toml_text = config_path.read_text(encoding="utf-8")
        if "[features]" in toml_text and "hooks" not in toml_text.split("[features]")[1].split("[")[0]:
            toml_text = toml_text.replace("[features]", "[features]\nhooks = true", 1)
            config_path.write_text(toml_text, encoding="utf-8")
        elif "[features]" not in toml_text:
            config_path.write_text(toml_text + "\n[features]\nhooks = true\n", encoding="utf-8")
    return str(hooks_path)


def uninstall_codex() -> bool:
    return _uninstall_json_hook(HOME / ".codex" / "hooks.json", "UserPromptSubmit")


def install_gemini() -> str:
    path = HOME / ".gemini" / "settings.json"
    if _json_has_hook(path):
        return "skip"
    _install_json_hook(path, "BeforeAgent", "gemini", timeout=5000, extra_fields={"name": "block-pleasantries"})
    data = _load_json(path)
    for g in data.get("hooks", {}).get("BeforeAgent", []):
        for h in g.get("hooks", []):
            if HOOK_MARKER in h.get("command", ""):
                g["matcher"] = "*"
    _save_json(path, data)
    return str(path)


def uninstall_gemini() -> bool:
    return _uninstall_json_hook(HOME / ".gemini" / "settings.json", "BeforeAgent")


def install_cursor() -> str:
    path = HOME / ".cursor" / "hooks.json"
    if _json_has_hook(path):
        return "skip"
    data = _load_json(path)
    data.setdefault("version", 1)
    data.setdefault("hooks", {}).setdefault("beforeSubmitPrompt", []).append({
        "command": _hook_command("cursor"),
        "timeout": 5,
    })
    _save_json(path, data)
    return str(path)


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
    path = HOME / ".copilot" / "hooks" / "pleasantries.json"
    if path.exists() and _json_has_hook(path):
        return "skip"
    _save_json(path, {
        "version": 1,
        "hooks": {"UserPromptSubmit": [{
            "type": "command",
            "command": _hook_command("copilot-chat"),
            "timeout": 5,
        }]},
    })
    return str(path)


def uninstall_copilot() -> bool:
    path = HOME / ".copilot" / "hooks" / "pleasantries.json"
    if path.exists():
        path.unlink()
        return True
    return False


def install_qwen() -> str:
    path = HOME / ".qwen" / "settings.json"
    if _json_has_hook(path):
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "qwen", timeout=5000)
    return str(path)


def uninstall_qwen() -> bool:
    return _uninstall_json_hook(HOME / ".qwen" / "settings.json", "UserPromptSubmit")


def install_junie() -> str:
    path = HOME / ".junie" / "config.json"
    if _json_has_hook(path):
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "junie", timeout=10)
    return str(path)


def uninstall_junie() -> bool:
    return _uninstall_json_hook(HOME / ".junie" / "config.json", "UserPromptSubmit")


def install_factory_droid() -> str:
    path = HOME / ".factory" / "hooks.json"
    if _json_has_hook(path):
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "factory-droid")
    return str(path)


def uninstall_factory_droid() -> bool:
    return _uninstall_json_hook(HOME / ".factory" / "hooks.json", "UserPromptSubmit")


def install_kimi_code() -> str:
    path = HOME / ".kimi-code" / "config.toml"
    if _toml_has_hook(path):
        return "skip"
    block = f'\n[[hooks]]\nevent = "UserPromptSubmit"\ncommand = "{_hook_command("kimi-code")}"\ntimeout = 5\n'
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(block.lstrip(), encoding="utf-8")
    return str(path)


def uninstall_kimi_code() -> bool:
    path = HOME / ".kimi-code" / "config.toml"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if HOOK_MARKER not in text:
        return False
    lines = text.split("\n")
    result, skip = [], False
    for i, line in enumerate(lines):
        if line.strip() == "[[hooks]]":
            if HOOK_MARKER in "\n".join(lines[i : i + 5]):
                skip = True
                continue
        if skip:
            if line.strip().startswith("[["):
                skip = False
                result.append(line)
            continue
        result.append(line)
    path.write_text("\n".join(result), encoding="utf-8")
    return True


def install_grok() -> str:
    path = HOME / ".grok" / "user-settings.json"
    if _json_has_hook(path):
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "grok", timeout=10)
    return str(path)


def uninstall_grok() -> bool:
    return _uninstall_json_hook(HOME / ".grok" / "user-settings.json", "UserPromptSubmit")


def install_kun() -> str:
    path = HOME / ".kun" / "data" / "config.json"
    if _json_has_hook(path):
        return "skip"
    data = _load_json(path)
    data.setdefault("hooks", []).append({
        "phase": "UserPromptSubmit",
        "command": _hook_command("kun"),
        "timeoutMs": 5000,
    })
    _save_json(path, data)
    return str(path)


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
        return "skip"
    _install_json_hook(path, "UserPromptSubmit", "open-interpreter", timeout=10)
    return str(path)


def uninstall_open_interpreter() -> bool:
    return _uninstall_json_hook(HOME / ".openinterpreter" / "hooks.json", "UserPromptSubmit")


# ---------------------------------------------------------------------------
# CLI registry
# ---------------------------------------------------------------------------

CLI_REGISTRY = [
    {"name": "Claude Code", "id": "claude", "detect_dir": HOME / ".claude", "install": install_claude, "uninstall": uninstall_claude},
    {"name": "Codex CLI", "id": "codex", "detect_dir": HOME / ".codex", "install": install_codex, "uninstall": uninstall_codex},
    {"name": "Gemini CLI", "id": "gemini", "detect_dir": HOME / ".gemini", "install": install_gemini, "uninstall": uninstall_gemini},
    {"name": "Cursor", "id": "cursor", "detect_dir": HOME / ".cursor", "install": install_cursor, "uninstall": uninstall_cursor},
    {"name": "Copilot Chat", "id": "copilot", "detect_dir": HOME / ".copilot", "install": install_copilot, "uninstall": uninstall_copilot},
    {"name": "Qwen Code", "id": "qwen", "detect_dir": HOME / ".qwen", "install": install_qwen, "uninstall": uninstall_qwen},
    {"name": "Junie CLI", "id": "junie", "detect_dir": HOME / ".junie", "install": install_junie, "uninstall": uninstall_junie},
    {"name": "Factory Droid", "id": "factory-droid", "detect_dir": HOME / ".factory", "install": install_factory_droid, "uninstall": uninstall_factory_droid},
    {"name": "Kimi Code", "id": "kimi-code", "detect_dir": HOME / ".kimi-code", "install": install_kimi_code, "uninstall": uninstall_kimi_code},
    {"name": "grok-cli", "id": "grok", "detect_dir": HOME / ".grok", "install": install_grok, "uninstall": uninstall_grok},
    {"name": "Kun", "id": "kun", "detect_dir": HOME / ".kun", "install": install_kun, "uninstall": uninstall_kun},
    {"name": "Open Interpreter", "id": "open-interpreter", "detect_dir": HOME / ".openinterpreter", "install": install_open_interpreter, "uninstall": uninstall_open_interpreter},
]

WORKSPACE_ONLY = ["Kiro (.kiro/hooks/)", "Devin (.devin/hooks.v1.json)"]


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

BANNER = r"""
 ____  _                       _
|  _ \| | ___  __ _ ___  ___ _ __(_) ___  ___
| |_) | |/ _ \/ _` / __|/ _ \ '__| |/ _ \/ __|
|  __/| |  __/ (_| \__ \  __/ |  | |  __/\__ \
|_|   |_|\___|\__,_|___/\___|_|  |_|\___||___/
"""


def show_banner() -> None:
    banner = Text(BANNER, style="bold cyan")
    console.print(Panel(banner, border_style="cyan", expand=False))
    console.print("  [dim]Block pleasantry-only prompts across AI coding CLIs[/dim]\n")


def detect_and_display() -> list[dict]:
    detected = [cli for cli in CLI_REGISTRY if cli["detect_dir"].is_dir()]

    table = Table(show_header=True, header_style="bold magenta", box=None, pad_edge=False)
    table.add_column("", width=4)
    table.add_column("CLI", min_width=20)
    table.add_column("Config dir", style="dim")
    table.add_column("Status", justify="right")

    for cli in detected:
        hook_path = cli["detect_dir"]
        already = False
        # Quick check if hook already exists in any config under this dir
        for f in hook_path.rglob("*"):
            if f.is_file() and f.suffix in (".json", ".toml"):
                try:
                    if HOOK_MARKER in f.read_text(encoding="utf-8"):
                        already = True
                        break
                except (OSError, UnicodeDecodeError):
                    pass

        status = "[yellow]installed[/yellow]" if already else "[green]ready[/green]"
        table.add_row("", cli["name"], str(cli["detect_dir"]), status)

    for ws in WORKSPACE_ONLY:
        table.add_row("", ws, "[dim]workspace-only[/dim]", "[dim]manual[/dim]")

    console.print(table)
    console.print()
    return detected


def select_clis(detected: list[dict]) -> list[dict]:
    if not detected:
        console.print("[red]No supported AI coding CLIs detected.[/red]")
        return []

    choices = [
        Choice(value=cli, name=f"{cli['name']}  ({cli['detect_dir']})")
        for cli in detected
    ]

    selected = inquirer.checkbox(
        message="Select CLIs to install the hook:",
        choices=choices,
        cycle=True,
        instruction="(space to toggle, enter to confirm)",
        long_instruction="Arrow keys to navigate, space to toggle, enter to confirm.",
        validate=lambda result: len(result) > 0,
        invalid_message="Select at least one CLI.",
    ).execute()

    return selected


def copy_script() -> None:
    src = Path(__file__).parent / SCRIPT_NAME
    if not src.exists():
        console.print(f"[red]Error:[/red] {src} not found. Run this from the pleasantries repo.")
        sys.exit(1)
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, INSTALL_DIR / SCRIPT_NAME)


def do_install() -> None:
    show_banner()

    with console.status("[cyan]Copying hook script...[/cyan]", spinner="dots"):
        copy_script()
    console.print(f"  [green]>[/green] Script installed to [bold]{INSTALL_DIR / SCRIPT_NAME}[/bold]\n")

    with console.status("[cyan]Scanning for installed CLIs...[/cyan]", spinner="dots"):
        detected = detect_and_display()

    if not detected:
        return

    selected = select_clis(detected)
    if not selected:
        return

    console.print()

    results = {"installed": [], "skipped": []}
    for cli in selected:
        with console.status(f"[cyan]Installing {cli['name']}...[/cyan]", spinner="dots"):
            result = cli["install"]()

        if result == "skip":
            console.print(f"  [yellow]>[/yellow] {cli['name']:<20} [yellow]already installed, skipped[/yellow]")
            results["skipped"].append(cli["name"])
        else:
            console.print(f"  [green]>[/green] {cli['name']:<20} [green]{result}[/green]")
            results["installed"].append(cli["name"])

    console.print()

    summary = Text()
    summary.append(f"{len(results['installed'])} installed", style="bold green")
    if results["skipped"]:
        summary.append(f"  |  {len(results['skipped'])} skipped", style="yellow")
    console.print(Panel(summary, title="Done", border_style="green", expand=False))
    console.print("\n  [dim]Restart your CLI sessions for hooks to take effect.[/dim]\n")


def do_uninstall() -> None:
    show_banner()
    console.print("  [bold red]Uninstall mode[/bold red]\n")

    removed = 0
    for cli in CLI_REGISTRY:
        try:
            if cli["uninstall"]():
                console.print(f"  [green]>[/green] {cli['name']:<20} [green]hook removed[/green]")
                removed += 1
        except Exception as e:
            console.print(f"  [red]![/red] {cli['name']:<20} [red]error: {e}[/red]")

    if INSTALL_DIR.exists():
        remove = inquirer.confirm(
            message=f"Remove {INSTALL_DIR}?",
            default=False,
        ).execute()
        if remove:
            shutil.rmtree(INSTALL_DIR)
            console.print(f"  [green]>[/green] Removed {INSTALL_DIR}")

    console.print()
    if removed:
        console.print(Panel(Text(f"{removed} hooks removed", style="bold green"), title="Done", border_style="green", expand=False))
    else:
        console.print(Panel(Text("No hooks found", style="yellow"), title="Done", border_style="yellow", expand=False))
    console.print()


def main() -> None:
    if "--uninstall" in sys.argv:
        do_uninstall()
    else:
        do_install()


if __name__ == "__main__":
    main()
