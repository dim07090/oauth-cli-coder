#!/usr/bin/env bash
#
# Creative Chain: Multi-Agent AI Pipeline (Shell version)
# ========================================================
#
# Demonstrates chaining four persistent AI sessions using the CLI.
# Each agent's output feeds into the next.
#
# Usage:
#   chmod +x examples/creative_chain.sh
#   ./examples/creative_chain.sh "Write a short story about time travel"

set -euo pipefail

TOPIC="${1:?Usage: $0 <topic>}"
ROUNDS="${2:-1}"

divider() { printf '\n%60s\n' | tr ' ' '='; }
label()   { printf '  %s\n' "$1"; }

echo "Creative Chain: Multi-Agent AI Pipeline"
divider
label "Topic: $TOPIC"
label "Rounds: $ROUNDS"

# --- Start all sessions (first call starts them, subsequent calls reuse) ---

run_chain() {
    local round=$1
    local topic="$2"

    divider
    label "ROUND $round | STEP 1: Gemini Idea Agent"
    divider
    IDEA=$(oauth-coder ask gemini \
        "Generate a creative, detailed idea and outline for: $topic. Include key themes, structure, unique angles. Under 300 words." \
        --session-id chain-idea)
    echo "$IDEA" | head -20

    divider
    label "ROUND $round | STEP 2: Claude Opus Author"
    divider
    DRAFT=$(oauth-coder ask claude \
        "Using this idea, write a polished piece under 500 words. IDEA: $IDEA" \
        --model opus \
        --session-id chain-author \
        -o "--system-prompt" -o "You are a skilled author. Expand ideas into polished prose. Output only the piece.")
    echo "$DRAFT" | head -20

    divider
    label "ROUND $round | STEP 3: Claude Sonnet Critic"
    divider
    CRITIQUE=$(oauth-coder ask claude \
        "Review this piece. Strengths, weaknesses, 3 actionable improvements. Under 200 words. PIECE: $DRAFT" \
        --model sonnet \
        --session-id chain-critic \
        -o "--system-prompt" -o "You are a sharp literary critic. Be constructive but honest.")
    echo "$CRITIQUE" | head -20

    divider
    label "ROUND $round | STEP 4: Codex Gap Finder"
    divider
    GAPS=$(oauth-coder ask codex \
        "Analyze this piece and critique. Identify gaps, missing perspectives, unexplored angles. Suggest refined direction in under 200 words. PIECE: $DRAFT CRITIQUE: $CRITIQUE" \
        --session-id chain-gaps)
    echo "$GAPS" | head -20
}

topic="$TOPIC"
for round in $(seq 1 "$ROUNDS"); do
    run_chain "$round" "$topic"

    if [ "$round" -lt "$ROUNDS" ]; then
        echo ""
        echo "  ~~~ Feeding gaps back for round $((round + 1)) ~~~"
        topic="Refine based on feedback. ORIGINAL: $TOPIC DRAFT: $DRAFT FEEDBACK: $CRITIQUE GAPS: $GAPS"
    fi
done

divider
label "CHAIN COMPLETE ($ROUNDS rounds)"
divider
echo ""
echo "  Sessions are still alive. Interact directly:"
echo "    oauth-coder ask claude 'revise the ending' --session-id chain-author"
echo "    oauth-coder ask gemini 'another angle?' --session-id chain-idea"
echo ""
echo "  Close all:"
echo "    oauth-coder stop claude --session-id chain-author"
echo "    oauth-coder stop claude --session-id chain-critic"
echo "    oauth-coder stop gemini --session-id chain-idea"
echo "    oauth-coder stop codex --session-id chain-gaps"
