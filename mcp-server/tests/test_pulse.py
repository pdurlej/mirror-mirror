"""
Tests for the pulse module.

These tests never patch time directly. Time-based assertions use either
the natural now (for "should not fire" checks) or a stub readout file
with a known historical timestamp (for "should fire" checks).
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import pulse as pulse_module


def _write_readout(path: Path, ts_iso: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"timestamp": ts_iso, "session_id": "t"}) + "\n", encoding="utf-8")


def _write_statusline(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("ts", time.time())
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(autouse=True)
def reset_activity_counter():
    pulse_module.reset_activity()
    yield
    pulse_module.reset_activity()


@pytest.fixture(autouse=True)
def enable_pulse(monkeypatch):
    """conftest disables most integrations by default; pulse tests need it on."""
    monkeypatch.setenv("MIRROR_MIRROR_PULSE", "on")
    yield


class TestActivityCounter:
    def test_starts_at_zero(self):
        assert pulse_module.get_activity_count() == 0

    def test_increment(self):
        assert pulse_module.increment_activity() == 1
        assert pulse_module.increment_activity() == 2
        assert pulse_module.get_activity_count() == 2

    def test_reset(self):
        pulse_module.increment_activity()
        pulse_module.increment_activity()
        pulse_module.reset_activity()
        assert pulse_module.get_activity_count() == 0


class TestEnabledFlag:
    def test_default_on(self, monkeypatch):
        monkeypatch.delenv("MIRROR_MIRROR_PULSE", raising=False)
        assert pulse_module.is_enabled() is True

    def test_off_disables(self, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_PULSE", "off")
        assert pulse_module.is_enabled() is False

    def test_disabled_assess_returns_minimal_payload(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_PULSE", "off")
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["due"] is False
        assert result["enabled"] is False
        assert result["severity"] == "none"


class TestActivityTrigger:
    def test_below_soft_no_pulse(self, tmp_path):
        for _ in range(5):
            pulse_module.increment_activity()
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["due"] is False
        assert result["signals"]["activity"]["severity"] == "none"

    def test_at_soft_fires_soft(self, tmp_path):
        for _ in range(8):
            pulse_module.increment_activity()
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["due"] is True
        assert result["severity"] == "soft"
        assert result["signals"]["activity"]["severity"] == "soft"
        assert any("8 mirror-mirror tool calls" in r for r in result["reasons"])

    def test_at_hard_fires_hard(self, tmp_path):
        for _ in range(24):
            pulse_module.increment_activity()
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["severity"] == "hard"
        assert result["signals"]["activity"]["severity"] == "hard"

    def test_custom_thresholds_via_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_PULSE_TOOLCALL_SOFT", "3")
        monkeypatch.setenv("MIRROR_MIRROR_PULSE_TOOLCALL_HARD", "5")
        for _ in range(4):
            pulse_module.increment_activity()
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["severity"] == "soft"
        pulse_module.increment_activity()
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["severity"] == "hard"


class TestContextTrigger:
    def test_no_statusline_no_signal(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(tmp_path / "missing.json"))
        result = pulse_module.assess(readouts_file=tmp_path / "r.jsonl")
        assert result["signals"]["context"]["severity"] == "none"
        assert result["signals"]["context"]["from_statusline"] is False

    def test_below_soft_no_signal(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_statusline(f, {"context_window": {"used_percentage": 10.0}})
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        result = pulse_module.assess(readouts_file=tmp_path / "r.jsonl")
        assert result["signals"]["context"]["severity"] == "none"
        assert result["signals"]["context"]["context_window_pct"] == 10.0

    def test_at_soft_fires_soft(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_statusline(f, {"context_window": {"used_percentage": 18.0}})
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        result = pulse_module.assess(readouts_file=tmp_path / "r.jsonl")
        assert result["severity"] == "soft"
        assert any("BABILong" in r for r in result["reasons"])

    def test_at_hard_fires_hard(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_statusline(f, {"context_window": {"used_percentage": 35.0}})
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        result = pulse_module.assess(readouts_file=tmp_path / "r.jsonl")
        assert result["severity"] == "hard"


class TestQuotaTrigger:
    def test_below_soft_no_signal(self, tmp_path):
        result = pulse_module.assess(
            readouts_file=tmp_path / "r.jsonl",
            usage_summary={"window_5h_pct": 40.0, "window_weekly_pct": 30.0},
        )
        assert result["signals"]["quota"]["severity"] == "none"

    def test_peak_drives_severity(self, tmp_path):
        result = pulse_module.assess(
            readouts_file=tmp_path / "r.jsonl",
            usage_summary={"window_5h_pct": 50.0, "window_weekly_pct": 75.0},
        )
        assert result["severity"] == "soft"
        assert any("weekly" in r.lower() for r in result["reasons"])

    def test_hard_threshold(self, tmp_path):
        result = pulse_module.assess(
            readouts_file=tmp_path / "r.jsonl",
            usage_summary={"window_5h_pct": 92.0},
        )
        assert result["severity"] == "hard"

    def test_quota_reason_flags_convention_status(self, tmp_path):
        result = pulse_module.assess(
            readouts_file=tmp_path / "r.jsonl",
            usage_summary={"window_5h_pct": 75.0},
        )
        # Soft quota reason MUST flag that this is ops convention, not research.
        assert any("convention" in r.lower() for r in result["reasons"])


class TestTimeTrigger:
    def test_no_readout_no_signal(self, tmp_path):
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["signals"]["time"]["severity"] == "none"

    def test_recent_readout_no_signal(self, tmp_path):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log = tmp_path / "r.jsonl"
        _write_readout(log, ts)
        result = pulse_module.assess(readouts_file=log)
        assert result["signals"]["time"]["severity"] == "none"

    def test_old_readout_fires_soft(self, tmp_path):
        past = datetime.now(timezone.utc) - timedelta(minutes=45)
        log = tmp_path / "r.jsonl"
        _write_readout(log, past.strftime("%Y-%m-%dT%H:%M:%SZ"))
        result = pulse_module.assess(readouts_file=log)
        assert result["severity"] == "soft"
        assert any("fail-safe" in r for r in result["reasons"])

    def test_very_old_readout_fires_hard(self, tmp_path):
        past = datetime.now(timezone.utc) - timedelta(minutes=90)
        log = tmp_path / "r.jsonl"
        _write_readout(log, past.strftime("%Y-%m-%dT%H:%M:%SZ"))
        result = pulse_module.assess(readouts_file=log)
        assert result["severity"] == "hard"


class TestAggregation:
    def test_max_severity_wins(self, tmp_path, monkeypatch):
        """activity=hard but context=none → still hard."""
        f = tmp_path / "status.json"
        _write_statusline(f, {"context_window": {"used_percentage": 5.0}})
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        for _ in range(24):
            pulse_module.increment_activity()
        result = pulse_module.assess(
            readouts_file=tmp_path / "missing.jsonl",
            usage_summary={"window_5h_pct": 10.0},
        )
        assert result["severity"] == "hard"

    def test_no_signals_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(tmp_path / "missing.json"))
        result = pulse_module.assess(readouts_file=tmp_path / "missing.jsonl")
        assert result["due"] is False
        assert result["severity"] == "none"
        assert result["reasons"] == []

    def test_reasons_include_all_firing_signals(self, tmp_path, monkeypatch):
        f = tmp_path / "status.json"
        _write_statusline(f, {"context_window": {"used_percentage": 20.0}})
        monkeypatch.setenv("MIRROR_MIRROR_STATUSLINE_PATH", str(f))

        for _ in range(10):
            pulse_module.increment_activity()

        result = pulse_module.assess(
            readouts_file=tmp_path / "missing.jsonl",
            usage_summary={"window_5h_pct": 73.0},
        )
        # At least three reasons (activity + context + quota)
        assert len(result["reasons"]) >= 3
