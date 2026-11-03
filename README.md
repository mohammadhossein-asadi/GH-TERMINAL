# GH-TERMINAL

<div align="center">

![GH-TERMINAL Logo](public/logo.png)

**GitHub in Your Terminal — Beautiful CLI for GitHub Operations**

[![Go](https://img.shields.io/badge/Go-1.22-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![Cobra](https://img.shields.io/badge/Cobra-1.8-000000?logo=cli&logoColor=white)](https://cobra.dev/)
[![Bubble Tea](https://img.shields.io/badge/Bubble_Tea-0.25-000000?logo=terminal&logoColor=white)](https://github.com/charmbracelet/bubbletea)
[![Lip Gloss](https://img.shields.io/badge/Lip_Gloss-0.9-FF6F61?logo=terminal&logoColor=white)](https://github.com/charmbracelet/lipgloss)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[🇬🇧 English](#-gh-terminal) • [🇮🇷 فارسی](README.fa.md) • [📖 Documentation](#-documentation) • [🚀 Quick Start](#-quick-start) • [🤝 Contributing](#-contributing)

</div>

---

## 🌟 Overview

**GH-TERMINAL** is a beautiful, interactive **TUI (Terminal User Interface)** for GitHub operations. Built with **Go**, **Bubble Tea**, and **Lip Gloss**, it brings GitHub's web experience to your terminal with full keyboard navigation, real-time updates, and stunning visuals.

### 🎯 Why GH-TERMINAL?

| Problem | GH-TERMINAL Solution |
|---------|---------------------|
| GitHub CLI is command-only | **Interactive TUI** with lists, forms, previews |
| Context switching browser ↔ terminal | **Everything in terminal** — issues, PRs, repos, notifications |
| No visual overview | **Rich tables, trees, markdown rendering** |
| Slow for repetitive tasks | **Keyboard-driven** with fuzzy search, shortcuts |

---

## ✨ Features

### 📋 **Issue Management**
- **List issues** — filter by state, labels, assignee, milestone
- **View issue** — markdown body, comments, timeline, reactions
- **Create issue** — interactive form with templates
- **Edit issue** — title, body, labels, assignees, milestone, project
- **Close/Reopen** — with reason
- **Comment** — markdown editor with preview

### 🔀 **Pull Request Management**
- **List PRs** — filter by state, base branch, author, labels
- **View PR** — diff, files, commits, checks, reviews, conversations
- **Review PR** — approve, request changes, comment on lines
- **Merge** — merge, squash, rebase with options
- **Checkout locally** — `gh pr checkout <number>`

### 📦 **Repository Operations**
- **Browse repos** — owned, starred, contributed, organizations
- **Clone** — SSH/HTTPS/CLI with directory selection
- **Create repo** — interactive form with templates
- **Fork** — with default branch tracking
- **View repo** — README, license, topics, languages, releases

### 🔔 **Notifications**
- **Unread count** — badge in header
- **List notifications** — filter by repo, type, reason
- **Mark read/unread** — bulk actions
- **Go to context** — jump to issue/PR/comment

### 🔍 **Search**
- **Global search** — code, issues, PRs, repos, users
- **Fuzzy finder** — Ctrl+P style repo/file jumping
- **Saved searches** — quick access

### ⌨️ **Keyboard-First UX**
| Key | Action |
|-----|--------|
| `j/k` / `↑/↓` | Navigate |
| `Enter` | Select/Open |
| `Esc` | Back/Cancel |
| `/` | Search/Filter |
| `?` | Help overlay |
| `q` | Quit |
| `Tab` | Next panel |
| `Shift+Tab` | Previous panel |
| `Ctrl+R` | Refresh |
| `Ctrl+O` | Open in browser |

### 🎨 **Visual Features**
- **Markdown rendering** — headers, code blocks, tables, task lists
- **Syntax highlighting** — 100+ languages (Chroma)
- **Diff view** — side-by-side or unified, colorized
- **Graphs** — commit history, contribution calendar
- **Themes** — Dracula, Tokyo Night, Catppuccin, Gruvbox, custom
- **True color** — 24-bit RGB support

### 🌍 **Persian Support**
| Feature | Implementation |
|---------|----------------|
| **RTL Text** | Bidi algorithm for Persian/Arabic |
| **Persian Numbers** | ۱۲۳۴۵۶۷۸۹۰ in counters |
| **Jalali Dates** | Relative time in Persian calendar |
| **Vazirmatn** | Font fallback for Persian text |

---

## 🏗️ Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Go 1.22+ |
| **TUI Framework** | Bubble Tea (charmbracelet) |
| **Styling** | Lip Gloss (charmbracelet) |
| **CLI Framework** | Cobra (spf13) |
| **GitHub API** | go-github (Google) |
| **Markdown** | goldmark + Chroma |
| **Config** | Viper (spf13) |
| **Keybinding** | harmony (charmbracelet) |
| **Testing** | testify (stretchr) |

### Project Structure

```
GH-TERMINAL/
├── cmd/
│   └── gh-terminal/
│       └── main.go             # Entry point
├── internal/
│   ├── app/
│   │   ├── model.go            # Bubble Tea model
│   │   ├── update.go           # Update loop
│   │   ├── view.go             # View rendering
│   │   └── keymap.go           # Key bindings
│   ├── ui/
│   │   ├── components/         # Reusable UI components
│   │   │   ├── list.go
│   │   │   ├── table.go
│   │   │   ├── form.go
│   │   │   ├── markdown.go
│   │   │   ├── diff.go
│   │   │   └── help.go
│   │   ├── themes/             # Color themes
│   │   │   ├── dracula.go
│   │   │   ├── tokyo-night.go
│   │   │   ├── catppuccin.go
│   │   │   └── custom.go
│   │   └── styles.go           # Lip Gloss styles
│   ├── github/
│   │   ├── client.go           # GitHub API wrapper
│   │   ├── issues.go
│   │   │   ├── pulls.go
│   │   │   ├── repos.go
│   │   │   ├── notifications.go
│   │   │   └── search.go
│   │   └── auth.go             # OAuth/token management
│   ├── config/
│   │   ├── config.go           # Viper config
│   │   └── defaults.go
│   └── persian/
│       ├── bidi.go             # RTL support
│       ├── numbers.go          # Persian numerals
│       └── jalali.go           # Jalali calendar
├── pkg/
│   └── utils/
├── configs/
│   └── config.yaml.example
├── go.mod
├── go.sum
├── Makefile
├── README.md
├── README.fa.md
└── LICENSE
```

---

## 🚀 Quick Start

### Prerequisites

- **Go** 1.22+
- **GitHub Personal Access Token** (classic or fine-grained)

### Installation

```bash
# From source
git clone https://github.com/mohammadhossein-asadi/GH-TERMINAL.git
cd GH-TERMINAL
make build
# Binary at ./bin/gh-terminal

# Or install directly
go install github.com/mohammadhossein-asadi/GH-TERMINAL/cmd/gh-terminal@latest

# Or download release
# https://github.com/mohammadhossein-asadi/GH-TERMINAL/releases
```

### Authentication

```bash
# Interactive login
gh-terminal auth login

# Or set token manually
gh-terminal auth token ghp_xxxxxxxxxxxx

# Verify
gh-terminal auth status
```

### Basic Usage

```bash
# Start TUI
gh-terminal

# Quick commands (without TUI)
gh-terminal issue list --repo owner/repo --state open
gh-terminal pr list --repo owner/repo --state open
gh-terminal repo list --user mohammadhossein-asadi
gh-terminal notification list --unread

# Search
gh-terminal search "bug" --type issues --repo owner/repo

# Config
gh-terminal config set theme dracula
gh-terminal config set vim_mode true
```

---

## ⚙️ Configuration

Create `~/.config/gh-terminal/config.yaml`:

```yaml
# GitHub
github:
  token: ""              # Set via auth command
  host: "github.com"     # For GitHub Enterprise

# UI
ui:
  theme: "tokyo-night"   # dracula, tokyo-night, catppuccin, gruvbox, auto
  vim_mode: true         # Vim-style keybindings
  show_line_numbers: true
  mouse_enabled: true
  confirm_on_quit: true

# Behavior
behavior:
  auto_refresh: 30       # Seconds (0 = disabled)
  page_size: 30          # Items per page
  preview_lines: 20      # Markdown preview lines
  diff_context: 3        # Diff context lines

# Persian
persian:
  enable_rtl: true
  persian_numbers: true
  jalali_dates: true
  font_fallback: "Vazirmatn"

# Keybindings (Vim mode shown)
keybindings:
  quit: "q"
  back: "Esc"
  select: "Enter"
  search: "/"
  help: "?"
  refresh: "Ctrl+R"
  open_browser: "Ctrl+O"
  next_tab: "Tab"
  prev_tab: "Shift+Tab"
  up: "k"
  down: "j"
  half_page_up: "Ctrl+U"
  half_page_down: "Ctrl+D"
```

---

## 🛠️ Development

### Setup

```bash
git clone https://github.com/mohammadhossein-asadi/GH-TERMINAL.git
cd GH-TERMINAL

# Install dependencies
go mod download

# Run
go run ./cmd/gh-terminal

# Build
make build

# Test
make test

# Lint
make lint

# Format
make fmt
```

### Makefile Targets

```bash
make build          # Build binary
make test           # Run tests
make test-coverage  # Coverage report
make lint           # golangci-lint
make fmt            # gofmt + goimports
make vet            # go vet
make install        # Install to GOPATH/bin
make release        # Build for all platforms
make clean          # Clean build artifacts
```

---

## 🧪 Testing

```bash
# Unit tests
go test ./...

# With coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Integration tests (requires GH token)
GH_TOKEN=xxx go test -tags=integration ./...
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | TUI architecture |
| [Keybindings](docs/KEYBINDINGS.md) | Complete key reference |
| [Theming](docs/THEMING.md) | Custom themes |
| [GitHub API](docs/GITHUB_API.md) | API wrapper usage |
| [Persian Support](docs/PERSIAN.md) | RTL, numbers, dates |

---

## 🚀 Building Releases

```bash
# Cross-compile
make release

# Outputs in dist/
# gh-terminal_linux_amd64
# gh-terminal_linux_arm64
# gh-terminal_darwin_amd64
# gh-terminal_darwin_arm64
# gh-terminal_windows_amd64.exe
```

### Homebrew Tap (Optional)

```bash
# Add to homebrew tap
brew tap mohammadhossein-asadi/gh-terminal
brew install gh-terminal
```

---

## 🔒 Security

- **Token storage** — OS keychain (macOS Credential Manager, Windows Credential Manager, libsecret)
- **No token logging** — Sanitized in logs
- **HTTPS only** — Enforced for all API calls
- **Minimal scopes** — Request only needed permissions

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

### Development Workflow

1. Fork & clone
2. Create feature branch
3. Make changes
4. Run: `make lint test fmt vet`
5. Commit with conventional messages
6. Push & PR

---

## 📋 Roadmap

- [x] Core TUI with Bubble Tea
- [x] Issues, PRs, Repos, Notifications
- [x] Markdown + diff rendering
- [x] Themes (Dracula, Tokyo Night, etc.)
- [x] Persian RTL + numbers + Jalali
- [x] Vim keybindings
- [ ] Code review inline comments
- [ ] GitHub Projects (beta) support
- [ ] Codespaces integration
- [ ] Actions/Workflows view
- [ ] Discussions support
- [ ] Gists management
- [ ] SSH key management
- [ ] Plugin system

---

## 📄 License

**MIT License** — See [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- **Bubble Tea** — TUI framework by Charmbracelet
- **Lip Gloss** — Styling by Charmbracelet
- **Cobra** — CLI framework by spf13
- **go-github** — GitHub API by Google
- **Chroma** — Syntax highlighting by Alec Thomas
- **Vazirmatn Font** — Persian typography by Rastikerdar

---

## 📞 Support & Community

- **Issues**: [GitHub Issues](https://github.com/mohammadhossein-asadi/GH-TERMINAL/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mohammadhossein-asadi/GH-TERMINAL/discussions)

---

<div align="center">

**Built with ❤️ for terminal-loving GitHub users**

[🇬🇧 English](README.md) • [🇮🇷 فارسی](README.fa.md) • [⭐ Star us on GitHub](https://github.com/mohammadhossein-asadi/GH-TERMINAL)

</div>