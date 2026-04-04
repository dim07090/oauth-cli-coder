# oauth-cli-coder

> Drive **Claude Code**, **Gemini CLI**, and **Codex** programmatically — through the same tmux session they already run in.

No API keys. No custom auth. If you're logged in on your terminal, `oauth-cli-coder` can use it.

```
              ┌──────────────┐
  your code   │  tmux pane   │   AI CLI
  ─────────>  │  (headless)  │  <──── claude / gemini / codex
              └──────────────┘
                  captures
                scrollback &
              extracts response
```

---

## Why?

AI CLI tools like `claude`, `gemini`, and `codex` are built for humans sitting at a terminal. They handle OAuth in the browser, show TUI prompts, and maintain rich session state. That's great — until you need to drive them from code.

**oauth-cli-coder** bridges the gap:

- Launches the real CLI binary in a background **tmux** session
- Types into it and reads back the full scrollback buffer — like a human would
- Automatically navigates past startup dialogs, trust prompts, and upgrade nags
- Keeps sessions alive across calls so you can build multi-turn conversations
- Works with your **existing OAuth tokens** — no API keys to manage

## Quick Start

```bash
pip install oauth-cli-coder
```

> **Requires:** `tmux` installed on your system (`apt install tmux` / `brew install tmux`)

### From the command line

```bash
# Ask a question
oauth-coder ask claude "explain this repo"

# Use a specific model
oauth-coder ask claude "review my code" --model opus

# Persistent session — keeps context across calls
oauth-coder ask claude "analyze this repo" --session-id my-project
oauth-coder ask claude "now suggest improvements" --session-id my-project

# Slash commands
oauth-coder slash claude /compact --session-id my-project

# Read the current screen without sending anything
oauth-coder read claude --session-id my-project

# Manage sessions
oauth-coder list
oauth-coder stop claude --session-id my-project
oauth-coder stop-all
```

### From Python

```python
from oauth_cli_coder import ClaudeProvider

coder = ClaudeProvider(model="sonnet", session_id="my-project")

response = coder.ask("What does this codebase do?")
print(response)

# Full scrollback — long responses aren't truncated
screen = coder.read_screen()

coder.slash_command("/compact")
coder.close()
```

### All providers

```python
from oauth_cli_coder import ClaudeProvider, GeminiProvider, CodexProvider

claude = ClaudeProvider(model="opus")
gemini = GeminiProvider()
codex  = CodexProvider()
```

## Features

### Persistent Sessions

Sessions stay alive between CLI calls. Use `--session-id` to name them and reconnect later — the session registry remembers the provider, model, and startup options so you don't have to repeat them.

```bash
# First call starts the session
oauth-coder ask claude "start analyzing" --session-id review --model opus

# Subsequent calls reconnect — no need to pass --model again
oauth-coder ask claude "what did you find?" --session-id review
```

### Multiple Concurrent Sessions

Run as many sessions as you want, across any mix of providers:

```bash
oauth-coder ask claude "write the code" --session-id writer
oauth-coder ask claude "review the code" --session-id reviewer --model opus
oauth-coder ask gemini "brainstorm ideas" --session-id ideas

# See everything that's running
oauth-coder list
```

### Startup Options

Pass extra flags through to the underlying CLI tool:

```bash
oauth-coder ask claude "help me" \
  -o "--system-prompt" -o "You are a concise code reviewer" \
  -o "--allowedTools" -o "Bash,Read"
```

```python
ClaudeProvider(
    model="sonnet",
    startup_options=["--system-prompt", "You are a concise code reviewer"],
)
```

### Full Scrollback Capture

Responses are captured from the complete tmux scrollback buffer, not just the visible terminal. Long outputs come back in full.

### Stealth Mode (PTY Isolation)

AI CLI tools can detect they're running inside tmux — via environment variables, the process tree, or PTY inspection — and may change behavior. **Stealth mode** (on by default) wraps the child process so it can't tell it's inside tmux:

- Scrubs `TMUX`, `TMUX_PANE`, and related env vars
- Sets `TERM=xterm-256color`
- Allocates a fresh PTY via `script` so the TTY path doesn't contain "tmux"
- Uses `setsid` for process-group isolation
- Falls back gracefully when `script` or `setsid` are unavailable
- Handles Linux vs macOS `script` flag differences

```bash
# Stealth is on by default — disable it if you don't need it
oauth-coder ask claude "hello" --no-stealth
```

```python
# Opt out from Python
ClaudeProvider(stealth=False)
```

### TUI Auto-Navigation

The library automatically handles startup friction:
- Trust dialogs ("Do you trust this project?")
- Yes/No prompts
- Version upgrade notices

