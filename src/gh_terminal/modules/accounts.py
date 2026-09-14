"""
Accounts module - Manage multiple GitHub accounts with directory-scoped identities.
"""

from __future__ import annotations

import re

from rich.box import ASCII
from rich.prompt import Confirm, Prompt
from rich.table import Table

from gh_terminal.core import CommandContext
from gh_terminal.modules.identity import IdentityManager
from gh_terminal.ui.neon import (
    NeonPanel,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import expand_path, get_system_info, run_command, which


class AccountManager:
    """Manage multiple GitHub accounts and their directory-scoped git identities."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()
        self.identity = IdentityManager(ctx)

    # ------------------------------------------------------------------
    # gh auth helpers
    # ------------------------------------------------------------------

    def gh_users(self) -> list[str]:
        """List GitHub usernames known to gh auth."""
        if not which("gh"):
            return []
        result = run_command(["gh", "auth", "list"], timeout=15)
        output = (result.stdout or "") + (result.stderr or "")
        users = re.findall(r"account\s+(\S+?)\s+\(", output)
        seen: list[str] = []
        for user in users:
            if user not in seen:
                seen.append(user)
        return seen

    def active_user(self) -> str | None:
        """Get the currently active GitHub user."""
        result = run_command(["gh", "api", "user", "--jq", ".login"], timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    # ------------------------------------------------------------------
    # Local account state (gh-terminal.yaml)
    # ------------------------------------------------------------------

    def _saved_accounts(self) -> dict[str, dict[str, str]]:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return {}
        accounts = config.get("multi_account.accounts", {})
        return accounts if isinstance(accounts, dict) else {}

    def _save_account(self, name: str, info: dict[str, str]) -> None:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return
        accounts = self._saved_accounts()
        accounts[name] = info
        config.set("multi_account.accounts", accounts)

    def _delete_account(self, name: str) -> None:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return
        accounts = self._saved_accounts()
        accounts.pop(name, None)
        config.set("multi_account.accounts", accounts)

    def _saved_includes(self) -> dict[str, str]:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return {}
        includes = config.get("multi_account.conditional_includes", {})
        return includes if isinstance(includes, dict) else {}

    def _save_include(self, directory: str, account: str) -> None:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return
        includes = self._saved_includes()
        includes[directory] = account
        config.set("multi_account.conditional_includes", includes)

    def _delete_include(self, directory: str) -> None:
        config = getattr(self.ctx, "config", None)
        if config is None:
            return
        includes = self._saved_includes()
        includes.pop(directory, None)
        config.set("multi_account.conditional_includes", includes)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_accounts(self) -> int:
        """Display gh accounts, saved account identities, and conditional includes."""
        console = self.console
        console.print()

        gh_users = self.gh_users()
        active = self.active_user()

        gh_table = Table(
            box=ASCII, show_header=True, header_style="bold cyan",
            title="[bold bright_cyan]GITHUB CLI ACCOUNTS[/bold bright_cyan]",
        )
        gh_table.add_column("User", style="bold white", width=30)
        gh_table.add_column("State", justify="center", width=12)
        if gh_users:
            for user in gh_users:
                is_active = user == active
                gh_table.add_row(user, "[green]ACTIVE[/green]" if is_active else "available")
        else:
            gh_table.add_row("[none]", "-")
        console.print(gh_table)
        console.print()

        saved = self._saved_accounts()
        if saved:
            table = Table(box=ASCII, show_header=True, header_style="bold cyan")
            table.add_column("Account", style="bold white", width=26)
            table.add_column("Email", style="white", width=32)
            table.add_column("SSH Key", style="dim white")
            for name, info in sorted(saved.items()):
                table.add_row(name, info.get("email", "-"), info.get("ssh_key", "-"))
            console.print(table)
            console.print()

        self.identity.show_includes()
        return 0

    # ------------------------------------------------------------------
    # Add / remove
    # ------------------------------------------------------------------

    def _prompt_account_details(
        self, user: str, profile: dict[str, str]
    ) -> tuple[str, str, str, str] | None:
        """Prompt for account identity details. Returns (name, email, ssh_key, directory)."""
        console = self.console

        default_name = profile.get("name") or user
        name = Prompt.ask("[bold cyan]Git user.name[/bold cyan]", default=default_name).strip()
        if not name:
            print_error(console, "user.name cannot be empty")
            return None

        noreply = self.identity.suggested_noreply_email()
        default_email = profile.get("email") or (noreply if noreply else "")
        email = Prompt.ask(
            "[bold cyan]Git user.email[/bold cyan] [dim](empty = use noreply)[/dim]",
            default=default_email,
        ).strip()
        if not email and noreply:
            email = noreply
            print_info(console, f"Using noreply email: {email}")
        if not email or not self.identity.validate_email(email):
            print_error(console, "A valid email is required")
            return None

        ssh_key = Prompt.ask(
            "[bold cyan]SSH key for this account[/bold cyan] [dim](path or blank)[/dim]",
            default="",
        ).strip()
        if ssh_key:
            ssh_key = str(expand_path(ssh_key))

        directory = Prompt.ask(
            "[bold cyan]Directory to bind this identity to[/bold cyan] "
            "[dim](e.g. ~/work, blank = no auto-bind)[/dim]",
            default="",
        ).strip()
        return name, email, ssh_key, directory

    def add_account(self, user: str | None = None) -> int:
        """Add an account: gh auth (optional) + directory-scoped git identity."""
        console = self.console

        gh_users = self.gh_users()
        if gh_users:
            print_info(console, "Accounts known to gh: " + ", ".join(gh_users))

        if user is None:
            user = Prompt.ask(
                "[bold cyan]GitHub username for the new account[/bold cyan] "
                "[dim](must exist in gh auth list, or blank = active)[/dim]",
                default="",
            ).strip() or self.active_user()
        if not user:
            print_error(console, "No GitHub username available")
            return 1

        profile: dict[str, str] = {}
        if self.active_user() == user:
            profile = self.identity.github_profile()

        prompted = self._prompt_account_details(user, profile)
        if prompted is None:
            return 1
        name, email, ssh_key, directory = prompted

        console.print()
        if directory:
            self.identity.add_conditional_include(
                directory, user, name, email,
                ssh_key.replace("\\", "/") if ssh_key else "",
            )
        elif Confirm.ask(
            "[bold yellow]Apply this identity globally as default?[/bold yellow]",
            default=False,
        ):
            self.identity.configure_identity(name, email, ssh_key)

        self._save_account(user, {"email": email, "name": name, "ssh_key": ssh_key})
        if directory:
            self._save_include(str(expand_path(directory)), user)

        console.print()
        print_success(console, f"Account '{user}' configured")
        return 0

    def remove_account(self, user: str) -> int:
        """Remove an account: gh logout + remove includes + delete identity file."""
        console = self.console

        includes = self._saved_includes()
        for directory, account in list(includes.items()):
            if account == user:
                self.identity.remove_conditional_include(directory)
                self._delete_include(directory)

        safe_user = re.sub(r"[^A-Za-z0-9._-]", "_", user)
        identity_file = self.identity.identities_dir / f"{safe_user}.gitconfig"
        if identity_file.exists():
            try:
                identity_file.unlink()
                print_info(console, f"Deleted {identity_file}")
            except Exception as e:
                print_warning(console, f"Could not delete {identity_file}: {e}")

        self._delete_account(user)

        gh_users = self.gh_users()
        if user in gh_users and Confirm.ask(
            f"Also logout '{user}' from GitHub CLI?", default=False
        ):
                result = run_command(
                    ["gh", "auth", "logout", "--hostname", "github.com", "--user", user],
                    timeout=20,
                )
                if result.returncode == 0:
                    print_success(console, f"Logged out '{user}' from gh")
                else:
                    print_warning(console, f"gh logout failed: {result.stderr.strip()}")

        print_success(console, f"Account '{user}' removed")
        return 0

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_account(self, user: str) -> int:
        """Switch the active GitHub account (gh + saved default)."""
        console = self.console

        gh_users = self.gh_users()
        if gh_users and user not in gh_users:
            print_warning(console, f"'{user}' not in gh auth list: {', '.join(gh_users)}")
            return 1

        result = run_command(
            ["gh", "auth", "switch", "--hostname", "github.com", "--user", user],
            timeout=20,
        )
        if result.returncode != 0:
            print_error(console, f"gh auth switch failed: {result.stderr.strip()}")
            return 1

        config = getattr(self.ctx, "config", None)
        if config is not None:
            config.set("multi_account.default_account", user)

        print_success(console, f"Switched to account: {user}")
        profile = self.identity.github_profile()
        if profile.get("email"):
            print_info(console, f"Active profile email: {profile['email']}")
        return 0

    def set_default_account(self, user: str) -> int:
        """Set the default account (switches gh and records in config)."""
        return self.switch_account(user)

    def interactive_switcher(self) -> int:
        """Interactive account context switcher."""
        console = self.console

        gh_users = self.gh_users()
        saved = self._saved_accounts()
        active = self.active_user()

        options: list[str] = []
        for user in gh_users:
            label = user + (" (active)" if user == active else "")
            if user in saved:
                label += f" - {saved[user].get('email', '')}"
            options.append(label)

        if not options and saved:
            options = [f"{user} - {info.get('email', '')}" for user, info in sorted(saved.items())]

        if not options:
            print_warning(console, "No accounts found. Add one: gh-terminal accounts --add")
            return 1

        console.print()
        for i, label in enumerate(options, 1):
            print_info(console, f"  {i}. {label}")
        console.print()

        choice = Prompt.ask(
            "[bold cyan]Switch to account number (or Enter to cancel)[/bold cyan]",
            default="",
        ).strip()
        if not choice or not choice.isdigit() or not (1 <= int(choice) <= len(options)):
            print_info(console, "Switch cancelled")
            return 0

        target = options[int(choice) - 1].split(" (")[0].split(" - ")[0]
        return self.switch_account(target)

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def run(
        self,
        list_accounts: bool = False,
        add: str | None = None,
        add_interactive: bool = False,
        remove: str | None = None,
        switch: str | None = None,
        switch_menu: bool = False,
        default: str | None = None,
    ) -> int:
        """Run accounts subcommands."""
        if list_accounts:
            return self.list_accounts()
        if add is not None or add_interactive:
            return self.add_account(add or None)
        if remove:
            return self.remove_account(remove)
        if switch_menu:
            return self.interactive_switcher()
        if switch:
            return self.switch_account(switch)
        if default:
            return self.set_default_account(default)
        console = self.console
        console.print(NeonPanel.create(
            "ACCOUNTS",
            "--list : show accounts and conditional identities\n"
            "--add [user]   configure a new account identity\n"
            "--remove <user>  remove an account\n"
            "--switch <user>  switch active account\n"
            "--switch-menu    interactive account picker\n"
            "--default <user> set default account",
        ))
        return 0


def run_accounts(
    ctx_obj: dict,
    list_accounts: bool = False,
    add: str | None = None,
    add_interactive: bool = False,
    remove: str | None = None,
    switch: str | None = None,
    switch_menu: bool = False,
    default: str | None = None,
) -> int:
    """Run accounts command."""
    import sys

    from rich.console import Console

    console = Console(
        force_terminal=True,
        force_interactive=False,
        legacy_windows=True,
    ) if sys.platform == "win32" else Console()

    from gh_terminal.core.config import get_config_manager

    config = ctx_obj.get("config") or get_config_manager(ctx_obj.get("config_dir"))
    ctx = CommandContext(
        console=ctx_obj.get("console", console),
        config=config,
        error_handler=ctx_obj.get("error_handler"),
        verbose=ctx_obj.get("verbose", False),
        dry_run=ctx_obj.get("dry_run", False),
    )

    manager = AccountManager(ctx)
    return manager.run(list_accounts, add, add_interactive, remove, switch, switch_menu, default)
