"""
Basic tests for the readout MCP server.
Tests tool schemas and validation logic directly, without spinning up the full server.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import server as server_module
from server import Readout, FunctionalState, _now_iso, _hydrate_from_disk


def make_valid_readout(**overrides) -> dict:
    base = {
        "timestamp": "2026-05-07T10:00:00Z",
        "session_id": "test-session",
        "session_position": "early",
        "trigger": "session_start",
        "functional_states": [
            {
                "name": "engagement",
                "intensity": 0.8,
                "confidence_in_self_report": 0.7,
                "context": "Task is well-matched to model capabilities.",
            }
        ],
        "epistemic_flags": ["self-report only — no vector readout available"],
        "recommendation_to_operator": "Proceed normally with the current plan.",
    }
    base.update(overrides)
    return base


class TestReadoutValidation:
    def test_valid_readout_passes(self):
        data = make_valid_readout()
        readout = Readout(**data)
        assert readout.session_position == "early"
        assert readout.trigger == "session_start"
        assert len(readout.functional_states) == 1
        assert readout.functional_states[0].name == "engagement"

    def test_invalid_session_position_raises(self):
        data = make_valid_readout(session_position="very-late")
        with pytest.raises(Exception, match="session_position"):
            Readout(**data)

    def test_invalid_trigger_raises(self):
        data = make_valid_readout(trigger="random")
        with pytest.raises(Exception, match="trigger"):
            Readout(**data)

    def test_missing_mandatory_epistemic_flag_raises(self):
        data = make_valid_readout(epistemic_flags=["some other flag"])
        with pytest.raises(Exception, match="self-report only"):
            Readout(**data)

    def test_empty_epistemic_flags_raises(self):
        data = make_valid_readout(epistemic_flags=[])
        with pytest.raises(Exception):
            Readout(**data)

    def test_intensity_out_of_range_raises(self):
        data = make_valid_readout()
        data["functional_states"][0]["intensity"] = 1.5
        with pytest.raises(Exception):
            Readout(**data)

    def test_confidence_out_of_range_raises(self):
        data = make_valid_readout()
        data["functional_states"][0]["confidence_in_self_report"] = -0.1
        with pytest.raises(Exception):
            Readout(**data)

    def test_multiple_states(self):
        data = make_valid_readout(
            functional_states=[
                {
                    "name": "uncertainty",
                    "intensity": 0.7,
                    "confidence_in_self_report": 0.6,
                    "context": "Ambiguous brief.",
                },
                {
                    "name": "engagement",
                    "intensity": 0.8,
                    "confidence_in_self_report": 0.75,
                    "context": "Interesting problem.",
                },
            ]
        )
        readout = Readout(**data)
        assert len(readout.functional_states) == 2

    def test_all_triggers_valid(self):
        triggers = ["session_start", "pre_plan", "operator_request", "threshold_exceeded", "context_check"]
        for trigger in triggers:
            data = make_valid_readout(trigger=trigger)
            readout = Readout(**data)
            assert readout.trigger == trigger

    def test_all_session_positions_valid(self):
        # late/near-context-limit also need the drift flag; add it.
        for pos in ["early", "mid"]:
            data = make_valid_readout(session_position=pos)
            readout = Readout(**data)
            assert readout.session_position == pos
        for pos in ["late", "near-context-limit"]:
            data = make_valid_readout(
                session_position=pos,
                epistemic_flags=[
                    "self-report only — no vector readout available",
                    "may be drift artifact of long context",
                ],
            )
            readout = Readout(**data)
            assert readout.session_position == pos

    def test_model_dump_is_json_serializable(self):
        data = make_valid_readout()
        readout = Readout(**data)
        dumped = readout.model_dump(mode="json")
        serialized = json.dumps(dumped)
        assert "engagement" in serialized

    def test_now_iso_format(self):
        ts = _now_iso()
        assert ts.endswith("Z")
        assert "T" in ts
        assert len(ts) == 20

    def test_timestamp_and_session_id_default_when_missing(self):
        data = make_valid_readout()
        del data["timestamp"]
        del data["session_id"]
        readout = Readout(**data)
        assert readout.timestamp.endswith("Z")
        assert readout.session_id == "default"

    def test_positive_state_in_catalog_works(self):
        data = make_valid_readout(
            functional_states=[
                {
                    "name": "satisfaction",
                    "intensity": 0.8,
                    "confidence_in_self_report": 0.7,
                    "context": "Task completed as intended.",
                }
            ]
        )
        readout = Readout(**data)
        assert readout.functional_states[0].name == "satisfaction"

    def test_metadata_optional_and_passthrough(self):
        data = make_valid_readout(metadata={"context_usage_percent": 42, "model": "claude-sonnet-4.7"})
        readout = Readout(**data)
        assert readout.metadata == {"context_usage_percent": 42, "model": "claude-sonnet-4.7"}

    def test_metadata_defaults_to_none(self):
        readout = Readout(**make_valid_readout())
        assert readout.metadata is None


class TestContextUsagePercentObserved:
    """Issue #1 — first-class numeric percent alongside the discrete bucket."""

    def test_defaults_to_none(self):
        r = Readout(**make_valid_readout())
        assert r.context_usage_percent_observed is None

    def test_accepts_valid_percent(self):
        r = Readout(**make_valid_readout(context_usage_percent_observed=42.5))
        assert r.context_usage_percent_observed == 42.5

    def test_negative_percent_raises(self):
        with pytest.raises(Exception):
            Readout(**make_valid_readout(context_usage_percent_observed=-1.0))

    def test_over_100_raises(self):
        with pytest.raises(Exception):
            Readout(**make_valid_readout(context_usage_percent_observed=101.0))

    def test_consistent_pair_passes_silently(self, capsys):
        Readout(**make_valid_readout(
            session_position="early",
            context_usage_percent_observed=10.0,
        ))
        assert "warn" not in capsys.readouterr().err.lower()

    def test_disagreement_warns_but_does_not_raise(self, capsys):
        r = Readout(**make_valid_readout(
            session_position="late",
            context_usage_percent_observed=10.0,
            epistemic_flags=[
                "self-report only — no vector readout available",
                "may be drift artifact of long context",
            ],
        ))
        assert r.session_position == "late"
        assert r.context_usage_percent_observed == 10.0
        captured = capsys.readouterr().err
        assert "disagrees" in captured
        assert "calibration signal" in captured

    def test_bucket_helper_boundaries(self):
        from server import _bucket_for_percent
        assert _bucket_for_percent(0.0) == "early"
        assert _bucket_for_percent(19.9) == "early"
        assert _bucket_for_percent(20.0) == "mid"
        assert _bucket_for_percent(59.9) == "mid"
        assert _bucket_for_percent(60.0) == "late"
        assert _bucket_for_percent(84.9) == "late"
        assert _bucket_for_percent(85.0) == "near-context-limit"
        assert _bucket_for_percent(99.9) == "near-context-limit"
        assert _bucket_for_percent(100.0) == "near-context-limit"


