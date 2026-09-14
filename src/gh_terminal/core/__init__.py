"""Core modules for GH-TERMINAL."""

from gh_terminal.core.cli import CommandContext, CommandRegistry, command, registry
from gh_terminal.core.config import ConfigManager, GHConfig, get_config_manager
from gh_terminal.core.errors import (
    GHError,
    GHErrorCode,
    GHErrorHandler,
    config_validation_failed,
    create_error,
    error_boundary,
    gh_auth_failed,
    gh_not_installed,
    git_not_installed,
    setup_logging,
    signing_verification_failed,
    ssh_key_not_found,
)

__all__ = [
    "CommandContext",
    "CommandRegistry",
    "ConfigManager",
    "GHConfig",
    "GHError",
    "GHErrorCode",
    "GHErrorHandler",
    "command",
    "config_validation_failed",
    "create_error",
    "error_boundary",
    "get_config_manager",
    "gh_auth_failed",
    "gh_not_installed",
    "git_not_installed",
    "registry",
    "setup_logging",
    "signing_verification_failed",
    "ssh_key_not_found",
]
