"""Stealth PTY wrapper for hiding tmux from programs running inside sessions.

Uses ``env``, ``setsid``, and ``script`` to create a clean pseudo-terminal
that is not directly tied to tmux, so child processes cannot detect they
are running inside a tmux session.
"""

from __future__ import annotations

import platform
import shutil
from typing import List, Optional


def _setsid_supports_wait() -> bool:
    """Return True if ``setsid --wait`` is supported on this system."""
    if not shutil.which("setsid"):
        return False
    import subprocess
    try:
        p = subprocess.run(
            ["setsid", "--help"],
            capture_output=True, text=True, timeout=5,
        )
        return "--wait" in (p.stdout + p.stderr)
    except Exception:
        return False


def _detect_script_flags() -> Optional[List[str]]:
    """Return the correct ``script`` flags for the current platform.

    Returns ``None`` if ``script`` is not found on ``$PATH``.

    Linux (util-linux):  ``script -q /dev/null``
    macOS (BSD):         ``script -q /dev/null``

    On Linux the command to run must follow the ``-c`` flag, while on
    macOS/BSD the command is given as a positional argument after the
    filename.
    """
    if not shutil.which("script"):
        return None

    system = platform.system()
    if system == "Darwin":
        # BSD script: script -q /dev/null <command ...>
        return ["script", "-q", "/dev/null"]
    else:
        # Linux (util-linux): script -q /dev/null -c <command>
        return ["script", "-q", "/dev/null", "-c"]


# Environment variables that leak tmux presence.
_TMUX_ENV_VARS = [
    "TMUX",
    "TMUX_PANE",
    "TMUX_PLUGIN_MANAGER_PATH",
]


def build_stealth_command(cmd_args: List[str]) -> List[str]:
    """Wrap *cmd_args* so the resulting process cannot detect tmux.

    The wrapper applies three layers of isolation:

    1. ``env -u …`` strips tmux-related environment variables and forces
       ``TERM=xterm-256color``.
    2. ``script -q /dev/null`` allocates a fresh PTY that is independent
       of the tmux PTY.
    3. ``setsid`` (inside the ``script`` PTY) starts a new session so the
       inner process group is no longer tied to tmux.  It is placed
       *inside* ``script -c`` so that ``script`` itself remains the
       foreground process for the tmux pane.

    If ``script`` or ``setsid`` are not available the wrapper degrades
    gracefully -- environment scrubbing is always applied.

    Parameters
    ----------
    cmd_args:
        The command and its arguments, e.g. ``["claude"]``.

    Returns
    -------
    list[str]
        A command list suitable for passing as trailing arguments to
        ``tmux new-session``.
    """
    inner_cmd = " ".join(_shell_quote(a) for a in cmd_args)

    # --- build the wrapper from inside-out ---
    #
    # Important: ``setsid`` must be placed *inside* ``script -c`` rather
    # than before ``script``.  If ``setsid`` wraps ``script``, it creates
    # a new session leader that detaches from tmux's controlling terminal,
    # causing tmux to consider the pane's foreground process dead and tear
    # down the session immediately.  By placing ``setsid`` inside
    # ``script -c``, only the inner command gets a new process group while
    # ``script`` itself remains the pane's foreground process.
    script_flags = _detect_script_flags()

    # Optionally prefix the inner command with setsid.
    # We must use ``setsid --wait`` so that the setsid process stays
    # alive until the child exits; plain ``setsid`` detaches and causes
    # the parent (script / tmux pane) to consider its child gone.
    if _setsid_supports_wait():
        inner_cmd = "setsid --wait " + inner_cmd

    if script_flags is not None:
        system = platform.system()
        if system == "Darwin":
            # BSD: script -q /dev/null bash -c <inner>
            wrapped = " ".join(script_flags) + " bash -c " + _shell_quote(inner_cmd)
        else:
            # Linux: script -q /dev/null -c <inner>
            wrapped = " ".join(script_flags) + " " + _shell_quote(inner_cmd)
    else:
        # No script available -- just run the command directly.
        wrapped = inner_cmd

    # Build env prefix to scrub tmux vars and set TERM.
    env_parts = ["env"]
    for var in _TMUX_ENV_VARS:
        env_parts.append(f"-u {var}")
    env_parts.append("TERM=xterm-256color")
    env_prefix = " ".join(env_parts)

    full_cmd = f"{env_prefix} {wrapped}"
    return ["bash", "-c", full_cmd]


def _shell_quote(s: str) -> str:
    """Return a shell-safe single-quoted version of *s*."""
    if not s:
        return "''"
    # If safe, return as-is.
    safe_chars = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "_-./=:@,"
    )
    if all(c in safe_chars for c in s):
        return s
    # Single-quote, escaping embedded single quotes.
    return "'" + s.replace("'", "'\"'\"'") + "'"
