"""
SSH Keys module - Manage SSH keys, agent, config, and PAT hygiene.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from rich.box import ASCII
from rich.prompt import Confirm, Prompt
from rich.table import Table

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonPanel,
    StatusBadge,
    StatusTable,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import OSType, get_system_info, run_command


class SSHManager:
    """Manage SSH keys, ssh-agent, SSH config, and PAT hygiene."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()
        self.ssh_dir = Path.home() / ".ssh"

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    def _ensure_ssh_dir(self) -> bool:
        """Ensure ~/.ssh directory exists with correct permissions."""
        try:
            self.ssh_dir.mkdir(parents=True, exist_ok=True)
            if self.system.os_type != OSType.WINDOWS:
                self.ssh_dir.chmod(0o700)
        except Exception as e:
            print_error(self.console, f"Failed to create SSH directory: {e}")
            return False
        return True

    def _set_key_permissions(self, key_path: Path) -> bool:
        """Set proper permissions for SSH key files."""
        try:
            if self.system.os_type != OSType.WINDOWS:
                key_path.chmod(0o600)
                pub = key_path.with_suffix(".pub")
                if pub.exists():
                    pub.chmod(0o644)
            else:
                print_info(
                    self.console,
                    f"Windows: lock down '{key_path.name}' via Properties > Security "
                    "(remove inherited access, keep only your user)",
                )
        except Exception:
            return False
        return True

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def list_keys(self) -> int:
        """List all SSH keys in ~/.ssh."""
        if not self.ssh_dir.exists():
            print_warning(self.console, f"SSH directory not found: {self.ssh_dir}")
            return 0

        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Type", style="bold white", width=14)
        table.add_column("Filename", style="white", width=26)
        table.add_column("Fingerprint", style="dim white", max_width=48)
        table.add_column("Perms", style="white", width=6)

        found = False
        for key_file in sorted(self.ssh_dir.glob("*")):
            if key_file.name.endswith(".pub") or key_file.name in (
                "known_hosts", "authorized_keys", "config", "allowed_signers",
            ):
                continue
            if not key_file.is_file():
                continue
            found = True
            fp = "N/A"
            try:
                fp_result = run_command(["ssh-keygen", "-l", "-f", str(key_file)])
                if fp_result.returncode == 0:
                    fp = fp_result.stdout.strip().split(" ", 2)[-1].split("(")[0].strip()
            except Exception:
                fp = "Error"

            perm = oct(key_file.stat().st_mode & 0o777)[2:]
            key_type = "Private"
            pub = key_file.with_suffix(".pub")
            if pub.exists():
                pub_content = pub.read_text(errors="ignore").strip()
                key_type = pub_content.split()[0] if pub_content else "Unknown"
            else:
                key_type = "Private"
            table.add_row(key_type, key_file.name, fp, perm)

        if not found:
            print_warning(self.console, "No private SSH keys found")
            print_info(self.console, "Generate one: gh-terminal ssh --generate")
            return 0

        self.console.print(table)
        return 0

    def generate_keys(
        self,
        key_type: str = "ed25519",
        key_name: str | None = None,
        comment: str | None = None,
        signing: bool = False,
    ) -> int:
        """Generate SSH key pair(s)."""
        if not self._ensure_ssh_dir():
            return 1

        if comment is None:
            comment = f"gh-terminal-{self.system.os_type.value}"

        keys_to_generate: list[tuple[Path, str]] = []
        if key_name:
            keys_to_generate.append((self.ssh_dir / key_name, comment))
        else:
            auth_key = self.ssh_dir / "id_ed25519"
            sign_key = self.ssh_dir / "id_ed25519_signing"
            keys_to_generate.append((auth_key, comment))
            if signing:
                keys_to_generate.append((sign_key, f"{comment}-signing"))

        for key_path, key_comment in keys_to_generate:
            if key_path.exists():
                print_warning(self.console, f"Key already exists: {key_path}")
                continue
            result = run_command(
                ["ssh-keygen", "-t", key_type, "-a", "100", "-f", str(key_path),
                 "-N", "", "-C", key_comment]
            )
            if result.returncode != 0:
                detail = f"Failed to generate {key_path.name}: {result.stderr.strip()}"
                print_error(self.console, detail)
                return 1
            self._set_key_permissions(key_path)
            print_success(self.console, f"Generated: {key_path}")

        print_info(self.console, "Upload to GitHub: gh-terminal ssh --upload <key-name>")
        return 0

    def upload_key(self, key_path: str, key_type: str = "authentication") -> int:
        """Upload public key to GitHub."""
        key_file = Path(key_path).expanduser()
        if not key_file.exists():
            key_file = self.ssh_dir / key_path
        if not key_file.exists():
            print_error(self.console, f"Key not found: {key_file}")
            return 1

        pub_file = key_file if key_file.suffix == ".pub" else key_file.with_suffix(".pub")
        if not pub_file.exists():
            print_error(self.console, f"Public key not found: {pub_file}")
            return 1

        gh_type = (
            "signing"
            if "signing" in key_type.lower() or "signing" in key_file.name
            else "authentication"
        )
        date = datetime.now().strftime("%Y-%m-%d")
        title = f"GH-TERMINAL {gh_type} key - {self.system.os_type.value} - {date}"

        result = run_command(
            ["gh", "ssh-key", "add", str(pub_file), "--title", title, "--type", gh_type],
            timeout=30,
        )
        if result.returncode == 0:
            print_success(self.console, f"Uploaded {gh_type} key: {pub_file.name}")
            return 0
        print_error(self.console, f"Failed to upload key: {result.stderr.strip()}")
        return 1

    def test_connection(self) -> int:
        """Test SSH connection to GitHub."""
        print_info(self.console, "Testing SSH connection to GitHub...")
        result = run_command(["ssh", "-T", "git@github.com"], capture=True, timeout=20)
        output = (result.stdout or "") + (result.stderr or "")

        if "successfully authenticated" in output.lower() or "hi " in output.lower():
            print_success(self.console, "SSH connection successful")
            for line in output.splitlines():
                if "hi " in line.lower():
                    print_info(self.console, line.strip())
            return 0
        if result.returncode in (0, 1):
            print_warning(self.console, "Connection attempted but auth unclear")
            print_info(self.console, output.strip()[:300])
            return 0
        print_error(self.console, f"SSH connection failed: {output.strip()[:300]}")
        print_info(self.console, "Ensure the key is added: gh-terminal ssh --agent")
        return 1

    # ------------------------------------------------------------------
    # SSH agent management
    # ------------------------------------------------------------------

    def agent_status(self) -> tuple[int, str]:
        """Return (loaded key count, status detail)."""
        result = run_command(["ssh-add", "-l"], timeout=10)
        if result.returncode == 0:
            keys = [k for k in result.stdout.splitlines() if k.strip()]
            return len(keys), "Agent running"
        if result.returncode == 1:
            return 0, "Agent running, no keys"
        return 0, "Agent not running"

    def agent_start(self) -> int:
        """Start ssh-agent cross-platform."""
        console = self.console

        if self.system.os_type == OSType.WINDOWS:
            result = run_command(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Service ssh-agent | Select-Object -ExpandProperty Status"],
                timeout=15,
            )
            if "Running" not in result.stdout:
                print_info(console, "Starting Windows ssh-agent service (may require elevation)...")
                run_command(
                    ["powershell", "-NoProfile", "-Command",
                     "Start-Process powershell -Verb RunAs -Wait -ArgumentList "
                     "'-NoProfile -Command Set-Service ssh-agent -StartupType Automatic; "
                     "Start-Service ssh-agent'"],
                    capture=False, timeout=60,
                )
                count, detail = self.agent_status()
                if "running" in detail.lower():
                    print_success(console, "ssh-agent started")
                else:
                    detail = "Agent service start could not be confirmed (elevation required?)"
                    print_warning(console, detail)
            else:
                print_success(console, "ssh-agent already running")
        else:
            if not os.environ.get("SSH_AUTH_SOCK"):
                print_info(console, "SSH_AUTH_SOCK not set. Run in your shell:")
                print_info(console, "  eval $(ssh-agent)")
                return 1
            print_success(console, "ssh-agent is available")

        count, detail = self.agent_status()
        print_info(console, f"{detail} ({count} key(s) loaded)")
        return 0

    def agent_add(self, key_path: str | None = None) -> int:
        """Add a key to ssh-agent."""
        if key_path is None:
            candidates = [
                self.ssh_dir / "id_ed25519",
                self.ssh_dir / "id_ed25519_signing",
            ]
            keys = [k for k in candidates if k.exists()]
            if not keys:
                print_error(self.console, "No keys found to add")
                return 1
            key_path = str(keys[0])

        key_file = Path(key_path).expanduser()
        if not key_file.exists():
            key_file = self.ssh_dir / key_path
        if not key_file.exists():
            print_error(self.console, f"Key not found: {key_file}")
            return 1

        result = run_command(["ssh-add", str(key_file)], timeout=15)
        if result.returncode == 0:
            print_success(self.console, f"Added {key_file.name} to ssh-agent")
            return 0
        print_error(self.console, f"ssh-add failed: {result.stderr.strip()}")
        return 1

    def agent_manage(self) -> int:
        """Show agent status and offer to start/add."""
        console = self.console
        count, detail = self.agent_status()
        status_table = StatusTable("SSH Agent")
        badge = StatusBadge.SUCCESS if count > 0 else (
            StatusBadge.WARNING if "running" in detail.lower() else StatusBadge.FAILED
        )
        status_table.add_row("ssh-agent", badge, f"{detail} ({count} key(s))")
        console.print(status_table.render())
        console.print()

        if count == 0:
            if "not running" in detail.lower() and Confirm.ask("Start ssh-agent?", default=True):
                self.agent_start()
                count, _ = self.agent_status()
            if count == 0 and Confirm.ask("Add default key to agent?", default=True):
                return self.agent_add()
        return 0

    # ------------------------------------------------------------------
    # SSH config management
    # ------------------------------------------------------------------

    def _config_path(self) -> Path:
        return self.ssh_dir / "config"

    def config_list_hosts(self) -> list[dict]:
        """Parse ~/.ssh/config into host entries."""
        config_file = self._config_path()
        if not config_file.exists():
            return []
        hosts: list[dict] = []
        current: dict | None = None
        for raw in config_file.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition(" ")
            value = value.strip()
            if key.lower() == "host":
                if current:
                    hosts.append(current)
                current = {"host": value, "hostname": "", "user": "", "identityfile": ""}
            elif current is not None:
                current[key.lower()] = value
        if current:
            hosts.append(current)
        return hosts

    def config_show(self) -> int:
        """Display SSH config hosts."""
        console = self.console
        hosts = self.config_list_hosts()
        if not hosts:
            print_warning(console, "No Host entries found in ~/.ssh/config")
            return 0
        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Host", style="bold cyan")
        table.add_column("HostName", style="white")
        table.add_column("User", style="white")
        table.add_column("IdentityFile", style="dim white")
        for h in hosts:
            table.add_row(
                h.get("host", ""),
                h.get("hostname") or "-",
                h.get("user") or "-",
                h.get("identityfile") or "-",
            )
        console.print(table)
        return 0

    def config_add_host(
        self,
        alias: str,
        hostname: str = "github.com",
        user: str = "git",
        identity_file: str | None = None,
        port: int | None = None,
    ) -> int:
        """Add or replace a Host block in ~/.ssh/config."""
        if not self._ensure_ssh_dir():
            return 1
        identity_file = identity_file or "~/.ssh/id_ed25519"

        block_lines = [f"  HostName {hostname}", f"  User {user}"]
        if port:
            block_lines.append(f"  Port {port}")
        block_lines.append(f"  IdentityFile {identity_file}")
        block_lines.append("  IdentitiesOnly yes")
        block = ["Host " + alias, *block_lines]
        block = "\n".join(block)

        config_file = self._config_path()
        content = config_file.read_text(errors="ignore") if config_file.exists() else ""

        pattern = re.compile(
            rf"(?ms)^Host\s+{re.escape(alias)}\s*$.*?(?=^Host\s|\Z)"
        )
        if pattern.search(content):
            content = pattern.sub(block + "\n\n", content)
            action = "Updated"
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += block + "\n\n"
            action = "Added"

        config_file.write_text(content, encoding="utf-8")
        print_success(self.console, f"{action} Host '{alias}' in {config_file}")
        print_info(self.console, f"Use with: git@{alias}:owner/repo.git")
        return 0

    def config_remove_host(self, alias: str) -> int:
        """Remove a Host block from ~/.ssh/config."""
        config_file = self._config_path()
        if not config_file.exists():
            print_warning(self.console, "No SSH config file found")
            return 1
        content = config_file.read_text(errors="ignore")
        pattern = re.compile(
            rf"(?ms)^Host\s+{re.escape(alias)}\s*$.*?(?=^Host\s|\Z)"
        )
        if not pattern.search(content):
            print_warning(self.console, f"Host '{alias}' not found")
            return 1
        config_file.write_text(pattern.sub("", content), encoding="utf-8")
        print_success(self.console, f"Removed Host '{alias}'")
        return 0

    def config_manage(self) -> int:
        """Interactive SSH config management."""
        console = self.console
        self.config_show()
        console.print()
        action = Prompt.ask(
            "[bold cyan]Config action[/bold cyan] [dim](add/remove/list, or Enter to skip)[/dim]",
            default="",
        ).strip().lower()
        if action == "add":
            alias = Prompt.ask("Host alias (e.g. github-work)")
            hostname = Prompt.ask("HostName", default="github.com")
            user = Prompt.ask("User", default="git")
            identity = Prompt.ask("IdentityFile", default="~/.ssh/id_ed25519")
            return self.config_add_host(alias, hostname, user, identity)
        if action == "remove":
            alias = Prompt.ask("Host alias to remove")
            return self.config_remove_host(alias)
        return 0

    # ------------------------------------------------------------------
    # PAT hygiene
    # ------------------------------------------------------------------

    def pat_manager(self) -> int:
        """PAT hygiene audit and guidance (GitHub does not allow listing your own PATs via API)."""
        console = self.console
        console.print()
        print_info(console, "Personal Access Token (PAT) Audit")
        console.print()

        table = StatusTable("Token Audit")
        auth_result = run_command(["gh", "auth", "status"], timeout=15)
        output = (auth_result.stdout or "") + (auth_result.stderr or "")

        if auth_result.returncode == 0:
            scopes_found = False
            for line in output.splitlines():
                if "Scopes:" in line:
                    scopes_found = True
                    scopes = line.split("Scopes:", 1)[1].strip()
                    if scopes and scopes != "'repo', 'gist', 'read:org', 'workflow'":
                        table.add_row(
                            "Current token scopes",
                            StatusBadge.INFO,
                            scopes,
                        )
                    else:
                        table.add_row(
                            "Current token scopes",
                            StatusBadge.SUCCESS,
                            scopes or "OAuth default set",
                        )
            if not scopes_found:
                table.add_row("Current token scopes", StatusBadge.INFO, "Not reported by gh")
            if "gho_" in output or "oauth" in output.lower():
                table.add_row("Auth method", StatusBadge.SUCCESS, "OAuth via gh (recommended)")
            elif "ghp_" in output or "github_pat_" in output:
                detail = "Classic/fine-grained PAT detected - consider OAuth flow"
                table.add_row("Current token", StatusBadge.WARNING, detail)
        else:
            table.add_row("gh auth", StatusBadge.FAILED, "Not authenticated")

        table.add_row("Self-listing PATs", StatusBadge.INFO,
                      "GitHub API cannot list your own PATs - audit at github.com/settings/tokens")

        console.print(table.render())
        console.print()

        guidance = (
            "PAT Best Practices:\n"
            "\n"
            "1. Prefer fine-grained PATs over classic:\n"
            "   - Limit to specific repositories\n"
            "   - Grant only needed permissions (Contents: Read, etc.)\n"
            "2. Always set an expiration (90 days recommended)\n"
            "3. NEVER paste tokens in chat, tickets, or commit them to files\n"
            "4. Store in the OS credential manager (git credential manager) or gh keyring\n"
            "5. Rotate tokens regularly; delete unused ones\n"
            "6. Use gh auth login (OAuth) instead of PATs where possible\n"
            "\n"
            "Manage tokens:\n"
            "  Classic:      https://github.com/settings/tokens\n"
            "  Fine-grained: https://github.com/settings/personal-access-tokens\n"
        )
        console.print(NeonPanel.create("PAT Guidance", guidance, border_style="yellow"))
        return 0

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def run(
        self,
        generate: bool = False,
        key_name: str | None = None,
        signing: bool = False,
        list_keys: bool = False,
        upload: str | None = None,
        test: bool = False,
        config: bool = False,
        agent: bool = False,
        pat: bool = False,
    ) -> int:
        """Run SSH subcommands."""
        if list_keys:
            return self.list_keys()
        if generate:
            return self.generate_keys(key_name=key_name, signing=signing)
        if upload:
            if upload == "all":
                failed = 0
                for key in sorted(self.ssh_dir.glob("id_*")):
                    if key.suffix == ".pub" or not key.is_file():
                        continue
                    if self.upload_key(str(key)) != 0:
                        failed += 1
                return 0 if failed == 0 else 1
            return self.upload_key(upload)
        if test:
            return self.test_connection()
        if config:
            return self.config_manage()
        if agent:
            return self.agent_manage()
        if pat:
            return self.pat_manager()
        print_info(
            self.console,
            "Use --generate, --list, --upload, --test, --config, --agent, or --pat",
        )
        return 0


def run_ssh(
    ctx_obj: dict,
    generate: bool = False,
    key_name: str | None = None,
    signing: bool = False,
    list_keys: bool = False,
    upload: str | None = None,
    test: bool = False,
    config: bool = False,
    agent: bool = False,
    pat: bool = False,
) -> int:
    """Run SSH command."""
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

    manager = SSHManager(ctx)
    return manager.run(generate, key_name, signing, list_keys, upload, test, config, agent, pat)
