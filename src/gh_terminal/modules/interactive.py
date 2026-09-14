"""
Interactive Main Control Panel for GH-TERMINAL.
"""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm, Prompt

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonPanel,
    print_error,
    print_info,
    print_warning,
)

MAIN_MENU_OPTIONS = [
    ("1", "Full Guided Setup Wizard", "Complete setup (Recommended)"),
    ("2", "System Diagnostics & Dashboard", "git, gh, SSH, signing, security status"),
    ("3", "Install / Configure / Authenticate gh", "Install gh, authenticate, protocol"),
    ("4", "Configure Git Identity", "Set user.name, user.email, signing key"),
    ("5", "Setup Commit Signing (SSH Signing)", "Signing key, upload, verify"),
    ("6", "SSH Keys & PAT Manager", "Generate, upload, test keys; PATs"),
    ("7", "Multi-Account Manager & Switcher", "Manage multiple GitHub accounts"),
    ("8", "Repository Manager", "Create, clone, fork, protect repos"),
    ("9", "Security Audit & Hardening", "Full audit with remediation"),
    ("10", "GitHub Actions Secrets & Environments", "Secrets, variables, environments"),
    ("11", "Advanced Power-User Tools", "Codespaces, Packages, dashboard"),
    ("12", "Generate Summary / Export Script", "Export checklist and scripts"),
    ("0", "Exit Session", "Exit GH-TERMINAL"),
]


def _build_ctx(console: Console, config) -> CommandContext:
    """Build a CommandContext for module calls."""
    return CommandContext(console=console, config=config, error_handler=None)


def _ctx_dict(console: Console, config) -> dict:
    """Build a ctx_obj dict for run_* module functions."""
    return {
        "console": console,
        "config": config,
        "error_handler": None,
        "verbose": False,
        "dry_run": False,
    }


def print_main_menu(console: Console, selected: int | None = None) -> None:
    """Print the main control panel menu."""
    panel = NeonPanel.menu("MAIN CONTROL PANEL", MAIN_MENU_OPTIONS, console, selected)
    console.print(panel)


def get_user_choice(console: Console) -> str:
    """Get user menu choice."""
    while True:
        choice = Prompt.ask(
            "\n[bold cyan]Enter choice[/bold cyan] [dim](0-12, or 'menu')[/dim]",
            default="",
            show_default=False,
        ).strip().lower()

        if choice in ("", "menu", "m"):
            return "menu"

        if choice.isdigit() and 0 <= int(choice) <= 12:
            return choice

        print_error(console, "Invalid choice. Enter a number 0-12 or 'menu'")


def confirm_action(console: Console, message: str, default: bool = True) -> bool:
    """Ask for confirmation."""
    return Confirm.ask(f"[bold yellow]! {message}[/bold yellow]", default=default)


def run_main_panel(console: Console, config, logger) -> int:
    """Run the main interactive control panel."""
    from gh_terminal.modules.diagnostics import run_diagnostics
    from gh_terminal.modules.setup import SetupWizard

    handlers = {
        "1": lambda: SetupWizard(_build_ctx(console, config)).run(),
        "2": lambda: run_diagnostics(_ctx_dict(console, config)),
        "3": lambda: run_gh_cli_setup(console, config),
        "4": lambda: run_git_identity_setup(console, config),
        "5": lambda: run_signing_setup(console, config),
        "6": lambda: run_ssh_manager(console, config),
        "7": lambda: run_multi_account(console, config),
        "8": lambda: run_repo_manager(console, config),
        "9": lambda: run_security_audit(console, config),
        "10": lambda: run_actions_secrets(console, config),
        "11": lambda: run_advanced_tools(console, config),
        "12": lambda: run_export_summary(console, config),
    }

    while True:
        print_main_menu(console)
        choice = get_user_choice(console)

        if choice in {"menu", ""}:
            continue

        if choice == "0":
            print_info(console, "Exiting GH-TERMINAL. Goodbye!")
            return 0

        try:
            handler = handlers.get(choice)
            if handler:
                handler()

            console.print()
            Prompt.ask("[dim]Press Enter to return to Main Control Panel[/dim]", default="")

        except KeyboardInterrupt:
            console.print()
            print_warning(console, "Operation cancelled")
            console.print()
        except Exception as e:
            print_error(console, f"Error: {e}")
            if logger is not None and logger.isEnabledFor(10):
                console.print_exception()


