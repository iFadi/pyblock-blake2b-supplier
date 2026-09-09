"""Tests for supplier.healthcheck — the StartOS-facing result mapping."""

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from supplier import healthcheck


def _run(state):
    with patch("supplier.healthcheck.read_state", return_value=state):
        buf = io.StringIO()
        with redirect_stdout(buf):
            healthcheck.main()
        return json.loads(buf.getvalue())


@pytest.mark.parametrize(
    "state,expected",
    [
        ("healthy_active", "success"),
        ("starting", "starting"),
        ("no_state", "starting"),
        ("node_unsynced", "loading"),
        ("config_error", "failure"),
        ("node_unavailable", "failure"),
        ("gbt_unsupported", "failure"),
        ("tor_unavailable", "failure"),
        ("pyblock_rejected", "failure"),
        ("stopped", "failure"),
        ("failed", "failure"),
        ("stale", "failure"),
        ("dead", "failure"),
        ("unreadable", "failure"),
    ],
)
def test_state_maps_to_startos_result(state, expected):
    out = _run({"state": state, "result": "?", "message": "msg"})
    assert out == {"result": expected, "message": "msg"}


def test_unknown_state_defaults_to_failure():
    """A state added later without updating the table must fail closed."""
    out = _run({"state": "some_future_state", "result": "?", "message": "msg"})
    assert out["result"] == "failure"


def test_check_never_crashes_and_reports_why():
    with patch("supplier.healthcheck.read_state", side_effect=RuntimeError("boom")):
        buf = io.StringIO()
        with redirect_stdout(buf):
            healthcheck.main()
        out = json.loads(buf.getvalue())
    assert out["result"] == "failure"
    assert "boom" in out["message"]
