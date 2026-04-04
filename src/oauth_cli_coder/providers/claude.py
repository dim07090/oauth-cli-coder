from __future__ import annotations

from typing import List, Optional

from oauth_cli_coder.base import TmuxProvider


class ClaudeProvider(TmuxProvider):
    """
    Claude Code (claude) provider — interactions via tmux.
    """
    def __init__(self, model: Optional[str] = None, cwd: Optional[str] = None, session_id: Optional[str] = None, startup_options: Optional[List[str]] = None):
        super().__init__("claude", model, cwd=cwd, session_id=session_id, startup_options=startup_options)

    def get_start_cmd(self) -> List[str]:
        # --permission-mode bypassPermissions is crucial for automation
        cmd = ["claude", "--permission-mode", "bypassPermissions"]
        if self.model:
            cmd.extend(["--model", self.model])
        return cmd

    def is_idle(self, screen_text: str) -> bool:
        has_prompt = "❯" in screen_text
        is_busy = any(c in screen_text for c in ["⠋", "Running", "Thinking"])
        return has_prompt and not is_busy

    def get_submit_keys(self) -> List[str]:
        return ["Enter"]

    def get_marker(self) -> str:
        # Claude Code responses often start with this marker character
        return "● "
