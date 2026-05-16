"""
Tests for the UserPromptSubmit hook injector.

These tests invoke hook_pulse_injector.py as a subprocess (matching
how Claude Code actually calls it) with a stub stdin JSON, and assert
on the script's stdout/exit-code behavior.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


HOOK_SCRIPT = Path(__file__).parent.parent / "hook_pulse_injector.py"


def _run_hook(env: dict[str, str], stdin_payload: dict | None = None) -> tuple[int, str, str]:
    """Invoke the hook script as a subprocess and return (rc, stdout, stderr).

    Stub stdin matches the rough shape Claude Code passes: a JSON object
    with session_id, transcript_path, cwd. The hook script does not rely
    on any specific field, so this is just for realism.
    """
    payload = stdin_payload if stdin_payload is not None else {
        "session_id": "hook-test",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": "/tmp",
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _base_env(tmp_path: Path) -> dict[str, str]:
    import os
    env = os.environ.copy()
    env["MIRROR_MIRROR_LOG"] = str(tmp_path / "readouts.jsonl")
    env["MIRROR_MIRROR_PULSE"] = "on"
    env["MIRROR_MIRROR_USAGE"] = "off"
    env["MIRROR_MIRROR_CLOCK"] = "off"
    env["MIRROR_MIRROR_STATUSLINE_PATH"] = str(tmp_path / "no-statusline.json")
    # Disable any inherited overrides that might fire spuriously
    for key in (
        "MIRROR_MIRROR_PULSE_TOOLCALL_SOFT",
        "MIRROR_MIRROR_PULSE_TOOLCALL_HARD",
        "MIRROR_MIRROR_PULSE_CONTEXT_PCT_SOFT",
        "MIRROR_MIRROR_PULSE_CONTEXT_PCT_HARD",
        "MIRROR_MIRROR_PULSE_QUOTA_SOFT",
        "MIRROR_MIRROR_PULSE_QUOTA_HARD",
        "MIRROR_MIRROR_PULSE_TIME_SOFT_MIN",
        "MIRROR_MIRROR_PULSE_TIME_HARD_MIN",
    ):
        env.pop(key, None)
    return env


def _write_readout(path: Path, ts_iso: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"timestamp": ts_iso, "session_id": "x"}) + "\n", encoding="utf-8")


class TestNoInjectionPath:
    def test_no_signals_emits_empty_stdout(self, tmp_path):
        # Fresh state: no readouts, no statusline, no activity → no pulse → no output.
        env = _base_env(tmp_path)
        rc, stdout, _ = _run_hook(env)
        assert rc == 0
        assert stdout.strip() == ""

    def test_disabled_via_env(self, tmp_path):
        env = _base_env(tmp_path)
        env["MIRROR_MIRROR_PULSE"] = "off"
        # Even with a very stale readout, pulse=off must produce no output.
        past = datetime.now(timezone.utc) - timedelta(hours=5)
        _write_readout(tmp_path / "readouts.jsonl", past.strftime("%Y-%m-%dT%H:%M:%SZ"))
        rc, stdout, _ = _run_hook(env)
        assert rc == 0
        assert stdout.strip() == ""


class TestSoftInjection:
    def test_soft_severity_produces_one_liner(self, tmp_path):
        env = _base_env(tmp_path)
        env["MIRROR_MIRROR_PULSE_TIME_SOFT_MIN"] = "30"
        env["MIRROR_MIRROR_PULSE_TIME_HARD_MIN"] = "1000"  # high enough to stay soft

        past = datetime.now(timezone.utc) - timedelta(minutes=45)
        _write_readout(tmp_path / "readouts.jsonl", past.strftime("%Y-%m-%dT%H:%M:%SZ"))

        rc, stdout, _ = _run_hook(env)
        assert rc == 0
        payload = json.loads(stdout.strip())
        ctx = payload["additionalContext"]
        assert "[mirror-mirror pulse: soft" in ctx
        assert "signal" in ctx
        # Should not include the HARD heading
        assert "HARD" not in ctx


class TestHardInjection:
    def test_hard_severity_produces_full_block(self, tmp_path):
        env = _base_env(tmp_path)
        env["MIRROR_MIRROR_PULSE_TIME_SOFT_MIN"] = "5"
        env["MIRROR_MIRROR_PULSE_TIME_HARD_MIN"] = "30"

        past = datetime.now(timezone.utc) - timedelta(minutes=120)
        _write_readout(tmp_path / "readouts.jsonl", past.strftime("%Y-%m-%dT%H:%M:%SZ"))

        rc, stdout, _ = _run_hook(env)
        assert rc == 0
        payload = json.loads(stdout.strip())
        ctx = payload["additionalContext"]
        assert "HARD" in ctx
        assert "degradation zone" in ctx.lower()
        assert "set_readout" in ctx
        assert "Reasons:" in ctx
        assert "fail-safe heuristic" in ctx.lower()

    def test_hard_block_includes_research_pointer(self, tmp_path):
        env = _base_env(tmp_path)
        env["MIRROR_MIRROR_PULSE_TIME_HARD_MIN"] = "1"
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        _write_readout(tmp_path / "readouts.jsonl", past.strftime("%Y-%m-%dT%H:%M:%SZ"))

        rc, stdout, _ = _run_hook(env)
        payload = json.loads(stdout.strip())
        assert "docs/RESEARCH.md" in payload["additionalContext"]
        assert "PROTOCOL.md" in payload["additionalContext"]


class TestRobustness:
    def test_bad_stdin_does_not_break_hook(self, tmp_path):
        env = _base_env(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="this is not json at all",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        # Hooks must never break Claude Code's prompt flow.
        assert proc.returncode == 0

    def test_no_stdin_at_all(self, tmp_path):
        env = _base_env(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode == 0
