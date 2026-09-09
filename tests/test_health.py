"""Tests for supplier.health — the fail-closed evaluation rules.

The invariant under test: read_state() reports "success"-eligible states only
when the record is fresh AND written by a process that is still alive. Every
other combination must degrade to a failing state.
"""

import json
import os
import time

import pytest

from supplier import health
from supplier.health import (
    HealthState,
    process_alive,
    read_health,
    read_pid,
    read_state,
    write_health,
    write_pid,
    write_state,
)


@pytest.fixture
def paths(tmp_path):
    return str(tmp_path / "health.json"), str(tmp_path / "supplier.pid")


def _write_record(path, **fields):
    record = {
        "state": "healthy_active",
        "result": "passing",
        "message": "Template accepted",
        "updated_at": time.time(),
        "pid": os.getpid(),
    }
    record.update(fields)
    with open(path, "w") as f:
        json.dump(record, f)
    return record


# ── writing ───────────────────────────────────────────────────────────────

def test_write_health_is_atomic_and_leaves_no_temp_file(paths, tmp_path):
    health_path, _ = paths
    state = HealthState()
    state.set("healthy_active", "up")
    write_health(state, health_path)

    assert read_health(health_path)["state"] == "healthy_active"
    assert not os.path.exists(health_path + ".tmp")
    assert os.listdir(tmp_path) == ["health.json"]


def test_write_health_creates_missing_directory(tmp_path):
    path = str(tmp_path / "nested" / "dir" / "health.json")
    write_state("starting", path=path)
    assert read_health(path)["state"] == "starting"


def test_write_state_records_the_writing_pid(paths):
    health_path, _ = paths
    write_state("starting", "Supplier starting", path=health_path)
    assert read_health(health_path)["pid"] == os.getpid()


def test_unknown_state_cannot_be_written():
    with pytest.raises(ValueError):
        HealthState().set("definitely_not_a_state")


def test_touch_refreshes_timestamp_without_changing_state():
    state = HealthState()
    state.set("healthy_active", "up")
    state.updated_at -= 100
    stale_at = state.updated_at
    state.touch()
    assert state.state == "healthy_active"
    assert state.message == "up"
    assert state.updated_at > stale_at


def test_write_and_read_pid(paths):
    _, pid_path = paths
    assert write_pid(pid_path) == os.getpid()
    assert read_pid(pid_path) == os.getpid()


def test_read_pid_missing_or_garbage(tmp_path):
    assert read_pid(str(tmp_path / "nope.pid")) is None
    garbage = tmp_path / "garbage.pid"
    garbage.write_text("not-a-pid")
    assert read_pid(str(garbage)) is None


# ── process liveness ──────────────────────────────────────────────────────

def test_process_alive_for_self():
    assert process_alive(os.getpid()) is True


def test_process_alive_rejects_missing_and_invalid_pids():
    assert process_alive(None) is False
    assert process_alive(0) is False
    assert process_alive(-1) is False
    # PID far above the default pid_max — cannot be running.
    assert process_alive(4_000_000) is False


# ── evaluation: fail closed ───────────────────────────────────────────────

def test_fresh_record_from_live_process_passes(paths):
    health_path, pid_path = paths
    _write_record(health_path)
    result = read_state(health_path, pid_path)
    assert result == {
        "state": "healthy_active",
        "result": "passing",
        "message": "Template accepted",
    }


def test_missing_file_reports_starting_not_success(paths):
    health_path, pid_path = paths
    result = read_state(health_path, pid_path)
    assert result["state"] == "no_state"
    assert result["result"] == "failing"


def test_corrupt_file_is_failing(paths):
    health_path, pid_path = paths
    with open(health_path, "w") as f:
        f.write("{not json")
    result = read_state(health_path, pid_path)
    assert result["state"] == "unreadable"
    assert result["result"] == "failing"


def test_unrecognised_state_is_failing(paths):
    health_path, pid_path = paths
    _write_record(health_path, state="totally_fine_trust_me")
    result = read_state(health_path, pid_path)
    assert result["state"] == "unreadable"
    assert result["result"] == "failing"


def test_stale_record_is_reported_stale_not_healthy(paths):
    health_path, pid_path = paths
    _write_record(health_path, updated_at=time.time() - 3600)
    result = read_state(health_path, pid_path, stale_after_s=60)
    assert result["state"] == "stale"
    assert result["result"] == "failing"
    # The last known state stays visible for diagnosis.
    assert "healthy_active" in result["message"]


def test_staleness_threshold_is_configurable(paths):
    health_path, pid_path = paths
    _write_record(health_path, updated_at=time.time() - 90)
    assert read_state(health_path, pid_path, stale_after_s=60)["state"] == "stale"
    assert read_state(health_path, pid_path, stale_after_s=600)["state"] == "healthy_active"


def test_record_without_timestamp_is_failing(paths):
    health_path, pid_path = paths
    _write_record(health_path, updated_at="soon")
    result = read_state(health_path, pid_path)
    assert result["state"] == "unreadable"
    assert result["result"] == "failing"


def test_dead_process_is_failing_even_when_record_is_fresh(paths):
    """The core fail-closed rule: a crashed loop must never read as healthy."""
    health_path, pid_path = paths
    _write_record(health_path, pid=4_000_000)
    result = read_state(health_path, pid_path)
    assert result["state"] == "dead"
    assert result["result"] == "failing"
    assert "healthy_active" in result["message"]


def test_starting_sentinel_left_by_a_crashed_process_is_failing(paths):
    """A crash during startup must not linger as an innocuous 'starting'."""
    health_path, pid_path = paths
    _write_record(health_path, state="starting", message="Supplier starting", pid=4_000_000)
    result = read_state(health_path, pid_path)
    assert result["state"] == "dead"
    assert result["result"] == "failing"


def test_pid_falls_back_to_the_pid_file_when_absent_from_the_record(paths):
    health_path, pid_path = paths
    record = _write_record(health_path)
    del record["pid"]
    with open(health_path, "w") as f:
        json.dump(record, f)

    write_pid(pid_path)
    assert read_state(health_path, pid_path)["state"] == "healthy_active"

    with open(pid_path, "w") as f:
        f.write("4000000")
    assert read_state(health_path, pid_path)["state"] == "dead"


def test_stopped_is_reported_as_stopped_not_dead(paths):
    """A deliberate stop keeps its own message; the process is meant to be gone."""
    health_path, pid_path = paths
    _write_record(
        health_path, state="stopped", message="Service stopped",
        pid=4_000_000, updated_at=time.time() - 3600,
    )
    result = read_state(health_path, pid_path)
    assert result["state"] == "stopped"
    assert result["result"] == "failing"


def test_failed_state_round_trips(paths):
    health_path, pid_path = paths
    write_state("failed", "Supplier exited unexpectedly: RuntimeError: boom", path=health_path)
    result = read_state(health_path, pid_path)
    assert result["state"] == "failed"
    assert result["result"] == "failing"
    assert "boom" in result["message"]


@pytest.mark.parametrize("state", sorted(health.STATES))
def test_only_healthy_active_passes(state):
    assert (health.STATES[state][0] == "passing") == (state == "healthy_active")
