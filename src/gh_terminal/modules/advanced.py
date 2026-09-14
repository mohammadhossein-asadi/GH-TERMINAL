"""
Advanced module - Power-user features: Actions, Codespaces, Packages, aliases, dashboard.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.box import ASCII
from rich.prompt import Confirm, Prompt
from rich.table import Table

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonPanel,
    NeonProgress,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import get_system_info, run_command


class AdvancedManager:
    """Advanced power-user features."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.system = get_system_info()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_repo(self, repo: str | None = None) -> str | None:
        """Use given repo or detect from the current directory."""
        if repo:
            return repo
        result = run_command(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            timeout=15,
        )
        if result.returncode == 0:
            value = result.stdout.strip()
            if value and value != "null":
                return value
        return None

    def _gh_json(self, args: list[str], timeout: int = 25):
        """Run a gh command and parse JSON output. Returns (ok, data_or_error)."""
        result = run_command(["gh", *args], timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr.strip()
        try:
            return True, json.loads(result.stdout or "null")
        except json.JSONDecodeError:
            return False, "Unexpected output"

    def _require_repo(self, repo: str | None, feature: str) -> str | None:
        repo = self._current_repo(repo)
        if not repo:
            print_error(
                self.console,
                f"Repository required. Run inside a repo or pass --repo owner/repo ({feature})",
            )
        return repo

    # ------------------------------------------------------------------
    # GitHub Actions: secrets, variables, environments
    # ------------------------------------------------------------------

    def actions_menu(self, repo: str | None = None) -> int:
        """Manage GitHub Actions secrets, variables, and environments."""
        repo = self._require_repo(repo, "Actions")
        if not repo:
            return 1

        console = self.console
        console.print()
        print_info(console, f"Actions manager: {repo}")
        console.print()

        while True:
            console.print(NeonPanel.create(
                f"ACTIONS - {repo}",
                "  1. List secrets        2. Set secret\n"
                "  3. Delete secret       4. List variables\n"
                "  5. Set variable        6. Delete variable\n"
                "  7. List environments   0. Back",
            ))
            choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()

            if choice == "0":
                return 0
            if choice == "1":
                self._secret_list(repo)
            elif choice == "2":
                self._secret_set(repo)
            elif choice == "3":
                self._secret_delete(repo)
            elif choice == "4":
                self._variable_list(repo)
            elif choice == "5":
                self._variable_set(repo)
            elif choice == "6":
                self._variable_delete(repo)
            elif choice == "7":
                self._environments_list(repo)
            console.print()

    def _secret_list(self, repo: str) -> int:
        ok, data = self._gh_json(
            ["api", f"repos/{repo}/actions/secrets", "--jq", ".secrets"]
        )
        if not ok:
            print_error(self.console, f"Failed: {data}")
            return 1
        secrets = data or []
        if not secrets:
            print_warning(self.console, "No secrets found")
            return 0
        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Secret", style="bold white")
        table.add_column("Updated", style="dim white")
        for s in secrets:
            table.add_row(s.get("name", ""), str(s.get("updated_at", ""))[:10])
        self.console.print(table)
        return 0

    def _secret_set(self, repo: str) -> int:
        name = Prompt.ask("Secret name").strip()
        if not name:
            return 1
        value = Prompt.ask("Secret value", password=True)
        if not value:
            print_warning(self.console, "Empty value; cancelled")
            return 1
        result = run_command(["gh", "secret", "set", name, "-R", repo], input=value)
        if result.returncode == 0:
            print_success(self.console, f"Secret '{name}' set")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def _secret_delete(self, repo: str) -> int:
        name = Prompt.ask("Secret name to delete").strip()
        if not name:
            return 1
        if not Confirm.ask(f"[bold yellow]Delete secret '{name}'?[/bold yellow]", default=False):
            return 0
        result = run_command(["gh", "secret", "delete", name, "-R", repo])
        if result.returncode == 0:
            print_success(self.console, f"Secret '{name}' deleted")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def _variable_list(self, repo: str) -> int:
        ok, data = self._gh_json(
            ["api", f"repos/{repo}/actions/variables", "--jq", ".variables"]
        )
        if not ok:
            print_error(self.console, f"Failed: {data}")
            return 1
        variables = data or []
        if not variables:
            print_warning(self.console, "No variables found")
            return 0
        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Variable", style="bold white")
        table.add_column("Value", style="dim white")
        for v in variables:
            table.add_row(v.get("name", ""), str(v.get("value", ""))[:40])
        self.console.print(table)
        return 0

    def _variable_set(self, repo: str) -> int:
        name = Prompt.ask("Variable name").strip()
        value = Prompt.ask("Variable value").strip()
        if not name or not value:
            return 1
        result = run_command(["gh", "variable", "set", name, "-R", repo, "-b", value])
        if result.returncode == 0:
            print_success(self.console, f"Variable '{name}' set")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def _variable_delete(self, repo: str) -> int:
        name = Prompt.ask("Variable name to delete").strip()
        if not name:
            return 1
        if not Confirm.ask(f"[bold yellow]Delete variable '{name}'?[/bold yellow]", default=False):
            return 0
        result = run_command(["gh", "variable", "delete", name, "-R", repo])
        if result.returncode == 0:
            print_success(self.console, f"Variable '{name}' deleted")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def _environments_list(self, repo: str) -> int:
        ok, data = self._gh_json(
            ["api", f"repos/{repo}/environments", "--jq", ".environments"]
        )
        if not ok:
            print_error(self.console, f"Failed: {data}")
            return 1
        envs = data or []
        if not envs:
            print_warning(self.console, "No environments found")
            return 0
        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Environment", style="bold white")
        table.add_column("Created", style="dim white")
        for e in envs:
            table.add_row(e.get("name", ""), str(e.get("created_at", ""))[:10])
        self.console.print(table)
        return 0

    # ------------------------------------------------------------------
    # Codespaces
    # ------------------------------------------------------------------

    def codespaces_menu(self, repo: str | None = None) -> int:
        """Manage Codespaces."""
        console = self.console
        console.print()
        print_info(console, "Codespaces manager")
        console.print()

        while True:
            console.print(NeonPanel.create(
                "CODESPACES",
                "  1. List codespaces     2. Create codespace\n"
                "  3. Stop codespace      4. Delete codespace\n"
                "  0. Back",
            ))
            choice = Prompt.ask("[bold cyan]Choice[/bold cyan]", default="0").strip()
            if choice == "0":
                return 0
            if choice == "1":
                self._codespace_list()
            elif choice == "2":
                repo_arg = repo or Prompt.ask("Repository (owner/repo)", default="").strip()
                if repo_arg:
                    run_command(
                        ["gh", "codespace", "create", "-R", repo_arg],
                        capture=False, timeout=60,
                    )
            elif choice == "3":
                name = Prompt.ask("Codespace name").strip()
                if name:
                    run_command(["gh", "codespace", "stop", "-c", name])
            elif choice == "4":
                self._codespace_delete()
            console.print()

    def _codespace_list(self) -> int:
        result = run_command(["gh", "codespace", "list"], timeout=30)
        if result.returncode != 0:
            print_error(self.console, f"Failed: {result.stderr.strip()}")
            return 1
        output = result.stdout.strip()
        if not output:
            print_warning(self.console, "No codespaces found")
            return 0
        lines = output.splitlines()
        header = lines[0] if lines else ""
        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        for column in header.split():
            table.add_column(column, style="white")
        for line in lines[1:]:
            parts = line.split()
            if parts:
                table.add_row(*parts[: len(header.split())])
        self.console.print(table)
        return 0

    def _codespace_delete(self) -> int:
        name = Prompt.ask("Codespace name to delete").strip()
        if not name:
            return 1
        if not Confirm.ask(f"[bold yellow]Delete codespace '{name}'?[/bold yellow]", default=False):
            return 0
        result = run_command(["gh", "codespace", "delete", "-c", name, "--yes"])
        if result.returncode == 0:
            print_success(self.console, f"Codespace '{name}' deleted")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    # ------------------------------------------------------------------
    # Packages
    # ------------------------------------------------------------------

    def packages_list(self, org: str | None = None) -> int:
        """List GitHub Packages via the API."""
        console = self.console

        if org:
            ok, data = self._gh_json(
                ["api", f"orgs/{org}/packages?per_page=100",
                 "--jq", '[.[] | {name, type: .package_type, visibility}]'],
                timeout=25,
            )
        else:
            ok, data = self._gh_json(
                ["api", "/user/packages?per_page=100",
                 "--jq", '[.[] | {name, type: .package_type, visibility}]'],
                timeout=25,
            )
        if not ok:
            print_error(console, f"Failed: {data}")
            return 1

        packages = data or []
        if not packages:
            print_warning(console, "No packages found")
        else:
            table = Table(box=ASCII, show_header=True, header_style="bold cyan")
            table.add_column("Package", style="bold white")
            table.add_column("Type", style="cyan")
            table.add_column("Visibility", style="dim white")
            for p in packages:
                table.add_row(p.get("name", ""), p.get("type", ""), p.get("visibility", ""))
            console.print(table)

        console.print()
        print_info(console, "ghcr.io usage:")
        print_info(console, "  docker login ghcr.io  (use a PAT with write:packages)")
        print_info(console, "  docker push ghcr.io/<owner>/<image>:<tag>")
        return 0

    # ------------------------------------------------------------------
    # Aliases + extensions + org roles
    # ------------------------------------------------------------------

    def aliases_menu(self) -> int:
        """List, set, and delete gh aliases."""
        console = self.console
        result = run_command(["gh", "alias", "list"], timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            table = Table(box=ASCII, show_header=True, header_style="bold cyan")
            table.add_column("Alias", style="bold cyan")
            table.add_column("Command", style="white")
            for line in result.stdout.strip().splitlines():
                name, _, cmd = line.partition(":")
                table.add_row(name.strip(), cmd.strip())
            console.print(table)
        else:
            print_warning(console, "No aliases configured")

        console.print()
        action = Prompt.ask(
            "[bold cyan]Alias action[/bold cyan] [dim](set/delete/Enter to skip)[/dim]",
            default="",
        ).strip().lower()
        if action == "set":
            name = Prompt.ask("Alias name").strip()
            command = Prompt.ask("Command (e.g. 'pr checkout')").strip()
            if name and command:
                result = run_command(["gh", "alias", "set", name, command])
                if result.returncode == 0:
                    print_success(console, f"Alias '{name}' set")
        elif action == "delete":
            name = Prompt.ask("Alias name to delete").strip()
            if name:
                result = run_command(["gh", "alias", "delete", name])
                if result.returncode == 0:
                    print_success(console, f"Alias '{name}' deleted")
        return 0

    def extensions_menu(self) -> int:
        """List and install gh extensions."""
        console = self.console
        result = run_command(["gh", "extension", "list"], timeout=20)
        console.print(result.stdout.strip() or "No extensions installed")
        console.print()

        if Confirm.ask("Install an extension?", default=False):
            spec = Prompt.ask("Extension (owner/name)").strip()
            if spec:
                result = run_command(["gh", "extension", "install", spec], timeout=60)
                if result.returncode == 0:
                    print_success(console, f"Installed {spec}")
        return 0

    def org_roles(self, org: str) -> int:
        """Show your membership/role in an organization."""
        result = run_command(["gh", "api", "user", "--jq", ".login"], timeout=15)
        login = result.stdout.strip() if result.returncode == 0 else ""
        if not login:
            print_error(self.console, "gh not authenticated")
            return 1

        ok, data = self._gh_json(["api", f"orgs/{org}/memberships/{login}"], timeout=20)
        if not ok:
            print_error(self.console, f"Failed: {data}")
            return 1

        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Organization", style="bold white")
        table.add_column("User", style="white")
        table.add_column("Role", style="bold cyan")
        table.add_column("State", style="dim white")
        table.add_row(
            str(data.get("organization", {}).get("login", org)),
            str(data.get("user", {}).get("login", login)),
            str(data.get("role", "-")),
            str(data.get("state", "-")),
        )
        self.console.print(table)
        return 0

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def dashboard(self, repo: str | None = None, watch: bool = False) -> int:
        """Show a repository status dashboard."""
        repo = self._require_repo(repo, "Dashboard")
        if not repo:
            return 1

        console = self.console
        while True:
            with NeonProgress(console) as progress:
                tasks = {
                    "workflows": progress.add_task("Fetching workflow runs...", total=1),
                    "issues": progress.add_task("Fetching issues...", total=1),
                    "prs": progress.add_task("Fetching PRs...", total=1),
                    "releases": progress.add_task("Fetching releases...", total=1),
                }

                ok_wf, wf = self._gh_json(
                    ["run", "list", "-R", repo, "--limit", "5",
                     "--json", "displayTitle,conclusion,createdAt,status"], timeout=25
                )
                progress.complete(tasks["workflows"])

                ok_is, issues = self._gh_json(
                    ["issue", "list", "-R", repo, "--limit", "5",
                     "--json", "title,state,author"], timeout=25
                )
                progress.complete(tasks["issues"])

                ok_pr, prs = self._gh_json(
                    ["pr", "list", "-R", repo, "--limit", "5",
                     "--json", "title,state,author"], timeout=25
                )
                progress.complete(tasks["prs"])

                ok_rel, releases = self._gh_json(
                    ["release", "list", "-R", repo, "--limit", "5"], timeout=25
                )
                progress.complete(tasks["releases"])

            console.print()
            console.print(NeonPanel.create(f"DASHBOARD - {repo}", ""))

            wf_table = Table(box=ASCII, show_header=True, header_style="bold cyan")
            wf_table.add_column("Workflow Run", style="bold white", max_width=40)
            wf_table.add_column("Status", justify="center", width=12)
            wf_table.add_column("Created", style="dim white", width=12)
            if ok_wf and wf:
                for run in wf:
                    conclusion = run.get("conclusion") or run.get("status") or "-"
                    wf_table.add_row(
                        run.get("displayTitle") or run.get("display_title") or "-",
                        str(conclusion),
                        str(run.get("createdAt", ""))[:10],
                    )
            console.print(wf_table)

            def items_table(title: str, items, ok: bool) -> Table:
                t = Table(box=ASCII, show_header=True, header_style="bold cyan")
                t.add_column(f"{title}", style="bold white", max_width=50)
                t.add_column("State", justify="center", width=10)
                t.add_column("Author", style="dim white", width=16)
                if ok and items:
                    for item in items:
                        t.add_row(
                            str(item.get("title", "-"))[:48],
                            str(item.get("state", "-")),
                            (item.get("author") or {}).get("login", "-"),
                        )
                return t

            console.print(items_table("Issue", issues, ok_is))
            console.print(items_table("Pull Request", prs, ok_pr))

            rel_table = Table(box=ASCII, show_header=True, header_style="bold cyan")
            rel_table.add_column("Release", style="bold white", max_width=40)
            rel_table.add_column("Tag", style="dim white")
            if ok_rel and releases:
                for rel in releases:
                    rel_table.add_row(
                        str(rel.get("name", "-"))[:38], str(rel.get("tagName", ""))
                    )
            console.print(rel_table)
            console.print()

            if not watch:
                return 0
            if not Confirm.ask("Refresh dashboard?", default=True):
                return 0

    # ------------------------------------------------------------------
    # Export reusable setup script
    # ------------------------------------------------------------------

    def export_script(self) -> int:
        """Generate a reusable shell script that reproduces this configuration."""
        console = self.console

        name = run_command(["git", "config", "--global", "user.name"]).stdout.strip()
        email = run_command(["git", "config", "--global", "user.email"]).stdout.strip()
        fmt = run_command(["git", "config", "--global", "gpg.format"]).stdout.strip()
        key = run_command(["git", "config", "--global", "user.signingkey"]).stdout.strip()
        sign_commits = run_command(["git", "config", "--global", "commit.gpgsign"]).stdout.strip()
        sign_tags = run_command(["git", "config", "--global", "tag.gpgsign"]).stdout.strip()

        sh_lines = [
            "#!/usr/bin/env bash",
            "# Generated by GH-TERMINAL - reusable GitHub/git setup script",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "set -euo pipefail",
            "",
            "# Git identity",
            f'git config --global user.name "{name}"',
            f'git config --global user.email "{email}"',
            "",
            "# gh CLI preferences",
            "gh config set git_protocol ssh",
            "gh config set prompt enabled",
            "",
        ]
        if fmt:
            sh_lines.append("# Commit signing")
            sh_lines.append(f"git config --global gpg.format {fmt}")
            if key:
                sh_lines.append(f"git config --global user.signingkey {key}")
            if sign_commits == "true":
                sh_lines.append("git config --global commit.gpgsign true")
            if sign_tags == "true":
                sh_lines.append("git config --global tag.gpgsign true")
            sh_lines.append("")

        ps_lines = [
            "# Generated by GH-TERMINAL - reusable GitHub/git setup script (Windows)",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f'git config --global user.name "{name}"',
            f'git config --global user.email "{email}"',
            "gh config set git_protocol ssh",
        ]
        if fmt:
            ps_lines.append(f"git config --global gpg.format {fmt}")
            if key:
                ps_lines.append(f"git config --global user.signingkey {key}")
            if sign_commits == "true":
                ps_lines.append("git config --global commit.gpgsign true")
            if sign_tags == "true":
                ps_lines.append("git config --global tag.gpgsign true")

        sh_file = Path.home() / "gh-terminal-setup.sh"
        ps_file = Path.home() / "gh-terminal-setup.ps1"
        sh_file.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
        ps_file.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")

        print_success(console, f"Shell script: {sh_file}")
        print_success(console, f"PowerShell script: {ps_file}")
        print_info(console, "Run the .sh on macOS/Linux/WSL, the .ps1 on Windows")
        return 0


def run_advanced(
    ctx_obj: dict,
    actions: bool = False,
    codespaces: bool = False,
    packages: bool = False,
    aliases: bool = False,
    dashboard: bool = False,
    extensions: bool = False,
    org: str | None = None,
    export_script: bool = False,
    repo_arg: str | None = None,
) -> int:
    """Run advanced command."""
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

    manager = AdvancedManager(ctx)

    if actions:
        return manager.actions_menu(repo_arg)
    if codespaces:
        return manager.codespaces_menu(repo_arg)
    if packages:
        return manager.packages_list(org)
    if aliases:
        return manager.aliases_menu()
    if extensions:
        return manager.extensions_menu()
    if org:
        return manager.org_roles(org)
    if dashboard:
        return manager.dashboard(repo_arg)
    if export_script:
        return manager.export_script()

    usage = (
        "Use --actions, --codespaces, --packages, --aliases, --extensions, "
        "--org, --dashboard, or --export-script"
    )
    print_info(ctx.console, usage)
    return 0
