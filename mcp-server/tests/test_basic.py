"""
Basic tests for the readout MCP server.
Tests tool schemas and validation logic directly, without spinning up the full server.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import Readout, FunctionalState, _now_iso


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
        "recommendation_to_operator": "Proceed normally.",
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
        positions = ["early", "mid", "late", "near-context-limit"]
        for pos in positions:
            data = make_valid_readout(session_position=pos)
            readout = Readout(**data)
            assert readout.session_position == pos

    def test_model_dump_is_json_serializable(self):
        data = make_valid_readout()
        readout = Readout(**data)
        dumped = readout.model_dump()
        serialized = json.dumps(dumped)
        assert "engagement" in serialized

    def test_now_iso_format(self):
        ts = _now_iso()
        assert ts.endswith("Z")
        assert "T" in ts
        assert len(ts) == 20


    def test_session_id_required(self):
        data = make_valid_readout()
        del data["session_id"]
        with pytest.raises(Exception):
            Readout(**data)

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
