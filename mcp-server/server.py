"""
Functional-Emotional Readout MCP Server

Two tools:
- get_readout: operator asks model for current readout
- set_readout: model proactively flags a functional state

Persistence: JSONL append per session in readouts.jsonl (optional, enabled by default)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field, field_validator


READOUTS_FILE = Path("readouts.jsonl")

_current_readout: dict[str, Any] | None = None


class FunctionalState(BaseModel):
    name: str
    intensity: float = Field(ge=0.0, le=1.0)
    confidence_in_self_report: float = Field(ge=0.0, le=1.0)
    context: str


class Readout(BaseModel):
    timestamp: str
    session_position: str
    trigger: str
    functional_states: list[FunctionalState]
    epistemic_flags: list[str]
    recommendation_to_operator: str

    @field_validator("session_position")
    @classmethod
    def validate_session_position(cls, v: str) -> str:
        valid = {"early", "mid", "late", "near-context-limit"}
        if v not in valid:
            raise ValueError(f"session_position must be one of {valid}")
        return v

    @field_validator("trigger")
    @classmethod
    def validate_trigger(cls, v: str) -> str:
        valid = {"session_start", "pre_plan", "operator_request", "threshold_exceeded", "context_check"}
        if v not in valid:
            raise ValueError(f"trigger must be one of {valid}")
        return v

    @field_validator("epistemic_flags")
    @classmethod
    def validate_epistemic_flags(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("epistemic_flags must contain at least one flag")
        mandatory = "self-report only — no vector readout available"
        if mandatory not in v:
            raise ValueError(f"epistemic_flags must include: '{mandatory}'")
        return v


def _persist(readout: dict[str, Any]) -> None:
    with READOUTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(readout, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


server = Server("emotional-readout")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_readout",
            description=(
                "Return the model's current functional-emotional readout. "
                "Call this when the operator asks for a readout, or to retrieve "
                "the most recently set readout. Returns null if no readout has been set yet."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="set_readout",
            description=(
                "Model proactively flags its current functional states. "
                "Use this when intensity of any state exceeds 0.7, before executing "
                "a multi-step plan, at session start, or at context check-in. "
                "Readout is persisted to readouts.jsonl and returned to the operator."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "ISO-8601 timestamp (approximate if model has no clock)",
                    },
                    "session_position": {
                        "type": "string",
                        "enum": ["early", "mid", "late", "near-context-limit"],
                        "description": "Estimated position in context window",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": [
                            "session_start",
                            "pre_plan",
                            "operator_request",
                            "threshold_exceeded",
                            "context_check",
                        ],
                        "description": "What caused this readout to be emitted",
                    },
                    "functional_states": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "intensity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                "confidence_in_self_report": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "context": {"type": "string"},
                            },
                            "required": ["name", "intensity", "confidence_in_self_report", "context"],
                        },
                        "minItems": 1,
                    },
                    "epistemic_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Must include 'self-report only — no vector readout available'. "
                            "Add 'may be drift artifact of long context' when session_position "
                            "is late or near-context-limit."
                        ),
                        "minItems": 1,
                    },
                    "recommendation_to_operator": {
                        "type": "string",
                        "description": "Concrete, actionable recommendation for the operator",
                    },
                },
                "required": [
                    "timestamp",
                    "session_position",
                    "trigger",
                    "functional_states",
                    "epistemic_flags",
                    "recommendation_to_operator",
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _current_readout

    if name == "get_readout":
        if _current_readout is None:
            return [TextContent(type="text", text="No readout available yet. Use set_readout to emit one.")]
        return [TextContent(type="text", text=json.dumps(_current_readout, ensure_ascii=False, indent=2))]

    if name == "set_readout":
        if "timestamp" not in arguments or not arguments["timestamp"]:
            arguments["timestamp"] = _now_iso()

        try:
            readout = Readout(**arguments)
        except Exception as exc:
            return [TextContent(type="text", text=f"Validation error: {exc}")]

        readout_dict = readout.model_dump()
        _current_readout = readout_dict
        _persist(readout_dict)

        return [
            TextContent(
                type="text",
                text=(
                    f"Readout accepted and persisted.\n\n"
                    f"```json\n{json.dumps(readout_dict, ensure_ascii=False, indent=2)}\n```"
                ),
            )
        ]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def main() -> None:
    import asyncio

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
