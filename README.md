# oauth-cli-coder

Seamlessly interact with AI CLI coders (**Claude Code**, **Gemini CLI**, **Codex**) via tmux TUI sessions.

## The Problem
Many AI-powered CLI tools (like Anthropic's `claude` or Google's `gemini` CLI) are designed for interactive terminal use (TUI). When an agent harness like **OpenClaw** or **Claude Code** needs to drive these tools, they often run into issues with:
- **Authentication**: CLI tools use their own OAuth/browser flows. Running them via simple API calls doesn't leverage existing local credentials.
- **TUI States**: Startup warnings, trust dialogs, and upgrade prompts can block simple non-interactive pipes.
- **Session Context**: Maintaining a long-lived conversation requires a stable environment.

## The Solution
`oauth-cli-coder` wraps these CLI tools in a **tmux** session. 
- It starts the real CLI (e.g. `claude`) in a background tmux pane.
- It types into the pane as if a human was using it.
- It parses the terminal output to extract the AI's response.
- **No `-c` required**: It doesn't use simple command-line execution (`claude -c "..."`), but interacts with the full TUI environment, preserving the native user experience and OAuth context.

## Installation
```bash
pip install oauth-cli-coder
```
**Requires:** `tmux` must be installed on your system.

## Usage

### Claude Code
```python
from oauth_cli_coder import ClaudeProvider

# Starts a tmux session and launches 'claude'
coder = ClaudeProvider(model="claude-3-5-sonnet-20241022")

# Send a prompt and get the response
response = coder.ask("What is the current git status?")
print(response)

# Send a slash command
coder.slash_command("/compact")

# Cleanup
coder.close()
```

### Gemini CLI
```python
from oauth_cli_coder import GeminiProvider

coder = GeminiProvider()
print(coder.ask("Hello!"))
coder.close()
```

## Command Line Interface (CLI)
`oauth-cli-coder` provides a CLI tool `oauth-coder` for easy interaction from shell scripts or agent harnesses without writing Python code.

### Ask a question
```bash
oauth-coder ask claude "how's it going?" --model claude-3-5-sonnet-20241022
```

### Run a slash command
```bash
oauth-coder slash claude /compact
```

### Persistent Sessions
You can reuse a session across multiple CLI calls by specifying a `--session-id`:
```bash
oauth-coder ask claude "Analyze this repo" --session-id my-project
oauth-coder slash claude /compact --session-id my-project
```

### Close a session
```bash
oauth-coder stop claude --session-id my-project
```

### Advanced: TUI State Assessment
The library uses rule-based logic to get past common prompts (e.g., trust dialogs). If you have the `gemini` CLI installed, it can optionally use an LLM to assess complex TUI states and decide which keys to send to reach the main prompt.

## Why 'OAuth'?
By running the actual CLI binary in a real terminal (tmux), the tool can access your existing OAuth tokens, browser sessions, and local configuration. This means you don't need to manage separate API keys for your automation—if you are logged in on your terminal, the library can use it.

## License
MIT
