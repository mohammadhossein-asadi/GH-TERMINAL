"""
GH-TERMINAL v3.1 Neon Edition - Main Entry Point
"""

from __future__ import annotations

import sys

from rich.console import Console

from gh_terminal.core.cli import main as cli_main
from gh_terminal.core.config import get_config_manager
from gh_terminal.core.errors import setup_logging
from gh_terminal.ui.neon import NeonHeader


def run_interactive(ctx_obj: dict) -> int:
    """Run interactive GH-TERMINAL control panel."""
    import sys

    from gh_terminal.modules.interactive import run_main_panel

    if sys.platform == "win32":
        import os
        os.system("chcp 65001 >nul 2>&1")
        console = Console(
            force_terminal=True,
            force_interactive=False,
            legacy_windows=True,
        )
    else:
        console = Console()
    verbose = ctx_obj.get("verbose", False)
    config_dir = ctx_obj.get("config_dir")

    log_level = 10 if verbose else 20
    logger, _ = setup_logging(level=log_level, console=console)

    config = get_config_manager(config_dir)

    # Show header
    header = NeonHeader(console)
    header.print()

    # Run main control panel
    return run_main_panel(console, config, logger)


def main() -> int:
    """Main entry point."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
