#!/usr/bin/env python3
"""
Creative Chain: Multi-Agent AI Pipeline
========================================

Spins up four persistent AI sessions and chains their outputs together
in a creative feedback loop:

  Gemini (Idea Agent)  -->  Claude Opus (Author)  -->  Claude Sonnet (Critic)  -->  Codex (Gap Finder)
        ^                                                                              |
        |______________________________________________________________________________|

Each agent has a role. One's output becomes the next's input.
Sessions stay alive so you can re-run the chain or interact individually.

Usage:
    python examples/creative_chain.py "Write a short story about time travel"
    python examples/creative_chain.py --rounds 3 "Design a CLI framework"
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from oauth_cli_coder import ClaudeProvider, GeminiProvider, CodexProvider


def create_agents() -> dict:
    """Start four persistent agent sessions with distinct roles."""
    print("[1/4] Starting Gemini Idea Agent...")
    idea_agent = GeminiProvider(
        session_id="chain-idea",
        startup_options=["--sandbox"],
    )

    print("[2/4] Starting Claude Opus Author...")
    author = ClaudeProvider(
        model="opus",
        session_id="chain-author",
        startup_options=["--system-prompt", "You are a skilled author. When given an idea or outline, expand it into polished, vivid prose. Be creative and concise. Output only the written piece, no meta-commentary."],
    )

    print("[3/4] Starting Claude Sonnet Critic...")
    critic = ClaudeProvider(
        model="sonnet",
        session_id="chain-critic",
        startup_options=["--system-prompt", "You are a sharp literary critic. Review the piece you receive. Point out strengths, weaknesses, and give 3 specific actionable improvements. Be constructive but honest. Keep it under 200 words."],
    )

    print("[4/4] Starting Codex Gap Finder...")
    gap_finder = CodexProvider(
        session_id="chain-gaps",
    )

    return {
        "idea": idea_agent,
        "author": author,
        "critic": critic,
        "gaps": gap_finder,
    }


def run_chain(agents: dict, topic: str, round_num: int = 1) -> dict:
    """
    Run one pass through the chain:
      idea -> author -> critic -> gap_finder
    Returns all intermediate outputs.
    """
    separator = "=" * 60

    # --- Step 1: Gemini generates the idea / outline ---
    print(f"\n{separator}")
    print(f"  ROUND {round_num} | STEP 1: Gemini Idea Agent")
    print(separator)

    idea_prompt = (
        f"Generate a creative, detailed idea and outline for the following topic. "
        f"Include key themes, structure, and unique angles. Keep it under 300 words.\n\n"
        f"Topic: {topic}"
    )
    idea = agents["idea"].ask(idea_prompt)
    print(textwrap.indent(idea[:500], "  "))
    if len(idea) > 500:
        print(f"  ... ({len(idea)} chars total)")

    # --- Step 2: Claude Opus writes the piece ---
    print(f"\n{separator}")
    print(f"  ROUND {round_num} | STEP 2: Claude Opus Author")
    print(separator)

    author_prompt = (
        f"Using the following idea and outline, write a polished piece. "
        f"Keep it under 500 words.\n\n"
        f"IDEA:\n{idea}"
    )
    draft = agents["author"].ask(author_prompt)
    print(textwrap.indent(draft[:500], "  "))
    if len(draft) > 500:
        print(f"  ... ({len(draft)} chars total)")

    # --- Step 3: Claude Sonnet critiques ---
    print(f"\n{separator}")
    print(f"  ROUND {round_num} | STEP 3: Claude Sonnet Critic")
    print(separator)

    critic_prompt = (
        f"Review this piece. Give strengths, weaknesses, and 3 actionable improvements.\n\n"
        f"PIECE:\n{draft}"
    )
    critique = agents["critic"].ask(critic_prompt)
    print(textwrap.indent(critique[:500], "  "))
    if len(critique) > 500:
        print(f"  ... ({len(critique)} chars total)")

    # --- Step 4: Codex finds gaps ---
    print(f"\n{separator}")
    print(f"  ROUND {round_num} | STEP 4: Codex Gap Finder")
    print(separator)

    gaps_prompt = (
        f"Analyze this piece and the critique. Identify gaps, missing perspectives, "
        f"or unexplored angles that would strengthen the next iteration. "
        f"Suggest a refined direction in under 200 words.\n\n"
        f"PIECE:\n{draft}\n\n"
        f"CRITIQUE:\n{critique}"
    )
    gaps = agents["gaps"].ask(gaps_prompt)
    print(textwrap.indent(gaps[:500], "  "))
    if len(gaps) > 500:
        print(f"  ... ({len(gaps)} chars total)")

    return {
        "idea": idea,
        "draft": draft,
        "critique": critique,
        "gaps": gaps,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Creative Chain: multi-agent AI pipeline demo"
    )
    parser.add_argument("topic", help="The creative topic or task to explore")
    parser.add_argument(
        "--rounds", type=int, default=1,
        help="Number of refinement rounds (each round feeds gaps back as the new topic)"
    )
    parser.add_argument(
        "--keep-alive", action="store_true", default=True,
        help="Keep sessions alive after completion (default: true)"
    )
    parser.add_argument(
        "--close", action="store_true",
        help="Close all sessions when done"
    )
    args = parser.parse_args()

    print("Creative Chain: Multi-Agent AI Pipeline")
    print("=" * 60)
    print(f"Topic: {args.topic}")
    print(f"Rounds: {args.rounds}")
    print()

    agents = create_agents()

    try:
        topic = args.topic
        for round_num in range(1, args.rounds + 1):
            results = run_chain(agents, topic, round_num)

            if round_num < args.rounds:
                # Feed the gaps analysis back as the refined topic
                topic = (
                    f"Refine and improve this piece based on feedback.\n\n"
                    f"ORIGINAL TOPIC: {args.topic}\n\n"
                    f"CURRENT DRAFT:\n{results['draft']}\n\n"
                    f"FEEDBACK:\n{results['critique']}\n\n"
                    f"GAPS TO ADDRESS:\n{results['gaps']}"
                )
                print(f"\n{'~' * 60}")
                print(f"  Feeding gaps back into the chain for round {round_num + 1}...")
                print(f"{'~' * 60}")

        # Final summary
        print(f"\n{'=' * 60}")
        print("  CHAIN COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Rounds completed: {args.rounds}")
        print(f"  Sessions still active: {', '.join(a.session_name for a in agents.values())}")
        print()
        print("  Reuse these sessions:")
        print(f'    oauth-coder ask claude "follow up" --session-id chain-author')
        print(f'    oauth-coder ask gemini "new idea" --session-id chain-idea')
        print()

    finally:
        if args.close:
            print("Closing all sessions...")
            for agent in agents.values():
                agent.close()
            print("Done.")
        else:
            print("Sessions kept alive. Use 'oauth-coder stop <provider> --session-id chain-*' to close.")


if __name__ == "__main__":
    main()
