"""Tests for the skill install and show CLI commands."""

import os
from pathlib import Path

from click.testing import CliRunner

from oauth_cli_coder.cli import cli
from oauth_cli_coder.skill_template import get_skill_content, PLATFORM_PATHS


runner = CliRunner()


def test_skill_show_outputs_content():
    result = runner.invoke(cli, ["skill", "show"])
    assert result.exit_code == 0
    content = get_skill_content()
    # The output should contain the full skill content
    assert "name: oauth-coder" in result.output
    assert "oauth-coder ask" in result.output


def test_skill_install_claude_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["skill", "install", "claude-code"])
    assert result.exit_code == 0
    expected = tmp_path / ".claude" / "skills" / "oauth-coder" / "SKILL.md"
    assert expected.exists()
    assert expected.read_text() == get_skill_content()
    assert "Installed:" in result.output


def test_skill_install_openclaw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["skill", "install", "openclaw"])
    assert result.exit_code == 0
    expected = tmp_path / ".agents" / "skills" / "oauth-coder" / "SKILL.md"
    assert expected.exists()
    assert expected.read_text() == get_skill_content()


def test_skill_install_codex(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["skill", "install", "codex"])
    assert result.exit_code == 0
    expected = tmp_path / ".agents" / "skills" / "oauth-coder" / "SKILL.md"
    assert expected.exists()


def test_skill_install_gemini(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["skill", "install", "gemini"])
    assert result.exit_code == 0
    expected = tmp_path / ".gemini" / "skills" / "oauth-coder" / "SKILL.md"
    assert expected.exists()
    assert expected.read_text() == get_skill_content()


def test_skill_install_all(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["skill", "install", "all"])
    assert result.exit_code == 0

    # Claude Code path
    assert (tmp_path / ".claude" / "skills" / "oauth-coder" / "SKILL.md").exists()
    # Shared agents path (openclaw + codex)
    assert (tmp_path / ".agents" / "skills" / "oauth-coder" / "SKILL.md").exists()
    # Gemini path
    assert (tmp_path / ".gemini" / "skills" / "oauth-coder" / "SKILL.md").exists()

    # openclaw and codex share a path -- output should mention dedup
    assert "same as above" in result.output


def test_skill_install_global(tmp_path, monkeypatch):
    # Point HOME to tmp_path so --global writes there
    monkeypatch.setenv("HOME", str(tmp_path))
    # Also patch Path.home() directly for robustness
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    result = runner.invoke(cli, ["skill", "install", "claude-code", "--global"])
    assert result.exit_code == 0
    expected = tmp_path / ".claude" / "skills" / "oauth-coder" / "SKILL.md"
    assert expected.exists()
    assert expected.read_text() == get_skill_content()


def test_skill_install_global_all(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    result = runner.invoke(cli, ["skill", "install", "all", "--global"])
    assert result.exit_code == 0

    assert (tmp_path / ".claude" / "skills" / "oauth-coder" / "SKILL.md").exists()
    assert (tmp_path / ".agents" / "skills" / "oauth-coder" / "SKILL.md").exists()
    assert (tmp_path / ".gemini" / "skills" / "oauth-coder" / "SKILL.md").exists()


def test_skill_install_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skill_path = tmp_path / ".claude" / "skills" / "oauth-coder" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("old content")

    result = runner.invoke(cli, ["skill", "install", "claude-code"])
    assert result.exit_code == 0
    assert skill_path.read_text() == get_skill_content()


def test_skill_install_invalid_platform():
    result = runner.invoke(cli, ["skill", "install", "bogus"])
    assert result.exit_code != 0


def test_skill_content_has_frontmatter():
    content = get_skill_content()
    assert content.startswith("---\n")
    assert "name: oauth-coder" in content
    assert 'description: "Interact with AI CLI coders' in content
