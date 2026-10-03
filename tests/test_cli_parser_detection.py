"""Tests for structural parser detection in agentcost.cli (#86)."""

import json

from agentcost.cli import (
    _parse_file,
    _resolve_parser_type,
    _classify_entry,
    _detect_agent_from_content,
)

CODEX_LINE = json.dumps({
    "model": "gpt-4o",
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "timestamp": "2026-10-03T12:00:00Z",
})

CLAUDE_LINE = json.dumps({
    "timestamp": "2026-10-03T12:00:00Z",
    "sessionId": "sess-1",
    "message": {
        "id": "msg-1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    },
})


class TestStructuralDetection:
    def test_codex_format_in_claude_path(self, tmp_path):
        """A file named *claude* but holding Codex content parses as Codex."""
        path = tmp_path / "claude-session.jsonl"
        path.write_text(CODEX_LINE + "\n")
        usages = _parse_file(path)
        assert usages
        assert all(u.agent_id == "codex-cli" for u in usages)

    def test_claude_format_in_codex_path(self, tmp_path):
        """A file named *codex* but holding Claude content parses as Claude."""
        path = tmp_path / "codex-session.jsonl"
        path.write_text(CLAUDE_LINE + "\n")
        usages = _parse_file(path)
        assert usages
        assert all(u.agent_id == "claude-code" for u in usages)

    def test_cursor_path_keeps_cursor_parser(self, tmp_path):
        """Same-family content (message-wrapped usage) keeps the path hint."""
        path = tmp_path / "cursor-session.jsonl"
        path.write_text(CLAUDE_LINE + "\n")
        usages = _parse_file(path)
        assert usages
        assert all(u.agent_id == "cursor-agent" for u in usages)

    def test_undetectable_content_falls_back_to_path(self, tmp_path):
        """Non-JSON content falls back to the path-based heuristic."""
        path = tmp_path / "claude-notes.txt"
        path.write_text("this is not json at all\n")
        assert _resolve_parser_type(path) == "claude"


class TestAgentOverride:
    def test_explicit_agent_overrides_detection(self, tmp_path):
        """An explicit --agent flag wins over both structure and path."""
        path = tmp_path / "codex-session.jsonl"
        path.write_text(CLAUDE_LINE + "\n")  # claude content in codex path
        assert _resolve_parser_type(path) == "claude"  # structure wins by default
        assert _resolve_parser_type(path, explicit_agent="hermes") == "hermes"


class TestWarningOnDisagreement:
    def test_warning_printed_when_structure_overrides_path(self, tmp_path, capsys):
        path = tmp_path / "claude-session.jsonl"
        path.write_text(CODEX_LINE + "\n")
        _parse_file(path)
        err = capsys.readouterr().err
        assert "Warning" in err
        assert "codex" in err

    def test_no_warning_when_families_agree(self, tmp_path, capsys):
        path = tmp_path / "cursor-session.jsonl"
        path.write_text(CLAUDE_LINE + "\n")
        _parse_file(path)
        err = capsys.readouterr().err
        assert "Warning" not in err


class TestClassifyEntry:
    def test_claude_entry(self):
        assert _classify_entry(json.loads(CLAUDE_LINE)) == "claude"

    def test_codex_entry(self):
        assert _classify_entry(json.loads(CODEX_LINE)) == "codex"

    def test_hermes_entry(self):
        entry = {"type": "message", "role": "assistant", "content": "hi",
                 "tokens": {"input_tokens": 1, "output_tokens": 1}}
        assert _classify_entry(entry) == "hermes"

    def test_unknown_entry(self):
        assert _classify_entry({"foo": "bar"}) is None
        assert _classify_entry("not a dict") is None
