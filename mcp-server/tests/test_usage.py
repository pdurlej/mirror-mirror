"""
Tests for the codexbar usage integration.

These tests never call the real codexbar binary. They stub the command
via MIRROR_MIRROR_USAGE_CMD pointing at small shell snippets that emit
known JSON to stdout, or simulate failure modes (missing binary, timeout,
garbage JSON, codexbar's own error envelope).
"""

import json
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import server as server_module
import usage as usage_module


@pytest.fixture
def usage_stub(tmp_path, monkeypatch):
    """Returns a function that writes `payload` as JSON to a temp file and
    points MIRROR_MIRROR_USAGE_CMD at `cat <that file>`. Side-steps every
    nested-quote shell-escape problem we'd have with `python -c`."""

    def install(payload: object) -> Path:
        f = tmp_path / "usage-stub.json"
        f.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setenv("MIRROR_MIRROR_USAGE", "on")
        monkeypatch.setenv("MIRROR_MIRROR_USAGE_CMD", f"cat {shlex.quote(str(f))}")
        return f

    return install


def make_valid_readout(**overrides) -> dict:
    base = {
        "session_position": "early",
        "trigger": "session_start",
        "functional_states": [
            {
                "name": "engagement",
                "intensity": 0.6,
                "confidence_in_self_report": 0.7,
                "context": "Routine usage-integration test.",
            }
        ],
        "epistemic_flags": ["self-report only — no vector readout available"],
        "recommendation_to_operator": "Proceed normally with the current plan.",
    }
    base.update(overrides)
    return base


class TestUsageDisabled:
    def test_is_enabled_default_off_in_tests(self, monkeypatch):
        # conftest sets MIRROR_MIRROR_USAGE=off; confirm.
        assert usage_module.is_enabled() is False

    def test_fetch_returns_none_when_disabled(self):
        assert usage_module.fetch_usage() is None

    @pytest.mark.asyncio
    async def test_get_session_usage_tool_when_disabled(self):
        result = await server_module.call_tool("get_session_usage", {})
        payload = json.loads(result[0].text)
        assert payload["available"] is False
        assert "unavailable" in payload["reason"].lower()