# ----------------------------------------------------------------------
# Option handlers
# ----------------------------------------------------------------------


def run_setup_wizard(console: Console, config, logger) -> None:
    """Run full guided setup wizard."""
    from gh_terminal.modules.setup import SetupWizard

    SetupWizard(_build_ctx(console, config)).run()


def run_gh_cli_setup(console: Console, config) -> None:
    """GitHub CLI install / configure / authenticate."""
    from gh_terminal.modules.auth import (
        configure_gh_settings,
        detect_os_install_command,
        run_gh_auth_status,
        run_gh_auth_token,
        run_gh_install,
    )
    from gh_terminal.utils.system import get_system_info, which

    ctx = _build_ctx(console, config)

    if not which("gh"):
        print_warning(console, "GitHub CLI (gh) is not installed")
        if Confirm.ask("Install GitHub CLI now?", default=True):
            run_gh_install(ctx)
            return
        install_cmd = detect_os_install_command(get_system_info().os_type)
        print_info(console, f"Install manually: {install_cmd}")
        return

    from gh_terminal.modules.auth import run_gh_auth_login

    run_gh_auth_status(ctx)
    console.print()

    if not Confirm.ask("Authenticate / re-authenticate with GitHub?", default=False):
        configure_gh_settings(ctx)
        return

    if Confirm.ask("Use browser authentication (recommended)?", default=True):
        run_gh_auth_login(ctx)
    else:
        token = Prompt.ask("Paste your token (input hidden)", password=True)
        if token:
            run_gh_auth_token(ctx, token)


def run_git_identity_setup(console: Console, config, logger=None) -> None:
    """Setup Git identity."""
    from gh_terminal.modules.identity import IdentityManager

    IdentityManager(_build_ctx(console, config)).interactive_setup()


def run_signing_setup(console: Console, config, logger=None) -> None:
    """Setup commit signing."""
    from gh_terminal.modules.signing import SigningManager

    manager = SigningManager(_build_ctx(console, config))
    console.print()
    print_info(console, "Commit Signing Manager")
    console.print()
    manager.show_status()
    console.print()

    choice = Prompt.ask(
        "[bold cyan]Action[/bold cyan] [dim](1=SSH setup, 2=GPG setup, 3=verify, Enter=skip)[/dim]",
        default="",
    ).strip()
    if choice == "1":
        manager.setup_ssh()
    elif choice == "2":
        manager.setup_gpg()
    elif choice == "3":
        manager.verify_signing()


def run_ssh_manager(console: Console, config, logger=None) -> None:
    """Manage SSH keys and PATs."""
    from gh_terminal.modules.ssh_keys import SSHManager

    manager = SSHManager(_build_ctx(console, config))
    console.print()

    while True:
        console.print(NeonPanel.create(
            "SSH & PAT MANAGER",
            "  1. List keys           2. Generate keys\n"
            "  3. Upload key          4. Test GitHub connection\n"
            "  5. SSH config hosts    6. ssh-agent management\n"
            "  7. PAT hygiene audit   0. Back",
        ))
        choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()

        if choice == "0":
            return
        if choice == "1":
            manager.list_keys()
        elif choice == "2":
            signing = Confirm.ask("Also generate a signing key?", default=False)
            manager.generate_keys(signing=signing)
        elif choice == "3":
            key = Prompt.ask("Key name or path", default="all").strip()
            manager.run(upload=key)
        elif choice == "4":
            manager.test_connection()
        elif choice == "5":
            manager.config_manage()
        elif choice == "6":
            manager.agent_manage()
        elif choice == "7":
            manager.pat_manager()
        console.print()


def run_multi_account(console: Console, config, logger=None) -> None:
    """Manage multiple accounts."""
    from gh_terminal.modules.accounts import AccountManager

    manager = AccountManager(_build_ctx(console, config))
    console.print()

    while True:
        console.print(NeonPanel.create(
            "MULTI-ACCOUNT MANAGER",
            "  1. List accounts & identities    2. Add account\n"
            "  3. Switch account (picker)       4. Remove account\n"
            "  0. Back",
        ))
        choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()

        if choice == "0":
            return
        if choice == "1":
            manager.list_accounts()
        elif choice == "2":
            manager.add_account()
        elif choice == "3":
            manager.interactive_switcher()
        elif choice == "4":
            user = Prompt.ask("GitHub username to remove").strip()
            if user:
                manager.remove_account(user)
        console.print()


