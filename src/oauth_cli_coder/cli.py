import click
from typing import Optional
from oauth_cli_coder.base import SessionRegistry
from oauth_cli_coder.providers.claude import ClaudeProvider
from oauth_cli_coder.providers.gemini import GeminiProvider
from oauth_cli_coder.providers.codex import CodexProvider

PROVIDERS = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "codex": CodexProvider,
}

@click.group()
def cli():
    """Seamlessly interact with CLI coders via tmux."""
    pass

def get_provider(provider_name: str, model: Optional[str], cwd: Optional[str], session_id: Optional[str]):
    provider_cls = PROVIDERS.get(provider_name.lower())
    if provider_cls is None:
        raise click.BadParameter(f"Unknown provider: {provider_name}")
    return provider_cls(model=model, cwd=cwd, session_id=session_id)

@cli.command()
@click.argument("provider")
@click.argument("prompt")
@click.option("--model", help="Model name to use.")
@click.option("--cwd", help="Working directory.")
@click.option("--session-id", help="Session ID to reuse.")
@click.option("--keep-alive", is_flag=True, default=True, help="Keep the session alive after the command (default).")
@click.option("--close", is_flag=True, help="Close the session after getting the response.")
def ask(provider, prompt, model, cwd, session_id, keep_alive, close):
    """Send a prompt to the provider and get the response."""
    p = get_provider(provider, model, cwd, session_id)
    try:
        response = p.ask(prompt)
        click.echo(response)
    finally:
        if close:
            p.close()

@cli.command()
@click.argument("provider")
@click.argument("command")
@click.option("--model", help="Model name to use.")
@click.option("--cwd", help="Working directory.")
@click.option("--session-id", help="Session ID to reuse.")
@click.option("--close", is_flag=True, help="Close the session after the command.")
def slash(provider, command, model, cwd, session_id, close):
    """Run a slash command (e.g. /clear, /compact)."""
    p = get_provider(provider, model, cwd, session_id)
    try:
        response = p.slash_command(command)
        click.echo(response)
    finally:
        if close:
            p.close()

@cli.command()
@click.argument("provider")
@click.option("--session-id", help="Session ID to identify the session.")
def stop(provider, session_id):
    """Close an existing session."""
    p = get_provider(provider, None, None, session_id)
    p.close()
    click.echo(f"Session {p.session_name} closed.")

@cli.command(name="list")
@click.option("--prune", is_flag=True, help="Remove stale entries whose tmux sessions no longer exist.")
def list_sessions(prune):
    """List active sessions from the registry."""
    if prune:
        pruned = SessionRegistry.prune()
        if pruned:
            click.echo(f"Pruned {len(pruned)} stale session(s): {', '.join(pruned)}")

    sessions = SessionRegistry.list_all()
    if not sessions:
        click.echo("No active sessions.")
        return

    # Header
    click.echo(f"{'SESSION NAME':<50} {'PROVIDER':<10} {'MODEL':<20} {'CREATED AT'}")
    click.echo("-" * 110)
    for name, entry in sessions.items():
        provider = entry.get("provider", "?")
        model = entry.get("model") or "-"
        created = entry.get("created_at", "?")
        click.echo(f"{name:<50} {provider:<10} {model:<20} {created}")

if __name__ == "__main__":
    cli()
