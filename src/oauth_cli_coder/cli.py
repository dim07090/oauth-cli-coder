import click
from typing import Optional
from oauth_cli_coder.providers.claude import ClaudeProvider
from oauth_cli_coder.providers.gemini import GeminiProvider
from oauth_cli_coder.providers.codex import CodexProvider

@click.group()
def cli():
    """Seamlessly interact with CLI coders via tmux."""
    pass

def get_provider(provider_name: str, model: Optional[str], cwd: Optional[str], session_id: Optional[str], startup_options: Optional[tuple] = None):
    opts = list(startup_options) if startup_options else []
    if provider_name.lower() == "claude":
        return ClaudeProvider(model=model, cwd=cwd, session_id=session_id, startup_options=opts)
    elif provider_name.lower() == "gemini":
        return GeminiProvider(model=model, cwd=cwd, session_id=session_id, startup_options=opts)
    elif provider_name.lower() == "codex":
        return CodexProvider(model=model, cwd=cwd, session_id=session_id, startup_options=opts)
    else:
        raise click.BadParameter(f"Unknown provider: {provider_name}")

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

@cli.command()
@click.argument("provider")
@click.option("--session-id", help="Session ID to identify the session.")
def stop(provider, session_id):
    """Close an existing session."""
    p = get_provider(provider, None, None, session_id)
    p.close()
    click.echo(f"Session {p.session_name} closed.")

if __name__ == "__main__":
    cli()
