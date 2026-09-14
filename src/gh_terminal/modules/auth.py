"""
Auth module - Manage GitHub CLI authentication and lifecycle.
"""

from __future__ import annotations

import sys

from rich.box import ASCII
from rich.table import Table

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import OSType, run_command, which


def get_gh_path() -> str | None:
    """Get gh CLI path."""
    return which("gh")


def get_gh_version() -> str | None:
    """Get gh CLI version."""
    result = run_command(["gh", "--version"])
    if result.returncode == 0:
        return result.stdout.strip().split("\n")[0].replace("gh version ", "")
    return None


def detect_os_install_command(os_type: OSType) -> str:
    """Get the installation command for the current OS."""
    if os_type == OSType.WINDOWS:
        return "winget install --id GitHub.cli"
    elif os_type == OSType.MACOS:
        return "brew install gh"
    elif os_type in (OSType.LINUX, OSType.WSL):
        return "sudo apt install gh"
    return "https://cli.github.com/"


def run_gh_auth_login(ctx: CommandContext) -> int:
    """Authenticate with GitHub using gh CLI."""
    from gh_terminal.utils.system import get_system_info

    system = get_system_info()
    console = ctx.console

    print_info(console, "Starting GitHub CLI authentication...")
    console.print()

    # Check if gh is installed
    gh_path = get_gh_path()
    if not gh_path:
        print_error(console, "GitHub CLI (gh) is not installed")
        console.print()
        print_info(console, f"Install command: {detect_os_install_command(system.os_type)}")
        console.print()
        if ctx.config and ctx.config.config.get("security", {}).get("require_signing", True):
            print_warning(console, "Authentication required for signing configuration")
        return 1

    # Check if already authenticated
    status_result = run_command(["gh", "auth", "status"])
    if status_result.returncode == 0 and "Logged in to" in status_result.stdout:
        print_success(console, "Already authenticated with GitHub")
        console.print()
        print_info(console, "Use --switch to change accounts or --logout to sign out")
        return 0

    # Launch interactive login
    console.print()
    print_info(console, "Launching gh auth login (browser preferred)...")
    console.print()

    result = run_command(["gh", "auth", "login"], capture=False)

    if result.returncode == 0:
        print_success(console, "Successfully authenticated with GitHub")
        console.print()
        configure_gh_settings(ctx)
        return 0
    else:
        print_error(console, "Authentication failed")
        console.print()
        print_info(console, "Alternative: use token authentication")
        console.print()
        print_info(console, "  gh auth login --with-token < token.txt")
        return 1


def configure_gh_settings(ctx: CommandContext) -> None:
    """Configure gh CLI settings after authentication."""
    console = ctx.console

    # Set protocol to SSH
    result = run_command(["gh", "config", "set", "git_protocol", "ssh"])
    if result.returncode == 0:
        print_success(console, "Set git protocol to SSH")
    else:
        print_warning(console, "Could not set git protocol to SSH")

    # Set editor
    editor = get_editor()
    if editor:
        result = run_command(["gh", "config", "set", "editor", editor])
        if result.returncode == 0:
            print_success(console, f"Set editor to {editor}")

    # Set prompt
    result = run_command(["gh", "config", "set", "prompt", "enabled"])
    if result.returncode == 0:
        print_success(console, "Set prompt to enabled")

    print_info(console, "GitHub CLI configuration complete")


def get_editor() -> str | None:
    """Detect available editor."""
    for editor in ["code --wait", "vim", "nano", "code"]:
        if which(editor.split()[0]):
            return editor
    return None


def run_gh_auth_logout(ctx: CommandContext) -> int:
    """Logout from GitHub."""
    console = ctx.console

    if not confirm_action(console, "This will log you out of all GitHub accounts. Continue?"):
        print_info(console, "Logout cancelled")
        return 0

    result = run_command(["gh", "auth", "logout", "--yes"])
    if result.returncode == 0:
        print_success(console, "Successfully logged out from GitHub")
        return 0
    else:
        print_error(console, "Logout failed")
        return 1


def confirm_action(console, message: str) -> bool:
    """Simple confirmation prompt."""
    from rich.prompt import Confirm
    return Confirm.ask(f"[bold yellow]{message}[/bold yellow]", default=False)


