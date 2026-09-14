"""
Configuration management for GH-TERMINAL.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from gh_terminal.utils.system import get_system_info


@dataclass
class GitIdentity:
    """Git identity configuration."""

    name: str = ""
    email: str = ""
    signing_key: str = ""
    gpg_format: str = "ssh"  # ssh or openpgp
    sign_commits: bool = True
    sign_tags: bool = True


@dataclass
class GitHubConfig:
    """GitHub CLI configuration."""

    protocol: str = "ssh"  # ssh or https
    editor: str = ""
    pager: str = "less -R"
    prompt: str = "enabled"
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class SSHKeyConfig:
    """SSH key configuration."""

    key_type: str = "ed25519"
    key_path: str = ""
    comment: str = ""
    use_agent: bool = True
    identities: list[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Security hardening configuration."""

    require_2fa: bool = True
    require_signing: bool = True
    prefer_ssh: bool = True
    credential_helper: str = "manager-core"
    token_expiry_days: int = 90
    enable_dependabot: bool = True
    enable_secret_scanning: bool = True
    enable_code_scanning: bool = True


@dataclass
class MultiAccountConfig:
    """Multi-account configuration."""

    # name -> {email, ssh_key, gh_user}
    accounts: dict[str, dict[str, str]] = field(default_factory=dict)
    default_account: str = ""
    # path -> account_name
    conditional_includes: dict[str, str] = field(default_factory=dict)


@dataclass
class GHConfig:
    """Main GH-TERMINAL configuration."""

    version: str = "3.1.0"
    system: dict[str, Any] = field(default_factory=dict)
    git_identity: GitIdentity = field(default_factory=GitIdentity)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    ssh: SSHKeyConfig = field(default_factory=SSHKeyConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    multi_account: MultiAccountConfig = field(default_factory=MultiAccountConfig)
    ui: dict[str, Any] = field(default_factory=lambda: {
        "theme": "neon",
        "show_progress": True,
        "compact_mode": False,
    })


class ConfigManager:
    """Manages GH-TERMINAL configuration."""

    CONFIG_FILENAME = "gh-terminal.yaml"

    def __init__(self, config_dir: Path | None = None):
        self.system_info = get_system_info()
        self.config_dir = config_dir or self.system_info.config_dir / "gh-terminal"
        self.config_path = self.config_dir / self.CONFIG_FILENAME
        self._config: GHConfig | None = None

    @property
    def config(self) -> GHConfig:
        """Get configuration, loading if necessary."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> GHConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            return self.create_default()

        try:
            data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}

            config = GHConfig()
            config.version = data.get("version", "3.1.0")
            config.system = data.get("system", {})
            config.ui = data.get("ui", config.ui)

            # Load nested configs
            if "git_identity" in data:
                config.git_identity = GitIdentity(**data["git_identity"])
            if "github" in data:
                config.github = GitHubConfig(**data["github"])
            if "ssh" in data:
                config.ssh = SSHKeyConfig(**data["ssh"])
            if "security" in data:
                config.security = SecurityConfig(**data["security"])
            if "multi_account" in data:
                config.multi_account = MultiAccountConfig(**data["multi_account"])
        except Exception:
            return self.create_default()
        return config

    def create_default(self) -> GHConfig:
        """Create default configuration."""
        config = GHConfig()
        config.system = self.system_info.to_dict()
        return config

    def save(self) -> bool:
        """Save configuration to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "version": self._config.version,
                "system": self._config.system,
                "git_identity": asdict(self._config.git_identity),
                "github": asdict(self._config.github),
                "ssh": asdict(self._config.ssh),
                "security": asdict(self._config.security),
                "multi_account": asdict(self._config.multi_account),
                "ui": self._config.ui,
            }

            yaml_text = yaml.dump(
                data, default_flow_style=False, sort_keys=False, allow_unicode=True
            )
        except Exception:
            return False
        try:
            self.config_path.write_text(yaml_text, encoding="utf-8")
        except Exception:
            return False
        return True

    def update_system_info(self) -> None:
        """Update system info in config."""
        if self._config:
            self._config.system = get_system_info().to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        """Get nested config value using dot notation."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> bool:
        """Set nested config value using dot notation."""
        keys = key.split(".")
        target = self.config

        for k in keys[:-1]:
            if hasattr(target, k):
                target = getattr(target, k)
            elif isinstance(target, dict):
                target = target.setdefault(k, {})
            else:
                return False

        last_key = keys[-1]
        if hasattr(target, last_key):
            setattr(target, last_key, value)
        elif isinstance(target, dict):
            target[last_key] = value
        else:
            return False

        return self.save()

    def reset(self) -> GHConfig:
        """Reset to default configuration."""
        self._config = self.create_default()
        self.save()
        return self._config

    def export_checklist(self) -> str:
        """Export configuration as a verification checklist."""
        lines = [
            "# GH-TERMINAL Setup Checklist",
            f"# Generated: {os.popen('date').read().strip() if os.name != 'nt' else 'N/A'}",
            "",
            "## System",
            f"- OS: {self.config.system.get('os_name', 'Unknown')}",
            f"- Shell: {self.config.system.get('shell_type', 'Unknown')}",
            f"- Package Managers: {', '.join(self.config.system.get('package_managers', []))}",
            "",
            "## Git Identity",
            f"- Name: {self.config.git_identity.name or '[NOT SET]'}",
            f"- Email: {self.config.git_identity.email or '[NOT SET]'}",
            f"- Signing Key: {self.config.git_identity.signing_key or '[NOT SET]'}",
            f"- GPG Format: {self.config.git_identity.gpg_format}",
            f"- Sign Commits: {self.config.git_identity.sign_commits}",
            f"- Sign Tags: {self.config.git_identity.sign_tags}",
            "",
            "## GitHub CLI",
            f"- Protocol: {self.config.github.protocol}",
            f"- Editor: {self.config.github.editor or '[DEFAULT]'}",
            f"- Pager: {self.config.github.pager}",
            "",
            "## SSH",
            f"- Key Type: {self.config.ssh.key_type}",
            f"- Key Path: {self.config.ssh.key_path or '[NOT SET]'}",
            f"- Use Agent: {self.config.ssh.use_agent}",
            "",
            "## Security",
            f"- Require 2FA: {self.config.security.require_2fa}",
            f"- Require Signing: {self.config.security.require_signing}",
            f"- Prefer SSH: {self.config.security.prefer_ssh}",
            f"- Token Expiry: {self.config.security.token_expiry_days} days",
            "",
        ]
        return "\n".join(lines)


def get_config_manager(config_dir: Path | None = None) -> ConfigManager:
    """Get singleton config manager instance."""
    return ConfigManager(config_dir)
