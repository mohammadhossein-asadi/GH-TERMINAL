"""
Neon Terminal UI Framework - Core visual components for GH-TERMINAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rich.align import Align
from rich.box import DOUBLE, HEAVY, ROUNDED, SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


class StatusBadge(Enum):
    """Status badge types with colors."""

    SUCCESS = ("[OK]", "green", "SUCCESS")
    PENDING = ("[..]", "yellow", "PENDING")
    FAILED = ("[!!]", "red", "FAILED")
    WARNING = ("[!!]", "orange3", "WARNING")
    INFO = ("[i]", "cyan", "INFO")
    CRITICAL = ("[!!]", "magenta", "CRITICAL")

    def __init__(self, symbol: str, color: str, label: str):
        self.symbol = symbol
        self.color = color
        self.label = label

    def render(self, text: str = "") -> Text:
        """Render badge with optional text."""
        badge = Text()
        badge.append(f"{self.symbol} ", style=f"bold {self.color}")
        badge.append(self.label, style=f"bold {self.color}")
        if text:
            badge.append(f" {text}", style=self.color)
        return badge


@dataclass
class ProgressBar:
    """Neon-style progress bar."""

    total: int = 100
    completed: int = 0
    description: str = ""
    width: int = 50

    @property
    def percentage(self) -> int:
        if self.total == 0:
            return 0
        return min(100, int((self.completed / self.total) * 100))

    def render(self) -> Text:
        """Render progress bar as Text."""
        filled = int((self.percentage / 100) * self.width)
        empty = self.width - filled

        bar = Text()
        bar.append("[", style="dim white")
        bar.append("#" * filled, style="bold cyan")
        bar.append("-" * empty, style="dim cyan")
        bar.append("]", style="dim white")
        bar.append(f" {self.percentage}%", style="bold cyan")
        if self.description:
            bar.append(f" - {self.description}", style="cyan")
        return bar


class NeonHeader:
    """GH-TERMINAL neon header component."""

    TITLE = "GH-TERMINAL v3.1  .  NEON EDITION  .  GITHUB CONTROL PLANE"
    SUBTITLE = "Status: ONLINE  |  Mode: INTERACTIVE  |  Security Level: HARDENED"
    PLATFORM = "Platform: Cross-Platform (Windows . macOS . Linux . WSL)"

    def __init__(self, console: Console):
        self.console = console

    def render(
        self,
        status: str = "ONLINE",
        mode: str = "INTERACTIVE",
        security: str = "HARDENED",
    ) -> Panel:
        """Render the neon header panel."""
        content = Text()
        content.append("+", style="bold cyan")
        content.append("=" * 76, style="bold cyan")
        content.append("+\n", style="bold cyan")
        content.append("|  ", style="bold cyan")
        content.append(self.TITLE, style="bold bright_cyan on black")
        content.append("  |\n", style="bold cyan")
        content.append("|  ", style="bold cyan")
        content.append(
            f"Status: {status}  |  Mode: {mode}  |  Security Level: {security}",
            style="bold green",
        )
        content.append("  |\n", style="bold cyan")
        content.append("|  ", style="bold cyan")
        content.append(self.PLATFORM, style="bold magenta")
        content.append("  |\n", style="bold cyan")
        content.append("+", style="bold cyan")
        content.append("=" * 76, style="bold cyan")
        content.append("+", style="bold cyan")

        return Panel(
            Align.center(content),
            box=DOUBLE,
            border_style="bright_cyan",
            padding=(0, 1),
        )

    def print(self, **kwargs) -> None:
        """Print the header to console."""
        self.console.print(self.render(**kwargs))


class NeonDivider:
    """Section divider."""

    @staticmethod
    def render(char: str = "-", length: int = 76, style: str = "dim cyan") -> Text:
        """Render a divider line."""
        return Text(char * length, style=style)

    @staticmethod
    def print(console: Console, **kwargs) -> None:
        """Print divider to console."""
        console.print(NeonDivider.render(**kwargs))


class NeonPanel:
    """Neon-styled panel for menus and content."""

    @staticmethod
    def create(
        title: str,
        content: str | Text | Table | Tree,
        border_style: str = "bright_cyan",
        box_style = ROUNDED,
        padding: tuple[int, int] = (1, 2),
    ) -> Panel:
        """Create a neon panel."""
        return Panel(
            content,
            title=f"[bold bright_cyan]{title}[/bold bright_cyan]",
            border_style=border_style,
            box=box_style,
            padding=padding,
        )

    @staticmethod
    def menu(
        title: str,
        options: list[tuple[str, str, str]],  # (number, label, description)
        console: Console,
        selected: int | None = None,
    ) -> Panel:
        """Create an interactive menu panel."""
        table = Table(box=SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Num", style="bold cyan", width=5)
        table.add_column("Label", style="bold white", width=30)
        table.add_column("Description", style="dim white")

        for num, label, desc in options:
            num_text = Text(f"  {num}.", style="bold cyan")
            is_selected = num == selected
            label_style = "bold black on cyan" if is_selected else "bold white"
            label_text = Text(label, style=label_style)
            desc_text = Text(desc, style="dim white")
            table.add_row(num_text, label_text, desc_text)

        return NeonPanel.create(title, table)


class StatusTable:
    """Status table with badges."""

    def __init__(self, title: str = "System Status"):
        self.title = title
        self.rows: list[tuple[str, StatusBadge, str]] = []

    def add_row(self, component: str, status: StatusBadge, detail: str = "") -> None:
        """Add a row to the status table."""
        self.rows.append((component, status, detail))

    def render(self) -> Table:
        """Render the status table."""
        table = Table(
            title=f"[bold bright_cyan]{self.title}[/bold bright_cyan]",
            box=HEAVY,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("Component", style="bold white", width=30)
        table.add_column("Status", justify="center", width=18)
        table.add_column("Details", style="dim white")

        for component, status, detail in self.rows:
            table.add_row(component, status.render(), detail)

        return table


class NeonProgress:
    """Neon-styled progress display."""

    def __init__(self, console: Console):
        self.console = console
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=40, style="dim cyan", complete_style="bright_cyan"),
            TaskProgressColumn(style="bold cyan"),
            TimeElapsedColumn(style="dim cyan"),
            console=console,
            transient=True,
        )

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, *args):
        self.progress.stop()

    def add_task(self, description: str, total: int = 100) -> int:
        """Add a progress task."""
        return self.progress.add_task(description, total=total)

    def update(self, task_id: int, advance: int = 1, description: str = "") -> None:
        """Update progress task."""
        if description:
            self.progress.update(task_id, description=description)
        self.progress.advance(task_id, advance)

    def complete(self, task_id: int, description: str = "Complete") -> None:
        """Mark task as complete."""
        self.progress.update(task_id, description=f"[green]{description}[/green]", completed=100)


def print_badge(console: Console, badge: StatusBadge, text: str = "") -> None:
    """Print a status badge."""
    console.print(badge.render(text))


def print_success(console: Console, message: str) -> None:
    """Print success message."""
    console.print(StatusBadge.SUCCESS.render(message))


def print_error(console: Console, message: str) -> None:
    """Print error message."""
    console.print(StatusBadge.FAILED.render(message))


def print_warning(console: Console, message: str) -> None:
    """Print warning message."""
    console.print(StatusBadge.WARNING.render(message))


def print_info(console: Console, message: str) -> None:
    """Print info message."""
    console.print(StatusBadge.INFO.render(message))


def print_critical(console: Console, message: str) -> None:
    """Print critical message."""
    console.print(StatusBadge.CRITICAL.render(message))
