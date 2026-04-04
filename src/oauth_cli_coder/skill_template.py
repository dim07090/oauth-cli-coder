"""Agent Skill template and install path mapping for oauth-coder."""

from pathlib import Path
from typing import Optional

SKILL_MD_CONTENT = """\
---
name: oauth-coder
description: "Interact with AI CLI coders (Claude Code, Gemini CLI, Codex) via persistent tmux sessions. Use when you need to delegate work to another AI assistant, chain multiple AI agents together, or maintain long-running conversations with CLI-based AI tools."
---

# oauth-coder

Drive **Claude Code**, **Gemini CLI**, and **Codex** programmatically through persistent tmux sessions.
No API keys required -- uses the user's existing OAuth tokens.

## Available Providers

- `claude` -- Claude Code
- `gemini` -- Gemini CLI
- `codex` -- Codex CLI

## Commands

### Start a session / send a prompt

```bash
oauth-coder ask <provider> "<prompt>" --session-id <id>
```

Options:
- `--model <model>` -- Model name (e.g. `opus`, `sonnet`)
- `--cwd <dir>` -- Working directory for the session
- `--session-id <id>` -- Name the session for reuse across calls
- `--option <flag>` / `-o <flag>` -- Extra startup flags passed to the CLI tool (repeatable)
- `--close` -- Close the session after getting the response

Example:
```bash
oauth-coder ask claude "explain this codebase" --session-id my-project --model sonnet
```

### Send follow-ups to an existing session

Use the same `--session-id` to continue a conversation:
```bash
oauth-coder ask claude "now suggest improvements" --session-id my-project
```

The session remembers provider, model, and startup options -- you only need `--session-id` on follow-ups.

### Read current output

Read the screen without sending anything:
```bash
oauth-coder read <provider> --session-id <id>
```

### Run slash commands

```bash
oauth-coder slash <provider> <command> --session-id <id>
```

Examples:
```bash
oauth-coder slash claude /compact --session-id my-project
oauth-coder slash claude /clear --session-id my-project
```

### List active sessions

```bash
oauth-coder list
```

Shows all running sessions with provider, model, and creation time.

### Stop sessions

Stop a specific session:
```bash
oauth-coder stop <provider> --session-id <id>
```

Stop all sessions:
```bash
oauth-coder stop-all
```

## Multi-Agent Pipeline Pattern

Chain outputs between providers to build powerful multi-agent workflows:

```bash
# Generate with one provider, review with another
DRAFT=$(oauth-coder ask claude "implement feature X" --session-id writer --model opus)
REVIEW=$(oauth-coder ask gemini "$DRAFT -- review this implementation" --session-id reviewer)
FINAL=$(oauth-coder ask claude "apply this feedback: $REVIEW" --session-id writer)
```

Each session is independent and persistent, so you can orchestrate complex multi-turn,
multi-provider pipelines.

## Tips

- Sessions persist across calls. Use `oauth-coder list` to see what is running.
- Use `--close` on the final call if you do not need the session anymore.
- Pass startup options with `-o`: `oauth-coder ask claude "help" -o "--allowedTools" -o "Bash,Read"`
- Read the screen with `oauth-coder read` to check on long-running responses.
"""


# Install paths per platform (relative to project or home root)
PLATFORM_PATHS = {
    "claude-code": Path(".claude/skills/oauth-coder/SKILL.md"),
    "openclaw": Path(".agents/skills/oauth-coder/SKILL.md"),
    "codex": Path(".agents/skills/oauth-coder/SKILL.md"),
    "gemini": Path(".gemini/skills/oauth-coder/SKILL.md"),
}

# All supported platform names
PLATFORM_NAMES = list(PLATFORM_PATHS.keys())


def get_skill_content() -> str:
    """Return the SKILL.md content."""
    return SKILL_MD_CONTENT


def get_install_path(platform: str, global_install: bool = False) -> Path:
    """Return the full install path for a platform.

    Args:
        platform: One of 'claude-code', 'openclaw', 'codex', 'gemini'.
        global_install: If True, install to the user's home directory.
                        Otherwise, install relative to the current directory.

    Returns:
        Absolute path where SKILL.md should be written.

    Raises:
        ValueError: If the platform is not recognized.
    """
    relative = PLATFORM_PATHS.get(platform)
    if relative is None:
        raise ValueError(
            f"Unknown platform: {platform!r}. "
            f"Choose from: {', '.join(PLATFORM_NAMES)}"
        )

    if global_install:
        return Path.home() / relative
    else:
        return Path.cwd() / relative
