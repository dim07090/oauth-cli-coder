from __future__ import annotations

from typing import List, Optional

from oauth_cli_coder.base import TmuxProvider


class GeminiProvider(TmuxProvider):
    """
    Gemini CLI provider — interactions via tmux.
    """
    def __init__(self, model: Optional[str] = None, cwd: Optional[str] = None, session_id: Optional[str] = None):
        super().__init__("gemini", model, cwd=cwd, session_id=session_id)

    def get_start_cmd(self) -> List[str]:
        # Starting with a long prompt to ensure it stays in interactive mode
        # or just 'gemini chat' if available.
        # Assuming 'gemini' CLI has a chat mode or similar.
        # Original rokugu code used 'gemini' directly.
        cmd = ["gemini"]
        if self.model:
            cmd.extend(["--model", self.model])
        return cmd

    def is_idle(self, screen_text: str) -> bool:
        # Gemini prompt character
        has_prompt = "✦" in screen_text
        is_busy = "loading" in screen_text.lower()
        return has_prompt and not is_busy

    def get_submit_keys(self) -> List[str]:
        return ["Enter"]

    def get_marker(self) -> str:
        return ""
