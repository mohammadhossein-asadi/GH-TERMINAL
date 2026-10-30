# Project DNA — GH-TERMINAL v3.1 Neon Edition

## Project Identity

| Field | Value |
|-------|-------|
| **Project Name** | GH-TERMINAL (gh-terminal) |
| **Repository** | `GH-TERMINAL` |
| **Type** | CLI Tool (Python) — GitHub Configuration & Management System with TUI |
| **Primary Language** | Python 3.10+ |
| **Package Manager** | pip / pipx / setuptools |
| **CLI Framework** | Click 8.1+ |
| **TUI Framework** | Textual 0.52+ |
| **Terminal Rendering** | Rich 13.7+ |

---

## Purpose & Problem Statement

**Problem**: Developers managing GitHub workflows face fragmented tools: `gh` CLI for API operations, `git` for version control, manual SSH/GPG key management, separate security auditing tools, and no unified interface for multi-account workflows. Configuration is scattered across global/local git config, SSH config, GPG keys, and GitHub CLI auth.

**Solution**: A single, beautiful terminal application (Neon Edition) that unifies GitHub configuration, security hardening, repository management, multi-account workflows, and power-user features (Actions, Codespaces, Packages) into an interactive TUI with guided wizards and exportable setup scripts.

---

## Target Users

- **Primary**: Developers and DevOps engineers managing multiple GitHub accounts/repos
- **Secondary**: Security-conscious developers wanting SSH commit signing and auditing
- **Tertiary**: Teams needing standardized GitHub onboarding (exportable scripts)
- **Quaternary**: Open source maintainers managing collaborators, protections, packages

---

## Core Features (Implemented)

| Feature | Status | Description |
|---------|--------|-------------|
| Interactive Main Control Panel | ✅ Implemented | Textual TUI with neon theme, headers, badges, progress bars |
| System Diagnostics (`doctor`) | ✅ Implemented | Health checks for git, gh CLI, SSH, GPG, signing, config |
| Guided Setup Wizard | ✅ Implemented | Step-by-step onboarding for beginners |
| Git Identity Management | ✅ Implemented | Global/local/conditional includes, noreply email, GitHub checks |
| Commit Signing (SSH/GPG) | ✅ Implemented | SSH primary, GPG fallback, status verification |
| SSH Key Management | ✅ Implemented | Keys, agent, config hosts, PAT hygiene |
| GitHub Auth Management | ✅ Implemented | Login, logout, status, account switching |
| Repository Management | ✅ Implemented | Create, clone, fork, remotes, collaborators, branch protection |
| Security Auditing | ✅ Implemented | Comprehensive audit, hardening recommendations, reports |
| Multi-Account Management | ✅ Implemented | Directory-scoped identities, per-account SSH keys, switching |
| Advanced Features | ✅ Implemented | Actions secrets/vars/environments, Codespaces, Packages, aliases |
| Export Setup Scripts | ✅ Implemented | Reproducible `.sh` / `.ps1` scripts for team onboarding |
| Cross-Platform | ✅ Implemented | Windows, macOS, Linux, WSL support |

---

## Technical Requirements

| Requirement | Detail |
|-------------|--------|
| **Runtime** | Python 3.10+ |
| **TUI** | Textual 0.52+ (CSS styling, reactive UI) |
| **Terminal** | Rich 13.7+ (syntax highlighting, tables, panels) |
| **CLI** | Click 8.1+ (command groups, options, prompts) |
| **Config** | PyYAML 6.0+ (platformdirs for cross-platform paths) |
| **System** | psutil 5.9+ (process, system info), python-dotenv |
| **Testing** | pytest 7.4+ with markers (unit, integration, slow, requires_gh, requires_git) |
| **Linting** | Ruff (comprehensive rule set, per-file ignores) |
| **Type Checking** | MyPy 1.7+ (strict mode) |
| **Packaging** | PyInstaller 6.1+ for standalone binaries |

---

## Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-01 | Launch interactive neon TUI control panel | ✅ |
| FR-02 | Run comprehensive system diagnostics | ✅ |
| FR-03 | Guided setup wizard for beginners | ✅ |
| FR-04 | Manage Git identity (global, local, conditional) | ✅ |
| FR-05 | SSH commit signing setup and verification | ✅ |
| FR-06 | GPG commit signing fallback | ✅ |
| FR-07 | SSH key generation, agent, config management | ✅ |
| FR-08 | GitHub CLI authentication flow | ✅ |
| FR-09 | Repository CRUD + advanced settings | ✅ |
| FR-10 | Security audit with hardening report | ✅ |
| FR-11 | Multi-account with directory-scoped identities | ✅ |
| FR-12 | GitHub Actions secrets/variables/environments | ✅ |
| FR-13 | Codespaces management | ✅ |
| FR-14 | GitHub Packages management | ✅ |
| FR-15 | Export reproducible setup scripts | ✅ |
| FR-16 | Configuration file management (get/set/list/export) | ✅ |
| FR-17 | Cross-platform path handling | ✅ |

---

## Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-01 | Startup time < 2s (cold) | [NOT VERIFIED] |
| NFR-02 | TUI responsive at 60fps | [NOT VERIFIED] |
| NFR-03 | Memory usage < 100MB | [NOT VERIFIED] |
| NFR-04 | Works on Windows/macOS/Linux/WSL | ✅ |
| NFR-05 | No external GUI dependencies | ✅ |
| NFR-06 | Works offline (except gh CLI calls) | ✅ |
| NFR-07 | Secure credential handling (no plaintext tokens) | [PARTIAL - uses keyring?] |
| NFR-08 | Accessible (screen reader compatible) | [NOT VERIFIED] |

---

## Business/Technical Objectives

- [ ] Publish to PyPI as `gh-terminal`
- [ ] Achieve 80%+ test coverage
- [ ] Create standalone binaries via PyInstaller for each platform
- [ ] Add GitHub Action for automated releases
- [ ] Implement plugin system for custom modules
- [ ] Add telemetry/usage analytics (opt-in)
- [ ] Create video tutorials for each module
- [ ] Add shell completions (bash, zsh, fish, PowerShell)

---

## Known Limitations

1. **Requires `gh` CLI** - Core functionality depends on GitHub CLI being installed
2. **No standalone binary yet** - PyInstaller configured but not verified
3. **GPG fallback only** - SSH signing is primary, GPG less tested
4. **No auto-update mechanism** - Users must reinstall via pipx/pip
5. **Test coverage unknown** - pytest configured but coverage not measured
6. **Windows terminal compatibility** - Neon theme may need specific terminal support
7. **Large codebase** - Some modules exceed complexity thresholds (ruff ignores)
8. **No plugin system** - Extensions require code changes

---

## Confirmed Decisions

| Decision | Rationale |
|----------|-----------|
| Textual for TUI | Modern, CSS-stylable, reactive, cross-platform |
| Rich for rendering | Best-in-class terminal formatting, tables, syntax |
| Click for CLI | Mature, composable, good Textual integration |
| PyYAML for config | Human-readable, supports comments, cross-platform |
| platformdirs for paths | Correct XDG/Base/AppData paths per OS |
| SSH signing over GPG | Modern, hardware key support (YubiKey), simpler |
| Directory-scoped identities | Git conditional includes, no env var pollution |
| Ruff for linting | Fast, comprehensive, replaces flake8+isort+black |
| MyPy strict mode | Catch bugs early, enforce type safety |
| pytest markers | Selective test runs (CI vs local) |

---

## Unknown Information / Needs Confirmation

| Question | Priority |
|----------|----------|
| Is PyPI publishing automated (GitHub Actions trusted publishing)? | HIGH |
| Are standalone binaries built and tested per platform? | HIGH |
| What is the current test coverage percentage? | HIGH |
| Is there a keyring/secure storage integration for tokens? | MEDIUM |
| Will there be a plugin/extension system? | MEDIUM |
| Are there plans for a web dashboard companion? | LOW |
| What is the release cadence? | LOW |

---

*Generated: 2026-10-30 | Stage 1 of 5 | [NEEDS CONFIRMATION] on unknowns*