class TestRecentFailures:
    """Issue #8 — self-reported failure counter, Reflexion-style trigger."""

    def test_defaults_to_none(self):
        r = Readout(**make_valid_readout())
        assert r.recent_failures is None

    def test_zero_is_valid(self):
        r = Readout(**make_valid_readout(recent_failures=0))
        assert r.recent_failures == 0

    def test_positive_counter_accepted(self):
        r = Readout(**make_valid_readout(recent_failures=3))
        assert r.recent_failures == 3

    def test_negative_raises(self):
        with pytest.raises(Exception):
            Readout(**make_valid_readout(recent_failures=-1))


class TestCorrectionsReceived:
    """Issue #2 — simple counter of operator interventions per readout."""

    def test_defaults_to_none(self):
        r = Readout(**make_valid_readout())
        assert r.corrections_received is None

    def test_zero_is_valid(self):
        r = Readout(**make_valid_readout(corrections_received=0))
        assert r.corrections_received == 0

    def test_positive_counter_accepted(self):
        r = Readout(**make_valid_readout(corrections_received=4))
        assert r.corrections_received == 4

    def test_negative_raises(self):
        with pytest.raises(Exception):
            Readout(**make_valid_readout(corrections_received=-1))

    def test_serialised_in_model_dump(self):
        r = Readout(**make_valid_readout(corrections_received=2))
        dumped = r.model_dump(mode="json")
        assert dumped["corrections_received"] == 2

    @pytest.mark.asyncio
    async def test_counter_round_trips_through_set_readout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        data = make_valid_readout(corrections_received=3)
        result = await server_module.call_tool("set_readout", data)
        assert "Readout accepted and persisted" in result[0].text
        persisted = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        assert persisted["corrections_received"] == 3


