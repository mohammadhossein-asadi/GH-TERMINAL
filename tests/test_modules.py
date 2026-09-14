"""
Tests for signing, ssh config parsing, and security checks (mocked commands).
"""

import pytest

from gh_terminal.core import CommandContext
from gh_terminal.modules.security import SecurityManager, StatusBadge
from gh_terminal.modules.ssh_keys import SSHManager


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def ctx(tmp_path):
    return CommandContext(console=None, config=None, error_handler=None)


class TestSSHConfigParsing:
    @pytest.mark.unit
    def test_parse_multiple_hosts(self, ctx, tmp_path, monkeypatch):
        manager = SSHManager(ctx)
        manager.ssh_dir = tmp_path
        config_file = tmp_path / "config"
        config_file.write_text(
            "Host github.com\n"
            "  HostName github.com\n"
            "  User git\n"
            "  IdentityFile ~/.ssh/id_ed25519\n"
            "\n"
            "Host github-work\n"
            "  HostName github.com\n"
            "  User git\n"
            "  IdentityFile ~/.ssh/id_ed25519_work\n",
            encoding="utf-8",
        )
        hosts = manager.config_list_hosts()
        expected_hosts = 2
        assert len(hosts) == expected_hosts
        assert hosts[0]["host"] == "github.com"
        assert hosts[0]["user"] == "git"
        assert hosts[1]["host"] == "github-work"
        assert hosts[1]["identityfile"] == "~/.ssh/id_ed25519_work"

    @pytest.mark.unit
    def test_parse_empty_config(self, ctx, tmp_path):
        manager = SSHManager(ctx)
        manager.ssh_dir = tmp_path
        assert manager.config_list_hosts() == []


class TestSigningGPGParse:
    @pytest.mark.unit
    def test_list_gpg_keys_parses_sec_lines(self, ctx, monkeypatch):
        from gh_terminal.modules.signing import SigningManager

        def fake_run(cmd, **kwargs):
            if "gpg" in cmd:
                return FakeResult(
                    0,
                    "sec   ed25519/ABCD1234EFGH5678 2024-01-01 [SC]\n"
                    "uid   Test User <test@example.com>\n",
                )
            return FakeResult(1, "", "")

        monkeypatch.setattr(
            "gh_terminal.modules.signing.run_command", fake_run
        )
        manager = SigningManager.__new__(SigningManager)
        keys = SigningManager.list_gpg_keys(manager)
        assert len(keys) == 1
        assert "ABCD1234EFGH5678" in keys[0]


class TestSecurityChecks:
    @pytest.mark.unit
    def test_signing_check_all_configured(self, ctx, monkeypatch):
        def fake_run(cmd, **kwargs):
            if "gpg.format" in cmd:
                return FakeResult(0, "ssh")
            if "user.signingkey" in cmd:
                return FakeResult(0, "~/.ssh/key.pub")
            if "commit.gpgsign" in cmd:
                return FakeResult(0, "true")
            return FakeResult(1, "", "")

        monkeypatch.setattr("gh_terminal.modules.security.run_command", fake_run)
        manager = SecurityManager(ctx)
        badge, _detail = manager._check_signing()
        assert badge == StatusBadge.SUCCESS
        assert "configured" in _detail.lower()

    @pytest.mark.unit
    def test_signing_check_not_configured(self, ctx, monkeypatch):
        def fake_run(cmd, **kwargs):
            return FakeResult(1, "", "")

        monkeypatch.setattr("gh_terminal.modules.security.run_command", fake_run)
        manager = SecurityManager(ctx)
        badge, _ = manager._check_signing()
        assert badge == StatusBadge.FAILED

    @pytest.mark.unit
    def test_2fa_disabled_warns(self, ctx, monkeypatch):
        def fake_run(cmd, **kwargs):
            return FakeResult(0, "false")

        monkeypatch.setattr("gh_terminal.modules.security.run_command", fake_run)
        manager = SecurityManager(ctx)
        badge, _ = manager._check_2fa()
        assert badge == StatusBadge.WARNING
