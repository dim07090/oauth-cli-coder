# Examples

## Creative Chain: Multi-Agent AI Pipeline

Chain four AI agents together, where each one's output feeds into the next:

```
Gemini (Idea Agent) --> Claude Opus (Author) --> Claude Sonnet (Critic) --> Codex (Gap Finder)
       ^                                                                          |
       |__________________________________________________________________________|
```

| Agent | Role | Provider |
|-------|------|----------|
| Idea Agent | Generates creative outlines and unique angles | Gemini |
| Author | Writes polished prose from the outline | Claude Opus |
| Critic | Reviews the draft with actionable feedback | Claude Sonnet |
| Gap Finder | Identifies missing perspectives and suggests refinements | Codex |

With multiple rounds, the gap analysis feeds back into the chain for iterative refinement. All sessions stay alive between rounds, so each agent retains its full conversation history.

### Python API version

```bash
# Single round
python examples/creative_chain.py "Write a short story about time travel"

# Three refinement rounds
python examples/creative_chain.py --rounds 3 "Design a CLI framework"

# Close sessions when done
python examples/creative_chain.py --close "Explain quantum computing"
```

### Shell CLI version

```bash
# Single round
./examples/creative_chain.sh "Write a short story about time travel"

# Three refinement rounds
./examples/creative_chain.sh "Design a CLI framework" 3
```

### After the chain completes

Sessions stay alive so you can follow up with any agent:

```bash
# Continue the conversation with the author
oauth-coder ask claude "revise the ending to be more hopeful" --session-id chain-author

# Ask the critic to re-evaluate
oauth-coder ask claude "how does the revised version compare?" --session-id chain-critic

# Get a fresh idea
oauth-coder ask gemini "give me a completely different angle" --session-id chain-idea

# Clean up
oauth-coder stop claude --session-id chain-author
oauth-coder stop claude --session-id chain-critic
oauth-coder stop gemini --session-id chain-idea
oauth-coder stop codex --session-id chain-gaps
```

### Startup Options

Both versions pass startup options to customize agent behavior. For example, the author and critic get system prompts that define their roles:

```bash
# Via CLI
oauth-coder ask claude "write something" \
  -o "--system-prompt" -o "You are a poet who writes in haiku"

# Via Python
ClaudeProvider(
    model="opus",
    session_id="my-poet",
    startup_options=["--system-prompt", "You are a poet who writes in haiku"],
)
```
