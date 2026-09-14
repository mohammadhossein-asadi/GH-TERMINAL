"""
System Diagnostics Module - Check and report system status.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.text import Text

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonHeader,
    StatusBadge,
    StatusTable,
    print_info,
    print_warning,
)
from gh_terminal.utils.system import run_command, which


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""

    component: str
    status: StatusBadge
    version: str = ""
    details: str = ""
    path: str = ""


def check_git(ctx: CommandContext) -> DiagnosticResult:
    """Check git installation and version."""
    git_path = which("git")
    if not git_path:
        return DiagnosticResult(
            component="Git",
            status=StatusBadge.FAILED,
            details="Not installed or not in PATH",
        )

    result = run_command(["git", "--version"])
    version = result.stdout.strip() if result.returncode == 0 else "Unknown"

    # Get global config
    name_result = run_command(["git", "config", "--global", "user.name"])
    email_result = run_command(["git", "config", "--global", "user.email"])
    name = name_result.stdout.strip() if name_result.returncode == 0 else "[NOT SET]"
    email = email_result.stdout.strip() if email_result.returncode == 0 else "[NOT SET]"

    # Get signing config
    gpg_format = run_command(["git", "config", "--global", "gpg.format"])
    signing_key = run_command(["git", "config", "--global", "user.signingkey"])
    commit_gpgsign = run_command(["git", "config", "--global", "commit.gpgsign"])

    details = f"user.name={name}, user.email={email}"
    if gpg_format.returncode == 0:
        details += f", gpg.format={gpg_format.stdout.strip()}"
    if signing_key.returncode == 0:
        details += f", signingkey={signing_key.stdout.strip()}"
    if commit_gpgsign.returncode == 0:
        details += f", commit.gpgsign={commit_gpgsign.stdout.strip()}"

    return DiagnosticResult(
        component="Git",
        status=StatusBadge.SUCCESS,
        version=version.replace("git version ", ""),
        details=details,
        path=git_path,
    )


def check_gh(ctx: CommandContext) -> DiagnosticResult:
    """Check GitHub CLI installation and auth status."""
    gh_path = which("gh")
    if not gh_path:
        return DiagnosticResult(
            component="GitHub CLI (gh)",
            status=StatusBadge.FAILED,
            details="Not installed or not in PATH",
        )

    result = run_command(["gh", "--version"])
    version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else "Unknown"

    # Check auth status
    auth_result = run_command(["gh", "auth", "status"])
    if auth_result.returncode == 0:
        status_text = "Authenticated"
        # Extract username from auth status
        for line in auth_result.stderr.split("\n"):
            if "Logged in to" in line or "github.com" in line:
                status_text += f" ({line.strip()})"
                break
        badge = StatusBadge.SUCCESS
    else:
        status_text = "Not authenticated"
        badge = StatusBadge.WARNING

    # Get config
    protocol_result = run_command(["gh", "config", "get", "git_protocol"])
    protocol = (
        protocol_result.stdout.strip()
        if protocol_result.returncode == 0
        else "https (default)"
    )

    details = f"{status_text}, protocol={protocol}"

    return DiagnosticResult(
        component="GitHub CLI (gh)",
        status=badge,
        version=version.replace("gh version ", ""),
        details=details,
        path=gh_path,
    )


def check_ssh_agent(ctx: CommandContext) -> DiagnosticResult:
    """Check SSH agent status and loaded keys."""
    # Check if ssh-agent is running
    result = run_command(["ssh-add", "-l"])
    if result.returncode == 0:
        keys = result.stdout.strip().split("\n")
        key_count = len([k for k in keys if k.strip()])
        details = f"{key_count} key(s) loaded"
        badge = StatusBadge.SUCCESS if key_count > 0 else StatusBadge.WARNING
    elif result.returncode == 1:
        details = "Agent running but no keys loaded"
        badge = StatusBadge.WARNING
    else:
        details = "SSH agent not running"
        badge = StatusBadge.FAILED

    return DiagnosticResult(
        component="SSH Agent",
        status=badge,
        details=details,
    )


def check_ssh_keys(ctx: CommandContext) -> DiagnosticResult:
    """Check SSH keys in ~/.ssh."""
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return DiagnosticResult(
            component="SSH Keys",
            status=StatusBadge.WARNING,
            details=f"Directory not found: {ssh_dir}",
            path=str(ssh_dir),
        )

    private_keys = list(ssh_dir.glob("id_*"))
    private_keys = [k for k in private_keys if not k.name.endswith(".pub")]
    public_keys = list(ssh_dir.glob("*.pub"))

    details = f"{len(private_keys)} private, {len(public_keys)} public key(s)"
    if private_keys:
        details += f" â€” {', '.join(k.name for k in private_keys)}"

    badge = StatusBadge.SUCCESS if private_keys else StatusBadge.WARNING

    return DiagnosticResult(
        component="SSH Keys",
        status=badge,
        details=details,
        path=str(ssh_dir),
    )


def check_gpg_keys(ctx: CommandContext) -> DiagnosticResult:
    """Check GPG keys."""
    result = run_command(["gpg", "--list-secret-keys", "--keyid-format=long"])
    if result.returncode == 0 and "sec" in result.stdout:
        lines = [line for line in result.stdout.split("\n") if "sec" in line]
        details = f"{len(lines)} secret key(s) found"
        badge = StatusBadge.SUCCESS
    else:
        details = "No GPG keys found"
        badge = StatusBadge.INFO

    return DiagnosticResult(
        component="GPG Keys",
        status=badge,
        details=details,
    )


def check_credential_helper(ctx: CommandContext) -> DiagnosticResult:
    """Check git credential helper."""
    result = run_command(["git", "config", "--global", "credential.helper"])
    helper = result.stdout.strip() if result.returncode == 0 else "Not configured"

    # Check for manager-core (recommended)
    if "manager-core" in helper or "manager" in helper:
        badge = StatusBadge.SUCCESS
    elif helper:
        badge = StatusBadge.WARNING
    else:
        badge = StatusBadge.FAILED

    return DiagnosticResult(
        component="Credential Helper",
        status=badge,
        details=helper or "None configured",
    )


def check_signing_config(ctx: CommandContext) -> DiagnosticResult:
    """Check git commit signing configuration."""
    checks = []
    issues = []

    # gpg.format
    fmt_result = run_command(["git", "config", "--global", "gpg.format"])
    if fmt_result.returncode == 0 and fmt_result.stdout.strip() == "ssh":
        checks.append("gpg.format=ssh [OK]")
    else:
        checks.append("gpg.format=ssh [!!]")
        issues.append("gpg.format not set to 'ssh'")

    # user.signingkey
    key_result = run_command(["git", "config", "--global", "user.signingkey"])
    if key_result.returncode == 0 and key_result.stdout.strip():
        checks.append(f"user.signingkey={key_result.stdout.strip()} [OK]")
    else:
        checks.append("user.signingkey [!!]")
        issues.append("No signing key configured")

    # commit.gpgsign
    commit_result = run_command(["git", "config", "--global", "commit.gpgsign"])
    if commit_result.returncode == 0 and commit_result.stdout.strip() == "true":
        checks.append("commit.gpgsign=true [OK]")
    else:
        checks.append("commit.gpgsign=true [!!]")
        issues.append("Commit signing not enabled")

    # tag.gpgsign
    tag_result = run_command(["git", "config", "--global", "tag.gpgsign"])
    if tag_result.returncode == 0 and tag_result.stdout.strip() == "true":
        checks.append("tag.gpgsign=true [OK]")
    else:
        checks.append("tag.gpgsign=true [!!]")
        issues.append("Tag signing not enabled")

    details = "; ".join(checks)
    badge = StatusBadge.SUCCESS if not issues else StatusBadge.WARNING

    if issues:
        details += f" - Issues: {'; '.join(issues)}"

    return DiagnosticResult(
        component="Commit Signing",
        status=badge,
        details=details,
    )


def check_allowed_signers(ctx: CommandContext) -> DiagnosticResult:
    """Check allowed_signers file."""
    allowed_signers = Path.home() / ".ssh" / "allowed_signers"
    if not allowed_signers.exists():
        return DiagnosticResult(
            component="Allowed Signers",
            status=StatusBadge.WARNING,
            details="File not found",
            path=str(allowed_signers),
        )

    try:
        content = allowed_signers.read_text().strip()
        lines = [
            line for line in content.split("\n")
            if line.strip() and not line.startswith("#")
        ]
        details = f"{len(lines)} entry(ies)"
        badge = StatusBadge.SUCCESS if lines else StatusBadge.WARNING
    except Exception:
        details = "Error reading file"
        badge = StatusBadge.FAILED

    return DiagnosticResult(
        component="Allowed Signers",
        status=badge,
        details=details,
        path=str(allowed_signers),
    )


def run_all_diagnostics(ctx: CommandContext) -> list[DiagnosticResult]:
    """Run all diagnostic checks."""
    checks = [
        ("Git", check_git),
        ("GitHub CLI", check_gh),
        ("SSH Agent", check_ssh_agent),
        ("SSH Keys", check_ssh_keys),
        ("GPG Keys", check_gpg_keys),
        ("Credential Helper", check_credential_helper),
        ("Commit Signing", check_signing_config),
        ("Allowed Signers", check_allowed_signers),
    ]

    results = []
    for name, check_fn in checks:
        try:
            result = check_fn(ctx)
            results.append(result)
        except Exception as e:
            results.append(DiagnosticResult(
                component=name,
                status=StatusBadge.FAILED,
                details=f"Error: {e}",
            ))

    return results


def print_diagnostics(ctx: CommandContext, results: list[DiagnosticResult]) -> None:
    """Print diagnostic results in a beautiful table."""
    table = StatusTable("System Diagnostics")

    for result in results:
        table.add_row(result.component, result.status, result.details)

    ctx.console.print()
    ctx.console.print(table.render())
    ctx.console.print()

    # Summary
    success = sum(1 for r in results if r.status == StatusBadge.SUCCESS)
    warning = sum(1 for r in results if r.status == StatusBadge.WARNING)
    failed = sum(1 for r in results if r.status == StatusBadge.FAILED)
    info = sum(1 for r in results if r.status == StatusBadge.INFO)

    summary = Text()
    summary.append("Summary: ", style="bold")
    summary.append(f"{success} OK", style="green")
    summary.append(f", {warning} Warnings", style="yellow")
    summary.append(f", {failed} Failed", style="red")
    if info:
        summary.append(f", {info} Info", style="cyan")

    ctx.console.print(summary)
    ctx.console.print()


def run_diagnostics(ctx_obj: dict) -> int:
    """Run diagnostics command."""
    ctx = CommandContext(
        console=ctx_obj.get("console", Console()),
        config=ctx_obj.get("config"),
        error_handler=ctx_obj.get("error_handler"),
        verbose=ctx_obj.get("verbose", False),
        dry_run=ctx_obj.get("dry_run", False),
    )

    # Show header
    header = NeonHeader(ctx.console)
    header.print()

    ctx.console.print()
    print_info(ctx.console, "Running system diagnostics...")
    ctx.console.print()

    # Run diagnostics
    results = run_all_diagnostics(ctx)

    # Print results
    print_diagnostics(ctx, results)

    # Show next steps
    failed = [r for r in results if r.status == StatusBadge.FAILED]
    if failed:
        ctx.console.print()
        print_warning(ctx.console, "Some checks failed. Recommended actions:")
        for result in failed:
            ctx.console.print(f"  â€¢ Fix {result.component}: {result.details}")
        ctx.console.print()
        print_info(ctx.console, "Run 'gh-terminal setup --wizard' for guided configuration")

    return 0 if not failed else 1
