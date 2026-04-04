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

def get_provider(provider_name: str, model: Optional[str], cwd: Optional[str], session_id: Optional[str], startup_options: Optional[tuple] = None):
    provider_cls = PROVIDERS.get(provider_name.lower())
    opts = list(startup_options) if startup_options else []
    if provider_cls is None:
        raise click.BadParameter(f"Unknown provider: {provider_name}")
    return provider_cls(model=model, cwd=cwd, session_id=session_id, startup_options=opts)

@cli.command()
@click.argument("provider")
@click.argument("prompt")
@click.option("--model", help="Model name to use.")
@click.option("--cwd", help="Working directory.")
@click.option("--session-id", help="Session ID to reuse.")
@click.option("--keep-alive", is_flag=True, default=True, help="Keep the session alive after the command (default).")
@click.option("--close", is_flag=True, help="Close the session after getting the response.")
@click.option("--option", "-o", multiple=True, help="Extra startup option passed to the CLI tool (repeatable).")
def ask(provider, prompt, model, cwd, session_id, keep_alive, close, option):
    """Send a prompt to the provider and get the response."""
    p = get_provider(provider, model, cwd, session_id, startup_options=option)
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
@click.option("--option", "-o", multiple=True, help="Extra startup option passed to the CLI tool (repeatable).")
def slash(provider, command, model, cwd, session_id, close, option):
    """Run a slash command (e.g. /clear, /compact)."""
    p = get_provider(provider, model, cwd, session_id, startup_options=option)
    try:
        response = p.slash_command(command)
        click.echo(response)
    finally:
        if close:
            p.close()

@cli.command(name="read")
@click.argument("provider")
@click.option("--session-id", help="Session ID to identify the session.")
def read_screen(provider, session_id):
    """Read the current screen output without sending anything."""
    p = get_provider(provider, None, None, session_id)
    click.echo(p.read_screen())

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

@cli.command(name="stop-all")
@click.confirmation_option(prompt="Close all active sessions?")
def stop_all():
    """Close all active sessions."""
    sessions = SessionRegistry.list_all()
    if not sessions:
        click.echo("No active sessions.")
        return

    import subprocess
    closed = 0
    for name in list(sessions.keys()):
        subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True, text=True)
        SessionRegistry.unregister(name)
        click.echo(f"  Closed {name}")
        closed += 1
    click.echo(f"{closed} session(s) closed.")

if __name__ == "__main__":
    cli()
