"""Health state tracker.

The service loop records its current state in a JSON file that the StartOS
health check reads out of band. That decouples the long-running loop from the
on-demand health check invocations, but it also means the file can outlive the
process that wrote it — so the state is treated as *evidence*, never as truth:

* A "starting" sentinel is written before any initialisation, so a crash during
  startup can never be mistaken for a service that has not started yet.
* Every record carries a timestamp. A record older than ``STALE_AFTER_S`` means
  the loop stopped updating it and is reported as stale, not as whatever it last
  managed to write.
* The loop's PID is recorded alongside it. If that process is gone, the state is
  reported as failed regardless of how recently it was written.

In other words the reader fails closed: only a fresh record, written by a live
process, in a passing state, is reported as healthy.
"""

import json
import os
import time

HEALTH_PATH = os.environ.get("PYBLOCK_HEALTH_PATH", "/root/start9/health.json")
PID_PATH = os.environ.get("PYBLOCK_PID_PATH", "/root/start9/supplier.pid")

# A record older than this means the main loop has stopped heartbeating. The
# loop publishes (and therefore writes health) at least every PUBLISH_INTERVAL_S
# seconds and heartbeats in between, so this leaves generous headroom.
STALE_AFTER_S = float(os.environ.get("PYBLOCK_HEALTH_MAX_AGE_S", "60"))

# State values — each maps to a StartOS health check result
STATES = {
    "starting":          ("failing", "Service is starting up"),
    "config_error":      ("failing", "Configuration error — check the Config action"),
    "node_unavailable":  ("failing", "Cannot reach Bitcoin node RPC"),
    "node_unsynced":     ("failing", "Bitcoin node is syncing (IBD in progress)"),
    "gbt_unsupported":   ("failing", "getblocktemplate rejected blake2b rule — node is not BLAKE2b-capable"),
    "tor_unavailable":   ("failing", "Tor requested but tor daemon is not ready — refusing clearnet fallback"),
    "pyblock_rejected":  ("failing", "PyBLOCK rejected the last template"),
    "healthy_active":    ("passing", "Template accepted — active on PyBLOCK Carousel"),
    "stopped":           ("failing", "Service stopped"),
    "failed":            ("failing", "Supplier exited unexpectedly — check the logs"),
}

# States synthesised by read_state() from the record's context rather than read
# out of the record itself. They can never be written by the loop.
DERIVED_STATES = {
    "no_state":  ("failing", "No health state recorded yet — the service is starting"),
    "unreadable": ("failing", "Health state file is missing or corrupt"),
    "stale":     ("failing", "Health state is stale — the supplier loop is not updating it"),
    "dead":      ("failing", "Supplier process is not running"),
}


class HealthState:
    def __init__(self):
        self.state = "starting"
        self.message = STATES["starting"][1]
        self.updated_at = time.time()
        self.extra: dict = {}

    def set(self, state: str, message: str | None = None, **extra):
        if state not in STATES:
            raise ValueError(f"Unknown health state: {state}")
        self.state = state
        default_msg = STATES[state][1]
        self.message = message or default_msg
        self.updated_at = time.time()
        self.extra = extra

    def touch(self):
        """Refresh the timestamp without changing the state.

        Used as a heartbeat while the loop is idling between publishes, so a
        healthy but quiet service is not reported as stale.
        """
        self.updated_at = time.time()

    def result(self) -> str:
        return STATES[self.state][0]

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "result": self.result(),
            "message": self.message,
            "updated_at": self.updated_at,
            "pid": os.getpid(),
            **self.extra,
        }


def write_health(health: HealthState, path: str = HEALTH_PATH):
    """Replace the health file atomically.

    Written to a sibling temp file and renamed over the target, so a concurrent
    health check reads either the whole previous record or the whole new one —
    never a half-written file that would parse as corrupt.
    """
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(health.to_dict(), f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic rename


def write_state(state: str, message: str | None = None, path: str = HEALTH_PATH, **extra):
    """Write a single state without needing an existing HealthState.

    Used for the pre-initialisation sentinel and the top-level crash handler,
    both of which must work even when nothing else has been constructed yet.
    """
    health = HealthState()
    health.set(state, message, **extra)
    write_health(health, path)
    return health


def read_health(path: str = HEALTH_PATH) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_pid(path: str = PID_PATH, pid: int | None = None) -> int:
    """Record the PID of the supplier loop for the liveness check."""
    pid = os.getpid() if pid is None else pid
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(pid))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return pid


def read_pid(path: str = PID_PATH) -> int | None:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def process_alive(pid: int | None) -> bool:
    """True if `pid` names a live, non-zombie process in this namespace.

    The health check runs inside the same container as the supplier, so /proc is
    shared. A zombie counts as dead: the loop is gone even though the entry has
    not been reaped yet.
    """
    if not pid or pid <= 0:
        return False
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    return not line.split(":", 1)[1].strip().startswith("Z")
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def read_state(
    health_path: str = HEALTH_PATH,
    pid_path: str = PID_PATH,
    stale_after_s: float | None = None,
    now: float | None = None,
) -> dict:
    """Evaluate the recorded health, failing closed.

    Returns ``{"state", "result", "message"}`` where ``result`` is "passing" or
    "failing". ``state`` may be one of STATES or of DERIVED_STATES.
    """
    stale_after_s = STALE_AFTER_S if stale_after_s is None else stale_after_s
    now = time.time() if now is None else now

    record = read_health(health_path)
    if record is None:
        state = "no_state" if not os.path.exists(health_path) else "unreadable"
        return {"state": state, "result": "failing", "message": DERIVED_STATES[state][1]}

    state = record.get("state", "")
    message = record.get("message") or STATES.get(state, ("", ""))[1]
    if state not in STATES:
        return {
            "state": "unreadable",
            "result": "failing",
            "message": f"Unknown health state: {state!r}",
        }

    # A deliberate stop is reported as-is: the process is expected to be gone
    # and the record is expected to stop advancing.
    if state == "stopped":
        return {"state": state, "result": "failing", "message": message}

    pid = record.get("pid")
    if not isinstance(pid, int):
        pid = read_pid(pid_path)
    if not process_alive(pid):
        return {
            "state": "dead",
            "result": "failing",
            "message": f"{DERIVED_STATES['dead'][1]} (last state: {state} — {message})",
        }

    updated_at = record.get("updated_at")
    if not isinstance(updated_at, (int, float)):
        return {
            "state": "unreadable",
            "result": "failing",
            "message": "Health state has no usable timestamp",
        }

    age = now - updated_at
    if age > stale_after_s:
        return {
            "state": "stale",
            "result": "failing",
            "message": (
                f"{DERIVED_STATES['stale'][1]} — last update {age:.0f}s ago "
                f"(last state: {state} — {message})"
            ),
        }

    return {"state": state, "result": STATES[state][0], "message": message}
