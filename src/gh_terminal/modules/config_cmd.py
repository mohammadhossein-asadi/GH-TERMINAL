"""
Config command module - Manage configuration.
"""

from __future__ import annotations

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import NeonPanel, print_info, print_success


def run_config(
    ctx_obj: dict,
    key: str | None = None,
    value: str | None = None,
    list_all: bool = False,
    reset: bool = False,
    export: bool = False,
) -> int:
    """Run config command."""
    import sys

    from rich.console import Console

    from gh_terminal.core.config import get_config_manager

    console = Console(
        force_terminal=True,
        force_interactive=False,
        legacy_windows=True,
    ) if sys.platform == "win32" else Console()

    ctx = CommandContext(
        console=ctx_obj.get("console", console),
        config=ctx_obj.get("config") or get_config_manager(ctx_obj.get("config_dir")),
        error_handler=ctx_obj.get("error_handler"),
        verbose=ctx_obj.get("verbose", False),
        dry_run=ctx_obj.get("dry_run", False),
    )

    config = ctx.config.config

    if reset:
        config = ctx.config.reset()
        print_success(ctx.console, "Configuration reset to defaults")
        return 0

    if export:
        checklist = ctx.config.export_checklist()
        ctx.console.print(NeonPanel.create("Setup Checklist", checklist, border_style="green"))
        return 0

    if list_all:
        import yaml
        yaml_text = yaml.dump(config.__dict__, default_flow_style=False)
        ctx.console.print(NeonPanel.create("Current Configuration", yaml_text))
        return 0

    if key and value:
        if ctx.config.set(key, value):
            print_success(ctx.console, f"Set {key} = {value}")
        else:
            print_info(ctx.console, f"Failed to set {key}")
        return 0

    if key:
        val = ctx.config.get(key)
        if val is not None:
            ctx.console.print(f"{key} = {val}")
        else:
            print_info(ctx.console, f"Key '{key}' not found")
        return 0

    print_info(ctx.console, "Use --list, --reset, --export, or key [value]")
    return 0
