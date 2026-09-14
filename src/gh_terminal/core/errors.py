"""
Logging and error handling framework for GH-TERMINAL.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import Traceback

from gh_terminal.ui.neon import (
    print_error,
    print_info,
)


class GHErrorCode(Enum):
    """Standard error codes."""

    # System errors (1000-1999)
    OS_DETECTION_FAILED = 1001
    SHELL_DETECTION_FAILED = 1002
    COMMAND_NOT_FOUND = 1003
    PERMISSION_DENIED = 1004

    # Git errors (2000-2999)
    GIT_NOT_INSTALLED = 2001
    GIT_CONFIG_FAILED = 2002
    GIT_IDENTITY_INVALID = 2003
    GIT_REPO_NOT_FOUND = 2004

    # GitHub CLI errors (3000-3999)
    GH_NOT_INSTALLED = 3001
    GH_AUTH_FAILED = 3002
    GH_API_ERROR = 3003
    GH_CONFIG_FAILED = 3004

    # SSH errors (4000-4999)
    SSH_KEY_GEN_FAILED = 4001
    SSH_KEY_NOT_FOUND = 4002
    SSH_AGENT_ERROR = 4003
    SSH_AUTH_FAILED = 4004
    SSH_CONFIG_ERROR = 4005

    # Signing errors (5000-5999)
    SIGNING_KEY_GEN_FAILED = 5001
    SIGNING_KEY_UPLOAD_FAILED = 5002
    SIGNING_VERIFICATION_FAILED = 5003
    ALLOWED_SIGNERS_ERROR = 5004

    # Config errors (6000-6999)
    CONFIG_LOAD_FAILED = 6001
    CONFIG_SAVE_FAILED = 6002
    CONFIG_VALIDATION_FAILED = 6003

    # Network errors (7000-7999)
    NETWORK_ERROR = 7001
    TIMEOUT_ERROR = 7002
    RATE_LIMITED = 7003

    # User errors (8000-8999)
    USER_CANCELLED = 8001
    INVALID_INPUT = 8002
    CONFIRMATION_REQUIRED = 8003


@dataclass
class GHError(Exception):
    """Base GH-TERMINAL exception with error code and recovery hints."""

    message: str
    code: GHErrorCode = GHErrorCode.GH_API_ERROR
    recoverable: bool = True
    hints: list[str] = None
    details: dict = None

    def __post_init__(self):
        self.hints = self.hints or []
        self.details = self.details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code.name}] {self.message}"

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "code": self.code.name,
            "code_value": self.code.value,
            "message": self.message,
            "recoverable": self.recoverable,
            "hints": self.hints,
            "details": self.details,
        }


class GHErrorHandler:
    """Centralized error handling with recovery suggestions."""

    def __init__(self, console: Console, logger: logging.Logger):
        self.console = console
        self.logger = logger

    def handle(self, error: Exception, context: str = "") -> bool:
        """Handle an error, return True if recovered."""
        if isinstance(error, GHError):
            return self._handle_gh_error(error, context)
        else:
            return self._handle_generic_error(error, context)

    def _handle_gh_error(self, error: GHError, context: str) -> bool:
        """Handle a GHError with specific recovery."""
        self.logger.error(
            f"{context}: {error}",
            extra={"error": error.to_dict()},
        )

        # Print user-friendly error
        print_error(self.console, error.message)

        # Print hints
        if error.hints:
            self.console.print("\n[bold yellow]Recovery suggestions:[/bold yellow]")
            for i, hint in enumerate(error.hints, 1):
                self.console.print(f"  {i}. {hint}")

        # Print details if available
        if error.details:
            self.console.print("\n[dim]Details:[/dim]")
            for k, v in error.details.items():
                self.console.print(f"  {k}: {v}")

        return False  # Not auto-recovered

    def _handle_generic_error(self, error: Exception, context: str) -> bool:
        """Handle unexpected errors."""
        self.logger.exception(f"{context}: {error}")

        print_error(self.console, f"Unexpected error: {error}")
        print_info(self.console, "This may be a bug. Please report it with the details below.")

        # Show traceback in debug mode
        if self.logger.isEnabledFor(logging.DEBUG):
            self.console.print("\n[dim]Traceback:[/dim]")
            self.console.print(Traceback.from_exception(type(error), error, error.__traceback__))

        return False


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
    console: Console | None = None,
) -> tuple[logging.Logger, Console]:
    """Set up logging with Rich handler."""
    if console is None:
        console = Console(stderr=True)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                markup=True,
            )
        ],
    )

    logger = logging.getLogger("gh_terminal")

    # Add file handler if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger, console


@contextmanager
def error_boundary(
    handler: GHErrorHandler,
    context: str = "",
    reraise: bool = False,
):
    """Context manager for error handling."""
    try:
        yield
    except GHError as e:
        handler.handle(e, context)
        if reraise:
            raise
    except Exception as e:
        handler.handle(e, context)
        if reraise:
            raise


def create_error(
    code: GHErrorCode,
    message: str,
    hints: list[str] | None = None,
    details: dict | None = None,
    recoverable: bool = True,
) -> GHError:
    """Factory function for creating GHErrors."""
    return GHError(
        message=message,
        code=code,
        hints=hints or [],
        details=details or {},
        recoverable=recoverable,
    )


# Common error factories
def git_not_installed(hint: str = "Install git from https://git-scm.com/") -> GHError:
    return create_error(
        GHErrorCode.GIT_NOT_INSTALLED,
        "Git is not installed or not in PATH",
        hints=[hint, "Verify with: git --version"],
    )


def gh_not_installed(os_type: str = "") -> GHError:
    hints = ["Install GitHub CLI: https://cli.github.com/"]
    if os_type == "windows":
        hints.append("Windows: winget install GitHub.cli")
    elif os_type == "macos":
        hints.append("macOS: brew install gh")
    elif os_type == "linux":
        hints.append("Linux: sudo apt install gh (or dnf/pacman/zypper)")
    return create_error(
        GHErrorCode.GH_NOT_INSTALLED, "GitHub CLI (gh) is not installed", hints=hints
    )


def gh_auth_failed(details: str = "") -> GHError:
    return create_error(
        GHErrorCode.GH_AUTH_FAILED,
        "GitHub CLI authentication failed",
        hints=[
            "Run: gh auth login",
            "Use browser authentication (recommended)",
            "Or use token: gh auth login --with-token < token.txt",
        ],
        details={"details": details} if details else {},
    )


def ssh_key_not_found(path: str) -> GHError:
    return create_error(
        GHErrorCode.SSH_KEY_NOT_FOUND,
        f"SSH key not found: {path}",
        hints=[
            f"Generate key: ssh-keygen -t ed25519 -f {path}",
            "Ensure correct permissions: chmod 600 <private_key>",
            "Add to agent: ssh-add <private_key>",
        ],
        details={"path": path},
    )


def signing_verification_failed(reason: str = "") -> GHError:
    return create_error(
        GHErrorCode.SIGNING_VERIFICATION_FAILED,
        "Commit signing verification failed",
        hints=[
            "Verify key is uploaded to GitHub as 'Signing Key' (not Authentication Key)",
            "Check allowed_signers file exists and has correct format",
            "Verify git config: git config --global gpg.format ssh",
            "Test with: git commit --allow-empty -m 'test' -S",
        ],
        details={"reason": reason} if reason else {},
    )


def config_validation_failed(field: str, expected: str, actual: str) -> GHError:
    return create_error(
        GHErrorCode.CONFIG_VALIDATION_FAILED,
        f"Configuration validation failed for '{field}'",
        hints=[
            f"Expected: {expected}",
            f"Actual: {actual}",
            "Run setup wizard to reconfigure",
        ],
        details={"field": field, "expected": expected, "actual": actual},
    )
