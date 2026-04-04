"""
End-to-end tests for the CLI request/response pattern across all 3 providers.

Tests the full flow: session startup → prompt submission → response parsing → cleanup.
Mocks at the subprocess (tmux) boundary to verify each provider's protocol.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from oauth_cli_coder.providers.claude import ClaudeProvider
from oauth_cli_coder.providers.gemini import GeminiProvider
from oauth_cli_coder.providers.codex import CodexProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_subprocess_mock(idle_marker, response_screen, startup_screen=None):
    """
    Build a subprocess.run side-effect that simulates a tmux session lifecycle:
      1. has-session → not found (returncode=1) so _start_session creates one
      2. capture-pane during startup → returns idle_marker (startup complete)
      3. has-session → found (returncode=0) for the ask() call
      4. capture-pane during ask() → first few calls return busy, then response_screen
    """
    state = {"phase": "startup", "capture_count": 0}
    startup_text = startup_screen or idle_marker

    def side_effect(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

        if "has-session" in cmd_str:
            if state["phase"] == "startup":
                return MagicMock(returncode=1)  # no session yet
            return MagicMock(returncode=0)  # session exists

        if "capture-pane" in cmd_str:
            state["capture_count"] += 1
            if state["phase"] == "startup":
                # After a couple captures, show idle prompt so startup completes
                if state["capture_count"] >= 2:
                    state["phase"] = "ready"
                    state["capture_count"] = 0
                return MagicMock(stdout=startup_text)
            # During ask(): first few captures show busy, then show response
            if state["capture_count"] <= 3:
                return MagicMock(stdout=idle_marker)  # still processing
            return MagicMock(stdout=response_screen)

        if "kill-session" in cmd_str:
            state["phase"] = "killed"
            return MagicMock(returncode=0, stdout="")

        # All other tmux commands (new-session, send-keys, load-buffer, paste-buffer, etc.)
        return MagicMock(returncode=0, stdout="")

    return side_effect


# ---------------------------------------------------------------------------
# Claude Provider E2E
# ---------------------------------------------------------------------------

class TestClaudeE2E:
    IDLE = "❯"
    RESPONSE = "❯\n● Here is the answer to your question.\nIt spans multiple lines."

    @patch("subprocess.run")
    def test_ask_returns_parsed_response(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-claude")
        response = provider.ask("What is 2+2?")

        assert "Here is the answer to your question." in response
        assert "It spans multiple lines." in response

    @patch("subprocess.run")
    def test_start_cmd_includes_bypass_permissions(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-cmd")
        cmd = provider.get_start_cmd()

        assert cmd[0] == "claude"
        assert "--permission-mode" in cmd
        assert "bypassPermissions" in cmd

    @patch("subprocess.run")
    def test_start_cmd_includes_model(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(model="opus", session_id="test-model")
        cmd = provider.get_start_cmd()

        assert "--model" in cmd
        assert "opus" in cmd

    @patch("subprocess.run")
    def test_is_idle_detects_prompt(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-idle")
        assert provider.is_idle("Some output\n❯") is True
        assert provider.is_idle("⠋ Thinking...") is False
        assert provider.is_idle("Running command...") is False
        assert provider.is_idle("❯ Thinking") is False

    @patch("subprocess.run")
    def test_submit_keys_is_enter(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-keys")
        assert provider.get_submit_keys() == ["Enter"]

    @patch("subprocess.run")
    def test_marker_is_bullet(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-marker")
        assert provider.get_marker() == "● "

    @patch("subprocess.run")
    def test_close_kills_session(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = ClaudeProvider(session_id="test-close")
        provider.close()

        kill_calls = [c for c in mock_run.call_args_list if "kill-session" in str(c)]
        assert len(kill_calls) > 0

    @patch("subprocess.run")
    def test_slash_command_routes_through_ask(self, mock_run):
        slash_response = "❯\n● Context cleared."
        mock_run.side_effect = make_subprocess_mock(self.IDLE, slash_response)

        provider = ClaudeProvider(session_id="test-slash")
        response = provider.slash_command("/clear")

        assert "Context cleared" in response

    @patch("subprocess.run")
    def test_clear_session_sends_clear(self, mock_run):
        slash_response = "❯\n● Session cleared."
        mock_run.side_effect = make_subprocess_mock(self.IDLE, slash_response)

        provider = ClaudeProvider(session_id="test-clearsess")
        response = provider.clear_session()

        assert "cleared" in response.lower()


# ---------------------------------------------------------------------------
# Gemini Provider E2E
# ---------------------------------------------------------------------------

class TestGeminiE2E:
    IDLE = "✦"
    RESPONSE = "✦\nHere is Gemini's answer.\nWith supporting details."

    @patch("subprocess.run")
    def test_ask_returns_parsed_response(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-gemini")
        response = provider.ask("Explain Python decorators")

        assert "Gemini's answer" in response or "supporting details" in response

    @patch("subprocess.run")
    def test_start_cmd_is_gemini(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-cmd")
        cmd = provider.get_start_cmd()

        assert cmd[0] == "gemini"

    @patch("subprocess.run")
    def test_start_cmd_includes_model(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(model="gemini-2.5-pro", session_id="test-model")
        cmd = provider.get_start_cmd()

        assert "--model" in cmd
        assert "gemini-2.5-pro" in cmd

    @patch("subprocess.run")
    def test_is_idle_detects_sparkle_prompt(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-idle")
        assert provider.is_idle("output\n✦") is True
        assert provider.is_idle("loading...") is False
        assert provider.is_idle("✦ loading something") is False

    @patch("subprocess.run")
    def test_marker_is_empty(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-marker")
        assert provider.get_marker() == ""

    @patch("subprocess.run")
    def test_submit_keys_is_enter(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-keys")
        assert provider.get_submit_keys() == ["Enter"]

    @patch("subprocess.run")
    def test_close_kills_session(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = GeminiProvider(session_id="test-close")
        provider.close()

        kill_calls = [c for c in mock_run.call_args_list if "kill-session" in str(c)]
        assert len(kill_calls) > 0

    @patch("subprocess.run")
    def test_gemini_response_without_marker_uses_fallback(self, mock_run):
        """Gemini has empty marker, so response parsing uses the fallback path."""
        # Screen with no ● marker - just raw text after the prompt
        response_screen = "✦\nPlain text response from Gemini."
        mock_run.side_effect = make_subprocess_mock(self.IDLE, response_screen)

        provider = GeminiProvider(session_id="test-fallback")
        response = provider.ask("Hello")

        # Should still extract content
        assert len(response) > 0


# ---------------------------------------------------------------------------
# Codex Provider E2E
# ---------------------------------------------------------------------------

class TestCodexE2E:
    IDLE = "❯"
    RESPONSE = "❯\n● Codex has generated the following code.\ndef hello(): pass"

    @patch("subprocess.run")
    def test_ask_returns_parsed_response(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-codex")
        response = provider.ask("Write a hello function")

        assert "Codex has generated the following code" in response
        assert "def hello(): pass" in response

    @patch("subprocess.run")
    def test_start_cmd_is_codex_chat(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-cmd")
        cmd = provider.get_start_cmd()

        assert cmd[0] == "codex"
        assert cmd[1] == "chat"

    @patch("subprocess.run")
    def test_start_cmd_includes_model(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(model="o3", session_id="test-model")
        cmd = provider.get_start_cmd()

        assert "--model" in cmd
        assert "o3" in cmd

    @patch("subprocess.run")
    def test_is_idle_detects_prompt(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-idle")
        assert provider.is_idle("output\n❯") is True
        assert provider.is_idle("thinking...") is False
        assert provider.is_idle("❯ thinking") is False

    @patch("subprocess.run")
    def test_marker_is_bullet(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-marker")
        assert provider.get_marker() == "● "

    @patch("subprocess.run")
    def test_submit_keys_is_enter(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-keys")
        assert provider.get_submit_keys() == ["Enter"]

    @patch("subprocess.run")
    def test_close_kills_session(self, mock_run):
        mock_run.side_effect = make_subprocess_mock(self.IDLE, self.RESPONSE)

        provider = CodexProvider(session_id="test-close")
        provider.close()

        kill_calls = [c for c in mock_run.call_args_list if "kill-session" in str(c)]
        assert len(kill_calls) > 0

    def test_trust_dialog_detected_by_tui_controller(self):
        """Codex 'Do you trust' dialog is handled by TUIController rule-based logic."""
        from oauth_cli_coder.base import TUIController

        trust_screen = "Do you trust the files in this folder?\n1) Yes\n2) No"
        keys = TUIController.assess_state(trust_screen, "codex")
        assert keys == ["1", "Enter"]

    def test_yes_no_prompt_detected_by_tui_controller(self):
        """Generic y/N prompts are handled by TUIController."""
        from oauth_cli_coder.base import TUIController

        yn_screen = "Do you want to continue? [y/N]"
        keys = TUIController.assess_state(yn_screen, "codex")
        assert keys == ["y", "Enter"]


# ---------------------------------------------------------------------------
# Cross-provider: session naming & reuse
# ---------------------------------------------------------------------------

class TestSessionManagement:
    @patch("subprocess.run")
    def test_session_name_includes_provider_and_id(self, mock_run):
        idle = "❯"
        mock_run.side_effect = make_subprocess_mock(idle, idle)

        claude = ClaudeProvider(session_id="abc123")
        assert "claude" in claude.session_name
        assert "abc123" in claude.session_name

    @patch("subprocess.run")
    def test_session_name_unique_without_id(self, mock_run):
        idle = "❯"
        mock_run.side_effect = make_subprocess_mock(idle, idle)

        p1 = ClaudeProvider()
        mock_run.side_effect = make_subprocess_mock(idle, idle)
        p2 = ClaudeProvider()

        assert p1.session_name != p2.session_name

    @patch("subprocess.run")
    def test_existing_session_reused(self, mock_run):
        """If has-session returns 0 on init, no new-session should be created."""
        calls = []

        def side_effect(cmd, *args, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            calls.append(cmd_str)
            if "has-session" in cmd_str:
                return MagicMock(returncode=0)  # session already exists
            if "capture-pane" in cmd_str:
                return MagicMock(stdout="❯")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        provider = ClaudeProvider(session_id="existing")
        new_session_calls = [c for c in calls if "new-session" in c]
        assert len(new_session_calls) == 0


# ---------------------------------------------------------------------------
# CLI entrypoint E2E (click commands)
# ---------------------------------------------------------------------------

class TestCLIEntrypoint:
    @patch("subprocess.run")
    def test_cli_ask_command(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        mock_run.side_effect = make_subprocess_mock("❯", "❯\n● CLI response here.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "claude", "What is 2+2?",
            "--session-id", "cli-test",
            "--close"
        ])

        assert result.exit_code == 0
        assert "CLI response here" in result.output

    @patch("subprocess.run")
    def test_cli_ask_gemini(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        mock_run.side_effect = make_subprocess_mock("✦", "✦\nGemini CLI answer.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "gemini", "Hello",
            "--session-id", "cli-gemini",
            "--close"
        ])

        assert result.exit_code == 0

    @patch("subprocess.run")
    def test_cli_ask_codex(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        mock_run.side_effect = make_subprocess_mock("❯", "❯\n● Codex CLI answer.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "ask", "codex", "Hello",
            "--session-id", "cli-codex",
            "--close"
        ])

        assert result.exit_code == 0
        assert "Codex CLI answer" in result.output

    @patch("subprocess.run")
    def test_cli_slash_command(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        mock_run.side_effect = make_subprocess_mock("❯", "❯\n● Cleared.")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "slash", "claude", "/clear",
            "--session-id", "cli-slash",
            "--close"
        ])

        assert result.exit_code == 0

    @patch("subprocess.run")
    def test_cli_stop_command(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        mock_run.side_effect = make_subprocess_mock("❯", "❯")

        runner = CliRunner()
        result = runner.invoke(cli, [
            "stop", "claude",
            "--session-id", "cli-stop"
        ])

        assert result.exit_code == 0
        assert "closed" in result.output.lower()

    @patch("subprocess.run")
    def test_cli_unknown_provider_fails(self, mock_run):
        from click.testing import CliRunner
        from oauth_cli_coder.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "unknown", "Hello"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Response parsing edge cases
# ---------------------------------------------------------------------------

class TestResponseParsing:
    @patch("subprocess.run")
    def test_multiline_response_preserved(self, mock_run):
        response = "❯\n● Line one.\nLine two.\nLine three."
        mock_run.side_effect = make_subprocess_mock("❯", response)

        provider = ClaudeProvider(session_id="test-multiline")
        result = provider.ask("multi")

        assert "Line one." in result
        assert "Line two." in result
        assert "Line three." in result

    @patch("subprocess.run")
    def test_response_stops_at_ui_boundary(self, mock_run):
        response = "❯\n● Real content.\n───\nUI footer"
        mock_run.side_effect = make_subprocess_mock("❯", response)

        provider = ClaudeProvider(session_id="test-boundary")
        result = provider.ask("test")

        assert "Real content." in result
        assert "UI footer" not in result

    @patch("subprocess.run")
    def test_response_stops_at_next_prompt(self, mock_run):
        response = "❯\n● Answer here.\n > next prompt"
        mock_run.side_effect = make_subprocess_mock("❯", response)

        provider = ClaudeProvider(session_id="test-prompt-stop")
        result = provider.ask("test")

        assert "Answer here." in result
        assert "next prompt" not in result

    @patch("subprocess.run")
    def test_empty_response_uses_fallback(self, mock_run):
        """When no marker is found, fallback extracts non-UI lines."""
        # Include ✦ so Gemini's is_idle returns True, but no ● marker
        response = "✦\nSome output without bullet markers."
        mock_run.side_effect = make_subprocess_mock("✦", response)

        provider = GeminiProvider(session_id="test-empty")
        result = provider.ask("test")

        assert len(result) > 0

    @patch("subprocess.run")
    def test_ansi_codes_stripped(self, mock_run):
        response = "❯\n● \x1B[32mColored text\x1B[0m here."
        mock_run.side_effect = make_subprocess_mock("❯", response)

        provider = ClaudeProvider(session_id="test-ansi")
        result = provider.ask("test")

        assert "\x1B" not in result
        assert "Colored text" in result