def run_gh_auth_status(ctx: CommandContext) -> int:
    """Show authentication status."""
    console = ctx.console

    gh_path = get_gh_path()
    if not gh_path:
        print_error(console, "GitHub CLI (gh) is not installed")
        console.print()
        print_info(console, f"Install: {detect_os_install_command(OSType.WINDOWS)}")
        return 1

    version = get_gh_version()
    status_result = run_command(["gh", "auth", "status"])

    # Build status table
    table = Table(box=ASCII, show_header=True, header_style="bold cyan")
    table.add_column("Field", style="bold white", width=20)
    table.add_column("Value", style="white")

    table.add_row("gh version", version or "Unknown")
    table.add_row("gh path", gh_path)

    if status_result.returncode == 0:
        lines = status_result.stdout.strip().split("\n")
        for line in lines:
            if "Logged in to" in line:
                table.add_row("Account", line.strip())
            elif "git_protocol" in line or "hostname" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    table.add_row(parts[0].strip(), parts[1].strip())

        print_success(console, "Authenticated with GitHub")
    else:
        table.add_row("Status", "Not authenticated")
        print_warning(console, "Not authenticated with GitHub")

    console.print()
    console.print(table)
    console.print()

    return 0


def run_gh_auth_switch(ctx: CommandContext, account: str) -> int:
    """Switch to a different GitHub account."""
    console = ctx.console

    if not account:
        print_info(console, "Usage: gh-terminal auth --switch <account>")
        return 1

    result = run_command(["gh", "auth", "switch", "--hostname", "github.com", "--user", account])
    if result.returncode == 0:
        print_success(console, f"Switched to account: {account}")
        return 0
    else:
        print_error(console, f"Failed to switch to account: {account}")
        return 1


def run_gh_auth_token(ctx: CommandContext, token: str) -> int:
    """Login with a personal access token."""
    console = ctx.console

    if not token:
        print_info(console, "Usage: gh-terminal auth --token <token>")
        console.print()
        print_info(console, "Token read from stdin (pipe): gh-terminal auth --token - < token.txt")
        return 1

    print_info(console, "Authenticating with token...")
    console.print()

    result = run_command(
        ["gh", "auth", "login", "--with-token"],
        input=token if token != "-" else None,
    )
    if result.returncode == 0:
        print_success(console, "Successfully authenticated with token")
        configure_gh_settings(ctx)
        return 0
    else:
        print_error(console, "Token authentication failed")
        return 1


def run_gh_install(ctx: CommandContext) -> int:
    """Install GitHub CLI."""
    from gh_terminal.utils.system import get_system_info

    system = get_system_info()
    console = ctx.console

    print_info(console, f"Installing GitHub CLI for {system.os_type.value}...")
    console.print()

    cmd = detect_os_install_command(system.os_type)
    print_info(console, f"Running: {cmd}")
    console.print()

    try:
        if system.os_type == OSType.WINDOWS:
            run_command(cmd, shell=True, capture=False)
        else:
            run_command(cmd.split(), capture=False)
        print_success(console, "GitHub CLI installed successfully")
    except Exception as e:
        print_error(console, f"Installation failed: {e}")
        return 1

    console.print()
    run_gh_auth_login(ctx)
    return 0


def run_auth(
    ctx_obj: dict,
    login: bool = False,
    logout: bool = False,
    status: bool = False,
    switch: str | None = None,
    token: str | None = None,
) -> int:
    """Run auth command."""
    from rich.console import Console

    console = Console(
        force_terminal=True,
        force_interactive=False,
        legacy_windows=True,
    ) if sys.platform == "win32" else Console()

    ctx = CommandContext(
        console=ctx_obj.get("console", console),
        config=ctx_obj.get("config"),
        error_handler=ctx_obj.get("error_handler"),
        verbose=ctx_obj.get("verbose", False),
        dry_run=ctx_obj.get("dry_run", False),
    )

    if login:
        return run_gh_auth_login(ctx)

    if logout:
        return run_gh_auth_logout(ctx)

    if status:
        return run_gh_auth_status(ctx)

    if switch:
        return run_gh_auth_switch(ctx, switch)

    if token is not None:
        return run_gh_auth_token(ctx, token)

    print_info(ctx.console, "Use --login, --logout, --status, --switch, or --token")
    return 0