def run_repo_manager(console: Console, config, logger=None) -> None:
    """Manage repositories."""
    from gh_terminal.modules.repo import RepoManager

    manager = RepoManager(_build_ctx(console, config))
    console.print()

    while True:
        console.print(NeonPanel.create(
            "REPOSITORY MANAGER",
            "  1. List repositories    2. Create repository\n"
            "  3. Clone repository     4. Fork repository\n"
            "  5. Remotes              6. Insights\n"
            "  7. Collaborators        8. Branch protection\n"
            "  9. CODEOWNERS           0. Back",
        ))
        choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()

        if choice == "0":
            return
        if choice == "1":
            manager.list_repos()
        elif choice == "2":
            name = Prompt.ask("Repository name").strip()
            if name:
                public = Confirm.ask("Public repository?", default=False)
                description = Prompt.ask("Description (optional)", default="").strip()
                readme = Confirm.ask("Add README?", default=True)
                manager.create(
                    name, public, description or None, readme,
                    Prompt.ask("Gitignore template (optional)", default="").strip() or None,
                    Prompt.ask("License (e.g. mit, blank to skip)", default="").strip() or None,
                )
        elif choice == "3":
            repo = Prompt.ask("Repository (owner/repo)").strip()
            if repo:
                manager.clone(repo)
        elif choice == "4":
            repo = Prompt.ask("Repository (owner/repo)").strip()
            if repo:
                manager.fork(repo)
        elif choice == "5":
            manager.remotes_list()
        elif choice == "6":
            manager.insights()
        elif choice == "7":
            manager.collaborators_list()
        elif choice == "8":
            manager.branch_protection()
        elif choice == "9":
            manager.codeowners_setup()
        console.print()


def run_security_audit(console: Console, config, logger=None) -> None:
    """Run security audit."""
    from gh_terminal.modules.security import SecurityManager

    manager = SecurityManager(_build_ctx(console, config))
    console.print()
    manager.run_audit()
    console.print()

    if Confirm.ask("Apply security hardening now?", default=False):
        manager.harden()


def run_actions_secrets(console: Console, config, logger=None) -> None:
    """Manage GitHub Actions secrets."""
    from gh_terminal.modules.advanced import AdvancedManager

    AdvancedManager(_build_ctx(console, config)).actions_menu()


def run_advanced_tools(console: Console, config, logger=None) -> None:
    """Advanced power-user tools."""
    from gh_terminal.modules.advanced import AdvancedManager

    manager = AdvancedManager(_build_ctx(console, config))
    console.print()

    while True:
        console.print(NeonPanel.create(
            "ADVANCED TOOLS",
            "  1. Codespaces           2. Packages (ghcr.io)\n"
            "  3. gh aliases           4. gh extensions\n"
            "  5. Organization roles   6. Live dashboard\n"
            "  0. Back",
        ))
        choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()

        if choice == "0":
            return
        if choice == "1":
            manager.codespaces_menu()
        elif choice == "2":
            org = Prompt.ask("Organization (blank = personal)", default="").strip()
            manager.packages_list(org or None)
        elif choice == "3":
            manager.aliases_menu()
        elif choice == "4":
            manager.extensions_menu()
        elif choice == "5":
            org = Prompt.ask("Organization name").strip()
            if org:
                manager.org_roles(org)
        elif choice == "6":
            manager.dashboard()
        console.print()


def run_export_summary(console: Console, config, logger=None) -> None:
    """Export setup summary, checklist, and reusable scripts."""
    from gh_terminal.modules.advanced import AdvancedManager

    console.print()
    checklist = config.export_checklist()
    console.print(NeonPanel.create("Setup Checklist", checklist, border_style="green"))
    console.print()

    if Confirm.ask("Also export reusable setup scripts (.sh / .ps1)?", default=True):
        AdvancedManager(_build_ctx(console, config)).export_script()