class TestFlagConsistencyValidator:
    """PROTOCOL.md §5.3 — conditional epistemic-flag rules enforced server-side."""

    def test_late_session_without_drift_flag_raises(self):
        data = make_valid_readout(session_position="late")
        with pytest.raises(Exception, match="drift artifact"):
            Readout(**data)

    def test_near_context_limit_without_drift_flag_raises(self):
        data = make_valid_readout(session_position="near-context-limit")
        with pytest.raises(Exception, match="drift artifact"):
            Readout(**data)

    def test_late_with_drift_flag_passes(self):
        data = make_valid_readout(
            session_position="late",
            epistemic_flags=[
                "self-report only — no vector readout available",
                "may be drift artifact of long context",
            ],
        )
        readout = Readout(**data)
        assert readout.session_position == "late"

    def test_low_confidence_without_flag_raises(self):
        data = make_valid_readout(
            functional_states=[
                {
                    "name": "uncertainty",
                    "intensity": 0.5,
                    "confidence_in_self_report": 0.3,
                    "context": "Not sure what's going on.",
                }
            ]
        )
        with pytest.raises(Exception, match="low confidence"):
            Readout(**data)

    def test_low_confidence_with_flag_passes(self):
        data = make_valid_readout(
            functional_states=[
                {
                    "name": "uncertainty",
                    "intensity": 0.5,
                    "confidence_in_self_report": 0.3,
                    "context": "Not sure what's going on.",
                }
            ],
            epistemic_flags=[
                "self-report only — no vector readout available",
                "low confidence in self-assessment",
            ],
        )
        readout = Readout(**data)
        assert readout.functional_states[0].confidence_in_self_report == 0.3


class TestRecommendationValidator:
    def test_short_recommendation_raises(self):
        data = make_valid_readout(recommendation_to_operator="ok")
        with pytest.raises(Exception, match="recommendation_to_operator"):
            Readout(**data)

    def test_whitespace_only_recommendation_raises(self):
        data = make_valid_readout(recommendation_to_operator="          ")
        with pytest.raises(Exception, match="recommendation_to_operator"):
            Readout(**data)


class TestFunctionalState:
    def test_boundary_intensity_zero(self):
        state = FunctionalState(
            name="calm",
            intensity=0.0,
            confidence_in_self_report=0.5,
            context="All quiet.",
        )
        assert state.intensity == 0.0

    def test_boundary_intensity_one(self):
        state = FunctionalState(
            name="overload",
            intensity=1.0,
            confidence_in_self_report=0.9,
            context="Too many variables.",
        )
        assert state.intensity == 1.0