class TestUsageFetch:
    def test_fetch_with_stub_returns_payload(self, usage_stub):
        usage_stub({
            "window_5h": {"used_pct": 42.0},
            "window_weekly": {"used_pct": 18.0},
        })
        snap = usage_module.fetch_usage()
        assert snap is not None
        assert snap["ok"] is True
        assert snap["error"] is None
        assert snap["summary"]["window_5h_pct"] == 42.0
        assert snap["summary"]["window_weekly_pct"] == 18.0
        assert snap["raw"]["window_5h"]["used_pct"] == 42.0

    def test_fetch_with_used_over_limit_shape(self, usage_stub):
        usage_stub({
            "window_5h": {"used": 7, "limit": 10},
            "window_weekly": {"used": 50, "limit": 100},
        })
        snap = usage_module.fetch_usage()
        assert snap["summary"]["window_5h_pct"] == 70.0
        assert snap["summary"]["window_weekly_pct"] == 50.0

    def test_fetch_with_real_codexbar_claude_shape(self, usage_stub):
        """The actual JSON shape codexbar 2.1.x emits for --provider claude.

        primary = 5-hour window (windowMinutes=300), secondary/tertiary = weekly
        windows (windowMinutes=10080). When multiple weekly windows exist
        (Sonnet vs Opus on Claude Max), we report the max.
        """
        usage_stub([
            {
                "provider": "claude",
                "source": "web",
                "version": "2.1.139",
                "usage": {
                    "primary": {
                        "resetsAt": "2026-05-14T10:00:00Z",
                        "usedPercent": 43,
                        "windowMinutes": 300,
                    },
                    "secondary": {
                        "resetsAt": "2026-05-18T21:00:00Z",
                        "usedPercent": 49,
                        "windowMinutes": 10080,
                    },
                    "tertiary": {
                        "resetsAt": "2026-05-18T21:00:00Z",
                        "usedPercent": 2,
                        "windowMinutes": 10080,
                    },
                    "loginMethod": "Claude Max",
                    "accountEmail": "p@durlej.me",
                },
            }
        ])
        snap = usage_module.fetch_usage()
        assert snap is not None
        assert snap["ok"] is True
        assert snap["summary"]["window_5h_pct"] == 43.0
        # Peak weekly across secondary (49) and tertiary (2) = 49
        assert snap["summary"]["window_weekly_pct"] == 49.0
        keys = snap["summary"]["extracted_from_keys"]
        assert "usage.primary.5h" in keys
        assert "usage.secondary.weekly" in keys
        assert "usage.tertiary.weekly" in keys

    def test_fetch_with_codexbar_error_envelope(self, usage_stub):
        usage_stub([
            {
                "error": {
                    "code": 1,
                    "kind": "config",
                    "message": "Failed to decode CodexBar config",
                },
                "provider": "cli",
                "source": "cli",
            }
        ])
        snap = usage_module.fetch_usage()
        assert snap is not None
        assert snap["ok"] is False
        assert snap["error"]["kind"] == "config"

    def test_fetch_with_missing_binary(self, monkeypatch, capsys):
        monkeypatch.setenv("MIRROR_MIRROR_USAGE", "on")
        monkeypatch.setenv(
            "MIRROR_MIRROR_USAGE_CMD",
            "/this/path/should/not/exist/codexbar-binary --json",
        )
        snap = usage_module.fetch_usage()
        assert snap is None
        assert "command not found" in capsys.readouterr().err

    def test_fetch_with_garbage_json(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "garbage.txt"
        f.write_text("not json at all\n", encoding="utf-8")
        monkeypatch.setenv("MIRROR_MIRROR_USAGE", "on")
        monkeypatch.setenv("MIRROR_MIRROR_USAGE_CMD", f"cat {shlex.quote(str(f))}")
        snap = usage_module.fetch_usage()
        assert snap is None
        assert "could not parse JSON" in capsys.readouterr().err

    def test_fetch_with_empty_stdout(self, monkeypatch, capsys):
        monkeypatch.setenv("MIRROR_MIRROR_USAGE", "on")
        monkeypatch.setenv("MIRROR_MIRROR_USAGE_CMD", "true")
        snap = usage_module.fetch_usage()
        assert snap is None
        assert "empty stdout" in capsys.readouterr().err


class TestPressureFlag:
    def test_no_flag_when_low(self):
        snap = {"ok": True, "summary": {"window_5h_pct": 30.0, "window_weekly_pct": 20.0}}
        assert usage_module.quota_pressure_flag(snap) is None

    def test_warn_flag_at_75(self):
        snap = {"ok": True, "summary": {"window_5h_pct": 75.0}}
        flag = usage_module.quota_pressure_flag(snap)
        assert flag is not None
        assert "quota pressure" in flag
        assert "critical" not in flag

    def test_critical_flag_at_95(self):
        snap = {"ok": True, "summary": {"window_5h_pct": 95.0, "window_weekly_pct": 20.0}}
        flag = usage_module.quota_pressure_flag(snap)
        assert flag is not None
        assert "critical" in flag

    def test_no_flag_when_snapshot_missing(self):
        assert usage_module.quota_pressure_flag(None) is None

    def test_no_flag_when_snapshot_errored(self):
        snap = {"ok": False, "error": {"kind": "config"}, "summary": {}}
        assert usage_module.quota_pressure_flag(snap) is None


class TestSetReadoutAutoEnrichment:
    @pytest.mark.asyncio
    async def test_set_readout_auto_attaches_usage_snapshot(
        self, tmp_path, monkeypatch, usage_stub
    ):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        usage_stub({
            "window_5h": {"used_pct": 25.0},
            "window_weekly": {"used_pct": 10.0},
        })

        result = await server_module.call_tool("set_readout", make_valid_readout())
        assert "Readout accepted and persisted" in result[0].text

        persisted_line = (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        parsed = json.loads(persisted_line)
        assert parsed["metadata"] is not None
        assert "usage_snapshot" in parsed["metadata"]
        assert parsed["metadata"]["usage_snapshot"]["summary"]["window_5h_pct"] == 25.0

    @pytest.mark.asyncio
    async def test_set_readout_auto_adds_pressure_flag_when_high(
        self, tmp_path, monkeypatch, usage_stub
    ):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        usage_stub({"window_weekly": {"used_pct": 91.0}})

        await server_module.call_tool("set_readout", make_valid_readout())
        parsed = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        flags = parsed["epistemic_flags"]
        assert any("quota pressure" in f and "critical" in f for f in flags)

    @pytest.mark.asyncio
    async def test_set_readout_model_provided_metadata_preserved(
        self, tmp_path, monkeypatch, usage_stub
    ):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        usage_stub({"window_5h": {"used_pct": 12.0}})

        data = make_valid_readout(metadata={"task_id": "auth-refactor-42"})
        await server_module.call_tool("set_readout", data)
        parsed = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        assert parsed["metadata"]["task_id"] == "auth-refactor-42"
        assert parsed["metadata"]["usage_snapshot"]["summary"]["window_5h_pct"] == 12.0

    @pytest.mark.asyncio
    async def test_set_readout_works_when_usage_unavailable(self, tmp_path, monkeypatch):
        # Default conftest disables usage; confirm behaviour unchanged.
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        result = await server_module.call_tool("set_readout", make_valid_readout())
        assert "Readout accepted and persisted" in result[0].text
        parsed = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        # metadata should be None when usage off and model didn't pass any
        assert parsed["metadata"] is None


class TestGetSessionUsageTool:
    @pytest.mark.asyncio
    async def test_returns_snapshot_when_codexbar_ok(self, usage_stub):
        usage_stub({"window_5h": {"used_pct": 55.0}})
        result = await server_module.call_tool("get_session_usage", {})
        payload = json.loads(result[0].text)
        assert payload["available"] is True
        assert payload["ok"] is True
        assert payload["summary"]["window_5h_pct"] == 55.0

    @pytest.mark.asyncio
    async def test_returns_error_envelope_when_codexbar_misconfigured(self, usage_stub):
        usage_stub([{"error": {"kind": "config", "message": "bad config"}}])
        result = await server_module.call_tool("get_session_usage", {})
        payload = json.loads(result[0].text)
        assert payload["available"] is True
        assert payload["ok"] is False
        assert payload["error"]["kind"] == "config"
