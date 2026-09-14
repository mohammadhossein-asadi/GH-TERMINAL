"""
CLI entry point and command registry for GH-TERMINAL.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import click
from rich.console import Console

from gh_terminal.core.config import ConfigManager, get_config_manager
from gh_terminal.core.errors import (
    GHErrorHandler,
    setup_logging,
)
from gh_terminal.ui.neon import (
    print_error,
)


@dataclass
class CommandContext:
    """Context passed to commands."""

    console: Console
    config: ConfigManager
    error_handler: GHErrorHandler
    verbose: bool = False
    dry_run: bool = False


class BaseCommand(ABC):
    """Base class for all commands."""

    name: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)

    @abstractmethod
    def execute(self, ctx: CommandContext, *args, **kwargs) -> int:
        """Execute the command. Return exit code."""
        pass

    def validate(self, ctx: CommandContext, *args, **kwargs) -> bool:
        """Validate preconditions. Return True if valid."""
        return True


class CommandRegistry:
    """Registry for all available commands."""

    def __init__(self):
        self._commands: dict[str, BaseCommand] = {}
        self._aliases: dict[str, str] = {}

    def register(self, command: BaseCommand) -> None:
        """Register a command."""
        self._commands[command.name] = command
        for alias in command.aliases:
            self._aliases[alias] = command.name

    def get(self, name: str) -> BaseCommand | None:
        """Get command by name or alias."""
        name = self._aliases.get(name, name)
        return self._commands.get(name)

    def list_commands(self) -> list[BaseCommand]:
        """List all registered commands."""
        return list(self._commands.values())

    def get_names(self) -> list[str]:
        """Get all command names and aliases."""
        names = list(self._commands.keys())
        names.extend(self._aliases.keys())
        return sorted(set(names))


# Global registry
registry = CommandRegistry()


def command(name: str, description: str = "", aliases: list[str] | None = None):
    """Decorator to register a command class."""

    def decorator(cls: type[BaseCommand]):
        cls.name = name
        cls.description = description
        cls.aliases = aliases or []
        registry.register(cls())
        return cls

    return decorator


def get_cli_app() -> click.Group:
    """Create the Click CLI application."""

    @click.group(
        name="gh-terminal",
        help="GH-TERMINAL v3.1 Neon Edition â€” GitHub Control Plane",
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    @click.version_option(version="3.1.0", prog_name="GH-TERMINAL")
    @click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
    @click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
    @click.option("--config-dir", type=click.Path(path_type=Path), help="Custom config directory")
    @click.pass_context
    def cli(ctx: click.Context, verbose: bool, dry_run: bool, config_dir: Path | None):
        """GH-TERMINAL - Ultimate GitHub Configuration & Management System"""
        ctx.ensure_object(dict)
        ctx.obj["verbose"] = verbose
        ctx.obj["dry_run"] = dry_run
        ctx.obj["config_dir"] = config_dir

    @cli.command("start")
    @click.pass_context
    def start_cmd(ctx: click.Context):
        """Start the interactive GH-TERMINAL control panel."""
        from gh_terminal.__main__ import run_interactive
        run_interactive(ctx.obj)

    @cli.command("doctor")
    @click.pass_context
    def doctor_cmd(ctx: click.Context):
        """Run system diagnostics and health check."""
        from gh_terminal.modules.diagnostics import run_diagnostics
        run_diagnostics(ctx.obj)

    @cli.command("setup")
    @click.option("--wizard", is_flag=True, help="Run full guided setup wizard")
    @click.pass_context
    def setup_cmd(ctx: click.Context, wizard: bool):
        """Run setup wizard or quick configuration."""
        from gh_terminal.modules.setup import run_setup
        run_setup(ctx.obj, wizard=wizard)

    @cli.command("config")
    @click.argument("key", required=False)
    @click.argument("value", required=False)
    @click.option("--list", "list_all", is_flag=True, help="List all configuration")
    @click.option("--reset", is_flag=True, help="Reset to defaults")
    @click.option("--export", is_flag=True, help="Export checklist")
    @click.pass_context
    def config_cmd(ctx: click.Context, key: str, value: str, list_all: bool,
                     reset: bool, export: bool):
        """Manage configuration."""
        from gh_terminal.modules.config_cmd import run_config
        run_config(ctx.obj, key, value, list_all, reset, export)

    @cli.command("identity")
    @click.option("--name", help="Set git user.name")
    @click.option("--email", help="Set git user.email")
    @click.option("--signing-key", help="Set signing key path")
    @click.option(
        "--format",
        "gpg_format",
        type=click.Choice(["ssh", "gpg"]),
        help="Set signing format",
    )
    @click.option("--list", "list_identities", is_flag=True, help="List configured identities")
    @click.option("--local", "use_local", is_flag=True, help="Apply to this repository only")
    @click.option("--noreply", is_flag=True, help="Use GitHub private noreply email")
    @click.option("--check-email", "check_email_addr", help="Validate email vs GitHub account")
    @click.option("--include", "include_dir", help="Conditional identity for a directory")
    @click.option("--remove-include", "remove_include", help="Remove a conditional identity")
    @click.option("--list-includes", "list_includes", is_flag=True, help="List conditional rules")
    @click.pass_context
    def identity_cmd(ctx: click.Context, name: str, email: str, signing_key: str, gpg_format: str,
                     list_identities: bool, use_local: bool, noreply: bool, check_email_addr: str,
                     include_dir: str, remove_include: str, list_includes: bool):
        """Manage Git identity (global, local, multi-account conditional includes)."""
        from gh_terminal.modules.identity import run_identity
        run_identity(
            ctx.obj, name, email, signing_key, gpg_format, list_identities,
            use_local, noreply, check_email_addr, include_dir, remove_include,
            list_includes,
        )

    @cli.command("signing")
    @click.option("--setup", is_flag=True, help="Setup SSH commit signing")
    @click.option("--verify", is_flag=True, help="Verify signing setup")
    @click.option("--gpg", is_flag=True, help="Use GPG instead of SSH")
    @click.option("--status", is_flag=True, help="Show signing configuration status")
    @click.option("--key-path", help="Custom signing key path")
    @click.pass_context
    def signing_cmd(ctx: click.Context, setup: bool, verify: bool, gpg: bool,
                    status: bool, key_path: str):
        """Manage commit signing."""
        from gh_terminal.modules.signing import run_signing
        run_signing(ctx.obj, setup, verify, gpg, status, key_path)

    @cli.command("ssh")
    @click.option("--generate", is_flag=True, help="Generate new SSH key")
    @click.option("--key-name", help="Custom key name for --generate")
    @click.option("--signing", is_flag=True, help="Also generate a signing key")
    @click.option("--list", "list_keys", is_flag=True, help="List SSH keys")
    @click.option("--upload", help="Upload key to GitHub (key path or 'all')")
    @click.option("--test", is_flag=True, help="Test SSH connection to GitHub")
    @click.option("--config", is_flag=True, help="Manage SSH config hosts")
    @click.option("--agent", is_flag=True, help="Manage ssh-agent (status, start, add)")
    @click.option("--pat", is_flag=True, help="PAT hygiene audit and guidance")
    @click.pass_context
    def ssh_cmd(ctx: click.Context, generate: bool, key_name: str, signing: bool,
                list_keys: bool, upload: str, test: bool, config: bool,
                agent: bool, pat: bool):
        """Manage SSH keys."""
        from gh_terminal.modules.ssh_keys import run_ssh
        run_ssh(ctx.obj, generate, key_name, signing, list_keys, upload, test,
                config, agent, pat)

    @cli.command("auth")
    @click.option("--login", is_flag=True, help="Authenticate with GitHub")
    @click.option("--logout", is_flag=True, help="Logout from GitHub")
    @click.option("--status", is_flag=True, help="Show authentication status")
    @click.option("--switch", help="Switch to different account")
    @click.option("--token", help="Login with token (stdin or file)")
    @click.pass_context
    def auth_cmd(ctx: click.Context, login: bool, logout: bool, status: bool,
                 switch: str, token: str):
        """Manage GitHub CLI authentication."""
        from gh_terminal.modules.auth import run_auth
        run_auth(ctx.obj, login, logout, status, switch, token)

    @cli.command("repo")
    @click.option("--create", "create", help="Create new repository (name)")
    @click.option("--clone", "clone_repo", help="Clone repository (owner/repo)")
    @click.option("--fork", "fork_repo", help="Fork repository (owner/repo)")
    @click.option("--list", "list_repos", is_flag=True, help="List repositories")
    @click.option("--public/--private", "public", default=None, help="Repository visibility")
    @click.option("--remote", "remote", help="Remote name (default: origin)")
    @click.option("--description", help="Repository description")
    @click.option("--readme", is_flag=True, help="Add README on create")
    @click.option("--gitignore", help="Gitignore template (e.g. Python)")
    @click.option("--license", "license_name", help="License template (e.g. mit)")
    @click.option("--remotes", is_flag=True, help="List remotes in current repo")
    @click.option("--remote-add", help="Add remote: 'name url'")
    @click.option("--remote-remove", help="Remove remote by name")
    @click.option("--remote-rename", help="Rename remote: 'old new'")
    @click.option("--remote-seturl", help="Set remote URL: 'name url'")
    @click.option("--default-branch", "default_branch", help="Set default branch of a repo")
    @click.option("--collaborators", is_flag=True, help="List collaborators")
    @click.option("--add-collaborator", "collab_add", help="Add collaborator: 'user [permission]'")
    @click.option("--remove-collaborator", "collab_remove", help="Remove collaborator (user)")
    @click.option("--insights", is_flag=True, help="Show repository insights")
    @click.option("--protect", "protect", is_flag=True, help="Branch protection setup")
    @click.option("--codeowners", is_flag=True, help="CODEOWNERS setup")
    @click.pass_context
    def repo_cmd(ctx: click.Context, create, clone_repo, fork_repo, list_repos, public,
                 remote, description, readme, gitignore, license_name, remotes,
                 remote_add, remote_remove, remote_rename, remote_seturl, default_branch,
                 collaborators, collab_add, collab_remove, insights, protect, codeowners):
        """Manage repositories."""
        from gh_terminal.modules.repo import run_repo
        run_repo(ctx.obj, create, clone_repo, fork_repo, list_repos, public, remote,
                 description, readme, gitignore, license_name, remotes, remote_add,
                 remote_remove, remote_rename, remote_seturl, default_branch,
                 collaborators, collab_add, collab_remove, insights, protect, codeowners)

    @cli.command("security")
    @click.option("--audit", is_flag=True, help="Run security audit")
    @click.option("--harden", is_flag=True, help="Apply security hardening")
    @click.option("--report", is_flag=True, help="Generate security report")
    @click.pass_context
    def security_cmd(ctx: click.Context, audit: bool, harden: bool, report: bool):
        """Security audit and hardening."""
        from gh_terminal.modules.security import run_security
        run_security(ctx.obj, audit, harden, report)

    @cli.command("accounts")
    @click.option("--list", "list_accounts", is_flag=True, help="List configured accounts")
    @click.option("--add", "add", help="Add account (username, or flag alone for interactive)")
    @click.option("--remove", help="Remove account (username)")
    @click.option("--switch", help="Switch to account (username)")
    @click.option("--switch-menu", "switch_menu", is_flag=True, help="Interactive account picker")
    @click.option("--default", help="Set default account")
    @click.pass_context
    def accounts_cmd(ctx: click.Context, list_accounts: bool, add: str, remove: str,
                     switch: str, switch_menu: bool, default: str):
        """Manage multiple GitHub accounts."""
        from gh_terminal.modules.accounts import run_accounts
        run_accounts(ctx.obj, list_accounts, add, remove, switch, switch_menu, default)

    @cli.command("advanced")
    @click.option("--actions", is_flag=True, help="Manage GitHub Actions secrets")
    @click.option("--codespaces", is_flag=True, help="Manage Codespaces")
    @click.option("--packages", is_flag=True, help="Manage GitHub Packages")
    @click.option("--aliases", is_flag=True, help="Manage gh aliases")
    @click.option("--extensions", is_flag=True, help="Manage gh extensions")
    @click.option("--org", help="Organization name (for org roles)")
    @click.option("--dashboard", is_flag=True, help="Show live status dashboard")
    @click.option("--export-script", is_flag=True, help="Export reusable setup script")
    @click.option("--repo", "repo_arg", help="Target repository (owner/repo)")
    @click.pass_context
    def advanced_cmd(ctx: click.Context, actions: bool, codespaces: bool, packages: bool,
                     aliases: bool, extensions: bool, org: str, dashboard: bool,
                     export_script: bool, repo_arg: str):
        """Advanced power-user features."""
        from gh_terminal.modules.advanced import run_advanced
        run_advanced(
            ctx.obj, actions, codespaces, packages, aliases, dashboard,
            extensions, org, export_script, repo_arg,
        )

    return cli


def create_context(ctx: click.Context) -> CommandContext:
    """Create command context from Click context."""
    import sys
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
    verbose = ctx.obj.get("verbose", False)
    dry_run = ctx.obj.get("dry_run", False)
    config_dir = ctx.obj.get("config_dir")

    # Setup logging
    log_level = 10 if verbose else 20  # DEBUG or INFO
    logger, _ = setup_logging(level=log_level, console=console)

    # Get config manager
    config = get_config_manager(config_dir)

    # Create error handler
    error_handler = GHErrorHandler(console, logger)

    return CommandContext(
        console=console,
        config=config,
        error_handler=error_handler,
        verbose=verbose,
        dry_run=dry_run,
    )


def main() -> int:
    """Main entry point."""
    cli = get_cli_app()

    # If no args, show help
    if len(sys.argv) == 1:
        cli.main(["--help"], standalone_mode=False)
        return 0

    try:
        return cli.main(standalone_mode=False)
    except click.exceptions.Exit as e:
        return e.exit_code
    except Exception as e:
        if sys.platform == "win32":
            import os
            os.system("chcp 65001 >nul 2>&1")
            console = Console(
                stderr=True,
                force_terminal=True,
                force_interactive=False,
                legacy_windows=True,
            )
        else:
            console = Console(stderr=True)
        print_error(console, f"Fatal error: {e}")
        if "--verbose" in sys.argv or "-v" in sys.argv:
            console.print_exception()
        return 1


if __name__ == "__main__":
    sys.exit(main())
