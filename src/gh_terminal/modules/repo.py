"""
Repo module - Manage repositories: create, clone, fork, remotes, collaborators, protection.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.box import ASCII
from rich.prompt import Confirm, Prompt
from rich.table import Table

from gh_terminal.core import CommandContext
from gh_terminal.ui.neon import (
    NeonPanel,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from gh_terminal.utils.system import run_command, which


class RepoManager:
    """Manage GitHub repositories."""

    def __init__(self, ctx: CommandContext):
        self.ctx = ctx
        self.console = ctx.console
        self.config = ctx.config.config if ctx.config else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_protocol(self) -> str:
        """Get git protocol from gh config or default to SSH."""
        result = run_command(["gh", "config", "get", "git_protocol"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "ssh"

    def _current_repo(self) -> str | None:
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

    def _gh_user_login(self) -> str | None:
        """Get the authenticated GitHub username."""
        result = run_command(["gh", "api", "user", "--jq", ".login"], timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def _gh(self, args: list[str], timeout: int = 30) -> tuple[bool, str]:
        """Run a gh command and return (success, output)."""
        if not which("gh"):
            print_error(self.console, "GitHub CLI (gh) is not installed")
            return False, ""
        result = run_command(["gh", *args], timeout=timeout)
        output = result.stdout if result.returncode == 0 else result.stderr
        return result.returncode == 0, output.strip()

    # ------------------------------------------------------------------
    # Create / clone / fork / list
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        public: bool | None = None,
        description: str | None = None,
        add_readme: bool = False,
        gitignore: str | None = None,
        license: str | None = None,
        remote: str = "origin",
        source: str | None = None,
    ) -> int:
        """Create a new repository."""
        cmd = ["gh", "repo", "create", name]

        cmd.append("--public" if public else "--private")

        if description:
            cmd.extend(["--description", description])
        if add_readme:
            cmd.append("--add-readme")
        if gitignore:
            cmd.extend(["--gitignore", gitignore])
        if license:
            cmd.extend(["--license", license])
        if source:
            cmd.extend(["--source", source, "--remote", remote, "--push"])

        visibility = "public" if public else "private"
        print_info(self.console, f"Creating {visibility} repository: {name}")
        result = run_command(cmd, timeout=60)

        if result.returncode == 0:
            print_success(self.console, f"Repository created: {result.stdout.strip() or name}")
            print_info(self.console, "Next steps:")
            print_info(self.console, "  gh-terminal repo --protect <repo>")
            print_info(self.console, "  gh-terminal repo --codeowners")
            print_info(self.console, "  gh-terminal advanced --actions")
            return 0
        print_error(self.console, f"Create failed: {result.stderr.strip()}")
        return 1

    def clone(self, repo: str, protocol: str | None = None) -> int:
        """Clone a repository; optionally rewrite origin to the requested protocol."""
        repo_name = repo.rsplit("/", maxsplit=1)[-1].replace(".git", "")
        print_info(self.console, f"Cloning {repo}...")
        result = run_command(["gh", "repo", "clone", repo], timeout=120)

        if result.returncode != 0:
            print_error(self.console, f"Clone failed: {result.stderr.strip()}")
            return 1

        proto = protocol or self._get_protocol()
        if proto:
            url_result = run_command(["git", "-C", repo_name, "remote", "get-url", "origin"])
            if url_result.returncode == 0:
                current = url_result.stdout.strip()
                if proto == "ssh" and current.startswith("https://github.com/"):
                    ssh_url = current.replace("https://github.com/", "git@github.com:")
                    run_command(["git", "-C", repo_name, "remote", "set-url", "origin", ssh_url])
                    print_success(self.console, "Remote rewritten to SSH")
                elif proto == "https" and current.startswith("git@github.com:"):
                    https_url = current.replace("git@github.com:", "https://github.com/")
                    run_command(["git", "-C", repo_name, "remote", "set-url", "origin", https_url])
                    print_success(self.console, "Remote rewritten to HTTPS")

        print_success(self.console, "Cloned successfully")
        return 0

    def fork(self, repo: str, clone: bool = False) -> int:
        """Fork a repository and set the upstream remote."""
        cmd = ["gh", "repo", "fork", repo]
        if clone:
            cmd.append("--clone")

        print_info(self.console, f"Forking {repo}...")
        result = run_command(cmd, timeout=120)

        if result.returncode != 0:
            print_error(self.console, f"Fork failed: {result.stderr.strip()}")
            return 1

        print_success(self.console, "Fork created")

        result_url = run_command(
            ["gh", "repo", "view", repo, "--json", "url", "--jq", ".url"], timeout=15
        )
        upstream_url = (
            result_url.stdout.strip()
            if result_url.returncode == 0 and result_url.stdout.strip()
            else f"https://github.com/{repo}.git"
        )

        remote_result = run_command(["git", "remote", "add", "upstream", upstream_url])
        if remote_result.returncode == 0:
            print_success(self.console, f"Added upstream remote: {upstream_url}")
        else:
            detail = f"Add upstream manually: git remote add upstream {upstream_url}"
            print_info(self.console, detail)
        return 0

    def list_repos(self, limit: int = 30) -> int:
        """List your repositories."""
        result = run_command(
            ["gh", "repo", "list", "--limit", str(limit),
             "--json", "name,description,visibility,defaultBranchRef,updatedAt,owner"],
            timeout=30,
        )
        if result.returncode != 0:
            print_error(self.console, f"List failed: {result.stderr.strip()}")
            return 1

        try:
            repos = json.loads(result.stdout.strip() or "[]")
        except json.JSONDecodeError:
            print_warning(self.console, "Unexpected output from gh")
            return 1

        if not repos:
            print_warning(self.console, "No repositories found")
            return 0

        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("Repository", style="bold white", max_width=35)
        table.add_column("Description", style="dim white", max_width=40)
        table.add_column("Visibility", justify="center", width=10)
        table.add_column("Branch", justify="center", width=10)
        table.add_column("Updated", style="dim white", width=10)

        max_desc = 38
        for repo in repos:
            desc = repo.get("description", "") or "(No description)"
            if len(desc) > max_desc:
                desc = desc[:35] + "..."
            table.add_row(
                f"{repo['owner']['login']}/{repo['name']}",
                desc,
                repo["visibility"],
                repo.get("defaultBranchRef", {}).get("name", "main"),
                repo.get("updatedAt", "")[:10],
            )

        self.console.print(table)
        return 0

    # ------------------------------------------------------------------
    # Remotes management
    # ------------------------------------------------------------------

    def remotes_list(self, repo_dir: str | None = None) -> int:
        """List git remotes."""
        repo_dir = repo_dir or str(Path.cwd())
        result = run_command(["git", "-C", repo_dir, "remote", "-v"])
        if result.returncode != 0:
            print_warning(self.console, "Not a git repository or no remotes")
            return 1
        print_info(self.console, "Current remotes:")
        self.console.print(result.stdout.strip() or "[none]")
        return 0

    def remote_add(self, name: str, url: str, repo_dir: str | None = None) -> int:
        """Add a git remote."""
        repo_dir = repo_dir or str(Path.cwd())
        result = run_command(["git", "-C", repo_dir, "remote", "add", name, url])
        if result.returncode == 0:
            print_success(self.console, f"Added remote '{name}' -> {url}")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def remote_remove(self, name: str, repo_dir: str | None = None) -> int:
        """Remove a git remote."""
        repo_dir = repo_dir or str(Path.cwd())
        result = run_command(["git", "-C", repo_dir, "remote", "remove", name])
        if result.returncode == 0:
            print_success(self.console, f"Removed remote '{name}'")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def remote_rename(self, old: str, new: str, repo_dir: str | None = None) -> int:
        """Rename a git remote."""
        repo_dir = repo_dir or str(Path.cwd())
        result = run_command(["git", "-C", repo_dir, "remote", "rename", old, new])
        if result.returncode == 0:
            print_success(self.console, f"Renamed remote '{old}' -> '{new}'")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    def remote_set_url(self, name: str, url: str, repo_dir: str | None = None) -> int:
        """Set a git remote URL."""
        repo_dir = repo_dir or str(Path.cwd())
        result = run_command(["git", "-C", repo_dir, "remote", "set-url", name, url])
        if result.returncode == 0:
            print_success(self.console, f"Set '{name}' -> {url}")
            return 0
        print_error(self.console, f"Failed: {result.stderr.strip()}")
        return 1

    # ------------------------------------------------------------------
    # Branch + collaborators + insights
    # ------------------------------------------------------------------

    def set_default_branch(self, branch: str, repo: str | None = None) -> int:
        """Set the default branch of a repository."""
        repo = repo or self._current_repo()
        if not repo:
            print_error(self.console, "Repository required (run inside a repo or pass owner/repo)")
            return 1
        ok, output = self._gh(["repo", "edit", repo, "--default-branch", branch], timeout=30)
        if ok:
            print_success(self.console, f"Default branch of {repo} set to '{branch}'")
            return 0
        print_error(self.console, f"Failed: {output}")
        return 1

    def collaborators_list(self, repo: str | None = None) -> int:
        """List repository collaborators."""
        repo = repo or self._current_repo()
        if not repo:
            print_error(self.console, "Repository required")
            return 1
        ok, output = self._gh(
            ["api", f"repos/{repo}/collaborators", "--jq",
             '.[] | "\\(.login)\t\\(.permissions.admin)\t\\(.permissions.push)"'],
            timeout=20,
        )
        if not ok:
            print_error(self.console, f"Failed: {output}")
            return 1

        table = Table(box=ASCII, show_header=True, header_style="bold cyan")
        table.add_column("User", style="bold white")
        table.add_column("Admin", justify="center", width=8)
        table.add_column("Push", justify="center", width=8)
        try:
            for line in output.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    admin = "[OK]" if parts[1] == "True" else "-"
                    push = "[OK]" if parts[2] == "True" else "-"
                    table.add_row(parts[0], admin, push)
            self.console.print(table)
        except Exception as e:
            print_warning(self.console, f"Parse issue: {e}")
            self.console.print(output)
        return 0

    def collaborator_add(self, user: str, permission: str, repo: str | None = None) -> int:
        """Add a collaborator to a repository."""
        repo = repo or self._current_repo()
        if not repo:
            print_error(self.console, "Repository required")
            return 1
        ok, output = self._gh(
            ["api", "-X", "PUT", f"repos/{repo}/collaborators/{user}",
             "-f", f"permission={permission}"],
            timeout=20,
        )
        if ok:
            print_success(self.console, f"Invited '{user}' to {repo} ({permission})")
            return 0
        print_error(self.console, f"Failed: {output}")
        return 1

    def collaborator_remove(self, user: str, repo: str | None = None) -> int:
        """Remove a collaborator from a repository."""
        repo = repo or self._current_repo()
        if not repo:
            print_error(self.console, "Repository required")
            return 1
        ok, output = self._gh(
            ["api", "-X", "DELETE", f"repos/{repo}/collaborators/{user}"], timeout=20
        )
        if ok:
            print_success(self.console, f"Removed '{user}' from {repo}")
            return 0
        print_error(self.console, f"Failed: {output}")
        return 1

    def insights(self, repo: str | None = None) -> int:
        """Show repository insights."""
        repo = repo or self._current_repo()
        if not repo:
            print_error(self.console, "Repository required")
            return 1

        ok, output = self._gh(
            ["repo", "view", repo, "--json",
             "nameWithOwner,description,stargazerCount,forkCount,watchers,"
             "primaryLanguage,licenseInfo,latestRelease,issues,pullRequests"],
            timeout=25,
        )
        if not ok:
            print_error(self.console, f"Failed: {output}")
            return 1

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            print_warning(self.console, "Unexpected output")
            return 1

        title = data.get('nameWithOwner', repo)
        table = Table(
            box=ASCII, show_header=True, header_style="bold cyan",
            title=f"[bold bright_cyan]INSIGHTS: {title}[/bold bright_cyan]",
        )
        table.add_column("Metric", style="bold white", width=20)
        table.add_column("Value", style="white")

        table.add_row("Stars", str(data.get("stargazerCount", 0)))
        table.add_row("Forks", str(data.get("forkCount", 0)))
        table.add_row("Watchers", str(data.get("watchers", {}).get("totalCount", 0)))
        table.add_row("Open Issues", str(data.get("issues", {}).get("totalCount", 0)))
        table.add_row("Open PRs", str(data.get("pullRequests", {}).get("totalCount", 0)))
        table.add_row("Language", (data.get("primaryLanguage") or {}).get("name", "-"))
        table.add_row("License", (data.get("licenseInfo") or {}).get("name", "-"))
        release = data.get("latestRelease")
        table.add_row("Latest Release", (release or {}).get("tagName", "-"))
        table.add_row("Description", data.get("description") or "-")

        self.console.print(table)
        return 0

    # ------------------------------------------------------------------
    # Protection + CODEOWNERS
    # ------------------------------------------------------------------

    def branch_protection(self, repo: str | None = None, branch: str = "main") -> int:
        """Interactive branch protection setup via GitHub API."""
        console = self.console
        repo = repo or self._current_repo()
        if not repo:
            print_error(console, "Repository required")
            return 1

        print_info(console, f"Configuring branch protection for {repo} (branch: {branch})")
        console.print()

        require_reviews = Confirm.ask("Require pull request reviews?", default=True)
        review_count = "1"
        if require_reviews:
            review_count = Prompt.ask("Required approving reviews", default="1")

        require_checks = Confirm.ask("Require status checks to pass?", default=False)
        contexts: list[str] = []
        if require_checks:
            raw = Prompt.ask("Required checks (comma-separated, e.g. ci/test)", default="")
            contexts = [c.strip() for c in raw.split(",") if c.strip()]

        enforce_admins = Confirm.ask("Include administrators?", default=True)
        require_signatures = Confirm.ask("Require signed commits?", default=True)

        apply_now = "[bold yellow]Apply branch protection now?[/bold yellow]"
        if not Confirm.ask(apply_now, default=False):
            print_info(console, "Protection setup cancelled")
            return 0

        payload: dict = {"enforce_admins": enforce_admins, "restrictions": None}
        if require_reviews:
            payload["required_pull_request_reviews"] = {
                "required_approving_review_count": int(review_count or 1)
            }
        if require_checks:
            payload["required_status_checks"] = {"strict": True, "contexts": contexts}
        if require_signatures:
            payload["required_signatures"] = True

        ok, output = self._gh(
            ["api", "-X", "PUT", f"repos/{repo}/branches/{branch}/protection", "--input", "-"],
            timeout=30,
        )
        if not ok:
            print_error(console, f"Failed: {output[:300]}")
            print_info(console, "Branch protection requires admin access to the repository")
            return 1

        print_success(console, f"Branch protection applied to {repo}:{branch}")
        return 0

    def codeowners_setup(self, repo_dir: str | None = None) -> int:
        """Show or create a CODEOWNERS file."""
        console = self.console
        repo_dir = repo_dir or str(Path.cwd())
        codeowners_file = Path(repo_dir) / "CODEOWNERS"

        if codeowners_file.exists():
            print_info(console, "CODEOWNERS file exists:")
            self.console.print(codeowners_file.read_text())
            return 0

        print_info(console, "No CODEOWNERS file found.")
        if not Confirm.ask("Create a CODEOWNERS template?", default=False):
            return 0

        login = self._gh_user_login() or "your-github-username"
        template = (
            "# CODEOWNERS - created by GH-TERMINAL\n"
            "# Global owners\n"
            f"* @{login}\n"
            "\n"
            "# Documentation\n"
            "# /docs/ @{login}\n"
            "\n"
            "# Source code\n"
            "# /src/ @{login}\n"
        )
        codeowners_file.write_text(template, encoding="utf-8")
        print_success(console, f"Created: {codeowners_file}")
        print_info(console, "Move it to .github/, docs/, or the repository root to activate")
        return 0

    def show_guidance(self) -> int:
        """Show repository management quick reference."""
        text = (
            "Repository Quick Reference:\n"
            "\n"
            "  gh-terminal repo --create <name> --readme --license mit --gitignore Python\n"
            "  gh-terminal repo --clone owner/repo\n"
            "  gh-terminal repo --fork owner/repo\n"
            "  gh-terminal repo --remotes / --remote-add 'upstream <url>'\n"
            "  gh-terminal repo --insights [owner/repo]\n"
            "  gh-terminal repo --collaborators [owner/repo]\n"
            "  gh-terminal repo --protect [owner/repo]\n"
            "  gh-terminal repo --codeowners\n"
        )
        self.console.print(NeonPanel.create("REPOSITORY MANAGER", text))
        return 0


def run_repo(
    ctx_obj: dict,
    create: str | None = None,
    clone: str | None = None,
    fork: str | None = None,
    list_repos: bool = False,
    public: bool | None = None,
    remote: str | None = None,
    description: str | None = None,
    readme: bool = False,
    gitignore: str | None = None,
    license: str | None = None,
    remotes_list: bool = False,
    remote_add: str | None = None,
    remote_remove: str | None = None,
    remote_rename: str | None = None,
    remote_seturl: str | None = None,
    default_branch: str | None = None,
    collaborators: bool = False,
    collab_add: str | None = None,
    collab_permission: str = "push",
    collab_remove: str | None = None,
    insights: bool = False,
    protect: bool = False,
    codeowners: bool = False,
) -> int:
    """Run repo command."""
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

    manager = RepoManager(ctx)

    if create:
        parts = create.split()
        name = parts[0]
        is_public = public if public is not None else ("--public" in parts)
        return manager.create(
            name, is_public, description, readme, gitignore, license,
            remote or "origin",
        )

    if clone:
        return manager.clone(clone)

    if fork:
        return manager.fork(fork, clone=False)

    if list_repos:
        return manager.list_repos()

    if remotes_list:
        return manager.remotes_list()
    if remote_add:
        parts = remote_add.split(maxsplit=1)
        if len(parts) != 2:
            print_error(ctx.console, "--remote-add requires 'name url'")
            return 1
        return manager.remote_add(parts[0], parts[1])
    if remote_remove:
        return manager.remote_remove(remote_remove)
    if remote_rename:
        parts = remote_rename.split()
        if len(parts) != 2:
            print_error(ctx.console, "--remote-rename requires 'old new'")
            return 1
        return manager.remote_rename(parts[0], parts[1])
    if remote_seturl:
        parts = remote_seturl.split(maxsplit=1)
        if len(parts) != 2:
            print_error(ctx.console, "--remote-seturl requires 'name url'")
            return 1
        return manager.remote_set_url(parts[0], parts[1])

    if default_branch:
        return manager.set_default_branch(default_branch)

    if collaborators:
        return manager.collaborators_list()
    if collab_add:
        parts = collab_add.split()
        user = parts[0]
        permission = parts[1] if len(parts) > 1 else collab_permission
        return manager.collaborator_add(user, permission)
    if collab_remove:
        return manager.collaborator_remove(collab_remove)

    if insights:
        return manager.insights()

    if protect:
        return manager.branch_protection()

    if codeowners:
        return manager.codeowners_setup()

    return manager.show_guidance()