For complex cases, it can optionally call `gemini` CLI as an LLM to assess the TUI state and figure out which keys to press.

## Multi-Agent Pipelines

The real power is chaining agents together. Each session is independent, so one agent's output can feed into the next.

```
  Gemini        Claude Opus      Claude Sonnet       Codex
  (Ideation) -> (Writing)     -> (Critique)       -> (Gap Analysis)
       ^                                                  |
       └──────────────────────────────────────────────────┘
```

```bash
# Start four agents with different roles
IDEA=$(oauth-coder ask gemini "outline a story about AI" --session-id idea-agent)
DRAFT=$(oauth-coder ask claude "$IDEA — expand into prose" --session-id author --model opus)
REVIEW=$(oauth-coder ask claude "$DRAFT — critique this" --session-id critic --model sonnet)
GAPS=$(oauth-coder ask codex "$DRAFT + $REVIEW — find gaps" --session-id gap-finder)

# Feed gaps back for another round
oauth-coder ask gemini "refine based on: $GAPS" --session-id idea-agent
```

See [`examples/`](examples/) for complete working demos including:
- **`creative_chain.py`** — Python API version with multi-round refinement
- **`creative_chain.sh`** — Pure shell version

## Agent Skills for Local Harnesses

If you're running `oauth-cli-coder` inside another agent harness (Claude Code, Gemini CLI, Codex, OpenClaw), you can install a **SKILL.md** file so the host agent automatically understands how to use `oauth-coder`.

### Installing a skill

```bash
# Install for a specific platform (into the current project directory)
oauth-coder skill install claude-code
oauth-coder skill install gemini
oauth-coder skill install codex
oauth-coder skill install openclaw

# Install for all supported platforms at once
oauth-coder skill install all

# Install globally (to your home directory instead of the project)
oauth-coder skill install claude-code --global
oauth-coder skill install all --global
```

Supported platforms and where the skill file is written:

| Platform | Local path (project) | Global path (home) |
|----------|---------------------|--------------------|
| `claude-code` | `.claude/skills/oauth-coder/SKILL.md` | `~/.claude/skills/oauth-coder/SKILL.md` |
| `gemini` | `.gemini/skills/oauth-coder/SKILL.md` | `~/.gemini/skills/oauth-coder/SKILL.md` |
| `codex` | `.agents/skills/oauth-coder/SKILL.md` | `~/.agents/skills/oauth-coder/SKILL.md` |
| `openclaw` | `.agents/skills/oauth-coder/SKILL.md` | `~/.agents/skills/oauth-coder/SKILL.md` |

### Previewing the skill content

```bash
oauth-coder skill show
```

This prints the full SKILL.md to stdout without writing any files — useful for review or piping to another tool.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `oauth-coder ask <provider> <prompt>` | Send a prompt and get the response |
| `oauth-coder slash <provider> <command>` | Run a slash command (`/compact`, `/clear`, etc.) |
| `oauth-coder read <provider>` | Read current screen output without sending anything |
| `oauth-coder list` | List all active sessions |
| `oauth-coder stop <provider>` | Close a specific session |
| `oauth-coder stop-all` | Close all sessions |
| `oauth-coder skill install <platform>` | Install the Agent Skill for a harness platform |
| `oauth-coder skill show` | Print the SKILL.md content to stdout |

**Common options:** `--model`, `--cwd`, `--session-id`, `--option`/`-o`, `--close`, `--stealth`/`--no-stealth`

## How It Works

1. `oauth-coder` starts a detached **tmux** session with a large virtual terminal (300x100)
2. **Stealth mode** wraps the CLI command to scrub tmux env vars, allocate a fresh PTY, and isolate the process group — so the child process can't detect it's inside tmux
3. It launches the CLI tool (`claude`, `gemini`, `codex`) inside that session
4. The **TUI controller** watches the screen and automatically navigates past startup prompts
5. When you call `ask()`, it pastes your prompt into the pane via tmux buffers (safe for large inputs)
6. It polls the screen until the CLI returns to an idle prompt
7. It captures the **full scrollback** and parses out the last response block
8. The session stays alive for the next call

## Why "OAuth"?

By running the actual CLI binary in a real terminal, the tool inherits your existing OAuth tokens, browser sessions, and local config. You authenticate once in your browser — `oauth-cli-coder` rides on top of that. No API keys, no token management, no separate credentials.

## Contributing

Contributions welcome! This project uses:
- **Python 3.12+** with **uv** for packaging
- **pytest** for tests
- **click** for the CLI

```bash
git clone https://github.com/codeninja/oauth-cli-coder.git
cd oauth-cli-coder
uv sync
uv run pytest
```

## License

MIT
