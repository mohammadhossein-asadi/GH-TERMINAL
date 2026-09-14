"""
Identity module - Manage Git identity (name, email, signing key) with
multi-identity conditional includes and GitHub email verification.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.box import ASCII
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from gh_terminal.core import CommandContext
from gh_terminal.core.config import get_config_manager
from gh_terminal.ui.neon import (
    NeonPanel,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import (
    OSType,
    expand_path,
    get_system_info,
    run_command,
    which,
)

EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
NOREPLY_DOMAIN = "users.noreply.github.com"


class IdentityManager:
    """Manage Git identity configuration."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()
        self.git_config = self.system.git_config_global

    # ------------------------------------------------------------------
    # Git config primitives
    # ------------------------------------------------------------------

    def _git(self, args: list[str], repo_dir: str | None = None) -> tuple[bool, str]:
        """Run a git config command. Returns (success, stdout)."""
        cmd = ["git"]
        if repo_dir:
            cmd.extend(["-C", repo_dir])
        cmd.extend(["config", *args])
        if self.ctx.dry_run:
            print_info(self.console, f"[dry-run] {' '.join(cmd)}")
            return True, ""
        result = run_command(cmd)
        return result.returncode == 0, result.stdout.strip()

    def get_global(self, key: str) -> str | None:
        """Get a global git config value."""
        ok, value = self._git(["--global", "--get", key])
        return value if ok and value else None

    def set_global(self, key: str, value: str) -> bool:
        """Set a global git config value."""
        ok, _ = self._git(["--global", key, value])
        return ok

    def unset_global(self, key: str) -> bool:
        """Remove a global git config value."""
        ok, _ = self._git(["--global", "--unset-all", key])
        return ok

    def get_local(self, key: str, repo_dir: str | None = None) -> str | None:
        """Get a local (repository) git config value."""
        repo = repo_dir or str(Path.cwd())
        ok, value = self._git(["--get", key], repo_dir=repo)
        return value if ok and value else None

    def set_local(self, key: str, value: str, repo_dir: str | None = None) -> bool:
        """Set a local (repository) git config value."""
        repo = repo_dir or str(Path.cwd())
        ok, _ = self._git([key, value], repo_dir=repo)
        return ok

    # ------------------------------------------------------------------
    # GitHub account helpers
    # ------------------------------------------------------------------

    def github_profile(self) -> dict[str, str]:
        """Get the authenticated GitHub user profile via gh CLI."""
        if not which("gh"):
            return {}
        try:
            result = run_command(["gh", "api", "user"], timeout=15)
        except Exception:
            return {}
        if result.returncode != 0:
            return {}
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return {}
        profile: dict[str, str] = {}
        for key in ("login", "id", "name", "email"):
            value = data.get(key)
            if value not in (None, ""):
                profile[key] = str(value)
        return profile

    def github_email(self) -> str | None:
        """Get the public email from the GitHub profile, if visible."""
        return self.github_profile().get("email")

    def suggested_noreply_email(self) -> str | None:
        """Build the GitHub noreply email (ID+login@users.noreply.github.com)."""
        profile = self.github_profile()
        user_id = profile.get("id")
        login = profile.get("login")
        if user_id and login:
            return f"{user_id}+{login}@{NOREPLY_DOMAIN}"
        return None

    def is_email_verified(self, email: str) -> bool | None:
        """Check if email is verified on GitHub. Returns None if unverifiable."""
        if not which("gh"):
            return None
        jq = f'.[] | select(.email == "{email}") | .verified'
        try:
            result = run_command(["gh", "api", "user/emails", "--jq", jq], timeout=15)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return "true" in result.stdout.lower()

    # ------------------------------------------------------------------
    # Email validation
    # ------------------------------------------------------------------

    def validate_email(self, email: str) -> bool:
        """Validate basic email format."""
        return re.match(EMAIL_PATTERN, email or "") is not None

    def check_email(self, email: str) -> bool:
        """Run email checks against GitHub. Returns True if safe to use."""
        console = self.console
        email = (email or "").strip()

        table = Table(
            box=ASCII,
            show_header=True,
            header_style="bold cyan",
            title=f"[bold bright_cyan]Email Check: {email}[/bold bright_cyan]",
        )
        table.add_column("Check", style="bold white", width=24)
        table.add_column("Result", justify="center", width=10)
        table.add_column("Details", style="dim white")

        if not self.validate_email(email):
            table.add_row("Format", "[!!] FAIL", "Invalid email format")
            console.print(table)
            return False
        table.add_row("Format", "[OK]", "")

        rows, usable = self._analyze_email(email)
        for check, result, detail in rows:
            table.add_row(check, result, detail)

        console.print()
        console.print(table)
        console.print()
        if usable:
            print_success(console, f"'{email}' is safe to use as git user.email")
        else:
            print_warning(console, f"'{email}' may not match your GitHub account")
        return usable

    def _analyze_email(self, email: str) -> tuple[list[tuple[str, str, str]], bool]:
        """Analyze email against the GitHub profile. Returns (rows, usable)."""
        rows: list[tuple[str, str, str]] = []
        profile = self.github_profile()
        login = profile.get("login", "")
        gh_email = profile.get("email")
        noreply = self.suggested_noreply_email()
        noreply_match = bool(noreply) and email.lower() == (noreply or "").lower()
        usable = True

        if email.lower().endswith("@" + NOREPLY_DOMAIN):
            if noreply_match:
                rows.append(("Noreply email", "[OK]", f"Private email for @{login}"))
            else:
                detail = "Custom noreply email; confirm it belongs to your account"
                rows.append(("Noreply email", "[!!]", detail))
                usable = False
            return rows, usable

        if gh_email:
            if gh_email.lower() == email.lower():
                rows.append(("GitHub account match", "[OK]", f"Public email of @{login}"))
            else:
                rows.append((
                    "GitHub account match",
                    "[!!]",
                    f"@{login} public email is {gh_email}",
                ))
                usable = False
            rows.extend(self._verification_rows(email))
        elif profile:
            rows.extend(self._verification_rows(email, login))
            if noreply:
                rows.append(("Suggested noreply", "[i]", noreply))
        else:
            rows.append(("GitHub account", "[..]", "gh not authenticated; checks skipped"))
        return rows, usable

    def _verification_rows(self, email: str, login: str = "") -> list[tuple[str, str, str]]:
        """Check verified status of an email against the GitHub API."""
        verified = self.is_email_verified(email)
        if verified is True:
            label = f"Email verified on @{login}" if login else "Email verified on GitHub"
            return [("GitHub verified", "[OK]", label)]
        if verified is False:
            return [("GitHub verified", "[!!]", "Not found among verified emails")]
        return [("GitHub verified", "[..]", "Cannot verify (gh needs user/read:user scope)")]

    # ------------------------------------------------------------------
    # Identity configuration
    # ------------------------------------------------------------------

    def _persist_identity(self, name: str, email: str, signing_key: str) -> None:
        """Persist identity to gh-terminal.yaml for setup tracking."""
        config = getattr(self.ctx, "config", None)
        if config is None or self.ctx.dry_run:
            return
        try:
            if name:
                config.set("git_identity.name", name)
            if email:
                config.set("git_identity.email", email)
            if signing_key:
                config.set("git_identity.signing_key", signing_key)
        except Exception:
            pass

    def configure_identity(
        self,
        name: str,
        email: str,
        signing_key: str = "",
        repo_dir: str | None = None,
    ) -> bool:
        """Configure git identity globally or locally."""
        if not name or not self.validate_email(email):
            print_error(self.console, "Invalid name or email")
            return False

        success = True
        if repo_dir:
            success = self.set_local("user.name", name, repo_dir) and success
            success = self.set_local("user.email", email, repo_dir) and success
            if signing_key:
                success = self.set_local("user.signingkey", signing_key, repo_dir) and success
        else:
            success = self.set_global("user.name", name) and success
            success = self.set_global("user.email", email) and success
            if signing_key:
                success = self.set_global("user.signingkey", signing_key) and success
            self._persist_identity(name, email, signing_key)
        return success

    def show_identity(self, repo_dir: str | None = None) -> int:
        """Display current git identity (global + local + effective)."""
        console = self.console

        table = Table(
            box=ASCII,
            show_header=True,
            header_style="bold cyan",
            title="[bold bright_cyan]GIT IDENTITY[/bold bright_cyan]",
        )
        table.add_column("Setting", style="bold white", width=18)
        table.add_column("Global", style="white", width=32)
        table.add_column("Effective (here)", style="cyan")

        settings = ["user.name", "user.email", "user.signingkey"]
        for key in settings:
            global_value = self.get_global(key)
            effective = self._git(["--get", key], repo_dir=repo_dir or str(Path.cwd()))
            effective_value = effective[1] if effective[0] and effective[1] else None
            table.add_row(
                key,
                global_value or "[NOT SET]",
                effective_value or "[NOT SET]",
            )

        console.print(table)
        console.print()

        profile = self.github_profile()
        if profile:
            login = profile.get("login", "")
            gh_email = profile.get("email")
            detail = f"@{login}"
            email = self.get_global("user.email") or ""
            if gh_email:
                detail += f" | public email: {gh_email}"
                if gh_email.lower() != email.lower():
                    print_warning(console, f"GitHub account: {detail} - global email MISMATCH")
                else:
                    print_info(console, f"GitHub account: {detail} - email match")
            elif email:
                verified = self.is_email_verified(email)
                if verified is True:
                    print_info(console, f"GitHub account: {detail} - email verified on GitHub")
                elif verified is False:
                    print_warning(
                        console, f"GitHub account: {detail} - email not verified on GitHub"
                    )
                else:
                    detail_msg = (
                        f"GitHub account: {detail} "
                        "(email privacy enabled; verify needs read:user scope)"
                    )
                    print_info(console, detail_msg)
            else:
                print_info(console, f"GitHub account: {detail}")
        else:
            print_info(console, "gh not authenticated; GitHub email checks skipped")

        if repo_dir:
            print_info(console, f"Repository: {repo_dir}")
        return 0

    # ------------------------------------------------------------------
    # Conditional includes (multi-identity)
    # ------------------------------------------------------------------

    @property
    def identities_dir(self) -> Path:
        """Directory storing per-identity gitconfig files."""
        config = getattr(self.ctx, "config", None)
        if config is not None:
            return Path(config.config_dir) / "identities"
        return Path.home() / ".config" / "gh-terminal" / "identities"

    @staticmethod
    def _gitdir_pattern(directory: str, os_type) -> tuple[Path, str]:
        """Expand a directory into (path, includeIf config key base)."""
        path = expand_path(directory)
        gitdir = path.as_posix()
        if not gitdir.endswith("/"):
            gitdir += "/"
        prefix = "gitdir/i:" if os_type == OSType.WINDOWS else "gitdir:"
        return path, f"includeIf.{prefix}{gitdir}"

    def add_conditional_include(
        self,
        directory: str,
        label: str,
        name: str,
        email: str,
        signing_key: str = "",
    ) -> bool:
        """Add an includeIf rule: repos under <directory> use this identity."""
        console = self.console

        if not name or not self.validate_email(email):
            print_error(console, "Both --name and a valid --email are required for --include")
            return False

        try:
            path, gitdir_key = self._gitdir_pattern(directory, self.system.os_type)
        except Exception as e:
            print_error(console, f"Invalid directory: {e}")
            return False

        if not path.exists():
            print_warning(console, f"Directory does not exist yet: {path}")

        safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", label or path.name)
        identities_dir = self.identities_dir
        identity_file = identities_dir / f"{safe_label}.gitconfig"

        if self.ctx.dry_run:
            print_info(console, f"[dry-run] would write {identity_file}")
            rule = f"git config --global --replace-all '{gitdir_key}.path'"
            print_info(console, f"[dry-run] {rule} '{identity_file.as_posix()}'")
            return True

        try:
            identities_dir.mkdir(parents=True, exist_ok=True)
            lines = ["[user]", f"\tname = {name}", f"\temail = {email}"]
            if signing_key:
                lines.append(f"\tsigningkey = {signing_key}")
            identity_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            print_error(console, f"Failed to write identity file: {e}")
            return False

        key = f"{gitdir_key}.path"
        ok, _ = self._git(["--global", "--replace-all", key, identity_file.as_posix()])
        verify_ok, verify_value = self._git(["--global", "--get", key])
        if not ok or not verify_ok or identity_file.as_posix() not in verify_value:
            print_error(console, "Failed to register includeIf rule in global git config")
            return False

        console.print()
        print_success(console, f"Conditional identity '{safe_label}' configured")
        print_info(console, f"  Directory : {path}")
        print_info(console, f"  Identity  : {name} <{email}>")
        print_info(console, f"  Config    : {identity_file}")
        print_info(console, f"  Git rule  : [{gitdir_key}] path = {identity_file.as_posix()}")
        print_info(console, "Applies to all repositories under that directory.")
        return True

    def list_conditional_includes(self) -> list[tuple[str, str]]:
        """List all includeIf gitdir rules from global git config."""
        ok, out = self._git(["--global", "--get-regexp", r"^includeIf\..*\.path$"])
        entries: list[tuple[str, str]] = []
        if not ok or not out:
            return entries
        for line in out.splitlines():
            key, _, value = line.partition(" ")
            key_lower = key.lower()
            if key_lower.startswith("includeif.") and key_lower.endswith(".path"):
                pattern = key[len("includeif.") : -len(".path")]
                entries.append((pattern, value))
        return entries

    def show_includes(self) -> int:
        """Display conditional includes table."""
        console = self.console
        entries = self.list_conditional_includes()

        table = Table(
            box=ASCII,
            show_header=True,
            header_style="bold cyan",
            title="[bold bright_cyan]CONDITIONAL IDENTITIES (includeIf)[/bold bright_cyan]",
        )
        table.add_column("Directory pattern", style="bold white")
        table.add_column("Identity file", style="cyan")
        table.add_column("Exists", justify="center", width=8)

        if not entries:
            table.add_row("[none]", "[none]", "-")
            console.print(table)
            print_info(console, "Add one: gh-terminal identity --include <dir> --name N --email E")
            return 0

        for pattern, identity_path in entries:
            exists = "[OK]" if Path(identity_path).exists() else "[!!]"
            table.add_row(pattern, identity_path, exists)

        console.print(table)
        return 0

    def remove_conditional_include(self, directory: str) -> int:
        """Remove an includeIf rule for a directory."""
        console = self.console
        try:
            _, gitdir_key = self._gitdir_pattern(directory, self.system.os_type)
        except Exception as e:
            print_error(console, f"Invalid directory: {e}")
            return 1

        key = f"{gitdir_key}.path"
        ok, existing = self._git(["--global", "--get-all", key])
        if not ok or not existing:
            print_warning(console, f"No conditional include found for: {gitdir_key}")
            return 1

        ok, _ = self._git(["--global", "--unset-all", key])
        if not ok:
            print_error(console, "Failed to remove includeIf rule")
            return 1

        print_success(console, f"Removed conditional include for: {gitdir_key}")
        print_info(console, "The identity file was kept; delete it manually if unwanted.")
        return 0

    # ------------------------------------------------------------------
    # Interactive flow (Main Control Panel option 4)
    # ------------------------------------------------------------------

    def _find_repo(self) -> str | None:
        """Find the git repository containing the current directory."""
        try:
            result = run_command(["git", "rev-parse", "--show-toplevel"], timeout=10)
        except Exception:
            return None
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def _print_setup_header(self, repo_dir: str | None, profile: dict[str, str]) -> None:
        """Print the interactive setup header with detected context."""
        console = self.console
        content = Text()
        content.append("Set your Git identity (global or per-repository).\n", style="white")
        content.append(
            "Multi-identity users can add conditional includes later:\n", style="dim white"
        )
        content.append("  gh-terminal identity --include <dir> --name N --email E", style="cyan")
        console.print(NeonPanel.create("GIT IDENTITY SETUP", content))
        console.print()

        self.show_identity()
        console.print()

        if profile:
            login = profile.get("login", "")
            gh_email = profile.get("email", "")
            detail = f"@{login}" + (f" <{gh_email}>" if gh_email else " (email private)")
            print_info(console, f"GitHub profile detected: {detail}")
        else:
            print_info(console, "gh not authenticated; using current values as defaults")
        if repo_dir:
            print_info(console, f"Repository detected: {repo_dir}")
        console.print()

    def _prompt_identity(
        self,
        repo_dir: str | None,
        profile: dict[str, str],
        noreply: str | None,
    ) -> tuple[str, str, str, str] | None:
        """Prompt for identity values. Returns (name, email, scope, signing_key)."""
        console = self.console

        if repo_dir:
            scope = Prompt.ask(
                "[bold cyan]Apply to [1] global (default) or [2] this repository?[/bold cyan]",
                choices=["1", "2"],
                default="1",
            )
        else:
            scope = "1"

        default_name = profile.get("name") or self.get_global("user.name") or ""
        name = Prompt.ask("[bold cyan]Git user.name[/bold cyan]", default=default_name).strip()
        if not name:
            print_error(console, "user.name cannot be empty")
            return None

        default_email = self.get_global("user.email") or ""
        email = Prompt.ask(
            "[bold cyan]Git user.email[/bold cyan] [dim](empty = use noreply)[/dim]",
            default=default_email,
        ).strip()
        if not email and noreply:
            email = noreply
            print_info(console, f"Using noreply email: {email}")
        if not email:
            print_error(console, "user.email is required")
            return None
        if not self.validate_email(email):
            print_error(console, f"Invalid email format: {email}")
            return None

        console.print()
        self.check_email(email)

        signing_key = ""
        if Confirm.ask("[bold cyan]Set a signing key now?[/bold cyan]", default=False):
            signing_key = Prompt.ask(
                "[bold cyan]Public signing key path[/bold cyan] (e.g. ~/.ssh/id_ed25519.pub)",
                default="",
            ).strip()
            if signing_key:
                key_path = expand_path(signing_key)
                if not key_path.exists():
                    print_warning(console, f"Key file not found: {key_path} (set anyway)")
                signing_key = str(key_path)

        return name, email, scope, signing_key

    def interactive_setup(self) -> int:
        """Interactive Git identity setup."""
        console = self.console

        repo_dir = self._find_repo()
        profile = self.github_profile()
        noreply = self.suggested_noreply_email()
        self._print_setup_header(repo_dir, profile)

        if noreply:
            print_info(console, f"GitHub noreply email available: {noreply}")
            console.print()

        prompted = self._prompt_identity(repo_dir, profile, noreply)
        if prompted is None:
            return 1
        name, email, scope, signing_key = prompted

        console.print()
        if not Confirm.ask("[bold yellow]Apply this identity?[/bold yellow]", default=True):
            print_info(console, "Identity setup cancelled")
            return 0

        target_repo = repo_dir if scope == "2" else None
        if self.configure_identity(name, email, signing_key, repo_dir=target_repo):
            scope_label = "repository" if target_repo else "global"
            print_success(console, f"Git identity configured ({scope_label})")
            return 0
        print_error(console, "Failed to configure git identity")
        return 1

    # ------------------------------------------------------------------
    # CLI entry
    # ------------------------------------------------------------------

    def _manage_includes(
        self,
        name: str | None,
        email: str | None,
        signing_key: str | None,
        include_dir: str | None,
        remove_include: str | None,
        list_includes: bool,
    ) -> int | None:
        """Handle conditional include subcommands. Returns None if not applicable."""
        console = self.console

        if list_includes:
            return self.show_includes()

        if remove_include:
            return self.remove_conditional_include(remove_include)

        if include_dir:
            if not (name and email):
                print_error(console, "--include requires --name and --email")
                return 1
            label = Path(expand_path(include_dir)).name
            ok = self.add_conditional_include(
                include_dir, label, name, email, signing_key or ""
            )
            return 0 if ok else 1

        return None

    def _resolve_noreply(
        self,
        name: str | None,
        email: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve noreply defaults. Returns (name, email, error)."""
        noreply_email = self.suggested_noreply_email()
        if not noreply_email:
            return name, email, "Cannot build noreply email (gh not installed or not authenticated)"
        email = email or noreply_email
        if not name:
            name = self.github_profile().get("name") or self.get_global("user.name") or ""
        return name, email, None

    def _manage_set(
        self,
        name: str | None,
        email: str | None,
        signing_key: str | None,
        use_local: bool,
        noreply: bool,
        gpg_format: str | None,
        repo_dir: str | None,
        list_only: bool,
        check_email_addr: str | None,
    ) -> int | None:
        """Handle identity set/check subcommands. Returns None if not applicable."""
        console = self.console

        if list_only:
            return self.show_identity(repo_dir)

        if check_email_addr:
            return 0 if self.check_email(check_email_addr) else 1

        if gpg_format and not self.set_global("gpg.format", gpg_format):
            print_error(console, "Failed to set gpg.format")
            return 1
        if gpg_format:
            print_success(console, f"Set gpg.format = {gpg_format}")

        error: str | None = None
        if noreply:
            name, email, noreply_error = self._resolve_noreply(name, email)
            if noreply_error:
                error = noreply_error

        if not error and not (name and email) and (name or email or signing_key or gpg_format):
            error = "Setting identity requires both --name and --email"
        if error:
            print_error(console, error)
            return 1
        if not (name and email):
            return None

        return self._apply_identity(name, email, signing_key or "", use_local)

    def _apply_identity(
        self,
        name: str,
        email: str,
        signing_key: str,
        use_local: bool,
    ) -> int:
        """Validate and apply an identity. Returns exit code."""
        console = self.console

        if not self.validate_email(email):
            print_error(console, f"Invalid email format: {email}")
            return 1

        self._warn_email_mismatch(email)

        target_repo = str(Path.cwd()) if use_local else None
        if self.configure_identity(name, email, signing_key, repo_dir=target_repo):
            if self.ctx.dry_run:
                print_info(console, "[dry-run] identity changes shown above were not applied")
                return 0
            scope_label = "local (this repository)" if use_local else "global"
            print_success(console, f"Git identity configured ({scope_label}): {name} <{email}>")
            return 0
        if use_local:
            detail = "is the current directory inside a git repository?"
            print_error(console, f"Failed to configure git identity ({detail})")
        else:
            print_error(console, "Failed to configure git identity")
        return 1

    def _warn_email_mismatch(self, email: str) -> None:
        """Warn when the email does not match the GitHub account."""
        console = self.console
        gh_email = self.github_email()
        noreply_email = self.suggested_noreply_email()
        is_noreply = bool(noreply_email) and email.lower() == (noreply_email or "").lower()
        if not gh_email or is_noreply or gh_email.lower() == email.lower():
            return
        verified = self.is_email_verified(email)
        if verified is False:
            detail = f"account email: {gh_email}"
            print_warning(console, f"Email '{email}' not verified on GitHub ({detail})")
        elif verified is None:
            print_info(console, "Could not verify email against GitHub (scope or auth missing)")

    def manage(
        self,
        name: str | None = None,
        email: str | None = None,
        signing_key: str | None = None,
        repo_dir: str | None = None,
        list_only: bool = False,
        use_local: bool = False,
        noreply: bool = False,
        check_email_addr: str | None = None,
        include_dir: str | None = None,
        remove_include: str | None = None,
        list_includes: bool = False,
        gpg_format: str | None = None,
    ) -> int:
        """Dispatch identity subcommands."""
        console = self.console

        includes_result = self._manage_includes(
            name, email, signing_key, include_dir, remove_include, list_includes
        )
        if includes_result is not None:
            return includes_result

        set_result = self._manage_set(
            name, email, signing_key, use_local, noreply, gpg_format,
            repo_dir, list_only, check_email_addr,
        )
        if set_result is not None:
            return set_result

        console.print(NeonPanel.create(
            "GIT IDENTITY",
            "Use --name + --email to set identity, --local for repository scope.\n"
            "--noreply uses your GitHub private noreply email.\n"
            "--include <dir> adds a conditional identity for a directory.\n"
            "--list shows current identity; --list-includes shows conditional rules.\n"
            "--check-email <email> validates against your GitHub account.",
        ))
        return 0


def run_identity(
    ctx_obj: dict,
    name: str | None = None,
    email: str | None = None,
    signing_key: str | None = None,
    gpg_format: str | None = None,
    list_identities: bool = False,
    use_local: bool = False,
    noreply: bool = False,
    check_email_addr: str | None = None,
    include_dir: str | None = None,
    remove_include: str | None = None,
    list_includes: bool = False,
) -> int:
    """Run identity command."""
    import sys

    from rich.console import Console

    console = Console(
        force_terminal=True,
        force_interactive=False,
        legacy_windows=True,
    ) if sys.platform == "win32" else Console()

    config = ctx_obj.get("config") or get_config_manager(ctx_obj.get("config_dir"))

    ctx = CommandContext(
        console=ctx_obj.get("console", console),
        config=config,
        error_handler=ctx_obj.get("error_handler"),
        verbose=ctx_obj.get("verbose", False),
        dry_run=ctx_obj.get("dry_run", False),
    )

    manager = IdentityManager(ctx)
    return manager.manage(
        name=name,
        email=email,
        signing_key=signing_key,
        list_only=list_identities,
        use_local=use_local,
        noreply=noreply,
        check_email_addr=check_email_addr,
        include_dir=include_dir,
        remove_include=remove_include,
        list_includes=list_includes,
        gpg_format=gpg_format,
    )
