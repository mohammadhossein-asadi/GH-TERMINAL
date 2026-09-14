"""
Tests for the identity module (pure-logic parts, no git/gh required).
"""

import pytest

from gh_terminal.core import CommandContext
from gh_terminal.modules.identity import NOREPLY_DOMAIN, IdentityManager
from gh_terminal.utils.system import OSType


@pytest.fixture
def manager():
    console = None
    ctx = CommandContext(console=console, config=None, error_handler=None)
    return IdentityManager(ctx)


class TestValidateEmail:
    @pytest.mark.unit
    def test_valid_emails(self, manager):
        assert manager.validate_email("user@example.com") is True
        assert manager.validate_email("first.last+tag@sub.domain.org") is True
        assert manager.validate_email("1234567+login@users.noreply.github.com") is True

    @pytest.mark.unit
    def test_invalid_emails(self, manager):
        assert manager.validate_email("") is False
        assert manager.validate_email("not-an-email") is False
        assert manager.validate_email("missing@tld") is False
        assert manager.validate_email("@no-local.com") is False


class TestGitdirPattern:
    @pytest.mark.unit
    def test_windows_case_insensitive(self, manager):
        path, key = IdentityManager._gitdir_pattern(
            "C:\\Users\\dev\\work", OSType.WINDOWS
        )
        assert str(path) == "C:\\Users\\dev\\work"
        assert key == "includeIf.gitdir/i:C:/Users/dev/work/"

    @pytest.mark.unit
    def test_linux_case_sensitive(self, manager):
        path, key = IdentityManager._gitdir_pattern(
            "C:/work/projects", OSType.LINUX
        )
        assert str(path) == "C:\\work\\projects"
        assert key == "includeIf.gitdir:C:/work/projects/"

    @pytest.mark.unit
    def test_trailing_slash_added(self, manager):
        _, key = IdentityManager._gitdir_pattern("C:/work", OSType.WINDOWS)
        assert key.endswith("/")


class TestNoreplyDomain:
    @pytest.mark.unit
    def test_domain_constant(self):
        assert NOREPLY_DOMAIN == "users.noreply.github.com"