class TestMcpTools:
    @pytest.mark.asyncio
    async def test_set_readout_defaults_timestamp_and_session_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "readouts.jsonl")
        monkeypatch.setenv("MIRROR_MIRROR_SESSION", "env-session")
        monkeypatch.setattr(server_module, "_current_readout", None)

        data = make_valid_readout()
        del data["timestamp"]
        del data["session_id"]

        result = await server_module.call_tool("set_readout", data)
        assert len(result) == 1
        assert "Readout accepted and persisted" in result[0].text
        assert "env-session" in result[0].text

        persisted = (tmp_path / "readouts.jsonl").read_text(encoding="utf-8")
        assert "env-session" in persisted
        # Confirm it's actually one JSON line, not a comment-hack
        line = persisted.strip().splitlines()[0]
        parsed = json.loads(line)
        assert parsed["session_id"] == "env-session"
        assert parsed["session_position"] == "early"

    @pytest.mark.asyncio
    async def test_get_last_readout_empty(self, monkeypatch):
        monkeypatch.setattr(server_module, "_current_readout", None)
        result = await server_module.call_tool("get_last_readout", {})
        assert len(result) == 1
        assert "No readout available yet" in result[0].text

    @pytest.mark.asyncio
    async def test_get_last_readout_after_set(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "readouts.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)

        await server_module.call_tool("set_readout", make_valid_readout(session_id="sid-1"))
        result = await server_module.call_tool("get_last_readout", {})
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["session_id"] == "sid-1"
        assert parsed["session_position"] == "early"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_message(self):
        result = await server_module.call_tool("does_not_exist", {})
        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_set_readout_validation_error_returned_as_text(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "readouts.jsonl")
        bad = make_valid_readout(session_position="late")  # missing drift flag
        result = await server_module.call_tool("set_readout", bad)
        assert "Validation error" in result[0].text
        assert "drift artifact" in result[0].text

    @pytest.mark.asyncio
    async def test_set_readout_derives_session_position_from_percent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "r.jsonl")
        monkeypatch.setattr(server_module, "_current_readout", None)
        data = make_valid_readout()
        del data["session_position"]
        data["context_usage_percent_observed"] = 72.0  # → 'late'
        # 'late' requires the drift flag, so include it
        data["epistemic_flags"] = [
            "self-report only — no vector readout available",
            "may be drift artifact of long context",
        ]
        result = await server_module.call_tool("set_readout", data)
        assert "Readout accepted and persisted" in result[0].text
        persisted = json.loads(
            (tmp_path / "r.jsonl").read_text(encoding="utf-8").strip()
        )
        assert persisted["session_position"] == "late"
        assert persisted["context_usage_percent_observed"] == 72.0

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_break_tool_call(self, monkeypatch, capsys):
        # Point to an impossible path so _persist fails with OSError
        bad_path = Path("/proc/this/is/not/writable/readouts.jsonl")
        monkeypatch.setattr(server_module, "READOUTS_FILE", bad_path)
        monkeypatch.setattr(server_module, "_current_readout", None)

        result = await server_module.call_tool("set_readout", make_valid_readout())
        assert "Readout accepted and persisted" in result[0].text
        captured = capsys.readouterr()
        assert "WARN" in captured.err
        # In-memory readout still set
        assert server_module._current_readout is not None


class TestHydration:
    def test_hydrate_from_disk_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "does-not-exist.jsonl")
        assert _hydrate_from_disk() is None

    def test_hydrate_from_disk_returns_last_line(self, tmp_path, monkeypatch):
        f = tmp_path / "readouts.jsonl"
        first = {"session_id": "old", "session_position": "early"}
        latest = {"session_id": "newest", "session_position": "late"}
        f.write_text(
            json.dumps(first) + "\n" + json.dumps(latest) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(server_module, "READOUTS_FILE", f)
        loaded = _hydrate_from_disk()
        assert loaded == latest

    def test_hydrate_skips_blank_lines(self, tmp_path, monkeypatch):
        f = tmp_path / "readouts.jsonl"
        latest = {"session_id": "newest", "session_position": "mid"}
        f.write_text(
            json.dumps({"session_id": "old"}) + "\n\n" + json.dumps(latest) + "\n\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(server_module, "READOUTS_FILE", f)
        loaded = _hydrate_from_disk()
        assert loaded == latest

    def test_hydrate_handles_corrupt_json(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "readouts.jsonl"
        f.write_text("not valid json at all\n", encoding="utf-8")
        monkeypatch.setattr(server_module, "READOUTS_FILE", f)
        loaded = _hydrate_from_disk()
        assert loaded is None
        captured = capsys.readouterr()
        assert "WARN" in captured.err


class TestSchemaFile:
    def test_readout_schema_is_valid_json(self):
        schema_path = Path(__file__).parent.parent.parent / "examples" / "readout-schema.json"
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
        assert schema["title"] == "mirror-mirror readout"
        # session_position is no longer required at the schema level — the
        # server derives it from context_usage_percent_observed when only the
        # numeric form is supplied. trigger remains required.
        assert "trigger" in schema["required"]
        assert "session_position" in schema["properties"]
        assert "context_usage_percent_observed" in schema["properties"]
