import pytest
from unittest.mock import MagicMock, patch, DEFAULT
from oauth_cli_coder import ClaudeProvider

@patch("subprocess.run")
def test_claude_provider_init(mock_run):
    # Mock tmux calls
    def side_effect(cmd, *args, **kwargs):
        if "has-session" in cmd:
            return MagicMock(returncode=1)
        if "capture-pane" in cmd:
            return MagicMock(stdout="❯")
        return MagicMock(returncode=0, stdout="")
        
    mock_run.side_effect = side_effect
    
    provider = ClaudeProvider()
    assert provider.command == "claude"
    assert "oauth-coder-claude-" in provider.session_name
    
@patch("subprocess.run")
def test_claude_provider_ask(mock_run):
    # Setup state for the mock
    state = {"count": 0}
    
    def side_effect(cmd, *args, **kwargs):
        if "has-session" in cmd:
            return MagicMock(returncode=0)
        if "capture-pane" in cmd:
            state["count"] += 1
            if state["count"] > 5:
                return MagicMock(stdout="❯\n● Response text")
            return MagicMock(stdout="❯")
        return MagicMock(returncode=0, stdout="")

    mock_run.side_effect = side_effect
    
    provider = ClaudeProvider()
    response = provider.ask("Hello")
    assert "Response text" in response
