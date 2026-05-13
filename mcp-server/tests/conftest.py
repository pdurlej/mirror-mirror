"""
Shared pytest fixtures for the mirror-mirror MCP server tests.

By default we disable the codexbar usage integration so that set_readout
tests don't shell out (and don't get auto-enriched metadata or flags).
Tests that exercise the integration explicitly re-enable it.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_usage_by_default(monkeypatch):
    monkeypatch.setenv("MIRROR_MIRROR_USAGE", "off")
    yield
