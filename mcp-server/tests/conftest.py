"""
Shared pytest fixtures for the mirror-mirror MCP server tests.

By default we disable both the codexbar usage integration and the wall-clock
auto-enrichment so set_readout tests don't shell out and don't get unexpected
metadata. Tests that exercise either integration explicitly re-enable it.
The get_session_clock and get_session_usage tools themselves are always
callable — those flags only affect the implicit attachment on set_readout.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_integrations_by_default(monkeypatch):
    monkeypatch.setenv("MIRROR_MIRROR_USAGE", "off")
    monkeypatch.setenv("MIRROR_MIRROR_CLOCK", "off")
    monkeypatch.setenv("MIRROR_MIRROR_PULSE", "off")
    yield
