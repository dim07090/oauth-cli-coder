from __future__ import annotations

from typing import List, Optional

from oauth_cli_coder.base import TmuxProvider


class CodexProvider(TmuxProvider):
    """
    Codex CLI provider — interactions via tmux.
    """
    def __init__(self, model: Optional[str] = None, cwd: Optional[str] = None, session_id: Optional[str] = None):
        super().__init__("codex", model, cwd=cwd, session_id=session_id)

    def get_start_cmd(self) -> List[str]:
        # 'codex chat' starts the interactive TUI
        cmd = ["codex", "chat"]
        if self.model:
            cmd.extend(["--model", self.model])
        return cmd

    def is_idle(self, screen_text: str) -> bool:
        # Codex prompt character
        has_prompt = "❯" in screen_text
        is_busy = "thinking" in screen_text.lower()
        return has_prompt and not is_busy

    def get_submit_keys(self) -> List[str]:
        return ["Enter"]

    def get_marker(self) -> str:
        return "● "
