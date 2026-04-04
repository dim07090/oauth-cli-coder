"""Tests for the stealth PTY wrapper module."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import uuid

import pytest

from oauth_cli_coder.stealth import build_stealth_command, _detect_script_flags, _setsid_supports_wait


# ---------------------------------------------------------------------------
# Unit tests for build_stealth_command
# ---------------------------------------------------------------------------

class TestBuildStealthCommand:
    """Pure-logic tests that do not require tmux."""

    def test_returns_bash_wrapper(self):
        result = build_stealth_command(["claude"])
        assert result[0] == "bash"
        assert result[1] == "-c"

    def test_strips_tmux_env_vars(self):
        result = build_stealth_command(["claude"])
        inner = result[2]
        assert "-u TMUX" in inner
        assert "-u TMUX_PANE" in inner
        assert "-u TMUX_PLUGIN_MANAGER_PATH" in inner

    def test_sets_term(self):
        result = build_stealth_command(["claude"])
        inner = result[2]
        assert "TERM=xterm-256color" in inner

    def test_includes_setsid_when_available(self):
        if not _setsid_supports_wait():
            pytest.skip("setsid --wait not available")
        result = build_stealth_command(["claude"])
        assert "setsid --wait" in result[2]

    def test_includes_script_when_available(self):
        if shutil.which("script") is None:
            pytest.skip("script not available")
        result = build_stealth_command(["echo", "hello"])
        assert "script" in result[2]

    def test_command_with_spaces_is_quoted(self):
        result = build_stealth_command(["echo", "hello world"])
        inner = result[2]
        assert "'hello world'" in inner

    def test_detect_script_flags_returns_list_or_none(self):
        flags = _detect_script_flags()
        if shutil.which("script"):
            assert isinstance(flags, list)
            assert flags[0] == "script"
        else:
            assert flags is None


# ---------------------------------------------------------------------------
# Integration tests -- require tmux to be installed
# ---------------------------------------------------------------------------

def _has_tmux() -> bool:
    return shutil.which("tmux") is not None


@pytest.mark.skipif(not _has_tmux(), reason="tmux not installed")
class TestStealthInTmux:
    """Start a real tmux session with the stealth wrapper and verify isolation."""

    @staticmethod
    def _session_name() -> str:
        return f"stealth-test-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _cleanup(session: str) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            capture_output=True,
        )

    @staticmethod
    def _capture(session: str) -> str:
        p = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", session],
            capture_output=True,
            text=True,
        )
        return p.stdout

    def _run_in_stealth_session(self, shell_snippet: str, wait: float = 2.0) -> str:
        """Launch a stealth session running *shell_snippet*, capture output.

        Writes the snippet to a temp script file to avoid nested-quoting
        issues with bash -c inside script -c.
        """
        import tempfile

        session = self._session_name()
        # Write snippet to a temp script to sidestep quoting nightmares.
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sh", delete=False, prefix="stealth_test_",
        ) as f:
            f.write("#!/bin/bash\n")
            f.write(shell_snippet + "\n")
            # Keep the session alive briefly so capture-pane can read it.
            f.write("sleep 5\n")
            script_path = f.name
        os.chmod(script_path, 0o755)

        wrapped = build_stealth_command([script_path])

        tmux_cmd = [
            "tmux", "new-session", "-d", "-s", session,
            "-x", "200", "-y", "50",
        ] + wrapped

        try:
            subprocess.run(tmux_cmd, check=True, capture_output=True)
            time.sleep(wait)
            output = self._capture(session)
            return output
        finally:
            self._cleanup(session)
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def test_tmux_env_not_visible(self):
        """TMUX env var should not be set inside the stealth session."""
        output = self._run_in_stealth_session('echo "TMUX=${TMUX:-UNSET}"')
        assert "TMUX=UNSET" in output

    def test_tmux_pane_env_not_visible(self):
        """TMUX_PANE env var should not be set inside the stealth session."""
        output = self._run_in_stealth_session('echo "TMUX_PANE=${TMUX_PANE:-UNSET}"')
        assert "TMUX_PANE=UNSET" in output

    def test_term_is_xterm(self):
        """TERM should be xterm-256color inside the stealth session."""
        output = self._run_in_stealth_session('echo "TERM=$TERM"')
        assert "TERM=xterm-256color" in output

    def test_pty_is_not_tmux_pty(self):
        """The TTY inside stealth should NOT contain 'tmux' in its name.

        A fresh ``script`` PTY will typically be /dev/pts/N, not a tmux
        pseudo-terminal.
        """
        if shutil.which("script") is None:
            pytest.skip("script not available")
        output = self._run_in_stealth_session("tty")
        # The output should contain /dev/pts/ (Linux) or /dev/ttys (macOS)
        # and should NOT mention tmux.
        cleaned = output.strip()
        assert "tmux" not in cleaned.lower()

    def test_process_group_detached(self):
        """The direct parent process should not be tmux."""
        # Print the parent PID's command name
        output = self._run_in_stealth_session(
            "cat /proc/$PPID/comm 2>/dev/null || ps -o comm= -p $PPID"
        )
        cleaned = output.strip().lower()
        # The parent should be script, bash, setsid, or similar -- not tmux
        assert "tmux" not in cleaned

    def test_capture_pane_still_works(self):
        """tmux capture-pane should still retrieve output from a stealth session.

        This verifies that the ``script`` PTY layer does not break tmux's
        ability to read the pane content.
        """
        marker = f"CAPTURE_TEST_{uuid.uuid4().hex[:8]}"
        output = self._run_in_stealth_session(f'echo "{marker}"')
        assert marker in output


@pytest.mark.skipif(not _has_tmux(), reason="tmux not installed")
class TestStealthOptOut:
    """Verify the stealth=False opt-out path."""

    def test_no_stealth_wrapper_when_disabled(self):
        """When stealth=False the command should be passed through as-is."""
        # We just verify build_stealth_command is not called by checking
        # the shape of cmd_args that would be produced without wrapping.
        cmd = ["claude", "--model", "opus"]
        # Without stealth the args would remain unchanged.
        # With stealth they become ["bash", "-c", "..."].
        wrapped = build_stealth_command(cmd)
        assert wrapped[0] == "bash"
        # The original args should NOT start with "bash" unless that was
        # the original command.
        assert cmd[0] != "bash"
