"""Tests for the SessionRegistry and session-persistence behaviour."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# We patch the module-level paths before importing so the tests don't touch
# the real ~/.config directory.

import oauth_cli_coder.base as base_mod


@pytest.fixture(autouse=True)
def _tmp_registry(tmp_path, monkeypatch):
    """Redirect the registry to a temp directory for every test."""
    monkeypatch.setattr(base_mod, "REGISTRY_DIR", tmp_path)
    monkeypatch.setattr(base_mod, "REGISTRY_PATH", tmp_path / "sessions.json")


class TestSessionRegistry:
    def test_register_and_get(self):
        base_mod.SessionRegistry.register("sess-1", {"provider": "claude", "model": "opus"})
        entry = base_mod.SessionRegistry.get("sess-1")
        assert entry is not None
        assert entry["provider"] == "claude"

    def test_get_missing_returns_none(self):
        assert base_mod.SessionRegistry.get("nonexistent") is None

    def test_unregister(self):
        base_mod.SessionRegistry.register("sess-1", {"provider": "claude"})
        base_mod.SessionRegistry.unregister("sess-1")
        assert base_mod.SessionRegistry.get("sess-1") is None

    def test_list_all_empty(self):
        assert base_mod.SessionRegistry.list_all() == {}

    def test_list_all_multiple(self):
        base_mod.SessionRegistry.register("a", {"provider": "claude"})
        base_mod.SessionRegistry.register("b", {"provider": "gemini"})
        sessions = base_mod.SessionRegistry.list_all()
        assert len(sessions) == 2
        assert "a" in sessions
        assert "b" in sessions

    @patch("subprocess.run")
    def test_prune_removes_dead_sessions(self, mock_run):
        base_mod.SessionRegistry.register("alive", {"provider": "claude"})
        base_mod.SessionRegistry.register("dead", {"provider": "gemini"})

        def side_effect(cmd, **kwargs):
            if "alive" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect

        pruned = base_mod.SessionRegistry.prune()
        assert "dead" in pruned
        assert "alive" not in pruned
        assert base_mod.SessionRegistry.get("dead") is None
        assert base_mod.SessionRegistry.get("alive") is not None

    @patch("subprocess.run")
    def test_prune_no_stale(self, mock_run):
        base_mod.SessionRegistry.register("alive", {"provider": "claude"})
        mock_run.return_value = MagicMock(returncode=0)
        pruned = base_mod.SessionRegistry.prune()
        assert pruned == []

    def test_concurrent_register(self):
        """Multiple registers in sequence (simulating concurrent use) keep all entries."""
        base_mod.SessionRegistry.register("s1", {"provider": "claude"})
        base_mod.SessionRegistry.register("s2", {"provider": "gemini"})
        base_mod.SessionRegistry.register("s3", {"provider": "codex"})
        sessions = base_mod.SessionRegistry.list_all()
        assert len(sessions) == 3


class TestTmuxProviderRegistry:
    """Verify that TmuxProvider writes/reads the registry on start/close."""

    @patch("subprocess.run")
    def test_start_session_registers(self, mock_run):
        def side_effect(cmd, *args, **kwargs):
            if "has-session" in cmd:
                return MagicMock(returncode=1)  # no existing session
            if "capture-pane" in cmd:
                return MagicMock(stdout="\u276f")  # idle prompt for claude
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        from oauth_cli_coder.providers.claude import ClaudeProvider
        p = ClaudeProvider(model="opus", cwd="/tmp", session_id="test1")
        entry = base_mod.SessionRegistry.get(p.session_name)
        assert entry is not None
        assert entry["provider"] == "claude"
        assert entry["model"] == "opus"
        assert entry["cwd"] == "/tmp"
        assert "created_at" in entry

    @patch("subprocess.run")
    def test_close_unregisters(self, mock_run):
        def side_effect(cmd, *args, **kwargs):
            if "has-session" in cmd:
                return MagicMock(returncode=1)
            if "capture-pane" in cmd:
                return MagicMock(stdout="\u276f")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        from oauth_cli_coder.providers.claude import ClaudeProvider
        p = ClaudeProvider(session_id="test2")

        # Session now in registry
        assert base_mod.SessionRegistry.get(p.session_name) is not None

        # After close, has-session returns True so kill-session gets called
        def close_side_effect(cmd, *args, **kwargs):
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = close_side_effect
        p.close()

        assert base_mod.SessionRegistry.get(p.session_name) is None

    @patch("subprocess.run")
    def test_reconnect_loads_registry_config(self, mock_run):
        """When a session already exists and is in the registry, config is restored."""
        session_name = "oauth-coder-claude-reconn"

        # Pre-populate the registry
        base_mod.SessionRegistry.register(session_name, {
            "provider": "claude",
            "model": "sonnet",
            "cwd": "/projects/foo",
            "startup_options": ["--verbose"],
            "session_name": session_name,
            "created_at": "2026-01-01T00:00:00+00:00",
        })

        call_count = {"n": 0}

        def side_effect(cmd, *args, **kwargs):
            if "has-session" in cmd:
                return MagicMock(returncode=0)  # session exists
            if "capture-pane" in cmd:
                return MagicMock(stdout="\u276f")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        from oauth_cli_coder.providers.claude import ClaudeProvider
        # Create provider with only session_id -- model/cwd should be loaded from registry
        p = ClaudeProvider(session_id="reconn")
        assert p.model == "sonnet"
        assert p.cwd == "/projects/foo"
        assert p.startup_options == ["--verbose"]


class TestCLIListCommand:
    """Test the ``oauth-coder list`` CLI command."""

    def test_list_empty(self):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "No active sessions" in result.output

    def test_list_with_sessions(self):
        base_mod.SessionRegistry.register("oauth-coder-claude-abc", {
            "provider": "claude",
            "model": "opus",
            "cwd": "/tmp",
            "created_at": "2026-01-01T00:00:00+00:00",
        })

        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "oauth-coder-claude-abc" in result.output
        assert "claude" in result.output
        assert "opus" in result.output

    @patch("subprocess.run")
    def test_list_prune(self, mock_run):
        base_mod.SessionRegistry.register("dead-session", {"provider": "claude"})
        mock_run.return_value = MagicMock(returncode=1)  # session doesn't exist

        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--prune"])
        assert result.exit_code == 0
        assert "Pruned" in result.output
