# GH-TERMINAL Usage Guide

GH-TERMINAL is a cross-platform terminal application for configuring, securing, and
managing your GitHub environment from one place.

## Quick Start

```bash
# Interactive control panel
gh-terminal start

# One-time guided setup
gh-terminal setup --wizard

# Health check
gh-terminal doctor
```

## Command Reference

### `start`
Interactive Main Control Panel with 12 options covering everything below.

### `doctor`
Runs 8 system diagnostics: git, gh CLI, SSH agent, SSH keys, GPG keys,
credential helper, commit signing config, and allowed_signers.

### `setup [--wizard]`
Quick status view, or the full guided wizard (diagnostics, gh install/auth,
identity, SSH keys, signing, hardening).

### `config [key] [value] [--list|--reset|--export]`
Manage `gh-terminal.yaml`. `--export` prints a setup checklist.

### `identity` - Git identity
| Flag | Purpose |
|------|---------|
| `--name N --email E` | Set identity (global by default) |
| `--local` | Apply to current repository only |
| `--noreply` | Use your GitHub private noreply email |
| `--list` | Show global + effective identity |
| `--check-email E` | Format / GitHub match / verified check |
| `--include <dir> --name N --email E` | Directory-scoped conditional identity |
| `--list-includes` / `--remove-include <dir>` | Manage conditional rules |

Conditional identities use git `includeIf` rules: every repository under the
bound directory automatically uses that account's name/email/key.

### `signing` - Commit signing
| Flag | Purpose |
|------|---------|
| `--setup` | Full SSH signing flow: generate ed25519 key, add to agent, upload as Signing Key, configure git, create allowed_signers |
| `--gpg` | GPG fallback flow (select key, configure git, export for GitHub) |
| `--status` | Show signing configuration table |
| `--verify` | Create a signed test commit in an isolated temp repo and verify it locally |
| `--key-path P` | Custom key location |

After `--setup`, push a commit and check the "Verified" badge on GitHub.

### `ssh` - Keys, agent, config, PATs
| Flag | Purpose |
|------|---------|
| `--generate [--key-name K] [--signing]` | Generate ed25519 keys |
| `--list` | List keys with fingerprints and permissions |
| `--upload <key\|all>` | Upload public keys to GitHub (`gh ssh-key add`) |
| `--test` | `ssh -T git@github.com` connectivity test |
| `--agent` | ssh-agent status, start (Windows service / POSIX), add keys |
| `--config` | Manage `~/.ssh/config` Host blocks (add/remove/list) |
| `--pat` | Token hygiene audit + fine-grained vs classic guidance |

### `auth` - GitHub CLI lifecycle
`--login` (browser or token), `--status`, `--logout`, `--switch <user>`.
`gh auth switch` uses `--user` (per gh CLI 2.x).

### `accounts` - Multi-account
| Flag | Purpose |
|------|---------|
| `--list` | gh accounts + saved identities + conditional includes |
| `--add [user]` | Configure a new account (name, email, key, directory binding) |
| `--switch <user>` | `gh auth switch --user` + record default |
| `--switch-menu` | Interactive account picker |
| `--remove <user>` | Remove identity files, includes, optional gh logout |
| `--default <user>` | Set default account |

### `repo` - Repository manager
`--create <name> [--public] --readme --gitignore Python --license mit --description "..."`,
`--clone`, `--fork` (auto upstream), `--list`, `--remotes`, `--remote-add 'name url'`,
`--remote-remove/--remote-rename/--remote-seturl`, `--default-branch <branch>`,
`--collaborators`, `--add-collaborator 'user [perm]'`, `--remove-collaborator user`,
`--insights`, `--protect` (interactive branch protection via API), `--codeowners`.

### `security` - Audit and hardening
`--audit` runs 9 checks (2FA, signing, protocol, credential helper, token hygiene,
Dependabot, secret scanning, code scanning, dangerous configs; repo-scoped checks
work when run inside a repository). `--harden` applies safe defaults after
confirmation. `--report` writes `~/gh-terminal-security-report.md` with
audit-driven remediation steps.

### `advanced` - Power-user features
`--actions` (secrets/variables/environments CRUD), `--codespaces`
(create/stop/delete), `--packages [--org O]` (via GitHub API), `--aliases`
(set/delete), `--extensions` (list/install), `--org <name>` (membership role),
`--dashboard [--repo R]` (workflow runs, issues, PRs, releases), and
`--export-script` (reproducible `.sh` / `.ps1` setup scripts).

### `config`
`key [value]`, `--list`, `--reset`, `--export`.

## Configuration Locations

- Windows: `%APPDATA%\gh-terminal\gh-terminal.yaml`
- macOS: `~/Library/Application Support/gh-terminal/gh-terminal.yaml`
- Linux/WSL: `~/.config/gh-terminal/gh-terminal.yaml`

Identity files for conditional includes live in the `identities/` subdirectory.

## Requirements

- Python 3.10+
- Git
- GitHub CLI (`gh`) - installation offered automatically when missing

## Tips

- Use `--dry-run` with `identity` to preview git config changes.
- Never paste private keys or tokens anywhere; GH-TERMINAL only ever asks for
  them through hidden prompts and passes them directly to the relevant tool.
- Run `gh-terminal doctor` inside a repository to include repo-scoped checks.
