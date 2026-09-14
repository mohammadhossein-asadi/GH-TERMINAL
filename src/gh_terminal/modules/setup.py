"""
Setup module - Full guided setup wizard and quick configuration.
"""

from __future__ import annotations

from pathlib import Path

from rich.prompt import Confirm, Prompt

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonHeader,
    NeonPanel,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import OSType, get_system_info, run_command, which


class SetupWizard:
    """Full guided setup wizard."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.config = ctx.config
        self.system = get_system_info()

    def run(self) -> int:
        """Run the full setup wizard."""
        header = NeonHeader(self.console)
        header.print()

        self.console.print()
        print_info(self.console, "Welcome to GH-TERMINAL Setup Wizard!")
        print_info(self.console, "This will guide you through configuring your GitHub environment.")
        self.console.print()

        steps = [
            ("System Diagnostics", self._step_diagnostics),
            ("GitHub CLI Install & Auth", self._step_gh_cli),
            ("Git Identity", self._step_git_identity),
            ("SSH Keys & Signing", self._step_ssh_signing),
            ("Security Hardening", self._step_security),
        ]

        for i, (name, step_fn) in enumerate(steps, 1):
            self.console.print()
            self.console.print(NeonPanel.create(f"Step {i}/{len(steps)}: {name}", ""))
            self.console.print()

            try:
                step_fn()
                print_success(self.console, f"✓ {name} completed")
            except Exception as e:
                print_error(self.console, f"✗ {name} failed: {e}")
                if not Confirm.ask("[yellow]Continue anyway?[/yellow]", default=True):
                    return 1

        self.console.print()
        print_success(self.console, "Setup wizard completed successfully!")
        self.console.print()
        self._print_summary()

        return 0

    def _ctx_obj(self) -> dict:
        """Build a ctx dict for module functions."""
        return {
            "console": self.console,
            "config": self.config,
            "error_handler": None,
            "verbose": False,
            "dry_run": False,
        }

    def _step_diagnostics(self) -> None:
        """Run system diagnostics."""
        from gh_terminal.modules.diagnostics import run_diagnostics
        run_diagnostics(self._ctx_obj())

    def _step_gh_cli(self) -> None:
        """Install and authenticate GitHub CLI."""
        gh_path = which("gh")
        if not gh_path:
            print_warning(self.console, "GitHub CLI (gh) not found")
            install_cmd = self._get_gh_install_cmd()
            print_info(self.console, f"Install command: {install_cmd}")
            if Confirm.ask("Install now?", default=True):
                is_windows = self.system.os_type == OSType.WINDOWS
                run_command(
                    install_cmd if is_windows else install_cmd.split(),
                    shell=is_windows, capture=False,
                )
                print_success(self.console, "GitHub CLI installed")

        auth_result = run_command(["gh", "auth", "status"])
        if auth_result.returncode != 0 or "Logged in to" not in auth_result.stdout:
            print_info(self.console, "Authenticating with GitHub...")
            if Confirm.ask("Use browser authentication (recommended)?", default=True):
                run_command(["gh", "auth", "login"], capture=False)
            else:
                print_info(self.console, "Run: gh auth login --with-token < token.txt")
        else:
            print_success(self.console, "Already authenticated")

        run_command(["gh", "config", "set", "git_protocol", "ssh"])
        run_command(["gh", "config", "set", "prompt", "enabled"])
        print_success(self.console, "GitHub CLI configured (SSH protocol)")

    def _step_git_identity(self) -> None:
        """Configure Git identity."""
        current_name = run_command(["git", "config", "--global", "user.name"])
        current_email = run_command(["git", "config", "--global", "user.email"])

        if current_name.returncode == 0 and current_email.returncode == 0:
            current = f"{current_name.stdout.strip()} <{current_email.stdout.strip()}>"
            print_info(self.console, f"Current: {current}")
            if not Confirm.ask("Update identity?", default=False):
                return

        default_name = current_name.stdout.strip() if current_name.returncode == 0 else ""
        default_email = current_email.stdout.strip() if current_email.returncode == 0 else ""
        name = Prompt.ask("Enter your name", default=default_name)
        email = Prompt.ask("Enter your email", default=default_email)

        run_command(["git", "config", "--global", "user.name", name])
        run_command(["git", "config", "--global", "user.email", email])
        print_success(self.console, "Git identity updated")

    def _step_ssh_signing(self) -> None:
        """Setup SSH keys and commit signing."""
        from gh_terminal.modules.signing import run_signing
        from gh_terminal.modules.ssh_keys import run_ssh

        print_info(self.console, "Setting up SSH keys and commit signing...")
        self.console.print()

        auth_key = Path.home() / ".ssh" / "id_ed25519"
        if not auth_key.exists() and Confirm.ask(
            "Generate SSH authentication key?", default=True
        ):
            run_ssh(self._ctx_obj(), generate=True)

        sign_key = Path.home() / ".ssh" / "id_ed25519_signing"
        if not sign_key.exists() and Confirm.ask(
            "Generate SSH signing key?", default=True
        ):
            run_signing(self._ctx_obj(), setup=True)

        run_ssh(self._ctx_obj(), test=True)

    def _step_security(self) -> None:
        """Apply security hardening."""
        from gh_terminal.modules.security import run_security

        print_info(self.console, "Applying security hardening...")
        run_security(self._ctx_obj(), harden=True)

    def _get_gh_install_cmd(self) -> str:
        """Get installation command for current OS."""
        if self.system.os_type == OSType.WINDOWS:
            return "winget install --id GitHub.cli"
        elif self.system.os_type == OSType.MACOS:
            return "brew install gh"
        elif self.system.os_type in (OSType.LINUX, OSType.WSL):
            return "sudo apt install gh"
        return "https://cli.github.com/"

    def _print_summary(self) -> None:
        """Print setup summary."""
        checklist = self.config.export_checklist()
        self.console.print(NeonPanel.create("Setup Checklist", checklist, border_style="green"))


def run_setup(ctx_obj: dict, wizard: bool = False) -> int:
    """Run setup command."""
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

    wizard_runner = SetupWizard(ctx)

    if wizard:
        return wizard_runner.run()
    else:
        print_info(ctx.console, "Quick setup - run with --wizard for full guided setup")
        # Quick setup: run diagnostics and show status
        from gh_terminal.modules.diagnostics import run_diagnostics
        return run_diagnostics(ctx_obj)
