"""
Cross-platform OS detection and system information utilities.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OSType(Enum):
    """Supported operating systems."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    WSL = "wsl"
    UNKNOWN = "unknown"


class ShellType(Enum):
    """Supported shell types."""

    POWERSHELL = "powershell"
    CMD = "cmd"
    GIT_BASH = "git_bash"
    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    UNKNOWN = "unknown"


class PackageManager(Enum):
    """Package managers per platform."""

    WINGET = "winget"
    SCOOP = "scoop"
    CHOCO = "chocolatey"
    BREW = "homebrew"
    MACPORTS = "macports"
    APT = "apt"
    DNF = "dnf"
    PACMAN = "pacman"
    ZYPPER = "zypper"
    UNKNOWN = "unknown"


@dataclass
class SystemInfo:
    """Complete system information."""

    os_type: OSType
    os_name: str
    os_version: str
    architecture: str
    shell_type: ShellType
    shell_path: str
    is_wsl: bool
    package_managers: list[PackageManager] = field(default_factory=list)
    home_dir: Path = field(default_factory=Path.home)
    config_dir: Path = field(default_factory=Path.home)
    ssh_dir: Path = field(default_factory=lambda: Path.home() / ".ssh")
    git_config_global: Path = field(default_factory=lambda: Path.home() / ".gitconfig")
    gh_config_dir: Path = field(default_factory=lambda: Path.home() / ".config" / "gh")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "os_type": self.os_type.value,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "shell_type": self.shell_type.value,
            "shell_path": self.shell_path,
            "is_wsl": self.is_wsl,
            "package_managers": [pm.value for pm in self.package_managers],
            "home_dir": str(self.home_dir),
            "config_dir": str(self.config_dir),
            "ssh_dir": str(self.ssh_dir),
            "git_config_global": str(self.git_config_global),
            "gh_config_dir": str(self.gh_config_dir),
        }


def detect_os() -> OSType:
    """Detect the operating system type."""
    system = platform.system().lower()

    if system == "windows":
        if is_wsl():
            return OSType.WSL
        return OSType.WINDOWS
    elif system == "darwin":
        return OSType.MACOS
    elif system == "linux":
        if is_wsl():
            return OSType.WSL
        return OSType.LINUX
    return OSType.UNKNOWN


def is_wsl() -> bool:
    """Check if running in WSL."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def detect_shell() -> tuple[ShellType, str]:
    """Detect the current shell type and path."""
    shell = os.environ.get("SHELL", "")
    ps_module = os.environ.get("PSModulePath", "")

    if ps_module:
        if "powershell" in shell.lower() or "pwsh" in shell.lower():
            return ShellType.POWERSHELL, shell or "powershell"
        return ShellType.POWERSHELL, "powershell"

    if "cmd.exe" in os.environ.get("COMSPEC", "").lower():
        return ShellType.CMD, os.environ.get("COMSPEC", "cmd.exe")

    shell_name = os.path.basename(shell).lower()
    if "bash" in shell_name:
        return ShellType.BASH, shell
    elif "zsh" in shell_name:
        return ShellType.ZSH, shell
    elif "fish" in shell_name:
        return ShellType.FISH, shell
    elif "git-bash" in shell.lower() or "mingw" in shell.lower():
        return ShellType.GIT_BASH, shell

    return ShellType.UNKNOWN, shell or "unknown"


def detect_package_managers(os_type: OSType) -> list[PackageManager]:
    """Detect available package managers for the OS."""
    managers = []

    if os_type in (OSType.WINDOWS, OSType.WSL):
        for cmd, pm in [
            ("winget", PackageManager.WINGET),
            ("scoop", PackageManager.SCOOP),
            ("choco", PackageManager.CHOCO),
        ]:
            if shutil.which(cmd):
                managers.append(pm)

    elif os_type == OSType.MACOS:
        for cmd, pm in [
            ("brew", PackageManager.BREW),
            ("port", PackageManager.MACPORTS),
        ]:
            if shutil.which(cmd):
                managers.append(pm)

    elif os_type == OSType.LINUX:
        for cmd, pm in [
            ("apt", PackageManager.APT),
            ("dnf", PackageManager.DNF),
            ("pacman", PackageManager.PACMAN),
            ("zypper", PackageManager.ZYPPER),
        ]:
            if shutil.which(cmd):
                managers.append(pm)

    return managers


def get_platform_paths(os_type: OSType, home: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Get platform-specific paths for config, SSH, git, gh."""
    if os_type == OSType.WINDOWS:
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        config_dir = appdata
        ssh_dir = home / ".ssh"
        git_config = home / ".gitconfig"
        gh_config = appdata / "gh"
    elif os_type == OSType.MACOS:
        config_dir = home / "Library" / "Application Support"
        ssh_dir = home / ".ssh"
        git_config = home / ".gitconfig"
        gh_config = home / "Library" / "Application Support" / "gh"
    else:  # Linux, WSL
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        config_dir = xdg_config
        ssh_dir = home / ".ssh"
        git_config = home / ".gitconfig"
        gh_config = xdg_config / "gh"

    return config_dir, ssh_dir, git_config, gh_config


def get_system_info() -> SystemInfo:
    """Get complete system information."""
    os_type = detect_os()
    shell_type, shell_path = detect_shell()
    is_wsl_env = is_wsl()
    package_managers = detect_package_managers(os_type)

    home = Path.home()
    config_dir, ssh_dir, git_config, gh_config = get_platform_paths(os_type, home)

    return SystemInfo(
        os_type=os_type,
        os_name=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine(),
        shell_type=shell_type,
        shell_path=shell_path,
        is_wsl=is_wsl_env,
        package_managers=package_managers,
        home_dir=home,
        config_dir=config_dir,
        ssh_dir=ssh_dir,
        git_config_global=git_config,
        gh_config_dir=gh_config,
    )


def run_command(
    cmd: list[str] | str,
    capture: bool = True,
    check: bool = False,
    timeout: int = 30,
    shell: bool = False,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a command cross-platform."""
    if isinstance(cmd, str) and not shell:
        cmd = cmd.split()

    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
        shell=shell,
        cwd=str(cwd) if cwd else None,
    )


def which(command: str) -> str | None:
    """Find executable in PATH (cross-platform)."""
    return shutil.which(command)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable."""
    return os.environ.get(key, default)


def set_env(key: str, value: str) -> None:
    """Set environment variable for current process."""
    os.environ[key] = value


def expand_path(path: str | Path) -> Path:
    """Expand user and environment variables in path."""
    return Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()
