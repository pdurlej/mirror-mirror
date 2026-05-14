"""
Tests for the Claude Code statusline bridge.
"""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import statusline as statusline_module


def _write_snapshot(path: Path, payload: dict, ts: float | None = None) -> None:
    if ts is not None:
        payload = dict(payload)
        payload["ts"] = ts
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestReadSnapshot:
    def test_returns_none_when_path_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(tmp_path / "nope.json"))
        assert statusline_module.read_snapshot() is None

    def test_returns_dict_when_fresh(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_snapshot(f, {
            "session_id": "abc-123",
            "context_window": {"used_percentage": 42.0},
        }, ts=time.time())
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        snap = statusline_module.read_snapshot()
        assert snap is not None
        assert snap["session_id"] == "abc-123"

    def test_returns_none_when_stale(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_snapshot(f, {"session_id": "old"}, ts=time.time() - 600)
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_MAX_AGE_S", "30")

        assert statusline_module.read_snapshot() is None

    def test_custom_max_age_can_extend(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_snapshot(f, {"session_id": "longish"}, ts=time.time() - 120)
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_MAX_AGE_S", "600")

        snap = statusline_module.read_snapshot()
        assert snap is not None and snap["session_id"] == "longish"

    def test_returns_none_on_corrupt_json(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "status.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("definitely not json", encoding="utf-8")
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        assert statusline_module.read_snapshot() is None
        assert "unreadable" in capsys.readouterr().err

    def test_returns_none_when_not_a_dict(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(["just", "a", "list"]), encoding="utf-8")
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        assert statusline_module.read_snapshot() is None


class TestContextWindowPct:
    def test_direct_percentage_field(self):
        snap = {"context_window": {"used_percentage": 73.4}}
        assert statusline_module.context_window_pct(snap) == 73.4

    def test_derived_from_totals(self):
        snap = {"context_window": {"total_input_tokens": 25000, "limit": 100000}}
        pct = statusline_module.context_window_pct(snap)
        assert pct is not None
        assert abs(pct - 25.0) < 0.01

    def test_none_when_snapshot_missing(self):
        assert statusline_module.context_window_pct(None) is None

    def test_none_when_context_window_missing(self):
        assert statusline_module.context_window_pct({"session_id": "x"}) is None

    def test_none_when_no_usable_fields(self):
        snap = {"context_window": {"some_other_field": 42}}
        assert statusline_module.context_window_pct(snap) is None


class TestExtractors:
    def test_session_id(self):
        assert statusline_module.session_id({"session_id": "s1"}) == "s1"
        assert statusline_module.session_id({}) is None
        assert statusline_module.session_id(None) is None
        # Non-string defensively returns None
        assert statusline_module.session_id({"session_id": 42}) is None

    def test_total_cost_usd(self):
        assert statusline_module.total_cost_usd({"cost": {"total_cost_usd": 1.25}}) == 1.25
        assert statusline_module.total_cost_usd({"cost": {}}) is None
        assert statusline_module.total_cost_usd({}) is None
        assert statusline_module.total_cost_usd(None) is None
