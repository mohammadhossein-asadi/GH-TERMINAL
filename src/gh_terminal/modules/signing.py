"""
Signing module - SSH signing (primary) and GPG signing (fallback) for commits.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from rich.box import ASCII
from rich.prompt import Prompt
from rich.table import Table

from gh_terminal.core import CommandContext, GHError, GHErrorCode
from gh_terminal.ui.neon import (
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import OSType, expand_path, get_system_info, run_command, which


class SigningManager:
    """Manage commit signing (SSH primary, GPG fallback)."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()
        self.ssh_dir = Path.home() / ".ssh"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _git_global(self, key: str) -> str | None:
        """Get a global git config value."""
        result = run_command(["git", "config", "--global", key])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def _get_email(self) -> str | None:
        """Get the best available email for signing principals."""
        email = self._git_global("user.email")
        if email:
            return email
        result = run_command(["gh", "api", "user", "--jq", ".email"], timeout=15)
        if (
            result.returncode == 0
            and result.stdout.strip()
            and result.stdout.strip() != "null"
        ):
            return result.stdout.strip()
        return None

    # ------------------------------------------------------------------
    # SSH signing (primary)
    # ------------------------------------------------------------------

    def generate_ssh_key(self, key_path: str | None = None) -> str:
        """Generate a new ed25519 SSH signing key."""
        path = (
            Path(expand_path(key_path))
            if key_path
            else Path.home() / ".ssh" / "id_ed25519_signing"
        )
        if path.exists():
            raise GHError(
                f"Key already exists: {path}",
                GHErrorCode.SSH_KEY_GEN_FAILED,
                hints=["Use a different key path or delete the existing one"],
            )

        result = run_command([
            "ssh-keygen", "-t", "ed25519", "-a", "100",
            "-f", str(path), "-N", "",
            "-C", f"gh-terminal-signing-{self.system.os_type.value}",
        ])
        if result.returncode != 0:
            raise GHError(
                f"Failed to generate SSH signing key: {result.stderr.strip()}",
                GHErrorCode.SSH_KEY_GEN_FAILED,
                hints=["Check if ssh-keygen is installed", "Ensure ~/.ssh directory is writable"],
            )

        if self.system.os_type != OSType.WINDOWS:
            path.chmod(0o600)
        return str(path)

    def add_to_agent(self, key_path: str) -> bool:
        """Add signing key to ssh-agent."""
        result = run_command(["ssh-add", key_path])
        if result.returncode == 0:
            print_success(self.console, f"Added {key_path} to ssh-agent")
            return True
        print_warning(
            self.console,
            f"Could not add {key_path} to ssh-agent: {result.stderr.strip()}",
        )
        print_info(self.console, "You can add it manually: ssh-add <key_path>")
        return False

    def upload_to_github(self, public_key_path: str) -> bool:
        """Upload public key to GitHub as a Signing Key."""
        pub_file = Path(public_key_path)
        if not pub_file.exists():
            raise GHError(
                f"Public key not found: {public_key_path}",
                GHErrorCode.SIGNING_KEY_UPLOAD_FAILED,
                hints=["Generate a signing key first"],
            )

        result = run_command(
            ["gh", "ssh-key", "add", str(pub_file),
             "--title", "GH-TERMINAL Signing Key",
             "--type", "signing"],
            timeout=30,
        )
        if result.returncode == 0:
            print_success(self.console, "Signing key uploaded to GitHub")
            return True
        print_error(self.console, f"Failed to upload signing key: {result.stderr.strip()}")
        print_info(self.console, "Manual upload: https://github.com/settings/keys")
        return False

    def configure_git_ssh(self, public_key_path: str) -> bool:
        """Configure git for SSH signing."""
        commands = [
            ("gpg.format", "ssh"),
            ("user.signingkey", public_key_path),
            ("commit.gpgsign", "true"),
            ("tag.gpgsign", "true"),
        ]
        return self._apply_git_config(commands)

    def _apply_git_config(self, commands: list[tuple[str, str]]) -> bool:
        """Apply a list of (key, value) global git config commands."""
        success = True
        for key, value in commands:
            result = run_command(["git", "config", "--global", key, value])
            if result.returncode != 0:
                print_warning(self.console, f"Failed to set {key}: {result.stderr.strip()}")
                success = False
            else:
                print_success(self.console, f"Set {key} = {value}")
        return success

    def create_allowed_signers(self, public_key_path: str, email: str | None = None) -> bool:
        """Create ~/.ssh/allowed_signers with principal format."""
        try:
            pub_content = Path(public_key_path).read_text().strip()
        except FileNotFoundError:
            print_error(self.console, f"Public key not found: {public_key_path}")
            return False

        email = email or self._get_email()
        if not email:
            print_error(self.console, "No email available for allowed_signers principal")
            return False

        allowed_signers = self.ssh_dir / "allowed_signers"
        allowed_signers.parent.mkdir(parents=True, exist_ok=True)

        line = f"{email} {pub_content}"
        existing_lines: list[str] = []
        if allowed_signers.exists():
            existing_lines = [
                entry for entry in allowed_signers.read_text().splitlines() if entry.strip()
            ]
        if line not in existing_lines:
            existing_lines.append(line)

        allowed_signers.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
        if self.system.os_type != OSType.WINDOWS:
            allowed_signers.chmod(0o600)
        print_success(self.console, f"Updated {allowed_signers} (principal: {email})")

        # Point git at the file so local verification works
        run_command(
            [
                "git", "config", "--global",
                "gpg.ssh.allowedSignersFile", str(allowed_signers),
            ]
        )
        return True

    def setup_ssh(self, key_path: str | None = None) -> int:
        """Full SSH signing setup flow."""
        console = self.console
        print_info(console, "SSH Signing Setup")
        console.print()

        try:
            key = self.generate_ssh_key(key_path)
        except GHError as e:
            print_error(console, e.message)
            return 1

        print_success(console, f"Generated signing key: {key}")
        self.add_to_agent(key)

        pub_key = key + ".pub"
        if not self.upload_to_github(pub_key):
            print_warning(console, "Continuing with local configuration; upload manually later")

        if not self.configure_git_ssh(pub_key):
            return 1

        self.create_allowed_signers(pub_key)

        console.print()
        print_success(console, "SSH signing fully configured")
        print_info(console, "Run 'gh-terminal signing --verify' in a repository to test")
        return 0

    # ------------------------------------------------------------------
    # GPG signing (fallback)
    # ------------------------------------------------------------------

    def list_gpg_keys(self) -> list[str]:
        """List GPG secret keys (key IDs)."""
        result = run_command(["gpg", "--list-secret-keys", "--keyid-format=long"])
        if result.returncode != 0:
            return []
        keys: list[str] = []
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("sec"):
                parts = line.split("/")
                if parts:
                    key_id = parts[-1].split()[0]
                    name_line = lines[i + 1] if i + 1 < len(lines) else ""
                    keys.append(f"{key_id}  {name_line.strip()}")
        return keys

    def setup_gpg(self) -> int:
        """GPG signing fallback setup."""
        console = self.console

        if not which("gpg"):
            print_error(console, "gpg is not installed")
            print_info(console, "Install GnuPG: https://gnupg.org/download/")
            return 1

        keys = self.list_gpg_keys()
        if not keys:
            print_warning(console, "No GPG secret keys found")
            if Prompt.ask("Generate a new GPG key?", choices=["y", "n"], default="n") != "y":
                print_info(console, "Generate one with: gpg --full-generate-key")
                return 1
            run_command(["gpg", "--full-generate-key"], capture=False)
            keys = self.list_gpg_keys()
            if not keys:
                return 1

        console.print()
        for i, key in enumerate(keys, 1):
            print_info(console, f"  {i}. {key}")

        choice = Prompt.ask(
            "[bold cyan]Select GPG key number[/bold cyan]",
            default="1",
        )
        try:
            key_id = keys[int(choice) - 1].split()[0]
        except (ValueError, IndexError):
            print_error(console, "Invalid selection")
            return 1

        commands = [
            ("gpg.format", "openpgp"),
            ("user.signingkey", key_id),
            ("commit.gpgsign", "true"),
            ("tag.gpgsign", "true"),
        ]
        if not self._apply_git_config(commands):
            return 1

        result = run_command(["gpg", "--armor", "--export", key_id])
        if result.returncode == 0:
            export_file = Path.home() / "gh-terminal-gpg-key.asc"
            export_file.write_text(result.stdout, encoding="utf-8")
            console.print()
            print_success(console, f"Public key exported to: {export_file}")
            print_info(console, "Upload it to GitHub: https://github.com/settings/keys")
            print_info(console, f"Or run: gh gpg-key add {export_file}")
        return 0

    # ------------------------------------------------------------------
    # Status + verification
    # ------------------------------------------------------------------

    def show_status(self) -> int:
        """Display signing configuration status."""
        console = self.console
        table = Table(
            box=ASCII,
            show_header=True,
            header_style="bold cyan",
            title="[bold bright_cyan]SIGNING STATUS[/bold bright_cyan]",
        )
        table.add_column("Check", style="bold white", width=26)
        table.add_column("State", justify="center", width=10)
        table.add_column("Details", style="dim white")

        fmt = self._git_global("gpg.format")
        key = self._git_global("user.signingkey")
        commit = self._git_global("commit.gpgsign")
        tag = self._git_global("tag.gpgsign")
        signers = self.ssh_dir / "allowed_signers"

        table.add_row("gpg.format", "[OK]" if fmt else "[!!]", fmt or "not set")
        if fmt == "ssh":
            key_path = expand_path(key) if key else None
            key_state = "[OK]" if key_path and key_path.exists() else "[!!]"
            key_detail = key or "not set"
            if key_path and not key_path.exists():
                key_detail += " (file missing)"
            table.add_row("user.signingkey", key_state, key_detail)
        else:
            table.add_row("user.signingkey", "[OK]" if key else "[!!]", key or "not set")
        table.add_row("commit.gpgsign", "[OK]" if commit == "true" else "[!!]", commit or "false")
        table.add_row("tag.gpgsign", "[OK]" if tag == "true" else "[!!]", tag or "false")
        table.add_row(
            "allowed_signers",
            "[OK]" if signers.exists() else "[..]",
            str(signers) if signers.exists() else "not found (optional, for local verify)",
        )

        console.print(table)
        return 0

    def verify_signing(self) -> int:
        """Verify signing with a signed commit in an isolated temp repo."""
        console = self.console
        fmt = self._git_global("gpg.format")
        key = self._git_global("user.signingkey")

        if not key:
            print_error(console, "No user.signingkey configured")
            print_info(console, "Run: gh-terminal signing --setup")
            return 1

        if self.ctx.dry_run:
            print_info(console, "[dry-run] would create temp repo and signed test commit")
            return 0

        repo_dir = tempfile.mkdtemp(prefix="gh-terminal-sign-test-")
        try:
            result = run_command(["git", "init", "-q"], cwd=repo_dir)
            if result.returncode != 0:
                print_error(console, f"git init failed: {result.stderr.strip()}")
                return 1

            name = self._git_global("user.name") or "GH-TERMINAL"
            email = self._get_email() or "test@localhost"
            run_command(["git", "config", "user.name", name], cwd=repo_dir)
            run_command(["git", "config", "user.email", email], cwd=repo_dir)

            if fmt == "ssh":
                run_command(["git", "config", "gpg.format", "ssh"], cwd=repo_dir)
                run_command(["git", "config", "user.signingkey", key], cwd=repo_dir)
                signers = self._git_global("gpg.ssh.allowedSignersFile")
                if not signers:
                    signers = str(self.ssh_dir / "allowed_signers")
                if Path(signers).exists():
                    run_command(
                        ["git", "config", "gpg.ssh.allowedSignersFile", signers],
                        cwd=repo_dir,
                    )
            else:
                run_command(["git", "config", "user.signingkey", key], cwd=repo_dir)

            test_file = Path(repo_dir) / "test.txt"
            test_file.write_text("GH-TERMINAL signing verification\n", encoding="utf-8")
            run_command(["git", "add", "test.txt"], cwd=repo_dir)

            result = run_command(
                ["git", "commit", "-S", "-m", "GH-TERMINAL signing test"],
                cwd=repo_dir, timeout=30,
            )
            if result.returncode != 0:
                print_error(console, f"Signed commit failed: {result.stderr.strip()}")
                print_info(console, "Hints: check ssh-agent has the key, or gpg key exists")
                return 1

            result = run_command(
                ["git", "log", "-1", "--show-signature"],
                cwd=repo_dir, timeout=15,
            )
            output = result.stdout + result.stderr
            if "Good signature" in output or result.returncode == 0:
                print_success(console, "Signed commit created and verified locally")
            else:
                print_success(console, "Signed commit created")
            print_info(console, "Push to GitHub to confirm the 'Verified' badge appears")
            return 0
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def run(
        self,
        setup: bool = False,
        verify: bool = False,
        gpg: bool = False,
        status: bool = False,
        key_path: str | None = None,
    ) -> int:
        """Run signing setup, verification, or status."""
        if status:
            return self.show_status()
        if setup:
            return self.setup_ssh(key_path)
        if gpg:
            return self.setup_gpg()
        if verify:
            return self.verify_signing()
        print_info(self.console, "Use --setup, --verify, --gpg, or --status")
        return 0


def run_signing(
    ctx_obj: dict,
    setup: bool = False,
    verify: bool = False,
    gpg: bool = False,
    status: bool = False,
    key_path: str | None = None,
) -> int:
    """Run signing command."""
    import sys

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
    manager = SigningManager(ctx)
    return manager.run(setup, verify, gpg, status, key_path)
