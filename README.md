<div align="center">

# GH-TERMINAL v3.1 Neon Edition

### Ultimate GitHub Configuration & Management System

A cross-platform, neon-aesthetic terminal application for fully configuring, securing, and optimizing your GitHub experience.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20WSL-lightgrey)](#installation)
[![GitHub CLI](https://img.shields.io/badge/GitHub_CLI-Required-181717?logo=github&logoColor=white)](https://cli.github.com/)

</div>

---

## Overview

GH-TERMINAL is a comprehensive terminal-based control panel for GitHub. It provides an interactive neon-themed UI for managing authentication, SSH keys, commit signing, repository settings, security auditing, GitHub Actions, Codespaces, and multi-account workflows — all from a single, beautiful CLI.

---

## Features

| Feature | Description |
|:--------|:------------|
| **Cross-Platform** | Windows, macOS, Linux, WSL |
| **Neon Terminal UI** | Headers, badges, progress bars, interactive menus |
| **Security First** | SSH signing (GPG fallback), security auditing, token hygiene |
| **Multi-Account** | Directory-scoped identities, account switching, per-account SSH keys |
| **Repository Management** | Create, clone, fork, remotes, collaborators, protection, insights |
| **Power-User Tools** | Actions secrets/variables/environments, Codespaces, Packages, aliases, extensions |
| **Guided Setup Wizard** | Step-by-step configuration for beginners |
| **Export** | Setup checklist + reproducible `.sh` / `.ps1` scripts |

---

## Installation

### Via pipx (Recommended)

```bash
pipx install gh-terminal
```

### Via pip

```bash
pip install gh-terminal
```

### From Source

```bash
git clone https://github.com/mohammadhossein-asadi/gh-terminal
cd gh-terminal
pip install -e .
```

---

## Quick Start

```bash
# Start interactive control panel
gh-terminal start

# Run system diagnostics
gh-terminal doctor

# Run guided setup wizard
gh-terminal setup --wizard

# Check GitHub CLI status
gh-terminal auth --status

# Configure Git identity
gh-terminal identity --name "Your Name" --email "you@example.com"

# Full SSH signing setup
gh-terminal signing --setup

# Security audit
gh-terminal security --audit
```

See [docs/usage.md](docs/usage.md) for the complete command reference.

---

## Commands

| Command | Description |
|:--------|:------------|
| `start` | Launch interactive Main Control Panel |
| `doctor` | Run system diagnostics & health check |
| `setup` | Guided setup wizard or quick config |
| `config` | Manage configuration (get/set/list/export) |
| `identity` | Git identity: global, local, conditional includes, noreply, GitHub checks |
| `signing` | Commit signing: SSH (primary), GPG (fallback), status, verify |
| `ssh` | SSH keys, agent, config hosts, PAT hygiene |
| `auth` | GitHub CLI authentication (login, logout, status, switch) |
| `repo` | Repositories: create, clone, fork, remotes, collaborators, protection |
| `security` | Security audit, hardening, report |
| `accounts` | Multi-account management with directory-scoped identities |
| `advanced` | Actions, Codespaces, Packages, aliases, extensions, dashboard, export |

---

## Configuration

Configuration is stored in:

| OS | Path |
|:---|:-----|
| **Windows** | `%APPDATA%\gh-terminal\gh-terminal.yaml` |
| **macOS** | `~/Library/Application Support/gh-terminal/gh-terminal.yaml` |
| **Linux/WSL** | `~/.config/gh-terminal/gh-terminal.yaml` |

See `config/gh-terminal.example.yaml` for all options.

---

## Requirements

- Python 3.10+
- Git
- GitHub CLI (`gh`) - will be installed if missing

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy src/gh_terminal
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

<div align="center">

**Mohammadhossein Asadi** — Frontend & Full-Stack Engineer

[![GitHub](https://img.shields.io/badge/GitHub-mohammadhossein--asadi-0a0a0a?style=flat-square&logo=github)](https://github.com/mohammadhossein-asadi)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-mohammadhossein--asadi-0a66c2?style=flat-square&logo=linkedin)](https://linkedin.com/in/mohammadhossein-asadi)

</div>