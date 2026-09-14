"""
Security module - Security audit and hardening.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.prompt import Confirm

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
from gh_terminal.utils.system import get_system_info, run_command


class SecurityManager:
    """Security audit and hardening."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()

    def run_audit(self) -> int:
        """Run comprehensive security audit."""
        print_info(self.console, "Running security audit...")
        self.console.print()

        checks = [
            ("2FA Status", self._check_2fa),
            ("Commit Signing", self._check_signing),
            ("Protocol Preference", self._check_protocol),
            ("Credential Helper", self._check_credential_helper),
            ("Token Hygiene", self._check_tokens),
            ("Dependabot Alerts", self._check_dependabot),
            ("Secret Scanning", self._check_secret_scanning),
            ("Code Scanning", self._check_code_scanning),
            ("Dangerous Git Configs", self._check_dangerous_configs),
        ]

        table = StatusTable("Security Audit Results")
        results = []

        for name, check_fn in checks:
            try:
                badge, details = check_fn()
                table.add_row(name, badge, details)
                results.append((name, badge, details))
            except Exception as e:
                table.add_row(name, StatusBadge.FAILED, f"Error: {e}")
                results.append((name, StatusBadge.FAILED, f"Error: {e}"))

        self.console.print()
        self.console.print(table.render())
        self.console.print()

        # Summary
        failed = sum(1 for _, b, _ in results if b == StatusBadge.FAILED)
        warning = sum(1 for _, b, _ in results if b == StatusBadge.WARNING)
        success = sum(1 for _, b, _ in results if b == StatusBadge.SUCCESS)

        summary = (
            f"Summary: {success} passed, {warning} warnings, {failed} failed"
        )
        if failed > 0:
            print_error(self.console, summary)
        elif warning > 0:
            print_warning(self.console, summary)
        else:
            print_success(self.console, summary)

        return 1 if failed > 0 else 0

    def _get_current_repo(self) -> str | None:
        """Detect owner/repo from the current directory."""
        result = run_command(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            value = result.stdout.strip()
            if value and value != "null":
                return value
        return None

    def _check_2fa(self) -> tuple:
        """Check 2FA status."""
        result = run_command(["gh", "api", "user", "--jq", ".two_factor_authentication"])
        if result.returncode == 0:
            enabled = result.stdout.strip().lower() == "true"
            return (StatusBadge.SUCCESS if enabled else StatusBadge.WARNING,
                    "Enabled" if enabled else "NOT ENABLED - Highly recommended")
        return (StatusBadge.FAILED, "Could not check (gh not authenticated)")

    def _check_signing(self) -> tuple:
        """Check commit signing status."""
        fmt = run_command(["git", "config", "--global", "gpg.format"])
        key = run_command(["git", "config", "--global", "user.signingkey"])
        commit = run_command(["git", "config", "--global", "commit.gpgsign"])

        if fmt.returncode == 0 and fmt.stdout.strip() == "ssh":
            if key.returncode == 0 and key.stdout.strip():
                if commit.returncode == 0 and commit.stdout.strip() == "true":
                    return (StatusBadge.SUCCESS, "SSH signing configured and enabled")
                return (StatusBadge.WARNING, "SSH key set but commit signing disabled")
            return (StatusBadge.WARNING, "SSH format set but no signing key")
        return (StatusBadge.FAILED, "Commit signing not configured")

    def _check_protocol(self) -> tuple:
        """Check git protocol preference."""
        result = run_command(["gh", "config", "get", "git_protocol"])
        if result.returncode == 0:
            proto = result.stdout.strip()
            return (StatusBadge.SUCCESS if proto == "ssh" else StatusBadge.WARNING,
                    f"Protocol: {proto}")
        return (StatusBadge.WARNING, "Not set (default: https)")

    def _check_credential_helper(self) -> tuple:
        """Check git credential helper."""
        result = run_command(["git", "config", "--global", "credential.helper"])
        if result.returncode == 0 and result.stdout.strip():
            helper = result.stdout.strip()
            if "manager-core" in helper or "manager" in helper:
                return (StatusBadge.SUCCESS, f"Helper: {helper}")
            return (StatusBadge.WARNING, f"Helper: {helper} (consider manager-core)")
        return (StatusBadge.FAILED, "No credential helper configured")

    def _check_tokens(self) -> tuple:
        """Check PAT hygiene."""
        result = run_command(["gh", "auth", "status"], capture=True)
        if result.returncode == 0:
            # Check if using token vs OAuth
            if "Token:" in result.stdout:
                return (StatusBadge.WARNING, "Using Personal Access Token (OAuth recommended)")
            return (StatusBadge.SUCCESS, "Using OAuth authentication")
        return (StatusBadge.FAILED, "Not authenticated")

    def _check_dependabot(self) -> tuple:
        """Check Dependabot alerts."""
        repo = self._get_current_repo()
        if not repo:
            return (StatusBadge.INFO, "Not in a git repository (run inside a repo)")
        result = run_command(
            ["gh", "api", f"repos/{repo}/dependabot/alerts", "--paginate"],
            capture=True, timeout=20,
        )
        if result.returncode == 0:
            try:
                alerts = json.loads(result.stdout.strip() or "[]")
            except (json.JSONDecodeError, ValueError):
                alerts = None
            if alerts is not None:
                open_alerts = [a for a in alerts if a.get("state") == "open"]
                if open_alerts:
                    return (StatusBadge.WARNING, f"{repo}: {len(open_alerts)} open alerts")
                return (StatusBadge.SUCCESS, f"{repo}: no open alerts")
        return (StatusBadge.INFO, f"{repo}: could not check (may need admin scope)")

    def _check_secret_scanning(self) -> tuple:
        """Check secret scanning status."""
        repo = self._get_current_repo()
        if not repo:
            return (StatusBadge.INFO, "Not in a git repository (run inside a repo)")
        result = run_command(
            ["gh", "api", f"repos/{repo}", "--jq", ".security_and_analysis.secret_scanning.status"],
            capture=True, timeout=20,
        )
        if result.returncode == 0 and result.stdout.strip():
            enabled = result.stdout.strip().lower() == "enabled"
            return (
                StatusBadge.SUCCESS if enabled else StatusBadge.WARNING,
                f"{repo}: secret scanning {'enabled' if enabled else 'disabled'}",
            )
        return (StatusBadge.INFO, f"{repo}: could not check (may need admin scope)")

    def _check_code_scanning(self) -> tuple:
        """Check code scanning status."""
        repo = self._get_current_repo()
        if not repo:
            return (StatusBadge.INFO, "Not in a git repository (run inside a repo)")
        result = run_command(
            ["gh", "api", f"repos/{repo}/code-scanning/alerts?state=open", "--paginate"],
            capture=True, timeout=20,
        )
        if result.returncode == 0:
            try:
                alerts = json.loads(result.stdout.strip() or "[]")
            except (json.JSONDecodeError, ValueError):
                alerts = None
            if alerts is not None:
                if alerts:
                    return (StatusBadge.WARNING, f"{repo}: {len(alerts)} open alerts")
                return (StatusBadge.SUCCESS, f"{repo}: no open alerts")
        return (StatusBadge.INFO, f"{repo}: could not check (may need admin scope)")

    def _check_dangerous_configs(self) -> tuple:
        """Check for dangerous git configurations."""
        issues = []

        # Check for credential.helper=store
        result = run_command(["git", "config", "--global", "credential.helper"])
        if result.returncode == 0 and "store" in result.stdout:
            issues.append("credential.helper=store (plaintext)")

        # Check for push.default=matching
        result = run_command(["git", "config", "--global", "push.default"])
        if result.returncode == 0 and result.stdout.strip() == "matching":
            issues.append("push.default=matching (deprecated)")

        # Check for no commit signing
        result = run_command(["git", "config", "--global", "commit.gpgsign"])
        if result.returncode != 0 or result.stdout.strip() != "true":
            issues.append("commit.gpgsign not enabled")

        if issues:
            return (StatusBadge.WARNING, "; ".join(issues))
        return (StatusBadge.SUCCESS, "No dangerous configs found")

    def harden(self) -> int:
        """Apply security hardening (with confirmation)."""
        console = self.console
        print_info(console, "Security hardening will modify your git and gh configuration:")
        print_info(console, "  - gh git_protocol -> ssh")
        print_info(console, "  - credential.helper -> manager")
        print_info(console, "  - commit.gpgsign -> true, tag.gpgsign -> true")
        console.print()
        if not Confirm.ask("[bold yellow]Apply these changes?[/bold yellow]", default=False):
            print_info(console, "Hardening cancelled")
            return 0

        print_info(console, "Applying security hardening...")
        self.console.print()

        actions = [
            ("Set SSH protocol", ["gh", "config", "set", "git_protocol", "ssh"]),
            (
                "Set credential helper",
                ["git", "config", "--global", "credential.helper", "manager-core"],
            ),
            ("Enable commit signing", ["git", "config", "--global", "commit.gpgsign", "true"]),
            ("Enable tag signing", ["git", "config", "--global", "tag.gpgsign", "true"]),
        ]

        for name, cmd in actions:
            result = run_command(cmd)
            if result.returncode == 0:
                print_success(self.console, f"✓ {name}")
            else:
                print_warning(self.console, f"✗ {name}: {result.stderr.strip()}")

        print_info(self.console, "")
        print_info(self.console, "Manual steps recommended:")
        print_info(self.console, "  • Enable 2FA: https://github.com/settings/security")
        print_info(self.console, "  • Enable secret/code scanning in repo settings")
        print_info(self.console, "  • Configure Dependabot alerts")
        return 0

    def generate_report(self) -> int:
        """Generate detailed security report with audit-driven remediation."""
        print_info(self.console, "Generating security report...")
        self.console.print()

        checks = [
            ("2FA Status", self._check_2fa),
            ("Commit Signing", self._check_signing),
            ("Protocol Preference", self._check_protocol),
            ("Credential Helper", self._check_credential_helper),
            ("Token Hygiene", self._check_tokens),
            ("Dependabot Alerts", self._check_dependabot),
            ("Secret Scanning", self._check_secret_scanning),
            ("Code Scanning", self._check_code_scanning),
            ("Dangerous Git Configs", self._check_dangerous_configs),
        ]

        report_lines = [
            "# GH-TERMINAL Security Report",
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Platform: {self.system.os_type.value}",
            "",
            "## Audit Results",
            ""
        ]

        remediation: list[str] = []
        remediation_map = {
            "2FA Status": "Enable 2FA: https://github.com/settings/security",
            "Commit Signing": "Run: gh-terminal signing --setup",
            "Protocol Preference": "Run: gh config set git_protocol ssh",
            "Credential Helper": "Run: git config --global credential.helper manager",
            "Token Hygiene": "Prefer OAuth (gh auth login); rotate PATs every 90 days",
            "Dependabot Alerts": "Review: gh api repos/{owner}/{repo}/dependabot/alerts",
            "Secret Scanning": "Enable in repo Settings > Code security",
            "Code Scanning": "Enable in repo Settings > Code security (needs Actions)",
            "Dangerous Git Configs": "Fix flagged git configs shown above",
        }

        for name, check_fn in checks:
            try:
                badge, details = check_fn()
            except Exception as e:
                badge, details = StatusBadge.FAILED, f"Check error: {e}"
            status = badge.label
            report_lines.append(f"- **{name}**: {status} - {details}")
            if badge in (StatusBadge.FAILED, StatusBadge.WARNING):
                hint = remediation_map.get(name)
                if hint:
                    remediation.append(f"- {name}: {hint}")

        report_lines.extend(["", "## Remediation", ""])
        if remediation:
            report_lines.extend(remediation)
        else:
            report_lines.append("All checks passed. Keep rotating tokens and reviewing alerts.")

        report_lines.extend([
            "",
            "## Recommended Commands",
            "",
            "```bash",
            "gh config set git_protocol ssh",
            "git config --global credential.helper manager",
            "gh-terminal signing --setup",
            "gh-terminal security --harden",
            "```",
        ])

        report = "\n".join(report_lines)
        self.console.print(NeonPanel.create("Security Report", report, border_style="green"))

        if self.ctx.dry_run:
            print_info(self.console, "[dry-run] report file not written")
            return 0

        report_file = Path.home() / "gh-terminal-security-report.md"
        report_file.write_text(report, encoding="utf-8")
        print_success(self.console, f"Report saved to: {report_file}")
        return 0


def run_security(
    ctx_obj: dict, audit: bool = False, harden: bool = False, report: bool = False
) -> int:
    """Run security command."""
    import sys

    from rich.console import Console

    from gh_terminal.core.config import get_config_manager

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

    manager = SecurityManager(ctx)

    if audit:
        return manager.run_audit()

    if harden:
        return manager.harden()

    if report:
        return manager.generate_report()

    print_info(ctx.console, "Use --audit, --harden, or --report")
    return 0
