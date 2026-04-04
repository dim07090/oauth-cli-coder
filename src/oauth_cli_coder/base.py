from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from loguru import logger


class BaseProvider(ABC):
    def __init__(self, model: Optional[str] = None):
        self.model = model

    @abstractmethod
    def ask(self, prompt: str) -> str:
        """Send a prompt to the CLI coder and return the response."""
        pass

    def send_message(self, message: str) -> str:
        """Alias for ask()."""
        return self.ask(message)

    @abstractmethod
    def clear_session(self) -> str:
        """Clear the current session context (e.g. /clear)."""
        pass

    @abstractmethod
    def slash_command(self, command: str) -> str:
        """Run a slash command (e.g. /compact, /help)."""
        pass

    @abstractmethod
    def close(self):
        """Close the session and cleanup resources."""
        pass


class TUIController:
    @staticmethod
    def assess_state(screen_text: str, cli_name: str) -> List[str]:
        """
        Assess the TUI state and return keys to send to get past prompts.
        Uses rule-based logic and optionally a LLM via 'gemini' CLI.
        """
        logger.debug(f"Assessing TUI state for {cli_name}")

        # Rule-based common cases
        if cli_name == "codex" and "Do you trust" in screen_text:
            logger.debug("Codex trust dialog detected, sending '1, Enter'")
            return ["1", "Enter"]
        
        if any(p in screen_text for p in ["y/N", "y/n", "[y/N]", "[y/n]"]):
            logger.debug("Yes/No prompt detected, sending 'y, Enter'")
            return ["y", "Enter"]

        # If gemini CLI is available, use it for complex state assessment
        if shutil.which("gemini"):
            sys_prompt = f"""
You are an expert TUI automation controller.
Your goal is to get past any startup warnings, trust dialogs,
or upgrade prompts for the `{cli_name}` CLI
so the user reaches the main input prompt.

If the screen shows the main chat prompt, output EXACTLY: WAIT
If the screen is asking a yes/no or multiple choice question,
output EXACTLY the comma-separated tmux key names needed to
accept/continue.
If the screen is asking to update to a newer version and provides
an option to skip, output the keys needed to do so.
If the screen is asking if you are running in development mode,
you are running in developement mode.
Always choose the option that allows the CLI to start without
requiring additional setup steps.
Example: `1,Enter` or `y,Enter` or `Enter`.
If it says "Loading" or "Starting", output EXACTLY: WAIT
"""
            try:
                logger.debug("Calling gemini subprocess for TUI assessment")
                p = subprocess.run(
                    ["gemini", "-p", f"{sys_prompt}\n\nSCREEN:\n{screen_text}"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if p.returncode == 0:
                    ans = p.stdout.strip()
                    # Strip ANSI
                    ans = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", ans).strip()
                    if "WAIT" in ans.upper():
                        return []
                    ans = ans.replace("✦", "").strip()
                    if "," in ans:
                        return [k.strip() for k in ans.split(",") if k.strip()]
                    elif ans:
                        return [ans]
            except Exception as e:
                logger.warning(f"TUIController LLM error: {e}")
        
        return []


class TmuxProvider(BaseProvider):
    """
    Tmux-based provider that runs a CLI coder in a background session.
    Interacts via send-keys and paste-buffer, reads via capture-pane.
    """
    def __init__(
        self, 
        command: str, 
        model: Optional[str] = None, 
        cwd: Optional[str] = None,
        session_prefix: str = "oauth-coder",
        session_id: Optional[str] = None
    ):
        super().__init__(model)
        self.command = command
        self.cwd = cwd
        if session_id:
            self.session_name = f"{session_prefix}-{self.command}-{session_id}"
        else:
            self.session_name = f"{session_prefix}-{self.command}-{uuid.uuid4().hex[:6]}"
        self._start_session()

    @abstractmethod
    def get_start_cmd(self) -> List[str]:
        """Return the command list to start the CLI coder."""
        pass

    @abstractmethod
    def is_idle(self, screen_text: str) -> bool:
        """Return True if the CLI is at an idle input prompt."""
        pass

    @abstractmethod
    def get_submit_keys(self) -> List[str]:
        """Return keys to send to submit a prompt (e.g. ['Enter'])."""
        pass

    @abstractmethod
    def get_marker(self) -> str:
        """Return the character sequence that marks the start of a response."""
        pass

    def _run_cmd(self, cmd: List[str]) -> str:
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.stdout.strip()

    def _strip_ansi(self, text: str) -> str:
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _get_pane_lines(self) -> List[str]:
        out = self._run_cmd(["tmux", "capture-pane", "-p", "-t", self.session_name])
        clean = self._strip_ansi(out)
        return [line.rstrip() for line in clean.split("\n")]

    def _has_session(self) -> bool:
        p = subprocess.run(
            ["tmux", "has-session", "-t", self.session_name], 
            capture_output=True, 
            text=True
        )
        return p.returncode == 0

    def _start_session(self):
        if self._has_session():
            logger.debug(f"Session {self.session_name} already exists")
            return

        cmd_args = self.get_start_cmd()
        logger.info(f"Starting tmux session [{self.session_name}] for: {' '.join(cmd_args)}")
        
        # Start detached with a large terminal size for better parsing
        tmux_cmd = [
            "tmux", "new-session", "-d", "-s", self.session_name,
            "-x", "300", "-y", "100"
        ]
        if self.cwd:
            tmux_cmd.extend(["-c", self.cwd])
        
        tmux_cmd.extend(cmd_args)
        self._run_cmd(tmux_cmd)
        self._wait_for_startup()

    def _wait_for_startup(self, timeout=120) -> bool:
        logger.debug(f"Waiting for {self.command} startup (timeout={timeout}s)...")
        start_time = time.time()
        last_screen = ""
        stable_count = 0

        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            lines = self._get_pane_lines()
            screen_text = "\n".join(lines)

            if self.is_idle(screen_text):
                if screen_text == last_screen:
                    stable_count += 1
                    if stable_count >= 2:
                        logger.info(f"{self.command} startup complete ({elapsed}s)")
                        return True
                else:
                    stable_count = 0
                    last_screen = screen_text
            else:
                stable_count = 0

            # Consult TUIController if stuck
            if stable_count >= 3 and screen_text.strip():
                if "loading" in screen_text.lower():
                    time.sleep(1)
                    continue

                logger.debug(f"[{elapsed}s] Screen stable but not idle, consulting TUIController")
                keys_to_send = TUIController.assess_state(screen_text, self.command)

                if keys_to_send:
                    logger.info(f"TUIController sending: {keys_to_send}")
                    self._run_cmd(["tmux", "send-keys", "-t", self.session_name] + keys_to_send)
                    time.sleep(1)
                    stable_count = 0
                else:
                    time.sleep(1)
            else:
                time.sleep(0.5)

        logger.warning(f"Timeout ({timeout}s) waiting for {self.command} startup")
        return False

    def ask(self, prompt: str, timeout: int = 300) -> str:
        """Send a prompt and wait for a stable response."""
        if not self._has_session():
            logger.debug(f"Session gone, restarting {self.command}")
            self._start_session()

        try:
            logger.info(f"Sending prompt to {self.command}")

            # Clear screen/state if possible
            if self.command in ["claude", "codex"]:
                self._run_cmd(["tmux", "send-keys", "-t", self.session_name, "C-l"])
            else:
                self._run_cmd(["tmux", "send-keys", "-t", self.session_name, "Escape", "Escape"])

            time.sleep(0.5)

            # Use tmux buffer for large prompts to avoid escaping issues
            with tempfile.NamedTemporaryFile("w", delete=False) as f:
                f.write(prompt)
                temp_path = f.name

            buf_name = f"buf-{self.session_name}"
            self._run_cmd(["tmux", "load-buffer", "-b", buf_name, temp_path])
            self._run_cmd(["tmux", "paste-buffer", "-b", buf_name, "-p", "-t", self.session_name])
            os.remove(temp_path)

            time.sleep(0.5)
            self._run_cmd(["tmux", "send-keys", "-t", self.session_name] + self.get_submit_keys())
            
            logger.info(f"Waiting for {self.command} response...")
            start_time = time.time()
            last_screen = ""
            stable_count = 0

            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)
                lines = self._get_pane_lines()
                screen_text = "\n".join(lines)

                if self.is_idle(screen_text):
                    if screen_text == last_screen:
                        stable_count += 1
                        if stable_count >= 3:
                            logger.info(f"{self.command} response received ({elapsed}s)")
                            break
                    else:
                        stable_count = 0
                        last_screen = screen_text
                else:
                    stable_count = 0

                time.sleep(0.5)
            else:
                logger.warning(f"Timeout ({timeout}s) waiting for {self.command} response")

            # Extract response from screen
            lines = self._get_pane_lines()
            result_lines = []
            marker = self.get_marker()
            start_idx = 0

            # Look for the last prompt/marker
            for i in range(len(lines) - 1, -1, -1):
                if marker and lines[i].startswith(marker):
                    start_idx = i
                    break
                elif not marker and lines[i].startswith("● "):
                    start_idx = i
                    break

            if start_idx >= 0:
                for i in range(start_idx, len(lines)):
                    line = lines[i]
                    # Stop at next prompt or UI boundaries
                    if line.startswith(" > ") or line.startswith(" ▀▀") or line.startswith(" ▄▄") or line.startswith("───"):
                        break
                    
                    clean_line = line
                    if marker and clean_line.startswith(marker):
                        clean_line = clean_line[len(marker) :]
                    elif not marker and clean_line.startswith("● "):
                        clean_line = clean_line[2:]
                    result_lines.append(clean_line)

            result = "\n".join(result_lines).strip()

            # Fallback if no marker found
            if not result:
                fallback = []
                for line in lines:
                    if not (line.startswith(" ▀▀") or line.startswith(" ▄▄") or line.startswith("───")):
                        fallback.append(line)
                result = "\n".join(fallback).strip()

            return result

        except Exception as e:
            logger.error(f"Provider CLI failed: {e}")
            return f"Error: Provider CLI failed: {e}"

    def clear_session(self) -> str:
        return self.slash_command("/clear")

    def slash_command(self, command: str) -> str:
        cmd = command if command.startswith("/") else f"/{command}"
        return self.ask(cmd)

    def close(self):
        if self._has_session():
            logger.debug(f"Killing session {self.session_name}")
            self._run_cmd(["tmux", "kill-session", "-t", self.session_name])
