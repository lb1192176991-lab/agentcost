"""Tests for structural parser detection in agentcost.cli (#86)."""

import json

import pytest

from agentcost.cli import (
    _parse_all_logs,
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


class TestEdgeCases:
    def test_empty_file_falls_back_to_path(self, tmp_path):
        """An empty file has no detectable format and must not raise."""
        path = tmp_path / "codex-empty.jsonl"
        path.write_text("")
        assert _detect_agent_from_content(path) is None
        assert _resolve_parser_type(path) == "codex"
        assert _parse_file(path) == []

    def test_unrecognised_json_entries_fall_back_to_path(self, tmp_path):
        """Valid JSON without usage keys is not a known format."""
        path = tmp_path / "cursor-weird.jsonl"
        path.write_text(json.dumps({"foo": "bar"}) + "\n")
        assert _resolve_parser_type(path) == "cursor"

    def test_blank_lines_before_first_entry_are_skipped(self, tmp_path):
        """Leading blank lines must not defeat detection."""
        path = tmp_path / "claude-blanks.jsonl"
        path.write_text("\n\n   \n" + CLAUDE_LINE + "\n")
        assert _detect_agent_from_content(path) == "claude"

    def test_scan_is_bounded_and_does_not_raise_on_bad_json(self, tmp_path):
        """More than 10 unclassifiable lines stops the peek safely."""
        path = tmp_path / "codex-noise.jsonl"
        path.write_text("".join(json.dumps({"foo": i}) + "\n" for i in range(50)))
        assert _detect_agent_from_content(path) is None
        assert _resolve_parser_type(path) == "codex"


class TestCursorTopLevelUsage:
    """CursorParser accepts top-level usage (``entry.get("message", entry)``).

    A cursor log using that shape must stay on the Cursor parser: the
    structural classifier cannot distinguish it from Codex, and Cursor's
    parser handles both shapes, so the path hint must win here.
    """

    CURSOR_TOPLEVEL_LINE = json.dumps({
        "timestamp": "2026-10-03T12:00:00Z",
        "model": "gpt-4o",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    })

    def test_cursor_top_level_usage_keeps_cursor_parser(self, tmp_path):
        path = tmp_path / "cursor-session.jsonl"
        path.write_text(self.CURSOR_TOPLEVEL_LINE + "\n")
        usages = _parse_file(path)
        assert usages
        assert all(u.agent_id == "cursor-agent" for u in usages)

    def test_cursor_top_level_usage_emits_no_warning(self, tmp_path, capsys):
        path = tmp_path / "cursor-session.jsonl"
        path.write_text(self.CURSOR_TOPLEVEL_LINE + "\n")
        _parse_file(path)
        assert "Warning" not in capsys.readouterr().err


class TestExplicitAgentOnAutoDiscovery:
    """``--agent`` must filter the auto-discovery branch too, not only --path."""

    @pytest.fixture
    def fake_discovery(self, monkeypatch, tmp_path):
        """Make LogDiscovery return one Claude and one Codex log."""
        claude = tmp_path / "discovered" / "claude-session.jsonl"
        claude.parent.mkdir()
        claude.write_text(CLAUDE_LINE + "\n")
        codex = tmp_path / "discovered" / "codex-session.jsonl"
        codex.write_text(CODEX_LINE + "\n")

        class FakeDiscovery:
            def discover(self):
                return {"claude": [claude], "codex": [codex], "opencode": [],
                        "hermes": [], "cursor": []}

        class FakeSQLite:
            def parse(self):
                return []

        monkeypatch.setattr("agentcost.cli.LogDiscovery", FakeDiscovery)
        monkeypatch.setattr("agentcost.cli.HermesSQLiteParser", FakeSQLite)
        return claude, codex

    def test_agent_filters_auto_discovery(self, fake_discovery):
        usages = _parse_all_logs(agent="codex")
        assert {u.agent_id for u in usages} == {"codex-cli"}

    def test_agent_filters_auto_discovery_to_claude(self, fake_discovery):
        usages = _parse_all_logs(agent="claude")
        assert {u.agent_id for u in usages} == {"claude-code"}

    def test_no_agent_keeps_all_discovered(self, fake_discovery):
        usages = _parse_all_logs()
        assert {u.agent_id for u in usages} == {"claude-code", "codex-cli"}

    def test_agent_excludes_sqlite_branch(self, fake_discovery, monkeypatch):
        """A non-hermes --agent must not pull in the Hermes SQLite rows."""
        from agentcost.cost import TokenUsage

        class LoudSQLite:
            def parse(self):
                return [TokenUsage(model="m", input_tokens=1, output_tokens=1,
                                   agent_id="hermes-agent")]

        monkeypatch.setattr("agentcost.cli.HermesSQLiteParser", LoudSQLite)
        usages = _parse_all_logs(agent="codex")
        assert {u.agent_id for u in usages} == {"codex-cli"}
        assert {u.agent_id for u in _parse_all_logs(agent="hermes")} == {"hermes-agent"}
