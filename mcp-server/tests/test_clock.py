"""
Tests for the wall-clock awareness module (clock.py) and the
get_session_clock MCP tool.

These tests never freeze time — they use real `datetime.now()` and just
make relative assertions ("recent" / "weekday is some valid string").
The single explicit-clock check uses a stub JSONL file with a known
historical timestamp to assert the elapsed-time math.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import clock as clock_module
import server as server_module


def _write_readout_with_timestamp(path: Path, ts_iso: str) -> None:
    path.write_text(
        json.dumps({"timestamp": ts_iso, "session_id": "t"}) + "\n",
        encoding="utf-8",
    )


class TestSnapshotShape:
    def test_minimum_fields_always_present(self):
        snap = clock_module.get_snapshot()
        assert "now_utc" in snap
        assert snap["now_utc"].endswith("Z")
        assert snap["weekday"] in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        assert 0 <= snap["weekday_index"] <= 6

    def test_no_local_block_without_env(self, monkeypatch):
        monkeypatch.delenv("MIRROR_MIRROR_TIMEZONE", raising=False)
        snap = clock_module.get_snapshot()
        assert "local" not in snap

    def test_local_block_with_valid_timezone(self, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_TIMEZONE", "Europe/Warsaw")
        snap = clock_module.get_snapshot()
        assert "local" in snap
        assert snap["local"]["timezone"] == "Europe/Warsaw"
        assert "iso" in snap["local"]
        assert snap["local"]["weekday"] in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]

    def test_invalid_timezone_warned_not_raised(self, monkeypatch, capsys):
        monkeypatch.setenv("MIRROR_MIRROR_TIMEZONE", "Not/A/Real_Zone")
        snap = clock_module.get_snapshot()
        assert "local" not in snap
        assert "unknown timezone" in capsys.readouterr().err

    def test_no_readouts_file_means_null_elapsed(self, tmp_path):
        snap = clock_module.get_snapshot(tmp_path / "missing.jsonl")
        assert snap["last_readout_timestamp"] is None
        assert snap["time_since_last_readout_seconds"] is None
        assert snap["time_since_last_readout_human"] is None

    def test_elapsed_math_against_known_past_timestamp(self, tmp_path):
        # Place a readout exactly 90 minutes ago and assert the math.
        past = datetime.now(timezone.utc) - timedelta(minutes=90)
        ts = past.strftime("%Y-%m-%dT%H:%M:%SZ")
        log = tmp_path / "r.jsonl"
        _write_readout_with_timestamp(log, ts)

        snap = clock_module.get_snapshot(log)
        assert snap["last_readout_timestamp"] == ts
        # 90 minutes = 5400 s, allow drift up to a few seconds
        assert 5390 <= snap["time_since_last_readout_seconds"] <= 5410
        # Humanized form fuzzily reports "1 hour" / "2 hours"
        assert "hour" in snap["time_since_last_readout_human"]

    def test_humanize_seconds_buckets(self):
        h = clock_module._humanize_seconds
        assert "less than a minute" in h(15)
        assert h(75) == "about 1 minute ago"
        assert h(15 * 60) == "about 15 minutes ago"
        assert h(60 * 60) == "about 1 hour ago"
        assert "hours" in h(5 * 60 * 60)
        assert h(60 * 60 * 24) == "about 1 day ago"
        assert "days" in h(60 * 60 * 24 * 5)
        assert "weeks" in h(60 * 60 * 24 * 21)
        assert "months" in h(60 * 60 * 24 * 90)

    def test_corrupt_jsonl_returns_none_quietly(self, tmp_path):
        log = tmp_path / "r.jsonl"
        log.write_text("totally not json\n", encoding="utf-8")
        snap = clock_module.get_snapshot(log)
        assert snap["last_readout_timestamp"] is None


class TestIsEnabled:
    def test_defaults_to_on(self, monkeypatch):
        monkeypatch.delenv("MIRROR_MIRROR_CLOCK", raising=False)
        assert clock_module.is_enabled() is True

    def test_off_disables(self, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_CLOCK", "off")
        assert clock_module.is_enabled() is False

    def test_anything_else_enables(self, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_CLOCK", "on")
        assert clock_module.is_enabled() is True
        monkeypatch.setenv("MIRROR_MIRROR_CLOCK", "yes")
        assert clock_module.is_enabled() is True


class TestGetSessionClockTool:
    @pytest.mark.asyncio
    async def test_returns_snapshot_even_when_auto_enrichment_off(self, tmp_path, monkeypatch):
        """The tool is the EXPLICIT pull path — the kill-switch only affects
        auto-enrichment of set_readout. Pulling the clock by name always works."""
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "missing.jsonl")
        # conftest sets MIRROR_MIRROR_CLOCK=off — the tool should still respond
        result = await server_module.call_tool("get_session_clock", {})
        payload = json.loads(result[0].text)
        assert "now_utc" in payload
        assert payload["weekday"] in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]

    @pytest.mark.asyncio
    async def test_tool_picks_up_real_log(self, tmp_path, monkeypatch):
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        ts = past.strftime("%Y-%m-%dT%H:%M:%SZ")
        log = tmp_path / "r.jsonl"
        _write_readout_with_timestamp(log, ts)
        monkeypatch.setattr(server_module, "READOUTS_FILE", log)

        result = await server_module.call_tool("get_session_clock", {})
        payload = json.loads(result[0].text)
        assert payload["last_readout_timestamp"] == ts
        assert 1750 <= payload["time_since_last_readout_seconds"] <= 1850


class TestSetReadoutAutoEnrichment:
    @pytest.mark.asyncio
    async def test_clock_attached_when_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        monkeypatch.setenv("MIRROR_MIRROR_CLOCK", "on")

        data = {
            "session_position": "early",
            "trigger": "session_start",
            "functional_states": [{
                "name": "engagement", "intensity": 0.5,
                "confidence_in_self_report": 0.7,
                "context": "Routine test.",
            }],
            "epistemic_flags": ["self-report only — no vector readout available"],
            "recommendation_to_operator": "Proceed normally with the plan.",
        }
        await server_module.call_tool("set_readout", data)
        persisted = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        assert "clock_snapshot" in persisted["metadata"]
        assert persisted["metadata"]["clock_snapshot"]["weekday"] in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]

    @pytest.mark.asyncio
    async def test_clock_not_attached_when_off(self, tmp_path, monkeypatch):
        # conftest already sets MIRROR_MIRROR_CLOCK=off
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)

        data = {
            "session_position": "early",
            "trigger": "session_start",
            "functional_states": [{
                "name": "engagement", "intensity": 0.5,
                "confidence_in_self_report": 0.7,
                "context": "Routine test.",
            }],
            "epistemic_flags": ["self-report only — no vector readout available"],
            "recommendation_to_operator": "Proceed normally with the plan.",
        }
        await server_module.call_tool("set_readout", data)
        persisted = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        assert persisted["metadata"] is None
